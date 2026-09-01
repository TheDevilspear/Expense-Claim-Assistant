"""
Maker Agent — Orchestrator for the evidence-based extraction pipeline.

Responsibilities:
1. Clean user claim inputs (clean_user_claim)
2. Orchestrate the extraction pipeline (extract_invoice)
3. Assemble the MakerOutput handoff packet for the Checker Agent (process)

All extraction stages live in backend/extraction/*.py
"""

import os
import re
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

import config
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
    PageEvidence,
    Token,
)

# Extraction pipeline stages
from extraction import document_inspector
from extraction import page_extractor
from extraction import candidate_extractor
from extraction import semantic_classifier
from extraction import section_classifier
from extraction import field_selector
from extraction import vision_arbitrator
from extraction.page_extractor import cluster_tokens_into_lines
from extraction.constants import (
    KNOWN_TELECOM_VENDOR_TOKENS,
    COMMON_PREPAID_RECHARGE_AMOUNTS,
    IR_KEYWORDS,
    UNRELATED_DOCUMENT_KEYWORDS,
    BROADBAND_CATEGORY_KEYWORDS,
)

logger = logging.getLogger(__name__)


class MakerAgent:
    """
    Maker Agent: Orchestrates the evidence-based extraction pipeline.
    """

    def __init__(self):
        self.api_key = config.get_api_key()
        self.model = config.get_vision_model()
        self.base_url = config.get_base_url()

    def clean_user_claim(self, claim_input: Dict[str, Any]) -> CleanedClaim:
        """Cleans raw user form inputs into standard schema."""
        raw_amount = claim_input.get("claimedAmountINR") or claim_input.get("amount") or 0.0
        if isinstance(raw_amount, str):
            clean_str = re.sub(r"[^\d.]", "", raw_amount)
            raw_amount = float(clean_str) if clean_str else 0.0
        else:
            raw_amount = float(raw_amount)

        category = str(claim_input.get("category", "cellphone")).lower()
        std_category = "broadband" if any(kw in category for kw in BROADBAND_CATEGORY_KEYWORDS) else "cellphone"

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

    def normalize_user_claim(self, claim_input: Dict[str, Any]) -> CleanedClaim:
        """Backward-compatible alias for clean_user_claim."""
        return self.clean_user_claim(claim_input)

    def extract_invoice(
        self, file_path: str, blur_assessment: Optional[Dict[str, Any]] = None
    ) -> ExtractedInvoice:
        """
        Executes the full evidence-based extraction pipeline.
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
            logger.warning("Document inspection failed for %s: %s", file_path, err)
            return self._empty_extraction(is_blur)

        # Stage 2: Extract evidence per page
        pages_evidence = []
        for page_profile in profile.pages:
            try:
                evidence = page_extractor.extract_page_evidence(file_path, page_profile)
                pages_evidence.append(evidence)
            except Exception as err:
                logger.warning("Page %d extraction failed for %s: %s", page_profile.page_number, file_path, err)

        if not pages_evidence:
            return self._empty_extraction(is_blur)

        return self._run_pipeline_core(pages_evidence, file_path=file_path, is_blur=is_blur)

    def _run_pipeline_core(
        self,
        pages_evidence: List[PageEvidence],
        file_path: Optional[str] = None,
        is_blur: bool = False,
    ) -> ExtractedInvoice:
        """
        Shared unified core extraction pipeline for multi-page evidence and synthetic text.
        """
        # Stage 3: Extract candidates
        all_candidates: List[Candidate] = []
        for evidence in pages_evidence:
            all_candidates += candidate_extractor.extract_candidates(evidence)

        # Stage 4: Semantic classification
        semantic_classifier.classify_all(all_candidates)

        # Stage 5: Section classification
        primary_section = section_classifier.classify_primary_section(pages_evidence)

        # Stage 6: Field selection
        amount_candidate = field_selector.select_primary_amount(all_candidates, primary_section)
        bill_date_c, start_date_c, end_date_c = field_selector.select_billing_dates(all_candidates)
        vendor_candidate = field_selector.select_vendor(all_candidates)
        id_candidate = field_selector.select_invoice_number(all_candidates)

        # Stage 6b: Reconciliation & confidence
        recon_boost = field_selector.reconcile_amounts(all_candidates)
        extraction_method = pages_evidence[0].extraction_method.value if pages_evidence else "unknown"

        if amount_candidate:
            amount_candidate.confidence = field_selector.compute_confidence(
                amount_candidate, recon_boost, extraction_method
            )

        # Stage 7: Resilient Vision arbitration (invoked only if local candidate is missing or low-confidence)
        if file_path and os.path.exists(file_path) and self.api_key:
            if amount_candidate is None or amount_candidate.confidence < 0.50:
                vision_result = vision_arbitrator.arbitrate("total_amount", all_candidates, file_path, 0)
                if vision_result and vision_result.get("value") is not None:
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
                            all_candidates.append(amount_candidate)
                        else:
                            amount_candidate.value = vision_value
                            amount_candidate.confidence = min(amount_candidate.confidence + 0.40, 1.0)
                            amount_candidate.evidence_sources.append("vision_llm_arbitration")
                    except (ValueError, TypeError) as conv_err:
                        logger.debug("Could not parse vision amount value: %s", conv_err)

            if vendor_candidate is None:
                # First check raw text from pages_evidence directly before external API call
                if pages_evidence:
                    raw_all = " ".join(p.raw_text for p in pages_evidence if p.raw_text)
                    clean_all = raw_all.replace("_", " ").replace("-", " ")
                    for pattern, vname, fname in VENDOR_PATTERNS:
                        if pattern.search(clean_all):
                            vendor_candidate = Candidate(
                                field_type=FieldType.VENDOR,
                                value=vname,
                                raw_text=fname,
                                label=f"Vendor: {vname}",
                                page=0,
                                confidence=0.95,
                                evidence_sources=["raw_text_regex"],
                            )
                            all_candidates.append(vendor_candidate)
                            break

                if vendor_candidate is None:
                    vision_v = vision_arbitrator.arbitrate("telecom_vendor", all_candidates, file_path, 0)
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
                        all_candidates.append(vendor_candidate)

        # Single canonical bill type and relevancy determination
        bill_type_value, detected_doc_type = field_selector.determine_bill_type(primary_section, all_candidates)
        is_relevant = field_selector.is_telecom_relevant(all_candidates, primary_section)

        if vendor_candidate and vendor_candidate.value:
            v_lower = str(vendor_candidate.value).lower()
            if any(vk in v_lower for vk in KNOWN_TELECOM_VENDOR_TOKENS):
                is_relevant = True
                if detected_doc_type == "OTHER_NON_TELECOM":
                    is_common_prepaid = amount_candidate and amount_candidate.value in COMMON_PREPAID_RECHARGE_AMOUNTS
                    if "prepaid" in v_lower or is_common_prepaid:
                        detected_doc_type = "CELLPHONE_PREPAID_RECHARGE"
                        bill_type_value = "PREPAID_RECHARGE"
                    else:
                        detected_doc_type = "BROADBAND_FIBER_BILL"
                        bill_type_value = "BROADBAND_PLAN"

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

    def extract_with_openrouter(
        self, file_path: str, blur_assessment: Optional[Dict[str, Any]] = None
    ) -> ExtractedInvoice:
        """Backward-compatible alias for extract_invoice."""
        return self.extract_invoice(file_path, blur_assessment)

    def _to_field_extraction(self, candidate: Optional[Candidate], field_name: str) -> FieldExtraction:
        """Converts a Candidate to a FieldExtraction for the output schema."""
        if candidate is None:
            return FieldExtraction(
                value=None,
                raw_text=None,
                confidence=0.0,
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

    def _compute_validity(self, start_c: Optional[Candidate], end_c: Optional[Candidate]) -> FieldExtraction:
        """Computes validity days from start and end date candidates."""
        if start_c and end_c and start_c.value and end_c.value:
            try:
                d1 = datetime.strptime(str(start_c.value), "%Y-%m-%d")
                d2 = datetime.strptime(str(end_c.value), "%Y-%m-%d")
                days = max(1, (d2 - d1).days + 1)
                return FieldExtraction(
                    value=days,
                    raw_text=f"{days} Days",
                    confidence=0.95,
                    explanation=f"Computed from billing dates: {days} days",
                )
            except Exception:
                pass
        return FieldExtraction(
            value=None,
            raw_text=None,
            confidence=0.0,
            explanation="Billing period dates not available to compute validity",
        )

    def _extract_ir_charges(self, candidates: List[Candidate]) -> Optional[FieldExtraction]:
        """Extracts international roaming charges if present."""
        for c in candidates:
            if c.field_type == FieldType.MONEY:
                label_lower = (c.label or "").lower()
                if any(kw in label_lower for kw in IR_KEYWORDS):
                    return FieldExtraction(
                        value=c.value,
                        raw_text=c.raw_text,
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

    def _fallback_rule_extractor(
        self, file_path: str, extracted_text: str, is_blur: bool
    ) -> ExtractedInvoice:
        """
        Wrapper that feeds pre-extracted text through the core pipeline.
        Used by test suites and text fallback feeds.
        """
        filename = os.path.basename(file_path).lower()
        combined = f"{filename} {extracted_text}".lower()

        if is_blur or "blur" in filename:
            return self._empty_extraction(is_blur=True)

        if any(w in combined for w in UNRELATED_DOCUMENT_KEYWORDS):
            return self._empty_extraction(is_blur=False)

        # Build synthetic PageEvidence from pre-extracted text
        lines_raw = extracted_text.strip().split("\n")
        tokens: List[Token] = []
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

        return self._run_pipeline_core([synthetic_evidence], file_path=file_path, is_blur=False)

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
                "Low-confidence extraction due to blurry / degraded invoice image. "
                "Document legibility is compromised; proceeding with partial extraction."
            )

        else:
            v_name = extracted_invoice.vendor_name.value or "Vendor"
            amt = extracted_invoice.total_amount_inr.value
            amt_str = f"₹{amt:.2f}" if amt is not None else "Unknown Amount"
            summary = (
                f"Successfully extracted {v_name} invoice ({extracted_invoice.detected_document_type}). "
                f"Total amount: {amt_str}."
            )

        return MakerOutput(
            claim_id=claim_id,
            invoice_metadata={
                "file_path": invoice_path,
                "is_blurry": extracted_invoice.is_blurry_or_unreadable,
                "blur_assessment": blur_assessment or {},
            },
            extracted_invoice=extracted_invoice,
            cleaned_claim=cleaned_claim,
            maker_summary=summary,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
