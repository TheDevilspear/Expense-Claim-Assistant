"""
Stage 3: Candidate Extractor.

Scans PageEvidence for ALL money, date, identifier, and vendor candidates.
Each candidate carries its spatial context and nearby label text.

Does NOT decide which candidate is "the answer" — that happens in
semantic_classifier.py and field_selector.py.
"""

import re
from typing import List
from models.extraction_schema import (
    Token,
    Line,
    PageEvidence,
    Candidate,
    FieldType,
    DateSemanticType,
)


# ---------------------------------------------------------------------------
# Money candidates
# ---------------------------------------------------------------------------

# Matches ₹1,199.00 / Rs. 799 / 2,416.64 / 999.00 / 1178.82 etc.
_MONEY_PATTERN = re.compile(
    r'(?:[₹$]|Rs\.?|INR)?\s*(\b\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\b\d+(?:\.\d{1,2})?\b)'
)

# Minimum and maximum plausible invoice amounts (filters page numbers, GST rates, etc.)
_MONEY_MIN = 10.0
_MONEY_MAX = 500_000.0


def extract_money_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Finds all monetary values in page evidence with their nearby labels."""
    candidates = []

    for line_idx, line in enumerate(evidence.lines):
        for match in _MONEY_PATTERN.finditer(line.full_text):
            try:
                value = float(match.group(1).replace(",", ""))
            except ValueError:
                continue

            if value < _MONEY_MIN or value > _MONEY_MAX:
                continue

            # Filter out 4-digit years in dates (e.g. 2022 in "08 Jan 2022" or 2025 in "30-JAN-2025")
            match_start = match.start()
            prefix_20 = line.full_text[max(0, match_start - 20):match_start]
            if re.search(r'[-/\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/\s]?$', prefix_20, re.I):
                continue
            if re.search(r'[-/]\d{1,2}[-/]$', prefix_20):
                continue

            # Check for negative sign (e.g. "-2787.93", "- 2,787.93", "TOTAL -2787.93")
            prefix_10 = line.full_text[max(0, match_start - 10):match_start]
            if re.search(r'[-–]\s*$', prefix_10) or "minus" in line.full_text.lower():
                value = -abs(value)

            # Find label: tokens to the LEFT of this match on the same line
            label = _extract_label_from_line(line, match_start)

            # If label on same line is empty, check previous line
            if not label and line_idx > 0:
                prev_line = evidence.lines[line_idx - 1]
                prev_text = prev_line.full_text.strip()
                if not re.match(r'^\d+(\.\d+)?$', prev_text):
                    label = prev_text

            bbox = _estimate_bbox_from_match(line, match)

            candidates.append(Candidate(
                field_type=FieldType.MONEY,
                value=value,
                raw_text=match.group(0).strip(),
                label=label,
                page=evidence.page_number,
                x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3],
                evidence_sources=[f"{evidence.extraction_method.value}_line_match"],
            ))

    return candidates


# ---------------------------------------------------------------------------
# Date candidates
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    # "08 Jan 2022", "16 DEC 2024", "26 Oct 2023"
    (re.compile(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{2,4})', re.I),
     lambda m: (f"{m.group(1)} {m.group(2)[:3].title()} {m.group(3)}", "%d %b %y" if len(m.group(3)) == 2 else "%d %b %Y")),
    # "08-Jan-2022", "16-DEC-2024", "26-APR-21"
    (re.compile(r'(\d{1,2})[-/](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/](\d{2,4})', re.I),
     lambda m: (f"{m.group(1)}-{m.group(2)[:3].title()}-{m.group(3)}", "%d-%b-%y" if len(m.group(3)) == 2 else "%d-%b-%Y")),
    # "16 April 2025", "06 February 2024"
    (re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{2,4})', re.I),
     lambda m: (f"{m.group(1)} {m.group(2).title()} {m.group(3)}", "%d %B %y" if len(m.group(3)) == 2 else "%d %B %Y")),
    # "2024-01-05"
    (re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'),
     lambda m: (f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}", "%Y-%m-%d")),
    # "05/01/2024", "05-01-2024" (DD/MM/YYYY)
    (re.compile(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})'),
     lambda m: (f"{m.group(1).zfill(2)}-{m.group(2).zfill(2)}-{m.group(3)}", "%d-%m-%y" if len(m.group(3)) == 2 else "%d-%m-%Y")),
]


def extract_date_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Finds all date-like values in page evidence with their nearby labels."""
    from datetime import datetime
    candidates = []
    seen_values = set()

    range_match = re.search(
        r'(?:Statement\s+Period|Bill\s+Period|Billing\s+Cycle(?:\s+Date)?|Usage\s+Period|Period(?:\s+Date)?)[:\s]*'
        r'(\d{1,2}[-\s/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s/]\d{2,4})\s*(?:to|-)\s*'
        r'(\d{1,2}[-\s/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s/]\d{2,4})',
        evidence.raw_text, re.I
    )
    if range_match:
        for idx, (group_idx, sem_type, label_name) in enumerate([
            (1, DateSemanticType.BILLING_PERIOD_START, "Billing Period Start"),
            (2, DateSemanticType.BILLING_PERIOD_END, "Billing Period End"),
        ]):
            raw_dt = range_match.group(group_idx).strip()
            clean_dt = raw_dt.replace("/", "-").replace(" ", "-")
            parts = clean_dt.split("-")
            if len(parts) == 3:
                day, mon, yr = parts[0], parts[1][:3].title(), parts[2]
                norm_dt = f"{day.zfill(2)}-{mon}-{yr}"
                fmt = "%d-%b-%y" if len(yr) == 2 else "%d-%b-%Y"
                try:
                    iso = datetime.strptime(norm_dt, fmt).strftime("%Y-%m-%d")
                    candidates.append(Candidate(
                        field_type=FieldType.DATE,
                        value=iso,
                        raw_text=raw_dt,
                        label=label_name,
                        page=evidence.page_number,
                        semantic_type=sem_type,
                        confidence=0.98,
                        evidence_sources=[f"{evidence.extraction_method.value}_range_match"],
                    ))
                    seen_values.add(iso)
                except Exception:
                    pass

    # 2. General date scan across all lines
    for line in evidence.lines:
        line_lower = line.full_text.lower()
        # Filter out dates from legal/tax disclaimer boilerplate (e.g. "effective 1-July-17...")
        if any(kw in line_lower for kw in ["effective", "directive", "service tax of", "replaced with", "reverse charge", "1-july-17", "01-july-17"]):
            continue

        for pattern, normalizer in _DATE_PATTERNS:
            for match in pattern.finditer(line.full_text):
                try:
                    normalized_str, fmt = normalizer(match)
                    parsed = datetime.strptime(normalized_str, fmt)
                    iso_date = parsed.strftime("%Y-%m-%d")
                except (ValueError, IndexError):
                    continue

                if iso_date in seen_values:
                    continue
                seen_values.add(iso_date)

                label = _extract_label_from_line(line, match.start())
                bbox = _estimate_bbox_from_match(line, match)

                candidates.append(Candidate(
                    field_type=FieldType.DATE,
                    value=iso_date,
                    raw_text=match.group(0).strip(),
                    label=label,
                    page=evidence.page_number,
                    x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3],
                    evidence_sources=[f"{evidence.extraction_method.value}_line_match"],
                ))

    return candidates


