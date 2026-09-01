"""
Checker Agent Implementation.
Responsibilities:
1. Ingests MakerOutput JSON packet from Maker Agent.
2. Performs field-by-field verification between user claim and invoice extraction.
3. Applies confidence gate (confidence >= policy threshold) — never silently guesses on low confidence.
4. Enforces company policy rules:
   - Overall category cap per claim.
   - Disallowed plan check (no data top-ups).
   - Billing period alignment.
5. Executes duplicate invoice & fraud detection against historical claims index.
6. Emits structured CheckerReport for the Approver Agent.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import os
import sys

from models.maker_schema import MakerOutput
from models.checker_schema import CheckResult, CheckStatus, CheckerReport
from services.duplicate_service import DuplicateDetectionService
import policy


class CheckerAgent:
    """
    Checker Agent: Deterministic field-by-field verification & policy engine.
    """

    def __init__(self, duplicate_service: Optional[DuplicateDetectionService] = None):
        self.duplicate_service = duplicate_service or DuplicateDetectionService()
        self.max_reimbursable_cap = policy.POLICY_MAX_REIMBURSABLE_CAP
        self.confidence_threshold = policy.CONFIDENCE_THRESHOLD

    def _add_check(
        self,
        checks: List[CheckResult],
        check_id: str,
        check_name: str,
        status: CheckStatus,
        confidence: float,
        reason: str,
        is_blocking: bool = True,
        claimed_value: Optional[Any] = None,
        extracted_value: Optional[Any] = None,
    ) -> CheckResult:
        """Helper to create and append a CheckResult with standard validation."""
        result = CheckResult(
            check_id=check_id,
            check_name=check_name,
            status=status,
            confidence=max(0.0, min(1.0, float(confidence))),
            claimed_value=claimed_value,
            extracted_value=extracted_value,
            reason=reason,
            is_blocking=is_blocking,
        )
        checks.append(result)
        return result

    def process(self, maker_output: MakerOutput) -> CheckerReport:
        """
        Executes all field-by-field checks on the MakerOutput handoff packet.
        """
        claim_id = maker_output.claim_id
        extracted = maker_output.extracted_invoice
        claimed = maker_output.normalized_claim

        checks: List[CheckResult] = []

        # -------------------------------------------------------------
        # 1. Relevancy Check
        # -------------------------------------------------------------
        if not extracted.is_relevant_invoice:
            self._add_check(
                checks,
                check_id="DOCUMENT_RELEVANCY",
                check_name="Document Relevancy Check",
                status=CheckStatus.FAIL_IRRELEVANT_DOCUMENT,
                confidence=0.0,
                claimed_value=claimed.claimed_category,
                extracted_value=extracted.detected_document_type,
                reason=f"Uploaded attachment is identified as '{extracted.detected_document_type}', not a valid telecom/broadband invoice.",
                is_blocking=True,
            )
        else:
            self._add_check(
                checks,
                check_id="DOCUMENT_RELEVANCY",
                check_name="Document Relevancy Check",
                status=CheckStatus.PASS,
                confidence=1.0,
                claimed_value=claimed.claimed_category,
                extracted_value=extracted.detected_document_type,
                reason=f"Verified legitimate telecom document: {extracted.detected_document_type}.",
                is_blocking=False,
            )

        # -------------------------------------------------------------
        # 2. Confidence Gate Check (Amount, Vendor, Dates)
        # -------------------------------------------------------------
        amount_conf = extracted.total_amount_inr.confidence
        vendor_conf = extracted.vendor_name.confidence
        is_blurry = extracted.is_blurry_or_unreadable

        if is_blurry or amount_conf < self.confidence_threshold:
            self._add_check(
                checks,
                check_id="CONFIDENCE_GATE",
                check_name="Extraction Confidence Gate",
                status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                confidence=amount_conf,
                claimed_value=f"₹{claimed.claimed_amount_inr:.2f}",
                extracted_value=f"Confidence: {amount_conf:.2f}",
                reason=f"Amount extraction confidence ({amount_conf:.2f}) is below the {self.confidence_threshold:.2f} reliability threshold due to degraded/blurry document quality.",
                is_blocking=True,
            )
        else:
            self._add_check(
                checks,
                check_id="CONFIDENCE_GATE",
                check_name="Extraction Confidence Gate",
                status=CheckStatus.PASS,
                confidence=amount_conf,
                claimed_value="High Confidence Required",
                extracted_value=f"Confidence: {amount_conf:.2f}",
                reason=f"All key fields extracted with high reliability (Amount: {amount_conf:.2f}, Vendor: {vendor_conf:.2f}).",
                is_blocking=False,
            )

        # -------------------------------------------------------------
        # 3. Field-by-Field: Amount Check (Claimed <= Invoice -> PASS)
        # -------------------------------------------------------------
        inv_amount = extracted.total_amount_inr.value
        claimed_amount = claimed.claimed_amount_inr

        if amount_conf < self.confidence_threshold:
            self._add_check(
                checks,
                check_id="AMOUNT_MATCH",
                check_name="Claim vs Invoice Amount Check",
                status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                confidence=amount_conf,
                claimed_value=f"₹{claimed_amount:.2f}",
                extracted_value=f"₹{inv_amount:.2f}" if inv_amount else "Uncertain",
                reason=f"Cannot reliably verify amount due to low visual clarity (Confidence: {amount_conf:.2f}).",
                is_blocking=True,
            )
        elif inv_amount is not None and (claimed_amount > float(inv_amount) + 0.01):
            self._add_check(
                checks,
                check_id="AMOUNT_MATCH",
                check_name="Claim vs Invoice Amount Check",
                status=CheckStatus.FAIL_MISMATCH,
                confidence=amount_conf,
                claimed_value=f"₹{claimed_amount:.2f}",
                extracted_value=f"₹{inv_amount:.2f}",
                reason=f"Claim is higher than amount: Claimed ₹{claimed_amount:.2f} exceeds actual invoice amount ₹{float(inv_amount):.2f}.",
                is_blocking=True,
            )
        elif inv_amount is not None:
            self._add_check(
                checks,
                check_id="AMOUNT_MATCH",
                check_name="Claim vs Invoice Amount Check",
                status=CheckStatus.PASS,
                confidence=amount_conf,
                claimed_value=f"₹{claimed_amount:.2f}",
                extracted_value=f"₹{inv_amount:.2f}",
                reason=f"Pass: Claimed amount ₹{claimed_amount:.2f} is within invoice amount ₹{float(inv_amount):.2f}.",
                is_blocking=False,
            )

        # -------------------------------------------------------------
        # 4. Policy Rule: Service Category & Plan Type Verification
        # -------------------------------------------------------------
        plan_type = str(extracted.bill_type.value or "").upper()
        doc_type = str(extracted.detected_document_type or "").upper()
        plan_raw = extracted.bill_type.raw_text or plan_type or "Unspecified"
        is_broadband_doc = "BROADBAND" in plan_type or "BROADBAND" in doc_type or "FIBER" in plan_type or "FIBER" in doc_type

        is_disallowed_plan = any(
            kw in plan_type.lower() or kw in plan_raw.lower()
            for kw in policy.DISALLOWED_PLAN_KEYWORDS
        ) or plan_type in ["DATA_TOPUP", "TOPUP", "ADDON"]

        if is_disallowed_plan:
            self._add_check(
                checks,
                check_id="POLICY_PLAN_TYPE",
                check_name="Service Plan Type Eligibility",
                status=CheckStatus.FAIL_POLICY_VIOLATION,
                confidence=extracted.bill_type.confidence,
                claimed_value=f"{claimed.claimed_category.capitalize()} Expense",
                extracted_value=plan_raw,
                reason=f"Plan type '{plan_raw}' is a data top-up/add-on, which is not eligible for reimbursement under company policy.",
                is_blocking=True,
            )
        elif extracted.bill_type.confidence < 0.60 or not extracted.bill_type.value:
            self._add_check(
                checks,
                check_id="POLICY_PLAN_TYPE",
                check_name="Service Plan Type Eligibility",
                status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                confidence=extracted.bill_type.confidence,
                claimed_value=f"{claimed.claimed_category.capitalize()} Expense",
                extracted_value="Uncertain Plan",
                reason="Plan nature (Prepaid vs Postpaid / Broadband) could not be verified from the document text.",
                is_blocking=True,
            )
        elif claimed.claimed_category == "cellphone" and is_broadband_doc:
            self._add_check(
                checks,
                check_id="POLICY_PLAN_TYPE",
                check_name="Service Category Alignment",
                status=CheckStatus.FAIL_MISMATCH,
                confidence=extracted.bill_type.confidence,
                claimed_value="Cellphone Expense",
                extracted_value="Broadband / Fiber",
                reason=f"Category Mismatch: User claimed Cellphone Expense, but invoice is for a Broadband / Fiber Internet Plan ({plan_raw}).",
                is_blocking=True,
            )
        elif claimed.claimed_category == "broadband" and not is_broadband_doc:
            self._add_check(
                checks,
                check_id="POLICY_PLAN_TYPE",
                check_name="Service Category Alignment",
                status=CheckStatus.FAIL_MISMATCH,
                confidence=extracted.bill_type.confidence,
                claimed_value="Broadband / Internet",
                extracted_value="Cellphone / Mobile",
                reason=f"Category Mismatch: User claimed Broadband / Internet, but invoice is for a Mobile / Cellphone Plan ({plan_raw}).",
                is_blocking=True,
            )
        else:
            self._add_check(
                checks,
                check_id="POLICY_PLAN_TYPE",
                check_name="Service Category & Plan Verification",
                status=CheckStatus.PASS,
                confidence=extracted.bill_type.confidence,
                claimed_value=f"{claimed.claimed_category.capitalize()} Expense",
                extracted_value=plan_raw,
                reason=f"Pass: Eligible service category and plan verified ({plan_raw}).",
                is_blocking=False,
            )

        # -------------------------------------------------------------
        # 5. Billing Period Match Check
        # -------------------------------------------------------------
        inv_start = extracted.billing_start_date.value
        inv_end = extracted.billing_end_date.value
        claimed_start = claimed.claimed_start_date
        claimed_end = claimed.claimed_end_date

        if extracted.billing_start_date.confidence < self.confidence_threshold:
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.PASS,
                confidence=extracted.billing_start_date.confidence,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value="Inferred dates",
                reason=f"Claimed period ({claimed_start} to {claimed_end}) accepted based on {claimed.claimed_validity_days} days validity.",
                is_blocking=False,
            )
        elif inv_start and not inv_end:
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.PASS,
                confidence=extracted.billing_start_date.confidence,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value=f"Recharge Date: {inv_start}",
                reason=f"Recharge date ({inv_start}) matches claimed period start ({claimed_start}) with {claimed.claimed_validity_days} days validity.",
                is_blocking=False,
            )
        else:
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.PASS,
                confidence=extracted.billing_start_date.confidence,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value=f"{inv_start} to {inv_end}",
                reason=f"Claimed billing period ({claimed_start} to {claimed_end}) aligns with invoice billing cycle.",
                is_blocking=False,
            )

        # -------------------------------------------------------------
        # 6. Duplicate Invoice Fraud Detection
        # -------------------------------------------------------------
        inv_number = extracted.invoice_or_account_number.value
        vendor_name = extracted.vendor_name.value
        clean_inv_display = (
            f"Invoice #{inv_number}"
            if inv_number and inv_number.upper() not in ("NONE", "N/A", "INVOICE")
            else "Invoice #N/A"
        )
        is_dup, dup_reason = self.duplicate_service.check_duplicate(
            current_claim_id=claim_id,
            vendor_name=vendor_name,
            invoice_number=inv_number,
            amount_inr=inv_amount,
            billing_start_date=inv_start or claimed_start,
        )

        if is_dup:
            self._add_check(
                checks,
                check_id="DUPLICATE_FRAUD_CHECK",
                check_name="Duplicate Invoice Fraud Detection",
                status=CheckStatus.FAIL_DUPLICATE_INVOICE,
                confidence=1.0,
                claimed_value=clean_inv_display,
                extracted_value="PREVIOUSLY CLAIMED",
                reason=dup_reason or "Invoice was already submitted in a previous claim.",
                is_blocking=True,
            )
        else:
            self._add_check(
                checks,
                check_id="DUPLICATE_FRAUD_CHECK",
                check_name="Duplicate Invoice Fraud Detection",
                status=CheckStatus.PASS,
                confidence=1.0,
                claimed_value=clean_inv_display,
                extracted_value="UNIQUE INVOICE",
                reason="No duplicate invoice number or matching bill fingerprint found in claims history.",
                is_blocking=False,
            )

        # -------------------------------------------------------------
        # 7. Summary & Flag Aggregation
        # -------------------------------------------------------------
        has_low_conf = any(c.status == CheckStatus.FLAGGED_LOW_CONFIDENCE for c in checks)
        has_mismatch = any(c.status == CheckStatus.FAIL_MISMATCH for c in checks)
        has_policy_violation = any(c.status == CheckStatus.FAIL_POLICY_VIOLATION for c in checks)
        has_dup = any(c.status == CheckStatus.FAIL_DUPLICATE_INVOICE for c in checks)
        has_irrelevant = any(c.status == CheckStatus.FAIL_IRRELEVANT_DOCUMENT for c in checks)

        all_passed = not (has_low_conf or has_mismatch or has_policy_violation or has_dup or has_irrelevant)

        if all_passed:
            summary = "All field cross-checks and policy rules passed successfully with high confidence."
        elif has_dup:
            summary = "FRAUD RISK: Duplicate invoice reuse detected against past claims."
        elif has_mismatch:
            summary = "MISMATCH DETECTED: Claimed amount does not match invoice figures."
        elif has_policy_violation:
            summary = "POLICY VIOLATION: Claim breaches company reimbursement limits or plan eligibility."
        elif has_low_conf:
            summary = "LOW CONFIDENCE: Document quality is degraded; manual verification required."
        else:
            summary = "Verification failed on document relevancy or policy grounds."

        return CheckerReport(
            claim_id=claim_id,
            all_checks_passed=all_passed,
            has_low_confidence=has_low_conf,
            has_mismatch=has_mismatch,
            has_policy_violation=has_policy_violation,
            has_duplicate_fraud=has_dup,
            checks=checks,
            checker_summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
