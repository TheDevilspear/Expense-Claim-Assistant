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
        # 5. Billing Period & Validity Match Check
        # -------------------------------------------------------------
        inv_start = extracted.billing_start_date.value or extracted.bill_date.value
        inv_end = extracted.billing_end_date.value
        inv_validity = extracted.validity_days.value
        claimed_start = claimed.claimed_start_date
        claimed_end = claimed.claimed_end_date
        claimed_validity = claimed.claimed_validity_days
        tolerance = policy.BILLING_DATE_TOLERANCE_DAYS

        # Step 1: Validate claimed dates validity
        try:
            c_start_dt = datetime.strptime(claimed_start, "%Y-%m-%d") if claimed_start else None
            c_end_dt = datetime.strptime(claimed_end, "%Y-%m-%d") if claimed_end else None
        except Exception:
            c_start_dt = None
            c_end_dt = None

        if not c_start_dt or not c_end_dt:
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.FAIL_MISMATCH,
                confidence=1.0,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value=f"{inv_start} to {inv_end}" if inv_end else f"{inv_start}",
                reason="Invalid Claim Dates: Billing start date and end date must be provided in valid ISO date format.",
                is_blocking=True,
            )
        elif c_end_dt < c_start_dt:
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.FAIL_MISMATCH,
                confidence=1.0,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value=f"{inv_start} to {inv_end}" if inv_end else f"{inv_start}",
                reason=f"Date Inversion: Claimed end date ({claimed_end}) cannot precede start date ({claimed_start}).",
                is_blocking=True,
            )
        elif extracted.is_blurry_or_unreadable or (extracted.billing_start_date.confidence < self.confidence_threshold and extracted.bill_date.confidence < self.confidence_threshold and not inv_start):
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                confidence=extracted.billing_start_date.confidence,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value="Uncertain dates",
                reason=f"Billing dates could not be verified from the document with high confidence ({extracted.billing_start_date.confidence:.2f}).",
                is_blocking=True,
            )
        elif inv_start and inv_end:
            try:
                i_start_dt = datetime.strptime(str(inv_start), "%Y-%m-%d")
                i_end_dt = datetime.strptime(str(inv_end), "%Y-%m-%d")
                start_diff = abs((c_start_dt - i_start_dt).days)
                end_diff = abs((c_end_dt - i_end_dt).days)

                if start_diff > tolerance:
                    self._add_check(
                        checks,
                        check_id="BILLING_PERIOD_MATCH",
                        check_name="Billing Period Cross-Check",
                        status=CheckStatus.FAIL_MISMATCH,
                        confidence=extracted.billing_start_date.confidence,
                        claimed_value=f"{claimed_start} to {claimed_end}",
                        extracted_value=f"{inv_start} to {inv_end}",
                        reason=f"Date Mismatch: Claimed start date ({claimed_start}) differs from invoice period start ({inv_start}) by {start_diff} days (tolerance: {tolerance} days).",
                        is_blocking=True,
                    )
                elif end_diff > tolerance:
                    if inv_validity is not None and isinstance(inv_validity, int) and abs(claimed_validity - inv_validity) > tolerance:
                        reason_msg = f"Validity Period Mismatch: Claimed validity ({claimed_validity} days) differs from invoice plan validity ({inv_validity} days). Claimed end date ({claimed_end}) differs from invoice period end ({inv_end}) by {end_diff} days (tolerance: {tolerance} days)."
                    else:
                        reason_msg = f"Date Mismatch: Claimed end date ({claimed_end}) differs from invoice period end ({inv_end}) by {end_diff} days (tolerance: {tolerance} days)."
                    self._add_check(
                        checks,
                        check_id="BILLING_PERIOD_MATCH",
                        check_name="Billing Period Cross-Check",
                        status=CheckStatus.FAIL_MISMATCH,
                        confidence=extracted.billing_end_date.confidence or extracted.billing_start_date.confidence,
                        claimed_value=f"{claimed_start} to {claimed_end}",
                        extracted_value=f"{inv_start} to {inv_end}",
                        reason=reason_msg,
                        is_blocking=True,
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
                        reason=f"Claimed billing period ({claimed_start} to {claimed_end}) aligns with invoice billing cycle ({inv_start} to {inv_end}).",
                        is_blocking=False,
                    )
            except Exception as e:
                self._add_check(
                    checks,
                    check_id="BILLING_PERIOD_MATCH",
                    check_name="Billing Period Cross-Check",
                    status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                    confidence=0.5,
                    claimed_value=f"{claimed_start} to {claimed_end}",
                    extracted_value=f"{inv_start} to {inv_end}",
                    reason=f"Date parsing error during cross-check: {e}",
                    is_blocking=True,
                )
        elif inv_start:
            # Single-date transaction (e.g. prepaid recharge, payment receipt)
            try:
                i_start_dt = datetime.strptime(str(inv_start), "%Y-%m-%d")
                start_diff = abs((c_start_dt - i_start_dt).days)

                if start_diff > tolerance:
                    self._add_check(
                        checks,
                        check_id="BILLING_PERIOD_MATCH",
                        check_name="Billing Period Cross-Check",
                        status=CheckStatus.FAIL_MISMATCH,
                        confidence=extracted.billing_start_date.confidence or extracted.bill_date.confidence,
                        claimed_value=f"{claimed_start} to {claimed_end}",
                        extracted_value=f"Recharge Date: {inv_start}",
                        reason=f"Date Mismatch: Claimed start date ({claimed_start}) does not match recharge/invoice date ({inv_start}). Diff: {start_diff} days (tolerance: {tolerance} days).",
                        is_blocking=True,
                    )
                elif inv_validity is not None and isinstance(inv_validity, int):
                    val_diff = abs(claimed_validity - inv_validity)
                    if val_diff > tolerance:
                        self._add_check(
                            checks,
                            check_id="BILLING_PERIOD_MATCH",
                            check_name="Billing Period Cross-Check",
                            status=CheckStatus.FAIL_MISMATCH,
                            confidence=extracted.validity_days.confidence,
                            claimed_value=f"{claimed_validity} days ({claimed_start} to {claimed_end})",
                            extracted_value=f"{inv_validity} days plan validity",
                            reason=f"Validity Period Mismatch: User claimed {claimed_validity} days validity, but invoice plan specifies {inv_validity} days validity (Diff: {val_diff} days).",
                            is_blocking=True,
                        )
                    else:
                        self._add_check(
                            checks,
                            check_id="BILLING_PERIOD_MATCH",
                            check_name="Billing Period Cross-Check",
                            status=CheckStatus.PASS,
                            confidence=extracted.billing_start_date.confidence or extracted.bill_date.confidence,
                            claimed_value=f"{claimed_start} to {claimed_end}",
                            extracted_value=f"Recharge Date: {inv_start} ({inv_validity} Days)",
                            reason=f"Recharge date ({inv_start}) matches claimed start date with {inv_validity} days plan validity.",
                            is_blocking=False,
                        )
                elif claimed_validity > 365:
                    self._add_check(
                        checks,
                        check_id="BILLING_PERIOD_MATCH",
                        check_name="Billing Period Cross-Check",
                        status=CheckStatus.FAIL_POLICY_VIOLATION,
                        confidence=1.0,
                        claimed_value=f"{claimed_validity} days",
                        extracted_value="Max 365 days allowed",
                        reason=f"Validity Period Exceeded: Claimed validity of {claimed_validity} days exceeds maximum allowable period (365 days).",
                        is_blocking=True,
                    )
                else:
                    self._add_check(
                        checks,
                        check_id="BILLING_PERIOD_MATCH",
                        check_name="Billing Period Cross-Check",
                        status=CheckStatus.PASS,
                        confidence=extracted.billing_start_date.confidence or extracted.bill_date.confidence,
                        claimed_value=f"{claimed_start} to {claimed_end}",
                        extracted_value=f"Recharge Date: {inv_start}",
                        reason=f"Recharge date ({inv_start}) matches claimed period start ({claimed_start}) with {claimed_validity} days validity.",
                        is_blocking=False,
                    )
            except Exception as e:
                self._add_check(
                    checks,
                    check_id="BILLING_PERIOD_MATCH",
                    check_name="Billing Period Cross-Check",
                    status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                    confidence=0.5,
                    claimed_value=f"{claimed_start} to {claimed_end}",
                    extracted_value=f"Recharge Date: {inv_start}",
                    reason=f"Date parsing error: {e}",
                    is_blocking=True,
                )
        else:
            self._add_check(
                checks,
                check_id="BILLING_PERIOD_MATCH",
                check_name="Billing Period Cross-Check",
                status=CheckStatus.FLAGGED_LOW_CONFIDENCE,
                confidence=0.0,
                claimed_value=f"{claimed_start} to {claimed_end}",
                extracted_value="Missing document dates",
                reason="No valid billing or transaction dates could be extracted from the invoice.",
                is_blocking=True,
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
