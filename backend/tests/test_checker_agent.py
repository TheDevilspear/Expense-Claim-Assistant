"""
Unit Tests for Checker Agent.
Verifies all core business scenarios:
1. Scenario 1: Clean matching claim (All checks PASS).
2. Scenario 2: Amount mismatch (FAIL_MISMATCH with clear difference reason).
3. Scenario 3: Low-confidence / Blurry extraction (FLAGGED_LOW_CONFIDENCE, no guessing).
4. Scenario 4: Duplicate invoice reuse (FAIL_DUPLICATE_INVOICE fraud detection).
5. Scenario 5: Service Category Mismatch (FAIL_MISMATCH).
"""

import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from models.checker_schema import CheckStatus
from services.duplicate_service import DuplicateDetectionService


class TestCheckerAgent(unittest.TestCase):
    def setUp(self):
        self.dup_service = DuplicateDetectionService()
        self.dup_service.clear_index()
        self.maker = MakerAgent()
        self.checker = CheckerAgent(duplicate_service=self.dup_service)

    def test_scenario_1_clean_matching_claim(self):
        """Scenario 1: Clean ₹799 broadband claim matching invoice."""
        claim_input = {
            "claimedAmountINR": 799.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-1", "airtel_broadband_799.pdf", claim_input)
        maker_out.extracted_invoice.vendor_name.value = "Airtel"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 799.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        report = self.checker.process(maker_out)

        self.assertTrue(report.all_checks_passed)
        self.assertFalse(report.has_mismatch)
        self.assertFalse(report.has_low_confidence)
        self.assertFalse(report.has_duplicate_fraud)

        amt_check = next(c for c in report.checks if c.check_id == "AMOUNT_MATCH")
        self.assertEqual(amt_check.status, CheckStatus.PASS)

    def test_scenario_2_amount_mismatch(self):
        """Scenario 2: User claims ₹1,200.00 but invoice shows ₹950.00."""
        claim_input = {
            "claimedAmountINR": 1200.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-2", "jio_bill_950.pdf", claim_input)
        maker_out.extracted_invoice.vendor_name.value = "Jio"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 950.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        report = self.checker.process(maker_out)

        self.assertFalse(report.all_checks_passed)
        self.assertTrue(report.has_mismatch)

        amt_check = next(c for c in report.checks if c.check_id == "AMOUNT_MATCH")
        self.assertEqual(amt_check.status, CheckStatus.FAIL_MISMATCH)
        self.assertIn("Claim is higher than amount", amt_check.reason)

    def test_scenario_3_low_confidence_blurry_invoice(self):
        """Scenario 3: Blurry invoice must be flagged as FLAGGED_LOW_CONFIDENCE, never silently passed."""
        claim_input = {
            "claimedAmountINR": 499.00,
            "category": "cellphone",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process(
            "CLM-SCENARIO-3",
            "blurry_receipt.jpg",
            claim_input,
            blur_assessment={"is_blur": True, "ensemble_score": 0.25},
        )
        report = self.checker.process(maker_out)

        self.assertFalse(report.all_checks_passed)
        self.assertTrue(report.has_low_confidence)

        conf_check = next(c for c in report.checks if c.check_id == "CONFIDENCE_GATE")
        self.assertEqual(conf_check.status, CheckStatus.FLAGGED_LOW_CONFIDENCE)

    def test_scenario_4_duplicate_invoice_fraud(self):
        """Scenario 4: Reusing an already-claimed invoice ID must trigger FAIL_DUPLICATE_INVOICE."""
        self.dup_service.register_claim(
            claim_id="CLM-PAST-001",
            vendor_name="Airtel",
            invoice_number="INV-999888",
            amount_inr=799.00,
            billing_start_date="2026-08-01",
            timestamp="2026-08-15T10:00:00Z",
        )

        claim_input = {
            "claimedAmountINR": 799.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-4", "airtel_bill_799.pdf", claim_input)
        maker_out.extracted_invoice.vendor_name.value = "Airtel"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.invoice_or_account_number.value = "INV-999888"
        maker_out.extracted_invoice.invoice_or_account_number.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 799.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        report = self.checker.process(maker_out)

        self.assertFalse(report.all_checks_passed)
        self.assertTrue(report.has_duplicate_fraud)

        dup_check = next(c for c in report.checks if c.check_id == "DUPLICATE_FRAUD_CHECK")
        self.assertEqual(dup_check.status, CheckStatus.FAIL_DUPLICATE_INVOICE)
        self.assertIn("already claimed in previous Claim #CLM-PAST-001", dup_check.reason)

    def test_scenario_5_category_mismatch(self):
        """Scenario 5: User claims Cellphone on Broadband invoice triggers category FAIL_MISMATCH."""
        claim_input = {
            "claimedAmountINR": 1178.82,
            "category": "cellphone",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-5", "airtel_broadband.pdf", claim_input)
        maker_out.extracted_invoice.vendor_name.value = "Airtel"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 1178.82
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        report = self.checker.process(maker_out)

        self.assertFalse(report.all_checks_passed)
        self.assertTrue(report.has_mismatch)

        cat_check = next(c for c in report.checks if c.check_id == "POLICY_PLAN_TYPE")
        self.assertEqual(cat_check.status, CheckStatus.FAIL_MISMATCH)
        self.assertIn("Category Mismatch", cat_check.reason)


if __name__ == "__main__":
    unittest.main()
