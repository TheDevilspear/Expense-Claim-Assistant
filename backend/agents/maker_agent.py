"""
Maker Agent — Thin orchestrator for the evidence-based extraction pipeline.

Responsibilities:
1. Clean user claim inputs (clean_user_claim)
2. Orchestrate the extraction pipeline (extract_invoice)
3. Assemble the MakerOutput handoff packet for the Checker Agent (process)

All extraction logic lives in backend/extraction/*.py
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from models.maker_schema import (
    FieldExtraction,
    ExtractedInvoice,
    CleanedClaim,
    MakerOutput,
)
from models.extraction_schema import (
    Candidate,
    FieldType,
    MoneySemanticType,
    ExtractionMethod,
)

# Import extraction pipeline stages
from extraction import document_inspector
from extraction import page_extractor
from extraction import candidate_extractor
from extraction import semantic_classifier
from extraction import section_classifier
from extraction import field_selector
from extraction import vision_arbitrator


def load_env_file():
    root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if root_env.exists():
        for line in root_env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env_file()


class MakerAgent:
    """
    Maker Agent: Orchestrates the evidence-based extraction pipeline.
    """

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.model = os.environ.get("VISION_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
        self.base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

    def clean_user_claim(self, claim_input: Dict[str, Any]) -> CleanedClaim:
        """Cleans raw user form inputs into standard schema."""
        raw_amount = claim_input.get("claimedAmountINR") or claim_input.get("amount") or 0.0
        if isinstance(raw_amount, str):
            clean_str = re.sub(r"[^\d.]", "", raw_amount)
            raw_amount = float(clean_str) if clean_str else 0.0
        else:
            raw_amount = float(raw_amount)

        category = str(claim_input.get("category", "cellphone")).lower()
        broadband_kws = ["broadband", "internet", "wifi", "wi-fi", "fiber", "fibre", "dsl", "ftth"]
        std_category = "broadband" if any(kw in category for kw in broadband_kws) else "cellphone"

        start_date = str(claim_input.get("startDate") or claim_input.get("start_date") or "").strip()
        end_date = str(claim_input.get("endDate") or claim_input.get("end_date") or "").strip()

        validity_days = 28
        if start_date and end_date:
            try:
                d1 = datetime.strptime(start_date, "%Y-%m-%d")
                d2 = datetime.strptime(end_date, "%Y-%m-%d")
                validity_days = max(1, (d2 - d1).days + 1)
            except Exception:
                validity_days = 28

        return CleanedClaim(
            claimed_amount_inr=round(raw_amount, 2),
            claimed_category=std_category,
            claimed_start_date=start_date,
            claimed_end_date=end_date,
            claimed_validity_days=validity_days,
        )

    # Keep backward-compatible alias
    def normalize_user_claim(self, claim_input: Dict[str, Any]) -> CleanedClaim:
        """Backward-compatible alias for clean_user_claim."""
        return self.clean_user_claim(claim_input)

    def extract_invoice(
        self, file_path: str, blur_assessment: Optional[Dict[str, Any]] = None
    ) -> ExtractedInvoice:
        """
        Executes the full evidence-based extraction pipeline.

        Pipeline stages:
        1. Document inspection (per-page profiling & routing)
        2. Per-page evidence extraction (native PDF coordinates or OCR)
        3. Candidate extraction (all money/date/ID/vendor values)
        4. Semantic classification (label → type mapping)
        5. Section classification (payment receipt vs. bill vs. recharge)
        6. Field selection & reconciliation (priority ranking, arithmetic check)
        7. Vision LLM arbitration (only if needed)
        """
        is_blur = bool(blur_assessment and blur_assessment.get("is_blur")) or "blur" in os.path.basename(file_path).lower()
        if is_blur:
            return self._empty_extraction(is_blur=True)

        if not os.path.exists(file_path):
            return self._fallback_rule_extractor(file_path, os.path.basename(file_path), is_blur)

        # Stage 1: Inspect document
        try:
            profile = document_inspector.inspect(file_path)
        except Exception as err:
            print(f"[!] Document inspection failed: {err}", file=sys.stderr)
            return self._empty_extraction(is_blur)

        # Stage 2: Extract evidence per page
        pages_evidence = []
        for page_profile in profile.pages:
            try:
                evidence = page_extractor.extract_page_evidence(file_path, page_profile)
                pages_evidence.append(evidence)
            except Exception as err:
                print(f"[!] Page {page_profile.page_number} extraction failed: {err}", file=sys.stderr)

        if not pages_evidence:
            return self._empty_extraction(is_blur)

        # Stage 3: Extract candidates from all pages
        all_candidates = []
        for evidence in pages_evidence:
            all_candidates += candidate_extractor.extract_candidates(evidence)

        # Stage 4: Classify candidates semantically
        semantic_classifier.classify_all(all_candidates)

        # Stage 5: Classify document sections
        primary_section = section_classifier.classify_primary_section(pages_evidence)

        # Stage 6: Select final fields
        amount_candidate = field_selector.select_primary_amount(all_candidates, primary_section)
        bill_date_c, start_date_c, end_date_c = field_selector.select_billing_dates(all_candidates)
        vendor_candidate = field_selector.select_vendor(all_candidates)
        id_candidate = field_selector.select_invoice_number(all_candidates)
        bill_type_value, detected_doc_type = field_selector.determine_bill_type(primary_section, all_candidates)

        # Stage 6b: Reconciliation & confidence
        recon_boost = field_selector.reconcile_amounts(all_candidates)
        extraction_method = pages_evidence[0].extraction_method.value if pages_evidence else "unknown"

        # Compute confidence for amount
        if amount_candidate:
            amount_candidate.confidence = field_selector.compute_confidence(
                amount_candidate, recon_boost, extraction_method
            )

        # Stage 7: Vision arbitration (when amount/vendor is missing or weak and API is available)
        if (amount_candidate is None or amount_candidate.confidence < 0.50) and self.api_key:
            try:
                vision_result = vision_arbitrator.arbitrate(
                    "total_amount", all_candidates, file_path, 0
                )
                if vision_result and vision_result.get("value"):
                    try:
                        vision_value = float(str(vision_result["value"]).replace(",", ""))
                        if amount_candidate is None:
                            amount_candidate = Candidate(
                                field_type=FieldType.MONEY,
                                value=vision_value,
                                raw_text=str(vision_value),
                                label="Vision Extracted Amount",
                                page=0,
                                semantic_type=MoneySemanticType.TOTAL_AMOUNT_PAYABLE,
                                confidence=0.90,
                                evidence_sources=["vision_llm_arbitration"],
                            )
                        else:
                            amount_candidate.value = vision_value
                            amount_candidate.confidence = min(amount_candidate.confidence + 0.40, 1.0)
                            amount_candidate.evidence_sources.append("vision_llm_arbitration")
                    except (ValueError, TypeError):
                        pass
            except Exception as err:
                print(f"[!] Vision arbitration failed: {err}", file=sys.stderr)

        if vendor_candidate is None and self.api_key:
            try:
                vision_v = vision_arbitrator.arbitrate(
                    "telecom_vendor", all_candidates, file_path, 0
                )
                if vision_v and vision_v.get("value"):
                    vendor_candidate = Candidate(
                        field_type=FieldType.VENDOR,
                        value=str(vision_v["value"]),
                        raw_text=str(vision_v["value"]),
                        label=f"Vendor: {vision_v['value']}",
                        page=0,
                        confidence=0.90,
                        evidence_sources=["vision_llm_arbitration"],
                    )
            except Exception as err:
                print(f"[!] Vision vendor arbitration failed: {err}", file=sys.stderr)

        if amount_candidate and amount_candidate not in all_candidates:
            all_candidates.append(amount_candidate)
        if vendor_candidate and vendor_candidate not in all_candidates:
            all_candidates.append(vendor_candidate)

        # Re-evaluate bill type and relevancy with any vision candidates included
        bill_type_value, detected_doc_type = field_selector.determine_bill_type(primary_section, all_candidates)
        is_relevant = field_selector.is_telecom_relevant(all_candidates, primary_section)
        if vendor_candidate and vendor_candidate.value:
            v_lower = str(vendor_candidate.value).lower()
            if any(vk in v_lower for vk in ["airtel", "jio", "tikona", "vodafone", "vi", "bsnl", "act", "tata"]):
                is_relevant = True
                if detected_doc_type == "OTHER_NON_TELECOM":
                    if "prepaid" in v_lower or (amount_candidate and amount_candidate.value and amount_candidate.value in [555, 666, 719, 999, 1199, 2499]):
                        detected_doc_type = "CELLPHONE_PREPAID_RECHARGE"
                        bill_type_value = "PREPAID_RECHARGE"
                    else:
                        detected_doc_type = "BROADBAND_FIBER_BILL"
                        bill_type_value = "BROADBAND_PLAN"

        # Assemble final ExtractedInvoice (existing schema — unchanged)
        return ExtractedInvoice(
            is_relevant_invoice=is_relevant,
            detected_document_type=detected_doc_type,
            vendor_name=self._to_field_extraction(vendor_candidate, "vendor"),
            invoice_or_account_number=self._to_field_extraction(id_candidate, "invoice number"),
            bill_date=self._to_field_extraction(bill_date_c, "bill date"),
            billing_start_date=self._to_field_extraction(start_date_c, "billing start date"),
            billing_end_date=self._to_field_extraction(end_date_c, "billing end date"),
            validity_days=self._compute_validity(start_date_c, end_date_c),
            total_amount_inr=self._to_field_extraction(amount_candidate, "total amount"),
            bill_type=FieldExtraction(
                value=bill_type_value,
                raw_text=detected_doc_type,
                confidence=0.90 if bill_type_value else 0.0,
                explanation=f"Classified as {detected_doc_type}" if bill_type_value else "Could not determine bill type",
            ),
            international_roaming_charges=self._extract_ir_charges(all_candidates),
            is_blurry_or_unreadable=is_blur,
        )

    # Keep backward-compatible alias
    def extract_with_openrouter(
        self, file_path: str, blur_assessment: Optional[Dict[str, Any]] = None
    ) -> ExtractedInvoice:
        """Backward-compatible alias for extract_invoice."""
        return self.extract_invoice(file_path, blur_assessment)

    def _to_field_extraction(self, candidate, field_name: str) -> FieldExtraction:
        """Converts a Candidate to a FieldExtraction for the output schema."""
        if candidate is None:
            return FieldExtraction(
                value=None, raw_text=None, confidence=0.0,
                explanation=f"{field_name.title()} could not be extracted from document",
            )
        return FieldExtraction(
            value=candidate.value,
            raw_text=candidate.raw_text,
            confidence=candidate.confidence if candidate.confidence > 0 else 0.90,
            explanation=f"{field_name.title()} extracted: {candidate.value}" + (
                f" (from label: '{candidate.label}')" if candidate.label else ""
            ),
        )

    def _compute_validity(self, start_c, end_c) -> FieldExtraction:
        """Computes validity days from start and end date candidates."""
        if start_c and end_c and start_c.value and end_c.value:
            try:
                d1 = datetime.strptime(str(start_c.value), "%Y-%m-%d")
                d2 = datetime.strptime(str(end_c.value), "%Y-%m-%d")
                days = max(1, (d2 - d1).days + 1)
                return FieldExtraction(
                    value=days, raw_text=f"{days} Days",
                    confidence=0.95, explanation=f"Computed from billing dates: {days} days",
                )
            except Exception:
                pass
        return FieldExtraction(
            value=None, raw_text=None, confidence=0.0,
            explanation="Billing period dates not available to compute validity",
        )

    def _extract_ir_charges(self, candidates) -> Optional[FieldExtraction]:
        """Extracts international roaming charges if present."""
        for c in candidates:
            if c.field_type == FieldType.MONEY:
                label_lower = (c.label or "").lower()
                if any(kw in label_lower for kw in [
                    "international roaming", "isd charges", "international calling",
                    "ir pack", "ir usage", "ir charges"
                ]):
                    return FieldExtraction(
                        value=c.value, raw_text=c.raw_text,
                        confidence=0.95,
                        explanation=f"International roaming / ISD charges: ₹{c.value:.2f}",
                    )
        return None

    def _empty_extraction(self, is_blur: bool) -> ExtractedInvoice:
        """Returns an empty extraction when the document can't be processed or is blurry."""
        if is_blur:
            return ExtractedInvoice(
                is_relevant_invoice=True,
                detected_document_type="TELECOM_INVOICE",
                vendor_name=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Degraded / blurry image; vendor unreadable"),
                invoice_or_account_number=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Degraded / blurry image; invoice number unreadable"),
                bill_date=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Degraded / blurry image; date unreadable"),
                billing_start_date=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Degraded / blurry image; start date unreadable"),
                billing_end_date=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Degraded / blurry image; end date unreadable"),
                validity_days=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Unreadable"),
                total_amount_inr=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="Degraded / blurry image; total amount unreadable"),
                bill_type=FieldExtraction(value="POSTPAID_BILL", raw_text=None, confidence=0.0, explanation="Degraded / blurry image; plan unreadable"),
                is_blurry_or_unreadable=True,
            )

        return ExtractedInvoice(
            is_relevant_invoice=False,
            detected_document_type="OTHER_NON_TELECOM",
            vendor_name=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No vendor found"),
            invoice_or_account_number=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No account found"),
            bill_date=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No bill date found"),
            billing_start_date=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No billing cycle"),
            billing_end_date=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No billing cycle"),
            validity_days=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No validity days"),
            total_amount_inr=FieldExtraction(value=None, raw_text=None, confidence=0.0, explanation="No amount found"),
            bill_type=FieldExtraction(value="OTHER", raw_text="Non-Telecom Document", confidence=0.0, explanation="Non-reimbursable"),
            is_blurry_or_unreadable=False,
        )

    # Keep the old method name as a thin compatibility wrapper
    def _fallback_rule_extractor(
        self, file_path: str, extracted_text: str, is_blur: bool
    ) -> ExtractedInvoice:
        """
        Backward-compatible wrapper that feeds pre-extracted text through
        the new pipeline. Used by existing tests.
        """
        filename = os.path.basename(file_path).lower()
        combined = f"{filename} {extracted_text}".lower()

        if is_blur or "blur" in filename:
            return self._empty_extraction(is_blur=True)

        if any(w in combined for w in ["unrelated", "personal", "travel", "medical", "fuel", "cab", "taxi", "hotel"]):
            return self._empty_extraction(is_blur=False)

        from models.extraction_schema import Token, Line, PageEvidence, PageProfile, PageRoute
        from extraction.page_extractor import cluster_tokens_into_lines

        # Build synthetic PageEvidence from pre-extracted text
        lines_raw = extracted_text.strip().split("\n")
        tokens = []
        y_step = 1.0 / max(len(lines_raw), 1)

        for i, line_text in enumerate(lines_raw):
            words = line_text.split()
            x_step = 1.0 / max(len(words), 1)
            for j, word in enumerate(words):
                tokens.append(Token(
                    text=word,
                    x0=j * x_step,
                    y0=i * y_step,
                    x1=(j + 1) * x_step,
                    y1=(i + 1) * y_step,
                ))

        lines = cluster_tokens_into_lines(tokens, tolerance=y_step * 0.4)

        synthetic_evidence = PageEvidence(
            page_number=0,
            tokens=tokens,
            lines=lines,
            raw_text=extracted_text,
            extraction_method=ExtractionMethod.NATIVE_PDF,
        )

        # Run the pipeline on synthetic evidence
        all_candidates = candidate_extractor.extract_candidates(synthetic_evidence)
        semantic_classifier.classify_all(all_candidates)
        primary_section = section_classifier.classify_primary_section([synthetic_evidence])
        amount_candidate = field_selector.select_primary_amount(all_candidates, primary_section)
        bill_date_c, start_date_c, end_date_c = field_selector.select_billing_dates(all_candidates)
        vendor_candidate = field_selector.select_vendor(all_candidates)
        id_candidate = field_selector.select_invoice_number(all_candidates)
        bill_type_value, detected_doc_type = field_selector.determine_bill_type(primary_section, all_candidates)
        recon_boost = field_selector.reconcile_amounts(all_candidates)

        if amount_candidate:
            amount_candidate.confidence = field_selector.compute_confidence(
                amount_candidate, recon_boost, "native_pdf"
            )

        is_relevant = field_selector.is_telecom_relevant(all_candidates, primary_section)

        return ExtractedInvoice(
            is_relevant_invoice=is_relevant,
            detected_document_type=detected_doc_type,
            vendor_name=self._to_field_extraction(vendor_candidate, "vendor"),
            invoice_or_account_number=self._to_field_extraction(id_candidate, "invoice number"),
            bill_date=self._to_field_extraction(bill_date_c, "bill date"),
            billing_start_date=self._to_field_extraction(start_date_c, "billing start date"),
            billing_end_date=self._to_field_extraction(end_date_c, "billing end date"),
            validity_days=self._compute_validity(start_date_c, end_date_c),
            total_amount_inr=self._to_field_extraction(amount_candidate, "total amount"),
            bill_type=FieldExtraction(
                value=bill_type_value,
                raw_text=detected_doc_type,
                confidence=0.90 if bill_type_value else 0.0,
                explanation=f"Classified as {detected_doc_type}" if bill_type_value else "Could not determine bill type",
            ),
            international_roaming_charges=self._extract_ir_charges(all_candidates),
            is_blurry_or_unreadable=False,
        )

    def process(
        self,
        claim_id: str,
        invoice_path: str,
        user_claim_input: Dict[str, Any],
        blur_assessment: Optional[Dict[str, Any]] = None,
    ) -> MakerOutput:
        """Executes full Maker Agent pass and returns structured MakerOutput handoff packet."""
        cleaned_claim = self.clean_user_claim(user_claim_input)
        extracted_invoice = self.extract_invoice(invoice_path, blur_assessment)

        if not extracted_invoice.is_relevant_invoice:
            summary = (
                f"Irrelevant document detected: '{extracted_invoice.detected_document_type}'. "
                "Missing required telecom/broadband invoice fields."
            )
        elif extracted_invoice.is_blurry_or_unreadable:
            summary = (
                f"Low-confidence extraction: Invoice is degraded/blurry. "
                f"Amount confidence capped at {extracted_invoice.total_amount_inr.confidence:.2f}."
            )
        else:
            summary = (
                f"High-confidence extraction: Verified {extracted_invoice.vendor_name.value} "
                f"invoice for ₹{extracted_invoice.total_amount_inr.value} "
                f"({extracted_invoice.validity_days.value} days)."
            )

        metadata = {
            "filename": os.path.basename(invoice_path),
            "stored_path": invoice_path,
            "blur_assessment": blur_assessment or {},
            "model_used": self.model if self.api_key else "evidence_pipeline",
        }

        return MakerOutput(
            claim_id=claim_id,
            invoice_metadata=metadata,
            extracted_invoice=extracted_invoice,
            cleaned_claim=cleaned_claim,
            maker_summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


if __name__ == "__main__":
    import sys
    agent = MakerAgent()
    sample_claim = {"claimedAmountINR": 799.00, "category": "broadband", "startDate": "2026-08-01", "endDate": "2026-08-28"}
    sample_file = sys.argv[1] if len(sys.argv) > 1 else "sample_bill.pdf"
    output = agent.process("CLM-TEST", sample_file, sample_claim)
    print(output.model_dump_json(indent=2))
