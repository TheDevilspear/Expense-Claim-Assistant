"""
Schemas for the Checker Agent.
Works seamlessly with Pydantic v2 if installed, with pure-Python fallback.
Defines:
1. CheckStatus: Enum representing all deterministic check outcomes.
2. CheckResult: Detailed result of an individual field or policy check.
3. CheckerReport: Complete structured handoff packet from Checker to Approver Agent.
"""

from typing import Optional, Any, List, Dict
from enum import Enum
import json

class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL_MISMATCH = "FAIL_MISMATCH"
    FAIL_POLICY_VIOLATION = "FAIL_POLICY_VIOLATION"
    FAIL_DUPLICATE_INVOICE = "FAIL_DUPLICATE_INVOICE"
    FAIL_IRRELEVANT_DOCUMENT = "FAIL_IRRELEVANT_DOCUMENT"
    FLAGGED_LOW_CONFIDENCE = "FLAGGED_LOW_CONFIDENCE"

try:
    from pydantic import BaseModel, Field

    class CheckResult(BaseModel):
        check_id: str
        check_name: str
        status: CheckStatus
        confidence: float
        claimed_value: Optional[Any] = None
        extracted_value: Optional[Any] = None
        reason: str
        is_blocking: bool

    class CheckerReport(BaseModel):
        claim_id: str
        all_checks_passed: bool
        has_low_confidence: bool
        has_mismatch: bool
        has_policy_violation: bool
        has_duplicate_fraud: bool
        checks: List[CheckResult]
        checker_summary: str
        timestamp: str

except ImportError:
    from dataclasses import dataclass, asdict, field

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

        def model_dump(self) -> Dict[str, Any]:
            def _conv(obj):
                if isinstance(obj, Enum):
                    return obj.value
                if hasattr(obj, "__dict__"):
                    return asdict(obj)
                return str(obj)
            return json.loads(json.dumps(asdict(self), default=_conv))

        def model_dump_json(self, indent: int = 2) -> str:
            return json.dumps(self.model_dump(), indent=indent)
