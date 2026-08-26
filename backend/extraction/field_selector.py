"""
Stage 6: Field Selector & Reconciliation.

Selects the final field values from classified candidates using:
1. Document-type-aware priority ranking
2. Arithmetic reconciliation (components + taxes == total?)
3. Evidence-based confidence scoring

This replaces the old "first regex match wins" approach.
"""

import re
from typing import List, Optional, Tuple
from models.extraction_schema import (
    Candidate,
    FieldType,
    MoneySemanticType,
    DateSemanticType,
    IdentifierSemanticType,
    SectionType,
    ExtractionMethod,
)


# ---------------------------------------------------------------------------
# Amount selection — priority depends on document type
# ---------------------------------------------------------------------------

_AMOUNT_PRIORITY = {
    SectionType.POSTPAID_BILL: [
        MoneySemanticType.TOTAL_AMOUNT_PAYABLE,
        MoneySemanticType.CURRENT_BILL_AMOUNT,
        MoneySemanticType.PAID_AMOUNT,
    ],
    SectionType.PREPAID_RECHARGE: [
        MoneySemanticType.RECHARGE_AMOUNT,
        MoneySemanticType.PAID_AMOUNT,
        MoneySemanticType.TOTAL_AMOUNT_PAYABLE,
    ],
    SectionType.BROADBAND_BILL: [
        MoneySemanticType.TOTAL_AMOUNT_PAYABLE,
        MoneySemanticType.CURRENT_BILL_AMOUNT,
        MoneySemanticType.PAID_AMOUNT,
    ],
    SectionType.PAYMENT_RECEIPT: [
        MoneySemanticType.PAID_AMOUNT,
        MoneySemanticType.TOTAL_AMOUNT_PAYABLE,
    ],
}


def select_primary_amount(
    candidates: List[Candidate],
    section_type: SectionType,
) -> Optional[Candidate]:
    """
    Selects the best amount candidate based on document type and priority ranking.
    """
    # Only consider positive amounts (negative amounts represent advance balances/credits, not charges)
    money_candidates = [c for c in candidates if c.field_type == FieldType.MONEY and isinstance(c.value, (int, float)) and c.value > 0]
    if not money_candidates:
        return None

    priority_order = _AMOUNT_PRIORITY.get(
        section_type, _AMOUNT_PRIORITY[SectionType.POSTPAID_BILL]
    )

    for target_type in priority_order:
        matches = [c for c in money_candidates if c.semantic_type == target_type]
        if matches:
            # Prefer the one with highest confidence, break ties by largest value
            return max(matches, key=lambda c: (c.confidence, c.value))

    # Fallback: largest amount that isn't a tax, discount, or component
    fallback_exclude = {
        MoneySemanticType.TAX,
        MoneySemanticType.DISCOUNT,
        MoneySemanticType.LATE_FEE,
        MoneySemanticType.SERVICE_COMPONENT,
        MoneySemanticType.PREVIOUS_BALANCE,
    }
    fallback = [c for c in money_candidates if c.semantic_type not in fallback_exclude]
    if fallback:
        return max(fallback, key=lambda c: c.value)

    # Last resort: just the largest money candidate
    return max(money_candidates, key=lambda c: c.value)


# ---------------------------------------------------------------------------
# Date selection
# ---------------------------------------------------------------------------

