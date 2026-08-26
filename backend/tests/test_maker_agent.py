"""
Unit Tests for Maker Agent.
Verifies:
1. Clean matching telecom invoice extraction (High confidence).
2. Blurry invoice handling (Low confidence capping & is_blurry flag).
3. Non-telecom document handling (is_relevant_invoice = False, confidence = 0.0).
4. User claim normalization into standardized schema.
5. JSON handoff validation for the Checker Agent.
"""

import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from agents.maker_agent import MakerAgent
from models.maker_schema import MakerOutput

AIRTEL_SAMPLE_TEXT = """
Bharti Airtel Limited - Tax Invoice
Shivanshu Gupta
A78 Block A, Rajajipuram, Lucknow, Uttar Pradesh
Account No: 20001093969
Bill NO: HT2209I001458573
Statement Period: 08 Jan 2022 to 07 Feb 2022
Your Plan: Airtel-UL-Xstream Value 999 Unlimited Data @ 200 Mbps
Charges for this Month: 1178.82
Total Amount: 1178.82
FIXEDLINE AND BROADBAND SERVICES
"""


class TestMakerAgent(unittest.TestCase):
    def setUp(self):
        self.agent = MakerAgent()

    def test_clean_telecom_invoice_extraction(self):
        """Test Case 1: Clean Airtel broadband invoice extraction."""
        extracted = self.agent._fallback_rule_extractor("airtel_bill.pdf", AIRTEL_SAMPLE_TEXT, is_blur=False)

        self.assertTrue(extracted.is_relevant_invoice)
        self.assertFalse(extracted.is_blurry_or_unreadable)
        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertGreaterEqual(extracted.vendor_name.confidence, 0.90)
        self.assertEqual(extracted.total_amount_inr.value, 1178.82)
        self.assertGreaterEqual(extracted.total_amount_inr.confidence, 0.90)
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

    def test_blurry_invoice_extraction(self):
        """Test Case 2: Blurry invoice extraction must flag low confidence."""
        user_claim = {
            "claimedAmountINR": 499.00,
            "category": "cellphone",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }

        output = self.agent.process(
            claim_id="CLM-002",
            invoice_path="blurry_receipt.jpg",
            user_claim_input=user_claim,
            blur_assessment={"is_blur": True, "ensemble_score": 0.28},
        )

        self.assertTrue(output.extracted_invoice.is_blurry_or_unreadable)
        self.assertLessEqual(output.extracted_invoice.total_amount_inr.confidence, 0.60)
        self.assertIn("Low-confidence", output.maker_summary)

    def test_random_non_telecom_document(self):
        """Test Case 3: Empty/unreadable text must have 0.0 amount confidence."""
        extracted = self.agent._fallback_rule_extractor("random_file.pdf", "Some random table without telecom keywords", is_blur=False)
        self.assertEqual(extracted.total_amount_inr.confidence, 0.0)
        self.assertIsNone(extracted.total_amount_inr.value)

    def test_claim_normalization_parsing(self):
        """Test Case 4: Normalization of formatted currency strings and categories."""
        raw_input = {
            "claimedAmountINR": "₹ 1,500.50",
            "category": "Home Fiber Wi-Fi",
            "startDate": "2026-01-01",
            "endDate": "2026-03-31",
        }

        normalized = self.agent.normalize_user_claim(raw_input)
        self.assertEqual(normalized.claimed_amount_inr, 1500.50)
        self.assertEqual(normalized.claimed_category, "broadband")
        self.assertEqual(normalized.claimed_validity_days, 90)

    def test_maker_output_json_serialization(self):
        """Test Case 5: MakerOutput JSON contract serialization for Checker handoff."""
        extracted = self.agent._fallback_rule_extractor("airtel_bill.pdf", AIRTEL_SAMPLE_TEXT, is_blur=False)
        normalized = self.agent.normalize_user_claim({
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2022-01-08",
            "endDate": "2022-02-07",
        })

        output = MakerOutput(
            claim_id="CLM-005",
            invoice_metadata={"filename": "airtel_bill.pdf", "stored_path": "airtel_bill.pdf", "blur_assessment": {}},
            extracted_invoice=extracted,
            cleaned_claim=normalized,
            maker_summary="Extraction summary",
            timestamp="2026-08-22T19:00:00Z",
        )
        json_str = output.model_dump_json()

        reparsed = MakerOutput.model_validate_json(json_str)
        self.assertEqual(reparsed.claim_id, "CLM-005")
        self.assertEqual(reparsed.extracted_invoice.total_amount_inr.value, 1178.82)


if __name__ == "__main__":
    unittest.main()
