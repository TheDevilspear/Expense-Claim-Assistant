"""
Stage 5: Section Classifier.

Classifies each page (or group of pages) into document sections:
  PAYMENT_RECEIPT, POSTPAID_BILL, PREPAID_RECHARGE, BROADBAND_BILL,
  EXPLANATORY, OTHER

This determines which amount semantics apply for final field selection.
For example: a PAYMENT_RECEIPT's primary amount is PAID_AMOUNT,
while a POSTPAID_BILL's primary amount is TOTAL_AMOUNT_PAYABLE.
"""

from typing import List
from models.extraction_schema import (
    PageEvidence,
    DocumentSection,
    SectionType,
)


# Keywords for each section type, ordered by specificity
_SECTION_KEYWORDS = {
    SectionType.PAYMENT_RECEIPT: [
        "payment receipt", "transaction receipt", "payment confirmation",
        "payment successful", "paid successfully",
    ],
    SectionType.PREPAID_RECHARGE: [
        "recharge successful", "recharge receipt", "prepaid recharge",
        "top-up", "voucher", "recharge of",
    ],
    SectionType.BROADBAND_BILL: [
        "broadband", "fiber", "fibre", "ftth", "dsl", "xstream",
        "jiofiber", "act fibernet", "tikona", "wifi", "wi-fi",
        "fixedline and broadband",
    ],
    SectionType.POSTPAID_BILL: [
        "postpaid", "monthly statement", "bill summary",
        "statement period", "tax invoice", "account number",
    ],
}

# Keywords that indicate a page is explanatory / filler
_EXPLANATORY_KEYWORDS = [
    "terms and conditions", "important information",
    "how to read your bill", "glossary", "abbreviations",
    "customer care", "toll free", "grievance",
    "registered office", "disclaimer",
]


def classify_sections(pages_evidence: List[PageEvidence]) -> List[DocumentSection]:
    """
    Classifies each page into a section type, then merges adjacent
    pages with the same type into contiguous sections.
    """
    if not pages_evidence:
        return [DocumentSection(pages=[0], section_type=SectionType.OTHER)]

    page_sections = []
    for page_ev in pages_evidence:
        section_type = _classify_page(page_ev)
        page_sections.append(DocumentSection(
            pages=[page_ev.page_number],
            section_type=section_type,
        ))

    return _merge_adjacent(page_sections)


def classify_primary_section(pages_evidence: List[PageEvidence]) -> SectionType:
    """
    Returns the primary (most important) section type for the document.
    Prefers bill/recharge types over receipts and explanatory.
    """
    sections = classify_sections(pages_evidence)

    # Priority: BROADBAND > POSTPAID > PREPAID > PAYMENT_RECEIPT > OTHER
    priority = [
        SectionType.BROADBAND_BILL,
        SectionType.POSTPAID_BILL,
        SectionType.PREPAID_RECHARGE,
        SectionType.PAYMENT_RECEIPT,
        SectionType.COMBINED_BILL,
        SectionType.OTHER,
    ]

    for target in priority:
        for section in sections:
            if section.section_type == target:
                return target

    return SectionType.OTHER


def _classify_page(page_ev: PageEvidence) -> SectionType:
    """Classifies a single page by keyword presence."""
    text_lower = page_ev.raw_text.lower()

    # Check for explanatory first (these are always low-value pages)
    if _is_explanatory(text_lower):
        return SectionType.EXPLANATORY

    # Score each section type by how many keywords match
    best_type = SectionType.OTHER
    best_score = 0

    for section_type, keywords in _SECTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_type = section_type

    # If broadband AND postpaid keywords both match, it's a broadband bill
    # (broadband bills are often postpaid)
    if best_type == SectionType.POSTPAID_BILL:
        broadband_score = sum(
            1 for kw in _SECTION_KEYWORDS[SectionType.BROADBAND_BILL]
            if kw in text_lower
        )
        if broadband_score > 0:
            best_type = SectionType.BROADBAND_BILL

    return best_type


def _is_explanatory(text_lower: str) -> bool:
    """Checks if a page is mostly explanatory / boilerplate content."""
    matches = sum(1 for kw in _EXPLANATORY_KEYWORDS if kw in text_lower)
    return matches >= 2


def _merge_adjacent(sections: List[DocumentSection]) -> List[DocumentSection]:
    """Merges consecutive sections with the same type."""
    if not sections:
        return []

    merged = [sections[0]]
    for section in sections[1:]:
        if section.section_type == merged[-1].section_type:
            merged[-1].pages.extend(section.pages)
        else:
            merged.append(section)

    return merged
