"""
Company Expense Claim Policies & Confidence Thresholds.
Single source of truth for all business rules, thresholds, and caps.
"""

# Maximum reimbursable amount per claim (₹5,000.00)
POLICY_MAX_REIMBURSABLE_CAP: float = 5000.00

# Maximum amount allowed for zero-touch auto-approval (₹5,000.00)
AUTO_APPROVE_AMOUNT_THRESHOLD: float = 5000.00

# Minimum confidence required for deterministic automated approval (0.80)
CONFIDENCE_THRESHOLD: float = 0.80

# Maximum allowable variance in days between claimed billing dates and invoice dates
BILLING_DATE_TOLERANCE_DAYS: int = 2

# Minimum character length for an invoice number to be valid for duplicate detection
MIN_INVOICE_NUMBER_LENGTH: int = 4

# Disallowed plan keywords for policy compliance check
DISALLOWED_PLAN_KEYWORDS = [
    "top-up",
    "topup",
    "data pack",
    "add-on",
    "addon",
    "data booster",
    "talktime",
    "voucher",
    "roaming pack",
]

# Standard confidence scores assigned across extraction stages
CONFIDENCE_LEVELS = {
    "VISION_ARBITRATION": 0.90,
    "EXPLICIT_KEYWORD_MATCH": 0.95,
    "HIGH_RECONCILIATION_MATCH": 0.90,
    "MEDIUM_RECONCILIATION_MATCH": 0.75,
    "LOW_HEURISTIC_MATCH": 0.50,
    "ABSENT_OR_UNREADABLE": 0.0,
}
