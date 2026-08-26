"""
Comprehensive Unit Tests for the Evidence-Based Document Extraction Pipeline.

Tests each pipeline stage independently:
1. Document Inspector (page profiling & routing)
2. Page Extractor & Line Clustering (cluster_tokens_into_lines)
3. Candidate Extractor (money, dates, identifiers, vendors)
4. Semantic Classifier (label -> semantic type mapping)
5. Section Classifier (document section categorization)
6. Field Selector & Reconciliation (priority ranking, arithmetic math, confidence)
"""

import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from models.extraction_schema import (
    Token,
    Line,
    PageProfile,
    PageEvidence,
    Candidate,
    PageRoute,
    FieldType,
    MoneySemanticType,
    DateSemanticType,
    SectionType,
    ExtractionMethod,
)
from extraction import document_inspector
from extraction import page_extractor
from extraction import candidate_extractor
from extraction import semantic_classifier
from extraction import section_classifier
from extraction import field_selector


class TestExtractionPipeline(unittest.TestCase):

    # -------------------------------------------------------------------------
    # 1. Line Clustering Tests
    # -------------------------------------------------------------------------
    def test_cluster_tokens_into_lines(self):
        """Tokens on same horizontal band should be grouped and ordered L -> R."""
        tokens = [
            Token(text="Charges:", x0=0.1, y0=0.20, x1=0.2, y1=0.22),
            Token(text="Total", x0=0.05, y0=0.10, x1=0.1, y1=0.12),
            Token(text="Amount:", x0=0.12, y0=0.10, x1=0.2, y1=0.12),
            Token(text="1,178.82", x0=0.30, y0=0.10, x1=0.45, y1=0.12),
            Token(text="999.00", x0=0.30, y0=0.20, x1=0.40, y1=0.22),
        ]

        lines = page_extractor.cluster_tokens_into_lines(tokens, tolerance=0.01)
        self.assertEqual(len(lines), 2)
        # Line 1 should be Total Amount: 1,178.82
        self.assertEqual(lines[0].full_text, "Total Amount: 1,178.82")
        # Line 2 should be Charges: 999.00
        self.assertEqual(lines[1].full_text, "Charges: 999.00")

    # -------------------------------------------------------------------------
    # 2. Candidate Extraction Tests
    # -------------------------------------------------------------------------
    def test_candidate_extraction_money_and_dates(self):
        """Extracts valid monetary values and dates while ignoring years in dates."""
        raw_text = """
        Bharti Airtel Limited - Tax Invoice
        Statement Period: 08 Jan 2022 to 07 Feb 2022
        Your Plan: Airtel-UL-Xstream Value 999
        Charges for this Month: 1178.82
        Total Amount Payable: 1178.82
        Taxes (GST): 179.82
        Monthly Plan Charges: 999.00
        Due Date: 20 Feb 2022
        """
        lines_raw = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]
        lines = []
        tokens = []
        for i, lt in enumerate(lines_raw):
            words = lt.split()
            line_tokens = [Token(text=w, x0=j*0.1, y0=i*0.1, x1=(j+1)*0.1, y1=(i+1)*0.1) for j, w in enumerate(words)]
            tokens.extend(line_tokens)
            lines.append(Line(tokens=line_tokens, full_text=lt, y_center=(i + 0.5)*0.1))

        evidence = PageEvidence(
            page_number=0,
            tokens=tokens,
            lines=lines,
            raw_text=raw_text,
            extraction_method=ExtractionMethod.NATIVE_PDF,
        )

        candidates = candidate_extractor.extract_candidates(evidence)
        semantic_classifier.classify_all(candidates)

        money_candidates = [c for c in candidates if c.field_type == FieldType.MONEY]
        money_values = [c.value for c in money_candidates]

        # 1178.82, 179.82, 999.00 should be captured
        self.assertIn(1178.82, money_values)
        self.assertIn(179.82, money_values)
        self.assertIn(999.0, money_values)
        # Year 2022 should NOT be extracted as a money candidate
        self.assertNotIn(2022.0, money_values)

        # Dates: 2022-01-08, 2022-02-07, 2022-02-20
        date_candidates = [c for c in candidates if c.field_type == FieldType.DATE]
        date_values = [c.value for c in date_candidates]
        self.assertIn("2022-01-08", date_values)
        self.assertIn("2022-02-07", date_values)
        self.assertIn("2022-02-20", date_values)

        # Vendor: Airtel
        vendor_candidates = [c for c in candidates if c.field_type == FieldType.VENDOR]
        self.assertTrue(any(v.value == "Airtel" for v in vendor_candidates))

    # -------------------------------------------------------------------------
    # 3. Semantic Classification Tests
    # -------------------------------------------------------------------------
    def test_semantic_classification(self):
        """Verifies correct mapping from label text to semantic enums."""
        c1 = Candidate(
            field_type=FieldType.MONEY, value=4718.82, raw_text="4718.82",
            label="Total Amount Payable", page=0
        )
        c2 = Candidate(
            field_type=FieldType.MONEY, value=719.82, raw_text="719.82",
            label="Taxes (GST)", page=0
        )
        c3 = Candidate(
            field_type=FieldType.MONEY, value=3999.00, raw_text="3999.00",
            label="Monthly Plan Charges", page=0
        )
        c4 = Candidate(
            field_type=FieldType.DATE, value="2024-01-05", raw_text="05 Jan 2024",
            label="Statement Period", page=0
        )

        semantic_classifier.classify_all([c1, c2, c3, c4])

        self.assertEqual(c1.semantic_type, MoneySemanticType.TOTAL_AMOUNT_PAYABLE)
        self.assertEqual(c2.semantic_type, MoneySemanticType.TAX)
        self.assertEqual(c3.semantic_type, MoneySemanticType.SERVICE_COMPONENT)
        self.assertEqual(c4.semantic_type, DateSemanticType.BILLING_PERIOD_START)

    # -------------------------------------------------------------------------
    # 4. Field Selector & Reconciliation Tests
    # -------------------------------------------------------------------------
    def test_field_selection_and_reconciliation(self):
        """Verifies arithmetic reconciliation math and priority-based amount selection."""
        candidates = [
            Candidate(field_type=FieldType.MONEY, value=3999.00, raw_text="3999.00", label="Plan Charges", page=0, semantic_type=MoneySemanticType.SERVICE_COMPONENT, evidence_sources=["line_match"]),
            Candidate(field_type=FieldType.MONEY, value=719.82, raw_text="719.82", label="Taxes (GST)", page=0, semantic_type=MoneySemanticType.TAX, evidence_sources=["line_match"]),
            Candidate(field_type=FieldType.MONEY, value=4718.82, raw_text="4718.82", label="Total Amount Payable", page=0, semantic_type=MoneySemanticType.TOTAL_AMOUNT_PAYABLE, evidence_sources=["line_match"]),
            Candidate(field_type=FieldType.DATE, value="2024-01-05", raw_text="05 Jan 2024", label="Statement Period", page=0, semantic_type=DateSemanticType.BILLING_PERIOD_START),
            Candidate(field_type=FieldType.DATE, value="2024-02-04", raw_text="04 Feb 2024", label="to", page=0, semantic_type=DateSemanticType.BILLING_PERIOD_END),
            Candidate(field_type=FieldType.VENDOR, value="Airtel", raw_text="Bharti Airtel", label="Vendor: Airtel", page=0, confidence=0.95),
            Candidate(field_type=FieldType.IDENTIFIER, value="HT2402P00981234", raw_text="Bill NO: HT2402P00981234", label="INVOICE_NUMBER", page=0, semantic_type="INVOICE_NUMBER"),
        ]

        # 1. Primary amount selection
        selected_amount = field_selector.select_primary_amount(candidates, SectionType.BROADBAND_BILL)
        self.assertIsNotNone(selected_amount)
        self.assertEqual(selected_amount.value, 4718.82)

        # 2. Arithmetic reconciliation: 3999.00 + 719.82 == 4718.82 -> +0.15 boost
        recon_boost = field_selector.reconcile_amounts(candidates)
        self.assertEqual(recon_boost, 0.15)

        # 3. Confidence computation
        confidence = field_selector.compute_confidence(selected_amount, recon_boost, "native_pdf")
        self.assertGreaterEqual(confidence, 0.95)

        # 4. Dates selection
        bill_d, start_d, end_d = field_selector.select_billing_dates(candidates)
        self.assertEqual(start_d.value, "2024-01-05")
        self.assertEqual(end_d.value, "2024-02-04")

        # 5. Vendor & Invoice number selection
        vendor = field_selector.select_vendor(candidates)
        self.assertEqual(vendor.value, "Airtel")
        inv_no = field_selector.select_invoice_number(candidates)
        self.assertEqual(inv_no.value, "HT2402P00981234")

    # -------------------------------------------------------------------------
    # 5. Image OCR Evidence Normalization & Line Clustering
    # -------------------------------------------------------------------------
    def test_image_ocr_token_normalization_and_clustering(self):
        """Simulates EasyOCR/pytesseract output tokens and verifies full pipeline execution."""
        # Simulated raw EasyOCR bounding boxes [(bbox, text, prob)]
        raw_ocr_boxes = [
            ([[50, 40], [250, 40], [250, 60], [50, 60]], "Bharti Airtel Limited", 0.98),
            ([[50, 100], [300, 100], [300, 120], [50, 120]], "Total Amount Payable: 1,579.82", 0.95),
            ([[50, 160], [350, 160], [350, 180], [50, 180]], "Statement Period: 26 Oct 2023 - 25 Nov 2023", 0.92),
            ([[50, 220], [250, 220], [250, 240], [50, 240]], "Airtel Black 1099 Plan", 0.90),
        ]
        img_w, img_h = 1000, 1500
        tokens = []
        for bbox, text, prob in raw_ocr_boxes:
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            x0, x1 = min(xs) / img_w, max(xs) / img_w
            y0, y1 = min(ys) / img_h, max(ys) / img_h
            words = text.split()
            w_step = (x1 - x0) / len(words)
            for idx, word in enumerate(words):
                tokens.append(Token(
                    text=word, x0=x0 + idx * w_step, y0=y0, x1=x0 + (idx + 1) * w_step, y1=y1
                ))

        lines = page_extractor.cluster_tokens_into_lines(tokens, tolerance=0.01)
        evidence = PageEvidence(
            page_number=0, tokens=tokens, lines=lines,
            raw_text=" ".join(line.full_text for line in lines),
            extraction_method=ExtractionMethod.OCR
        )

        candidates = candidate_extractor.extract_candidates(evidence)
        semantic_classifier.classify_all(candidates)
        primary_section = section_classifier.classify_primary_section([evidence])
        amount = field_selector.select_primary_amount(candidates, primary_section)
        bill_d, start_d, end_d = field_selector.select_billing_dates(candidates)
        vendor = field_selector.select_vendor(candidates)

        self.assertEqual(vendor.value, "Airtel")
        self.assertEqual(amount.value, 1579.82)
        self.assertEqual(start_d.value, "2023-10-26")
        self.assertEqual(end_d.value, "2023-11-25")


if __name__ == "__main__":
    unittest.main(verbosity=2)
