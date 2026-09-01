"""
Approver Agent Implementation.
Responsibilities:
1. Ingests MakerOutput and CheckerReport from Maker and Checker agents.
2. Applies the final decision matrix:
   - AUTO_APPROVE: All checks passed with high confidence AND amount <= reimbursable cap.
   - AUTO_REJECT: Blatant fraud (duplicate invoice), irrelevant document, or policy violation (> cap, top-ups).
   - ESCALATE_TO_HUMAN: Mismatches, low extraction confidence, or unverified documents.
3. Generates clear, specific, actionable user-facing explanation (never a bare 'rejected').
4. Formulates complete audit log rationale with risk score calculation.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from models.maker_schema import MakerOutput
from models.checker_schema import CheckerReport, CheckStatus
from models.approver_schema import ApproverDecision, ApprovalDecisionType
import policy


class ApproverAgent:
    """
    Approver Agent: Final decision engine and audit trail assembler.
    """

    def __init__(self):
        self.max_cap = policy.POLICY_MAX_REIMBURSABLE_CAP
        self.auto_approve_threshold = policy.AUTO_APPROVE_AMOUNT_THRESHOLD
        self.confidence_threshold = policy.CONFIDENCE_THRESHOLD

    def process(self, maker_output: MakerOutput, checker_report: CheckerReport) -> ApproverDecision:
        """
        Evaluates CheckerReport and outputs the final ApproverDecision.
        """
        claim_id = maker_output.claim_id
        extracted = maker_output.extracted_invoice
        claimed = maker_output.normalized_claim

        claimed_amt = claimed.claimed_amount_inr
        inv_amt = extracted.total_amount_inr.value
        verified_amt = float(inv_amt) if inv_amt is not None else claimed_amt

        # -------------------------------------------------------------
        # Decision Case 1: Automatic Rejections (Non-Negotiable)
        # -------------------------------------------------------------
        if checker_report.has_duplicate_fraud:
            dup_check = next((c for c in checker_report.checks if c.check_id == "DUPLICATE_FRAUD_CHECK"), None)
            dup_reason = dup_check.reason if dup_check else "Duplicate invoice detected."
            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.AUTO_REJECT,
                approved_amount_inr=None,
                actionable_user_reason=f"Rejected (Duplicate): {dup_reason}",
                internal_rationale="Rejected automatically due to duplicate invoice number / bill fingerprint reuse across claims.",
                risk_score=1.0,
                escalation_tags=["DUPLICATE_FRAUD"],
                requires_human_action=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if not extracted.is_relevant_invoice:
            doc_label = extracted.detected_document_type.replace('_', ' ').title()
            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.AUTO_REJECT,
                approved_amount_inr=None,
                actionable_user_reason=f"Rejected (Invalid Receipt): Uploaded file is a '{doc_label}', not an eligible telecom invoice.",
                internal_rationale="Rejected automatically because the document failed telecom/broadband relevancy checks.",
                risk_score=0.9,
                escalation_tags=["IRRELEVANT_DOCUMENT"],
                requires_human_action=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Policy Cap Check (> Policy Cap Maximum Reimbursable Limit)
        if claimed_amt > self.max_cap or (verified_amt and verified_amt > self.max_cap):
            violating_amt = max(claimed_amt, verified_amt or 0.0)
            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.AUTO_REJECT,
                approved_amount_inr=None,
                actionable_user_reason=f"Rejected (Policy Cap): Claimed ₹{violating_amt:,.2f} exceeds company limit of ₹{self.max_cap:,.0f} per claim.",
                internal_rationale=f"Rejected automatically because amount ₹{violating_amt:,.2f} exceeds the ₹{self.max_cap:,.2f} reimbursable policy cap.",
                risk_score=0.75,
                escalation_tags=["POLICY_CAP_EXCEEDED"],
                requires_human_action=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Amount Discrepancy Check (Claimed Amount > Invoice Amount)
        if (
            extracted.total_amount_inr.confidence >= self.confidence_threshold
            and claimed_amt > verified_amt
        ):
            diff = max(0.0, claimed_amt - verified_amt)
            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.AUTO_REJECT,
                approved_amount_inr=None,
                actionable_user_reason=f"Rejected (Amount Discrepancy): Claimed ₹{claimed_amt:,.2f} exceeds invoice amount ₹{verified_amt:,.2f} (+₹{diff:,.2f}).",
                internal_rationale=f"Rejected automatically because claimed amount exceeds invoice figure. Diff: +₹{diff:,.2f}.",
                risk_score=0.85,
                escalation_tags=["AMOUNT_HIGHER_THAN_INVOICE"],
                requires_human_action=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        if checker_report.has_policy_violation:
            plan_check = next((c for c in checker_report.checks if c.check_id == "POLICY_PLAN_TYPE" and c.status == CheckStatus.FAIL_POLICY_VIOLATION), None)
            if plan_check:
                reason = "Rejected (Ineligible Plan): Data top-ups and add-on packs are not reimbursable under policy."
                tag = "DISALLOWED_PLAN_TYPE"
            else:
                reason = "Rejected (Policy Violation): Claim breaches company reimbursement eligibility guidelines."
                tag = "POLICY_VIOLATION"

            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.AUTO_REJECT,
                approved_amount_inr=None,
                actionable_user_reason=reason,
                internal_rationale="Rejected automatically on non-negotiable company policy grounds.",
                risk_score=0.75,
                escalation_tags=[tag],
                requires_human_action=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # -------------------------------------------------------------
        # Decision Case 2: Escalations to Human Review
        # -------------------------------------------------------------
        # Case 2a: Low-Confidence / Blurry Extraction
        if checker_report.has_low_confidence or extracted.is_blurry_or_unreadable:
            if extracted.is_blurry_or_unreadable:
                user_msg = "Manual Review (Blurry Image): Receipt is unreadable due to low sharpness/glare."
            else:
                user_msg = "Manual Review: Key fields could not be verified with sufficient confidence from the document."
            
            conf_check = next((c for c in checker_report.checks if c.status == CheckStatus.FLAGGED_LOW_CONFIDENCE), None)
            reason_details = conf_check.reason if conf_check else "Visual legibility is degraded."
            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.ESCALATE_TO_HUMAN,
                approved_amount_inr=None,
                actionable_user_reason=user_msg,
                internal_rationale=f"Escalated due to low extraction confidence. {reason_details}",
                risk_score=0.60,
                escalation_tags=["LOW_CONFIDENCE_BLUR"],
                requires_human_action=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Case 2b: Field Mismatch (Billing Period, Category, or Amount)
        if checker_report.has_mismatch:
            # Check if billing period / date mismatch
            date_mismatch = next(
                (c for c in checker_report.checks if c.check_id == "BILLING_PERIOD_MATCH" and c.status == CheckStatus.FAIL_MISMATCH),
                None,
            )
            cat_mismatch = next(
                (c for c in checker_report.checks if c.check_id == "POLICY_PLAN_TYPE" and c.status == CheckStatus.FAIL_MISMATCH),
                None,
            )
            amt_mismatch = next(
                (c for c in checker_report.checks if c.check_id == "AMOUNT_MATCH" and c.status == CheckStatus.FAIL_MISMATCH),
                None,
            )

            if date_mismatch:
                user_msg = f"Billing Period Mismatch: {date_mismatch.reason}"
                internal_msg = f"Escalated due to billing period / validity mismatch: {date_mismatch.reason}"
                tag = "BILLING_PERIOD_MISMATCH"
                score = 0.70
            elif cat_mismatch:
                cat_claimed = claimed.claimed_category.capitalize()
                doc_type_label = extracted.detected_document_type.replace('_', ' ').title()
                user_msg = f"Category Mismatch: Claimed as {cat_claimed} Expense, but receipt is for a {doc_type_label}."
                internal_msg = f"Escalated due to service category mismatch: Claimed {cat_claimed} vs Detected {doc_type_label}."
                tag = "CATEGORY_MISMATCH"
                score = 0.65
            elif amt_mismatch:
                user_msg = f"Amount Mismatch: {amt_mismatch.reason}"
                internal_msg = f"Escalated due to amount mismatch: {amt_mismatch.reason}"
                tag = "AMOUNT_MISMATCH"
                score = 0.70
            else:
                user_msg = "Manual Review: One or more claim fields do not match the invoice details."
                internal_msg = "Escalated due to unverified field discrepancy against document."
                tag = "FIELD_MISMATCH"
                score = 0.65

            return ApproverDecision(
                claim_id=claim_id,
                decision=ApprovalDecisionType.ESCALATE_TO_HUMAN,
                approved_amount_inr=None,
                actionable_user_reason=user_msg,
                internal_rationale=internal_msg,
                risk_score=score,
                escalation_tags=[tag],
                requires_human_action=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # -------------------------------------------------------------
        # Decision Case 3: Clean Auto-Approval (<= Threshold & 100% Pass)
        # -------------------------------------------------------------
        vendor_name = extracted.vendor_name.value or "telecom"
        return ApproverDecision(
            claim_id=claim_id,
            decision=ApprovalDecisionType.AUTO_APPROVE,
            approved_amount_inr=verified_amt,
            actionable_user_reason=f"Approved: ₹{verified_amt:,.2f} verified against {vendor_name} invoice.",
            internal_rationale="All field cross-checks and policy rules passed with high confidence. Amount is within auto-approval policy cap.",
            risk_score=0.05,
            escalation_tags=["AUTO_APPROVED_CLEAN"],
            requires_human_action=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