# ---------------------------------------------------------------------------
# Identifier candidates (account numbers, invoice numbers, etc.)
# ---------------------------------------------------------------------------

_ID_PATTERNS = [
    # Explicit labeled patterns
    (re.compile(r'(?:Account\s*(?:No|Number|#)\.?\s*[:\s]*)([\w-]{6,20})', re.I), "ACCOUNT_NUMBER"),
    (re.compile(r'(?:Bill\s*(?:No|Number|NO)\.?\s*[:\s]*)([\w-]{6,20})', re.I), "INVOICE_NUMBER"),
    (re.compile(r'(?:Invoice\s*(?:No|Number)\.?\s*[:\s]*)([\w-]{6,20})', re.I), "INVOICE_NUMBER"),
    (re.compile(r'(?:Tax\s+Invoice\s*(?:No|Number)\.?\s*[:\s]*)([\w-]{6,20})', re.I), "INVOICE_NUMBER"),
    (re.compile(r'(?:Transaction\s*(?:ID|Id|No)\.?\s*[:\s]*)([\w-]{6,30})', re.I), "TRANSACTION_ID"),
    (re.compile(r'(?:Statement\s*(?:No|Number)\.?\s*[:\s]*)([\w-]{6,20})', re.I), "STATEMENT_NUMBER"),
    (re.compile(r'(?:Reference\s*(?:ID|Id|No)\.?\s*[:\s]*)([\w-]{6,30})', re.I), "REFERENCE_NUMBER"),
    # Direct telecom invoice alphanumeric pattern (e.g. AT3318A20179032, HT2405I000591921, MH0520B108767930)
    (re.compile(r'\b((?:AT|HT|FD|MH|KA|DL|TN|PA)\d{2,6}[A-Z\d]{6,16})\b', re.I), "INVOICE_NUMBER"),
]

# Words that should NOT be treated as identifiers
_ID_STOPWORDS = {
    "STATEMENT", "SUMMARY", "NUMBER", "DETAILS", "CHARGES", "AMOUNT", "TOTAL",
    "PLAN", "INVOICE", "DATE", "PREPAID", "POSTPAID", "BILLING", "RECEIPT",
    "CUSTOMER", "PAYMENT", "SERVICES", "ORIGINAL", "RECIPIENT", "RECHARGE"
}


