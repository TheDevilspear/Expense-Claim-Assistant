"""
Schemas for the Approver Agent.
Works seamlessly with Pydantic v2 if installed, with pure-Python fallback.
Defines:
1. ApprovalDecisionType: "AUTO_APPROVE", "AUTO_REJECT", or "ESCALATE_TO_HUMAN".
2. ApproverDecision: Structured decision packet with actionable reasoning.
3. AuditTrailRecord: Full end-to-end audit trail packet capturing the entire pipeline lifecycle.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import json

class ApprovalDecisionType(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    AUTO_REJECT = "AUTO_REJECT"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"

try:
    from pydantic import BaseModel, Field

    class ApproverDecision(BaseModel):
        claim_id: str
        decision: ApprovalDecisionType
        approved_amount_inr: Optional[float] = None
        actionable_user_reason: str
        internal_rationale: str
        risk_score: float
        escalation_tags: List[str] = []
        requires_human_action: bool
        timestamp: str

        @property
        def reimbursable_amount_inr(self) -> Optional[float]:
            return self.approved_amount_inr

    class AuditTrailRecord(BaseModel):
        claim_id: str
        decision: ApproverDecision
        maker_output: Dict[str, Any]
        checker_report: Dict[str, Any]
        completed_at: str

except ImportError:
    from dataclasses import dataclass, asdict, field

    @dataclass
    class ApproverDecision:
        claim_id: str
        decision: ApprovalDecisionType
        actionable_user_reason: str
        internal_rationale: str
        risk_score: float
        requires_human_action: bool
        timestamp: str
        approved_amount_inr: Optional[float] = None
        escalation_tags: List[str] = field(default_factory=list)

        @property
        def reimbursable_amount_inr(self) -> Optional[float]:
            return self.approved_amount_inr

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

    @dataclass
    class AuditTrailRecord:
        claim_id: str
        decision: ApproverDecision
        maker_output: Dict[str, Any]
        checker_report: Dict[str, Any]
        completed_at: str
