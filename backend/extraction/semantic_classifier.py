"""
Stage 4: Semantic Classifier.

Takes raw candidates and classifies their semantic meaning based on
nearby label text. For example:

  Candidate(value=2416.64, label="Total Amount Payable")
    → semantic_type = MoneySemanticType.TOTAL_AMOUNT_PAYABLE

  Candidate(value="2024-01-05", label="Statement Period")
    → semantic_type = DateSemanticType.BILLING_PERIOD_START

Purely deterministic — keyword dictionary driven, no LLM calls.
"""

from typing import List
from models.extraction_schema import (
    Candidate,
    FieldType,
    MoneySemanticType,
    DateSemanticType,
    IdentifierSemanticType,
)


# ---------------------------------------------------------------------------
# Money label → semantic type mapping
# Ordered by specificity: longer keywords first to avoid partial matches
# ---------------------------------------------------------------------------

_MONEY_LABEL_MAP = {
    MoneySemanticType.TOTAL_AMOUNT_PAYABLE: [
        "total amount payable", "total amount", "total payable", "amount payable",
        "net payable", "grand total", "total due", "amount due", "invoice value",
        "invoice total", "invoice amount", "bill amount", "gross amount", "net amount",
        "total (incl", "total(incl", "total current charges", "total:", "amount:",
        "amount (rs)", "amount (inr)", "total (rs.)", "total (inr)", "amount payable (rs.)",
        "payable:", "due:", "total charges", "total",
    ],
    MoneySemanticType.CURRENT_BILL_AMOUNT: [
        "current bill amount", "charges for this month",
        "this month's charges", "total current charges",
        "total charges", "monthly charges total",
        "charges summary", "this month's charges summary",
        "current charges", "bill summary",
    ],
    MoneySemanticType.PAID_AMOUNT: [
        "paid amount", "payment received", "amount paid",
        "payment made", "received from", "total paid",
    ],
    MoneySemanticType.RECHARGE_AMOUNT: [
        "recharge amount", "recharge value", "plan amount",
        "top-up amount", "pack price", "recharge of",
        "recharge successful",
    ],
    MoneySemanticType.TAX: [
        "taxes (gst)", "taxes(gst)", "total tax",
        "cgst", "sgst", "igst", "service tax",
        "cess", "taxes", "tax",
    ],
    MoneySemanticType.SERVICE_COMPONENT: [
        "plan charges", "monthly plan charges", "monthly charges",
        "rental", "subscription", "fiber", "broadband", "dsl",
        "telemedia", "dth", "recurring charges", "one time charge",
        "installation",
    ],
    MoneySemanticType.PREVIOUS_BALANCE: [
        "previous balance", "outstanding", "arrears",
        "brought forward", "opening balance", "last bill amount",
    ],
    MoneySemanticType.LATE_FEE: [
        "late fee", "late payment", "penalty",
        "overdue charge", "late charge",
    ],
    MoneySemanticType.DISCOUNT: [
        "discount", "rebate", "credit", "adjustment",
        "waiver", "concession",
    ],
}

# ---------------------------------------------------------------------------
# Date label → semantic type mapping
# ---------------------------------------------------------------------------

_DATE_LABEL_MAP = {
    DateSemanticType.BILLING_PERIOD_START: [
        "statement period", "billing cycle", "billing period",
        "bill period", "service period",
    ],
    DateSemanticType.BILLING_PERIOD_END: [
        # These are typically extracted as part of a "X to Y" range
        # The classifier handles ranges specially below
    ],
    DateSemanticType.BILL_DATE: [
        "bill date", "invoice date", "statement date",
        "date of invoice", "billing date",
    ],
    DateSemanticType.DUE_DATE: [
        "due date", "payment due", "pay by", "payable by",
    ],
    DateSemanticType.PAYMENT_DATE: [
        "payment date", "paid on", "transaction date",
        "date of payment",
    ],
    DateSemanticType.ACTIVATION_DATE: [
        "activation date", "activated on", "start date",
    ],
    DateSemanticType.TRANSACTION_TIMESTAMP: [
        "transaction date", "transaction time",
    ],
}


def classify(candidate: Candidate) -> None:
    """
    Classifies a candidate's semantic type in-place based on its label.
    Modifies candidate.semantic_type directly.
    """
    if candidate.field_type == FieldType.MONEY:
        candidate.semantic_type = _classify_money(candidate)
    elif candidate.field_type == FieldType.DATE:
        candidate.semantic_type = _classify_date(candidate)
    elif candidate.field_type == FieldType.IDENTIFIER:
        # Already classified during extraction (label contains the type)
        if candidate.semantic_type is None:
            candidate.semantic_type = IdentifierSemanticType.OTHER_ID
    # VENDOR candidates don't need further classification


def classify_all(candidates: List[Candidate]) -> None:
    """Classifies all candidates in-place."""
    for candidate in candidates:
        classify(candidate)


def _classify_money(candidate: Candidate) -> MoneySemanticType:
    """Classifies a money candidate by matching its label against known keywords."""
    label_lower = candidate.label.lower()

    best_type = MoneySemanticType.OTHER
    best_score = 0

    for sem_type, keywords in _MONEY_LABEL_MAP.items():
        for kw in keywords:
            if kw in label_lower:
                # Longer match = more specific = higher score
                score = len(kw)
                if score > best_score:
                    best_score = score
                    best_type = sem_type

    return best_type


def _classify_date(candidate: Candidate) -> DateSemanticType:
    """Classifies a date candidate by matching its label against known keywords."""
    label_lower = candidate.label.lower()

    best_type = DateSemanticType.OTHER_DATE
    best_score = 0

    for sem_type, keywords in _DATE_LABEL_MAP.items():
        for kw in keywords:
            if kw in label_lower:
                score = len(kw)
                if score > best_score:
                    best_score = score
                    best_type = sem_type

    return best_type