def extract_identifier_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Finds account numbers, invoice numbers, transaction IDs, etc."""
    candidates = []

    # Use raw_text for cross-line matching (labels and values may be on different lines)
    # Also try each line individually
    search_texts = [evidence.raw_text] + [line.full_text for line in evidence.lines]

    seen = set()
    for text in search_texts:
        for pattern, id_type in _ID_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1).strip()
                # Stopwords filter
                if value.upper() in _ID_STOPWORDS:
                    continue
                # Real invoice/account/transaction IDs must contain at least one digit
                if not any(char.isdigit() for char in value):
                    continue
                key = (id_type, value)
                if key in seen:
                    continue
                seen.add(key)

                candidates.append(Candidate(
                    field_type=FieldType.IDENTIFIER,
                    value=value,
                    raw_text=match.group(0).strip(),
                    label=id_type,
                    page=evidence.page_number,
                    semantic_type=id_type,
                    evidence_sources=[f"{evidence.extraction_method.value}_regex"],
                ))

    return candidates


# ---------------------------------------------------------------------------
# Vendor candidates
# ---------------------------------------------------------------------------

_VENDOR_PATTERNS = [
    (re.compile(r'\bjio\b|reliance\s+jio', re.I), "Jio", "Reliance Jio Infocomm"),
    (re.compile(r'\bairtel\b|bharti\s+airtel', re.I), "Airtel", "Bharti Airtel Limited"),
    (re.compile(r'\bact\s*fibernet\b|atria\s+convergence', re.I), "ACT Fibernet", "Atria Convergence Technologies"),
    (re.compile(r'\bvodafone\b|\bvi\b(?!\w)|vodafone\s+idea', re.I), "Vodafone", "Vodafone Idea Limited"),
    (re.compile(r'\bbsnl\b|bharat\s+sanchar', re.I), "BSNL", "Bharat Sanchar Nigam Limited"),
    (re.compile(r'\btikona\b', re.I), "Tikona", "Tikona Infinet"),
    (re.compile(r'\btata\s+sky\b|\btata\s+play\b', re.I), "Tata Play", "Tata Play Limited"),
    (re.compile(r'\bphonepe\b', re.I), "PhonePe", "PhonePe Private Limited"),
]


def extract_vendor_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Identifies telecom vendors mentioned in the page text."""
    candidates = []
    # Replace underscores and hyphens with spaces for boundary matching (e.g. jio_bill -> jio bill)
    clean_text = evidence.raw_text.replace("_", " ").replace("-", " ")

    for pattern, vendor_name, full_name in _VENDOR_PATTERNS:
        match = pattern.search(clean_text)
        if match:
            candidates.append(Candidate(
                field_type=FieldType.VENDOR,
                value=vendor_name,
                raw_text=full_name,
                label=f"Vendor: {vendor_name}",
                page=evidence.page_number,
                confidence=0.95,
                evidence_sources=[f"{evidence.extraction_method.value}_keyword"],
            ))

    return candidates


# ---------------------------------------------------------------------------
# Aggregate extractor
# ---------------------------------------------------------------------------

def extract_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Extracts all candidate types from a single page's evidence."""
    candidates = []
    candidates += extract_money_candidates(evidence)
    candidates += extract_date_candidates(evidence)
    candidates += extract_identifier_candidates(evidence)
    candidates += extract_vendor_candidates(evidence)
    return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_label_from_line(line: Line, match_start_char: int) -> str:
    """
    Extracts the label text to the LEFT of a regex match within a line.
    Uses character position in the full_text to find which tokens precede the match.
    """
    prefix = line.full_text[:match_start_char].strip()
    if not prefix:
        return ""
    # Take the last ~60 chars as the label (avoids very long prefixes)
    label = prefix[-60:].strip()
    # Clean trailing colons, dashes, etc.
    label = re.sub(r'[:\-=]+$', '', label).strip()
    return label


def _estimate_bbox_from_match(line: Line, match) -> tuple:
    """
    Estimates the bounding box of a regex match within a line.
    Returns (x0, y0, x1, y1) in normalized coordinates.
    """
    if not line.tokens:
        return (0.0, 0.0, 0.0, 0.0)

    # Simple estimation: use the line's y-band and approximate x from char position
    y0 = min(t.y0 for t in line.tokens)
    y1 = max(t.y1 for t in line.tokens)

    # Find tokens that overlap with the match text
    match_text = match.group(0).strip()
    matching_tokens = [t for t in line.tokens if t.text in match_text or match_text in t.text]

    if matching_tokens:
        x0 = min(t.x0 for t in matching_tokens)
        x1 = max(t.x1 for t in matching_tokens)
    else:
        x0 = line.tokens[0].x0
        x1 = line.tokens[-1].x1

    return (x0, y0, x1, y1)