def select_billing_dates(
    candidates: List[Candidate],
) -> Tuple[Optional[Candidate], Optional[Candidate], Optional[Candidate]]:
    """
    Selects bill_date, billing_start_date, and billing_end_date.
    Returns (bill_date, start_date, end_date).
    """
    date_candidates = [c for c in candidates if c.field_type == FieldType.DATE]
    if not date_candidates:
        return None, None, None

    start_date = _find_by_semantic([DateSemanticType.BILLING_PERIOD_START], date_candidates)
    end_date = _find_by_semantic([DateSemanticType.BILLING_PERIOD_END], date_candidates)
    bill_date = _find_by_semantic([DateSemanticType.BILL_DATE], date_candidates)

    # If we have a billing period start but only found start, try to find end
    # by looking for dates with "to" or "-" in the label context or next chronologically
    if start_date and not end_date:
        for c in date_candidates:
            if c == start_date:
                continue
            if ("to" in c.label.lower() or "-" in c.label or c.value > start_date.value) and c != bill_date:
                end_date = c
                if end_date.semantic_type == DateSemanticType.OTHER_DATE:
                    end_date.semantic_type = DateSemanticType.BILLING_PERIOD_END
                break

    # If no explicitly labeled start/end dates, look at non-due dates
    if not start_date and not end_date and len(date_candidates) >= 2:
        sorted_dates = sorted(date_candidates, key=lambda c: c.value)
        non_due = [c for c in sorted_dates if c.semantic_type != DateSemanticType.DUE_DATE]
        if len(non_due) >= 2:
            # Sanity check: billing cycle must be <= 90 days apart
            try:
                from datetime import datetime
                d_first = datetime.strptime(non_due[0].value, "%Y-%m-%d")
                d_last = datetime.strptime(non_due[-1].value, "%Y-%m-%d")
                if 0 <= (d_last - d_first).days <= 90:
                    start_date = non_due[0]
                    end_date = non_due[-1]
                    start_date.semantic_type = DateSemanticType.BILLING_PERIOD_START
                    end_date.semantic_type = DateSemanticType.BILLING_PERIOD_END
                else:
                    # Anachronistic or unrelated dates (e.g. 2017 regulatory text vs 2021 bill)
                    # Pick the latest date as the bill/transaction date
                    start_date = non_due[-1]
                    end_date = None
            except Exception:
                start_date = non_due[-1]
                end_date = None

    # Bill date defaults to start date if not explicitly found
    if not bill_date and start_date:
        bill_date = start_date

    return bill_date, start_date, end_date


def _find_by_semantic(
    target_types: list, candidates: List[Candidate]
) -> Optional[Candidate]:
    """Finds the first candidate matching any of the target semantic types."""
    for target in target_types:
        for c in candidates:
            if c.semantic_type == target:
                return c
    return None


# ---------------------------------------------------------------------------
# Vendor selection
# ---------------------------------------------------------------------------

def select_vendor(candidates: List[Candidate]) -> Optional[Candidate]:
    """Selects the best vendor candidate (highest confidence, first page)."""
    vendor_candidates = [c for c in candidates if c.field_type == FieldType.VENDOR]
    if not vendor_candidates:
        return None
    # Prefer first-page vendors, then highest confidence
    return min(vendor_candidates, key=lambda c: (c.page, -c.confidence))


# ---------------------------------------------------------------------------
# Identifier selection
# ---------------------------------------------------------------------------

def select_invoice_number(candidates: List[Candidate]) -> Optional[Candidate]:
    """Selects the best invoice/account number."""
    id_candidates = [c for c in candidates if c.field_type == FieldType.IDENTIFIER]
    if not id_candidates:
        return None

    # Prefer INVOICE_NUMBER over ACCOUNT_NUMBER over others
    priority = ["INVOICE_NUMBER", "ACCOUNT_NUMBER", "STATEMENT_NUMBER", "TRANSACTION_ID"]
    for target in priority:
        matches = [c for c in id_candidates if c.semantic_type == target]
        if matches:
            return matches[0]

    return id_candidates[0]


# ---------------------------------------------------------------------------
# Bill type classification
# ---------------------------------------------------------------------------

