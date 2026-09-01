"""
Constants and Pattern Definitions for Extraction Pipeline.
Single source of truth for vendor patterns, keywords, and domain heuristics.
"""

import re
from typing import List, Tuple, Pattern, Set

# Regex patterns for identifying known telecom / utility vendors:
# (RegexPattern, StandardizedShortName, FullLegalName)
VENDOR_PATTERNS: List[Tuple[Pattern, str, str]] = [
    (re.compile(r'\bjio\s*(?:prepaid|postpaid|fiber|fibernet)?\b|reliance\s+jio', re.I), "Jio", "Reliance Jio Infocomm"),
    (re.compile(r'\bairtel\s*(?:prepaid|postpaid|xstream|broadband|black)?\b|bharti\s+airtel', re.I), "Airtel", "Bharti Airtel Limited"),
    (re.compile(r'\bact\s*fibernet\b|atria\s+convergence', re.I), "ACT Fibernet", "Atria Convergence Technologies"),
    (re.compile(r'\bvodafone\b|\bvi\s*(?:prepaid|postpaid)?\b(?!\w)|vodafone\s+idea', re.I), "Vodafone", "Vodafone Idea Limited"),
    (re.compile(r'\bbsnl\s*(?:prepaid|postpaid)?\b|bharat\s+sanchar', re.I), "BSNL", "Bharat Sanchar Nigam Limited"),
    (re.compile(r'\btikona\b', re.I), "Tikona", "Tikona Infinet"),
    (re.compile(r'\btata\s+sky\b|\btata\s+play\b|\btata\s+teleservices', re.I), "Tata Play", "Tata Play Limited"),
    (re.compile(r'\bphonepe\b', re.I), "PhonePe", "PhonePe Private Limited"),
    (re.compile(r'\bpaytm\b', re.I), "Paytm", "One97 Communications Limited"),
    (re.compile(r'\bgoogle\s*pay\b|\bgpay\b', re.I), "Google Pay", "Google Pay"),
]

# Set of lowercase vendor identifiers for quick substring and token matching
KNOWN_TELECOM_VENDOR_TOKENS: Set[str] = {
    "airtel",
    "airtel prepaid",
    "airtel postpaid",
    "jio",
    "jio prepaid",
    "jio postpaid",
    "jio fiber",
    "jiofiber",
    "tikona",
    "vodafone",
    "vi",
    "vi prepaid",
    "vi postpaid",
    "bsnl",
    "bsnl prepaid",
    "bsnl postpaid",
    "act",
    "act fibernet",
    "tata",
    "tata play",
    "phonepe",
    "paytm",
    "gpay",
}

# Specific prepaid classification tokens
PREPAID_CLASSIFICATION_KEYWORDS = [
    "jio prepaid",
    "airtel prepaid",
    "vi prepaid",
    "bsnl prepaid",
    "vodafone prepaid",
    "prepaid recharge",
    "prepaid",
    "recharge successful",
    "recharge receipt",
    "recharge",
    "top-up",
    "topup",
    "voucher",
]

# Specific postpaid classification tokens
POSTPAID_CLASSIFICATION_KEYWORDS = [
    "jio postpaid",
    "airtel postpaid",
    "vi postpaid",
    "bsnl postpaid",
    "vodafone postpaid",
    "airtel black",
    "postpaid bill",
    "postpaid",
    "post-paid",
    "monthly statement",
    "bill summary",
    "tax invoice",
    "statement period",
    "account number",
]

# Standard Indian telecom prepaid recharge price points for document classification
COMMON_PREPAID_RECHARGE_AMOUNTS: Set[float] = {
    239.0, 299.0, 399.0, 479.0, 539.0, 549.0, 555.0, 666.0, 719.0,
    749.0, 839.0, 999.0, 1199.0, 1499.0, 2499.0, 2999.0
}

# Keywords indicating international roaming or ISD charges
IR_KEYWORDS = [
    "international roaming",
    "isd charges",
    "international calling",
    "ir pack",
    "ir usage",
    "ir charges",
]

# Keywords strongly signaling non-telecom / unrelated expenses
UNRELATED_DOCUMENT_KEYWORDS = [
    "unrelated",
    "personal",
    "travel",
    "medical",
    "fuel",
    "cab",
    "taxi",
    "hotel",
]


# Keywords indicating broadband vs cellphone category in user claims
BROADBAND_CATEGORY_KEYWORDS = [
    "broadband",
    "internet",
    "wifi",
    "wi-fi",
    "fiber",
    "fibre",
    "dsl",
    "ftth",
    "xstream",
    "jiofiber",
    "jio fiber",
    "airtel xstream",
    "airtel broadband",
    "act fibernet",
    "tikona",
]
