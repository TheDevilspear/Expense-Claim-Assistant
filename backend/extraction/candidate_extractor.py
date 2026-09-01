"""
Stage 3: Candidate Extractor.

Scans PageEvidence for ALL money, date, identifier, and vendor candidates.
Each candidate carries its spatial context and nearby label text.

Does NOT decide which candidate is "the answer" — that happens in
semantic_classifier.py and field_selector.py.
"""

import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
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

    # Fallback to scanning raw_text lines if no line structures were found
    if not candidates and evidence.raw_text:
        for raw_line in evidence.raw_text.splitlines():
            for match in _MONEY_PATTERN.finditer(raw_line):
                try:
                    value = float(match.group(1).replace(",", ""))
                except ValueError:
                    continue
                if value < _MONEY_MIN or value > _MONEY_MAX:
                    continue
                match_start = match.start()
                label = raw_line[:match_start].strip()
                candidates.append(Candidate(
                    field_type=FieldType.MONEY,
                    value=value,
                    raw_text=match.group(0).strip(),
                    label=label,
                    page=evidence.page_number,
                    confidence=0.85,
                    evidence_sources=["raw_text_regex"],
                ))

    return candidates


# ---------------------------------------------------------------------------
# Date candidates & Validity candidates
# ---------------------------------------------------------------------------

_MONTH_NAMES = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'

_DATE_PATTERNS = [
    # "08 Jan 2022", "16 DEC 2024", "26 Oct 2023", "16 April 2025", "06 February 2024", "18 April 25", "03 Aug 21"
    re.compile(rf'\b(\d{{1,2}})\s+({_MONTH_NAMES})\s+(\d{{4}}|\d{{2}})(?!\s*:)\b', re.I),
    # "08-Jan-2022", "16-DEC-2024", "26-APR-21", "06-Jan-2018", "21-JAN-2023"
    re.compile(rf'\b(\d{{1,2}})[-/\.]({_MONTH_NAMES})[-/\.](\d{{4}}|\d{{2}})(?!\s*:)\b', re.I),
    # "Jan 08, 2022", "April 16, 2025", "Jul 05 2021"
    re.compile(rf'\b({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}}|\d{{2}})(?!\s*:)\b', re.I),
    # "2024-01-05", "2023/11/11", "2024.01.05"
    re.compile(r'\b(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})\b'),
    # "05/01/2024", "05-01-2024", "14/12/2023", "03/08/21" (DD/MM/YYYY or DD/MM/YY)
    re.compile(r'\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4}|\d{2})(?!\s*:)\b'),
]

_DATE_RANGE_REGEX = re.compile(
    rf'(?:Statement\s+Period|Bill\s+Period|Billing\s+Period|Billing\s+Cycle(?:\s+Date)?|Usage\s+Period|Service\s+Period|Period(?:\s+Date)?|Plan\s+Period|Validity\s+Period)[:\s]*'
    rf'([0-9A-Za-z\s\-/\.]{{6,25}})\s*(?:to|-|till|through|–)\s*([0-9A-Za-z\s\-/\.]{{6,25}})',
    re.I
)

_VALIDITY_PATTERNS = [
    # "Validity: 28 Days", "Plan Validity: 84 Days", "Validity - 365 Days", "Validity: 28 days"
    (re.compile(r'(?:plan\s+|pack\s+|tariff\s+)?validity\s*[:\-]?\s*(\d+)\s*(?:days?|day)\b', re.I), lambda m: int(m.group(1))),
    # "28 Days Validity", "84 days validity", "365 days validity"
    (re.compile(r'\b(\d+)\s*(?:days?|day)\s+validity\b', re.I), lambda m: int(m.group(1))),
    # "Validity: 1 Month", "Validity: 3 Months", "Validity: 12 Months"
    (re.compile(r'(?:plan\s+|pack\s+|tariff\s+)?validity\s*[:\-]?\s*(\d+)\s*(?:months?|month)\b', re.I), lambda m: int(m.group(1)) * 30),
    # "Valid for 28 days", "Valid for 84 days"
    (re.compile(r'\bvalid\s+for\s*[:\-]?\s*(\d+)\s*(?:days?|day)\b', re.I), lambda m: int(m.group(1))),
    # "Validity: 1 Year", "Validity: 2 Years"
    (re.compile(r'(?:plan\s+|pack\s+|tariff\s+)?validity\s*[:\-]?\s*(\d+)\s*(?:years?|year)\b', re.I), lambda m: int(m.group(1)) * 365),
]