def determine_bill_type(
    section_type: SectionType,
    candidates: List[Candidate],
) -> Tuple[Optional[str], str]:
    """
    Determines the bill_type and detected_document_type from section classification.
    Returns (bill_type_value, detected_document_type).
    """
    raw_text_combined = " ".join(c.raw_text for c in candidates if c.raw_text).lower()

    # Check for specific plan details
    is_broadband = section_type == SectionType.BROADBAND_BILL
    is_prepaid = section_type == SectionType.PREPAID_RECHARGE
    is_postpaid = section_type == SectionType.POSTPAID_BILL

    if not is_broadband and not is_prepaid and not is_postpaid:
        for c in candidates:
            text_to_check = f"{c.label or ''} {c.raw_text or ''} {c.value or ''}".lower()
            if any(kw in text_to_check for kw in ["broadband", "fiber", "dsl", "ftth", "wifi", "xstream", "jiofiber", "tikona", "act fibernet"]):
                is_broadband = True
                break
            if any(kw in text_to_check for kw in ["prepaid", "recharge", "top-up", "voucher"]):
                is_prepaid = True
                break
            if any(kw in text_to_check for kw in ["postpaid", "statement", "bill summary", "tax invoice", "bill", "airtel", "jio", "vodafone", "bsnl"]):
                is_postpaid = True
                break

    if is_broadband:
        return "BROADBAND_PLAN", "BROADBAND_FIBER_BILL"
    elif is_prepaid:
        return "PREPAID_RECHARGE", "CELLPHONE_PREPAID_RECHARGE"
    elif is_postpaid:
        return "POSTPAID_BILL", "CELLPHONE_POSTPAID_BILL"
    else:
        return None, "OTHER_NON_TELECOM"


# ---------------------------------------------------------------------------
# Arithmetic reconciliation
# ---------------------------------------------------------------------------

def reconcile_amounts(candidates: List[Candidate]) -> float:
    """
    Checks if service components + taxes ≈ total.
    Returns a confidence boost (0.0 to 0.15).
    """
    money = [c for c in candidates if c.field_type == FieldType.MONEY]

    components = [c.value for c in money if c.semantic_type == MoneySemanticType.SERVICE_COMPONENT]
    taxes = [c.value for c in money if c.semantic_type == MoneySemanticType.TAX]
    totals = [c.value for c in money if c.semantic_type in (
        MoneySemanticType.TOTAL_AMOUNT_PAYABLE,
        MoneySemanticType.CURRENT_BILL_AMOUNT,
    )]

    if components and taxes and totals:
        computed = sum(components) + sum(taxes)
        for total in totals:
            if abs(computed - total) < 0.10:  # ₹0.10 rounding tolerance
                return 0.15

    return 0.0


# ---------------------------------------------------------------------------
# Evidence-based confidence scoring
# ---------------------------------------------------------------------------

def compute_confidence(
    candidate: Candidate,
    reconciliation_boost: float,
    extraction_method: str,
    cross_page_confirmed: bool = False,
) -> float:
    """
    Builds an explainable confidence score from independent evidence signals.
    """
    score = 0.0

    # 1. Explicit high-priority label exists
    if candidate.semantic_type and candidate.semantic_type != MoneySemanticType.OTHER:
        score += 0.55

    # 2. Value was spatially associated with its label
    if any("line_match" in s or "spatial" in s for s in candidate.evidence_sources):
        score += 0.20

    # 3. Native PDF text (not OCR with potential errors)
    if extraction_method in ("native_pdf", ExtractionMethod.NATIVE_PDF):
        score += 0.15

    # 4. Arithmetic reconciliation succeeded
    score += reconciliation_boost  # 0.0 or 0.15

    # 5. Value appears consistently on multiple pages
    if cross_page_confirmed:
        score += 0.10

    # 6. Correct document section
    score += 0.05

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Relevance check
# ---------------------------------------------------------------------------

def is_telecom_relevant(candidates: List[Candidate], section_type: SectionType) -> bool:
    """
    Determines if the document is a relevant telecom/broadband invoice.
    """
    # If we found a known vendor, it's relevant
    vendor_candidates = [c for c in candidates if c.field_type == FieldType.VENDOR]
    if vendor_candidates:
        return True

    # If the section type is a known bill type, it's relevant
    if section_type in (
        SectionType.POSTPAID_BILL,
        SectionType.PREPAID_RECHARGE,
        SectionType.BROADBAND_BILL,
        SectionType.PAYMENT_RECEIPT,
    ):
        return True

    # Check for telecom keywords in any candidate labels
    all_text = " ".join(c.label for c in candidates).lower()
    telecom_keywords = [
        "telecom", "broadband", "fiber", "mobile", "cellphone",
        "postpaid", "prepaid", "recharge", "airtel", "jio",
        "vodafone", "bsnl", "act fibernet",
    ]
    return any(kw in all_text for kw in telecom_keywords)
