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
    Selects (bill_date, billing_start_date, billing_end_date) using a 4-layer smart date engine:
    1. Lock Anchor Date (T_bill: Bill Date / Statement Date / Invoice Date / Payment Date).
    2. Collect explicit period ranges and candidate date pairs.
    3. Filter out past activations and future plan expirations (> T_bill + 60 days).
    4. Score all candidate pairs (D_start, D_end) based on duration plausibility and proximity to T_bill.
    5. Fallback for single-date prepaid recharges with validity days computation.
    """
    from datetime import datetime, timedelta
    date_candidates = [c for c in candidates if c.field_type == FieldType.DATE and c.value]
    if not date_candidates:
        return None, None, None

    # Step 1: Lock Anchor Date (T_bill)
    bill_date_c = _find_by_semantic([DateSemanticType.BILL_DATE, DateSemanticType.INVOICE_DATE], date_candidates)
    payment_date_c = _find_by_semantic([DateSemanticType.PAYMENT_DATE, DateSemanticType.TRANSACTION_TIMESTAMP], date_candidates)
    
    anchor_c = bill_date_c or payment_date_c
    anchor_dt = None
    if anchor_c and anchor_c.value:
        try:
            anchor_dt = datetime.strptime(str(anchor_c.value), "%Y-%m-%d")
        except Exception:
            anchor_dt = None

    # If no explicit bill/payment label, choose latest non-future date as anchor
    if not anchor_dt:
        plausible_dates = []
        for c in date_candidates:
            if c.semantic_type not in (DateSemanticType.PLAN_EXPIRY_DATE, DateSemanticType.RENEWAL_DATE, DateSemanticType.DUE_DATE):
                try:
                    dt = datetime.strptime(str(c.value), "%Y-%m-%d")
                    plausible_dates.append((dt, c))
                except Exception:
                    pass
        if plausible_dates:
            plausible_dates.sort(key=lambda x: x[0])
            anchor_dt, anchor_c = plausible_dates[-1]

    # Step 2: Form candidate pairs (c_start, c_end)
    candidate_pairs: List[Tuple[Candidate, Candidate, float]] = []  # (start, end, score)

    # 2a. Check explicit range matches from candidate extractor (highest confidence)
    range_starts = [c for c in date_candidates if c.semantic_type == DateSemanticType.BILLING_PERIOD_START]
    range_ends = [c for c in date_candidates if c.semantic_type == DateSemanticType.BILLING_PERIOD_END]

    for s in range_starts:
        for e in range_ends:
            if str(s.value) < str(e.value):
                candidate_pairs.append((s, e, 150.0))

    # 2b. Form all plausible pairs from non-excluded dates
    eligible_dates = [
        c for c in date_candidates
        if c.semantic_type not in (
            DateSemanticType.ACTIVATION_DATE,
            DateSemanticType.PLAN_EXPIRY_DATE,
            DateSemanticType.RENEWAL_DATE,
        )
    ]

    for i in range(len(eligible_dates)):
        for j in range(len(eligible_dates)):
            if i != j:
                s = eligible_dates[i]
                e = eligible_dates[j]
                if str(s.value) < str(e.value):
                    candidate_pairs.append((s, e, 0.0))

    # Step 3: Score candidate pairs based on cycle duration and temporal anchoring
    scored_pairs = []
    seen_pair_keys = set()

    for s, e, initial_score in candidate_pairs:
        key = (str(s.value), str(e.value))
        if key in seen_pair_keys:
            continue
        seen_pair_keys.add(key)

        try:
            d_start = datetime.strptime(str(s.value), "%Y-%m-%d")
            d_end = datetime.strptime(str(e.value), "%Y-%m-%d")
            delta_days = (d_end - d_start).days + 1
        except Exception:
            continue

        score = initial_score + (s.confidence + e.confidence) * 15.0

        # Bonus for explicit semantic classification
        if s.semantic_type == DateSemanticType.BILLING_PERIOD_START:
            score += 40.0
        if e.semantic_type == DateSemanticType.BILLING_PERIOD_END:
            score += 40.0
        if any("range_match" in src for src in s.evidence_sources + e.evidence_sources):
            score += 50.0

        # Duration Plausibility Brackets
        if 25 <= delta_days <= 34:
            score += 80.0  # Standard 1-month billing cycle
        elif 55 <= delta_days <= 65:
            score += 50.0  # 2-month billing cycle
        elif 80 <= delta_days <= 95:
            score += 60.0  # 3-month / 84-day cycle
        elif 175 <= delta_days <= 190:
            score += 40.0  # 6-month cycle
        elif 355 <= delta_days <= 370:
            score += 30.0  # 1-year annual cycle
        elif delta_days < 7:
            score -= 120.0  # Not a billing cycle (just invoice issue vs payment date)
        elif 100 <= delta_days < 350:
            score -= 80.0   # Atypical multi-month gap
        elif delta_days > 370:
            score -= 200.0  # Distant future plan expiration (e.g. 2025/2026)

        # Proximity to Anchor Date (T_bill)
        if anchor_dt:
            # End date should be close to or slightly before the bill/statement date
            diff_end_anchor = (d_end - anchor_dt).days
            if -35 <= diff_end_anchor <= 5:
                score += 40.0
            elif diff_end_anchor > 60:
                score -= 250.0  # Future plan expiry date, not this month's statement!

            diff_start_anchor = (d_start - anchor_dt).days
            if -45 <= diff_start_anchor <= 0:
                score += 30.0

        scored_pairs.append((score, s, e))

    # Step 4: Pick best scoring pair if above threshold
    best_start = None
    best_end = None

    if scored_pairs:
        scored_pairs.sort(key=lambda x: x[0], reverse=True)
        top_score, top_s, top_e = scored_pairs[0]
        if top_score >= 30.0:
            best_start = top_s
            best_end = top_e
            best_start.semantic_type = DateSemanticType.BILLING_PERIOD_START
            best_end.semantic_type = DateSemanticType.BILLING_PERIOD_END

    # Step 5: Fallback for single-date / prepaid recharge bills
    if not best_start:
        best_start = anchor_c or (date_candidates[0] if date_candidates else None)

    # Check for explicit validity candidate (e.g. 28 Days, 84 Days)
    if best_start and not best_end and best_start.value:
        validity_candidates = [c for c in candidates if c.field_type == FieldType.VALIDITY]
        if validity_candidates:
            try:
                val_days = int(validity_candidates[0].value)
                d_start = datetime.strptime(str(best_start.value), "%Y-%m-%d")
                d_end = d_start + timedelta(days=val_days - 1)
                iso_end = d_end.strftime("%Y-%m-%d")
                best_end = Candidate(
                    field_type=FieldType.DATE,
                    value=iso_end,
                    raw_text=f"{val_days} Days",
                    label="Billing Period End (Computed from Plan Validity)",
                    page=best_start.page,
                    semantic_type=DateSemanticType.BILLING_PERIOD_END,
                    confidence=0.92,
                    evidence_sources=["computed_from_validity"],
                )
            except Exception:
                pass

    final_bill_date = bill_date_c or anchor_c or best_start

    return final_bill_date, best_start, best_end


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
            if any(kw in text_to_check for kw in ["broadband", "fiber", "fibre", "dsl", "ftth", "wifi", "xstream", "jiofiber", "jio fiber", "tikona", "act fibernet"]):
                is_broadband = True
                break
            if any(kw in text_to_check for kw in ["jio prepaid", "airtel prepaid", "vi prepaid", "bsnl prepaid", "vodafone prepaid", "prepaid", "recharge", "top-up", "topup", "voucher", "mobile recharge"]):
                is_prepaid = True
                break
            if any(kw in text_to_check for kw in ["jio postpaid", "airtel postpaid", "vi postpaid", "bsnl postpaid", "vodafone postpaid", "postpaid", "post-paid", "statement", "bill summary", "tax invoice", "bill", "airtel", "jio", "vodafone", "bsnl"]):
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
    else:
        score += 0.40

    # 2. Value was spatially associated with its label
    if any("line_match" in s or "spatial" in s or "regex" in s for s in candidate.evidence_sources):
        score += 0.20

    # 3. Native PDF text (not OCR with potential errors)
    if extraction_method in ("native_pdf", ExtractionMethod.NATIVE_PDF, "native_pdf_regex", "native_pdf_line_match"):
        score += 0.20

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
