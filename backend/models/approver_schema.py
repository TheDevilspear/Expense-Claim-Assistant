"""
Pydantic Schemas & Data Structures for the Approver Agent.
Defines:
1. ApprovalDecisionType: "AUTO_APPROVE", "AUTO_REJECT", or "ESCALATE_TO_HUMAN".
2. ApproverDecision: Structured decision packet with actionable reasoning.
3. AuditTrailRecord: Full end-to-end audit trail packet capturing the entire pipeline lifecycle.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import json

try:
    from pydantic import BaseModel, Field

    class ApprovalDecisionType(str, Enum):
        AUTO_APPROVE = "AUTO_APPROVE"
        AUTO_REJECT = "AUTO_REJECT"
        ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"

    class ApproverDecision(BaseModel):
        claim_id: str = Field(..., description="Unique claim reference ID")
        decision: ApprovalDecisionType = Field(..., description="AUTO_APPROVE, AUTO_REJECT, or ESCALATE_TO_HUMAN")
        approved_amount_inr: Optional[float] = Field(None, description="Final approved reimbursement amount in INR (if approved)")
        actionable_user_reason: str = Field(..., description="Clear, user-facing explanation of the decision or reason for rejection/escalation")
        internal_rationale: str = Field(..., description="Auditor-facing rationale based on risk score and check outcomes")
        risk_score: float = Field(..., ge=0.0, le=1.0, description="Calculated fraud & error risk score (0.0 = low risk, 1.0 = high risk)")
        escalation_tags: List[str] = Field(default_factory=list, description="Tags e.g. ['HIGH_VALUE', 'LOW_CONFIDENCE', 'AMOUNT_MISMATCH']")
        requires_human_action: bool = Field(..., description="True if a human reviewer must take manual action")
        timestamp: str = Field(..., description="ISO 8601 timestamp of Approver Agent decision")

    class AuditTrailRecord(BaseModel):
        claim_id: str
        decision: ApproverDecision
        maker_output: Dict[str, Any]
        checker_report: Dict[str, Any]
        completed_at: str

except ImportError:
    from dataclasses import dataclass, asdict, field

    class ApprovalDecisionType(str, Enum):
        AUTO_APPROVE = "AUTO_APPROVE"
        AUTO_REJECT = "AUTO_REJECT"
        ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"

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
