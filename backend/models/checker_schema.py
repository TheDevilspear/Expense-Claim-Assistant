"""
Pydantic Schemas & Data Structures for the Checker Agent.
Defines:
1. CheckStatus: Enum representing all deterministic check outcomes.
2. CheckResult: Detailed result of an individual field or policy check.
3. CheckerReport: Complete structured handoff packet from Checker to Approver Agent.
"""

from typing import Optional, Any, List, Dict
from enum import Enum
import json

try:
    from pydantic import BaseModel, Field

    class CheckStatus(str, Enum):
        PASS = "PASS"
        FAIL_MISMATCH = "FAIL_MISMATCH"
        FAIL_POLICY_VIOLATION = "FAIL_POLICY_VIOLATION"
        FAIL_DUPLICATE_INVOICE = "FAIL_DUPLICATE_INVOICE"
        FAIL_IRRELEVANT_DOCUMENT = "FAIL_IRRELEVANT_DOCUMENT"
        FLAGGED_LOW_CONFIDENCE = "FLAGGED_LOW_CONFIDENCE"

    class CheckResult(BaseModel):
        check_id: str = Field(..., description="Unique check identifier, e.g. 'AMOUNT_MATCH', 'POLICY_MAX_CAP'")
        check_name: str = Field(..., description="Human-readable title of the check")
        status: CheckStatus = Field(..., description="Evaluation outcome")
        confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score for this field")
        claimed_value: Optional[Any] = Field(None, description="Value submitted by the user")
        extracted_value: Optional[Any] = Field(None, description="Value extracted from the invoice attachment")
        reason: str = Field(..., description="Explicit, actionable explanation of the check result")
        is_blocking: bool = Field(..., description="True if this failure prevents auto-approval")

    class CheckerReport(BaseModel):
        claim_id: str = Field(..., description="Unique claim reference ID")
        all_checks_passed: bool = Field(..., description="True if 100% of checks passed with high confidence")
        has_low_confidence: bool = Field(..., description="True if any critical field had confidence < 0.80")
        has_mismatch: bool = Field(..., description="True if claimed details do not match invoice details")
        has_policy_violation: bool = Field(..., description="True if company reimbursement policy was violated")
        has_duplicate_fraud: bool = Field(..., description="True if invoice was already claimed previously")
        checks: List[CheckResult] = Field(..., description="List of all individual check outcomes")
        checker_summary: str = Field(..., description="Summary narrative of the verification report")
        timestamp: str = Field(..., description="ISO 8601 timestamp of Checker Agent completion")

except ImportError:
    from dataclasses import dataclass, asdict, field

    class CheckStatus(str, Enum):
        PASS = "PASS"
        FAIL_MISMATCH = "FAIL_MISMATCH"
        FAIL_POLICY_VIOLATION = "FAIL_POLICY_VIOLATION"
        FAIL_DUPLICATE_INVOICE = "FAIL_DUPLICATE_INVOICE"
        FAIL_IRRELEVANT_DOCUMENT = "FAIL_IRRELEVANT_DOCUMENT"
        FLAGGED_LOW_CONFIDENCE = "FLAGGED_LOW_CONFIDENCE"

    @dataclass
    class CheckResult:
        check_id: str
        check_name: str
        status: CheckStatus
        confidence: float
        reason: str
        is_blocking: bool
        claimed_value: Optional[Any] = None
        extracted_value: Optional[Any] = None

    @dataclass
    class CheckerReport:
        claim_id: str
        all_checks_passed: bool
        has_low_confidence: bool
        has_mismatch: bool
        has_policy_violation: bool
        has_duplicate_fraud: bool
        checks: List[CheckResult]
        checker_summary: str
        timestamp: str

        def model_dump_json(self, indent: int = 2) -> str:
            def serialize(obj):
                if isinstance(obj, Enum):
                    return obj.value
                if hasattr(obj, "__dict__"):
                    return asdict(obj)
                return str(obj)
            return json.dumps(asdict(self), default=serialize, indent=indent)

        def model_dump(self) -> Dict[str, Any]:
            return asdict(self)