def _parse_date_string(dt_str: str) -> Optional[str]:
    """Robustly parses arbitrary telecom date strings to ISO YYYY-MM-DD format."""
    if not dt_str:
        return None
    clean = dt_str.strip()
    clean = re.sub(r'[,]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d-%b-%Y", "%d %b %Y", "%d/%b/%Y", "%d.%b.%Y",
        "%d-%B-%Y", "%d %B %Y", "%d/%B/%Y", "%d.%B.%Y",
        "%d-%b-%y", "%d %b %y", "%d/%b/%y", "%d.%b.%y",
        "%d-%B-%y", "%d %B %y", "%d/%B/%y", "%d.%B.%y",
        "%b %d %Y", "%B %d %Y",
        "%b %d %y", "%B %d %y",
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(clean, fmt)
            if 2000 <= parsed.year <= 2099:
                return parsed.strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def extract_date_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Finds all date-like values in page evidence with their nearby labels."""
    candidates: List[Candidate] = []
    seen_values = set()

    # 1. Check multi-word date ranges (e.g. "Statement Period: 08 Jan 2022 to 07 Feb 2022")
    search_texts = [evidence.raw_text] if evidence.raw_text else []
    search_texts.extend([line.full_text for line in evidence.lines])

    for text in search_texts:
        for match in _DATE_RANGE_REGEX.finditer(text):
            raw_start = match.group(1).strip()
            raw_end = match.group(2).strip()
            iso_start = _parse_date_string(raw_start)
            iso_end = _parse_date_string(raw_end)

            if iso_start and iso_end:
                if iso_start not in seen_values:
                    candidates.append(Candidate(
                        field_type=FieldType.DATE,
                        value=iso_start,
                        raw_text=raw_start,
                        label="Billing Period Start",
                        page=evidence.page_number,
                        semantic_type=DateSemanticType.BILLING_PERIOD_START,
                        confidence=0.98,
                        evidence_sources=[f"{evidence.extraction_method.value}_range_match"],
                    ))
                    seen_values.add(iso_start)

                if iso_end not in seen_values:
                    candidates.append(Candidate(
                        field_type=FieldType.DATE,
                        value=iso_end,
                        raw_text=raw_end,
                        label="Billing Period End",
                        page=evidence.page_number,
                        semantic_type=DateSemanticType.BILLING_PERIOD_END,
                        confidence=0.98,
                        evidence_sources=[f"{evidence.extraction_method.value}_range_match"],
                    ))
                    seen_values.add(iso_end)

    # 2. General date scan across all lines (and raw_text fallback)
    lines_to_scan = evidence.lines if evidence.lines else [
        Line(tokens=[], full_text=l, y_center=0.0) for l in (evidence.raw_text or "").splitlines()
    ]

    for line_idx, line in enumerate(lines_to_scan):
        line_lower = line.full_text.lower()
        # Filter out dates from legal/tax disclaimer boilerplate (e.g. "effective 1-July-17...")
        if any(kw in line_lower for kw in [
            "effective", "directive", "service tax of", "replaced with",
            "reverse charge", "1-july-17", "01-july-17", "01-jul-17"
        ]):
            continue

        for pattern in _DATE_PATTERNS:
            for match in pattern.finditer(line.full_text):
                match_raw = match.group(0).strip()
                iso_date = _parse_date_string(match_raw)
                if not iso_date or iso_date in seen_values:
                    continue

                seen_values.add(iso_date)

                # Label resolution: left of match or previous line
                label = _extract_label_from_line(line, match.start())
                if not label and line_idx > 0:
                    prev_text = lines_to_scan[line_idx - 1].full_text.strip()
                    if not re.match(r'^\d+(\.\d+)?$', prev_text):
                        label = prev_text

                # Semantic type heuristics from label
                sem_type = DateSemanticType.OTHER_DATE
                label_lower = label.lower()
                if any(kw in label_lower for kw in ["bill date", "invoice date", "statement date", "date of invoice", "billing date"]):
                    sem_type = DateSemanticType.BILL_DATE
                elif any(kw in label_lower for kw in ["due date", "pay by", "payable by", "due on"]):
                    sem_type = DateSemanticType.DUE_DATE
                elif any(kw in label_lower for kw in ["payment date", "paid on", "transaction date", "recharge date"]):
                    sem_type = DateSemanticType.PAYMENT_DATE
                elif any(kw in label_lower for kw in ["statement period", "billing cycle", "billing period", "bill period", "service period"]):
                    sem_type = DateSemanticType.BILLING_PERIOD_START
                elif any(kw in label_lower for kw in ["activation date", "activated on"]):
                    sem_type = DateSemanticType.ACTIVATION_DATE

                bbox = _estimate_bbox_from_match(line, match)

                candidates.append(Candidate(
                    field_type=FieldType.DATE,
                    value=iso_date,
                    raw_text=match_raw,
                    label=label,
                    page=evidence.page_number,
                    semantic_type=sem_type,
                    confidence=0.90 if sem_type != DateSemanticType.OTHER_DATE else 0.85,
                    x0=bbox[0], y0=bbox[1], x1=bbox[2], y1=bbox[3],
                    evidence_sources=[f"{evidence.extraction_method.value}_line_match"],
                ))

    return candidates


def extract_validity_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Finds explicit plan validity numbers (e.g. 'Validity: 28 Days', '84 Days Validity')."""
    candidates: List[Candidate] = []
    search_texts = [evidence.raw_text] if evidence.raw_text else []
    search_texts.extend([line.full_text for line in evidence.lines])

    for text in search_texts:
        for pattern, val_parser in _VALIDITY_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    days = val_parser(match)
                    if 1 <= days <= 730:
                        candidates.append(Candidate(
                            field_type=FieldType.VALIDITY,
                            value=days,
                            raw_text=match.group(0).strip(),
                            label="Plan Validity",
                            page=evidence.page_number,
                            confidence=0.95,
                            evidence_sources=[f"{evidence.extraction_method.value}_validity_regex"],
                        ))
                except Exception:
                    continue

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


from extraction.constants import VENDOR_PATTERNS



def extract_vendor_candidates(evidence: PageEvidence) -> List[Candidate]:
    """Identifies telecom vendors mentioned in the page text."""
    candidates = []
    # Replace underscores and hyphens with spaces for boundary matching (e.g. jio_bill -> jio bill)
    clean_text = evidence.raw_text.replace("_", " ").replace("-", " ")

    for pattern, vendor_name, full_name in VENDOR_PATTERNS:
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
    candidates += extract_validity_candidates(evidence)
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
