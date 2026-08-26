"""
Unit Tests for Approver Agent and Full Multi-Agent Pipeline.
Verifies all core business scenarios:
1. Scenario 1: Clean matching claim <= ₹5k -> AUTO_APPROVE
2. Scenario 2: Amount higher than invoice -> AUTO_REJECT (AMOUNT_HIGHER_THAN_INVOICE)
3. Scenario 3: Low-confidence / Blurry scan -> ESCALATE_TO_HUMAN (LOW_CONFIDENCE_BLUR)
4. Scenario 4: Duplicate invoice reuse -> AUTO_REJECT (DUPLICATE_FRAUD)
5. Scenario 5: Policy violation (> ₹5k cap) -> AUTO_REJECT (POLICY_CAP_EXCEEDED)
6. Scenario 6: Category mismatch -> ESCALATE_TO_HUMAN (CATEGORY_MISMATCH)
"""

import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent
from models.approver_schema import ApprovalDecisionType
from services.duplicate_service import DuplicateDetectionService


class TestApproverAgentScenarios(unittest.TestCase):
    def setUp(self):
        self.dup_service = DuplicateDetectionService()
        self.dup_service.clear_index()
        self.maker = MakerAgent()
        self.checker = CheckerAgent(duplicate_service=self.dup_service)
        self.approver = ApproverAgent()

    def test_scenario_1_clean_auto_approve(self):
        """Scenario 1: Clean ₹799 broadband claim -> AUTO_APPROVE."""
        claim = {
            "claimedAmountINR": 799.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-1", "airtel_broadband_799.pdf", claim)
        # Mock extracted values
        maker_out.extracted_invoice.vendor_name.value = "Airtel"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 799.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)
        self.assertEqual(decision.approved_amount_inr, 799.00)
        self.assertFalse(decision.requires_human_action)
        self.assertIn("Approved:", decision.actionable_user_reason)

    def test_scenario_2_amount_higher_than_invoice_rejected(self):
        """Scenario 2: User claims ₹1,200 but invoice shows ₹950 -> AUTO_REJECT."""
        claim = {
            "claimedAmountINR": 1200.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-2", "jio_bill_950.pdf", claim)
        maker_out.extracted_invoice.vendor_name.value = "Jio"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 950.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_REJECT)
        self.assertFalse(decision.requires_human_action)
        self.assertIn("AMOUNT_HIGHER_THAN_INVOICE", decision.escalation_tags)
        self.assertIn("exceeds invoice amount", decision.actionable_user_reason)

    def test_scenario_3_low_confidence_blur_escalation(self):
        """Scenario 3: Blurry invoice with low confidence -> ESCALATE_TO_HUMAN."""
        claim = {
            "claimedAmountINR": 499.00,
            "category": "cellphone",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process(
            "CLM-SCENARIO-3",
            "blurry_receipt.jpg",
            claim,
            blur_assessment={"is_blur": True, "ensemble_score": 0.25},
        )
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.ESCALATE_TO_HUMAN)
        self.assertTrue(decision.requires_human_action)
        self.assertIn("LOW_CONFIDENCE_BLUR", decision.escalation_tags)
        self.assertIn("Manual Review (Blurry Image)", decision.actionable_user_reason)

    def test_scenario_4_duplicate_invoice_fraud_rejection(self):
        """Scenario 4: Reused invoice ID -> AUTO_REJECT (DUPLICATE_FRAUD)."""
        self.dup_service.register_claim(
            claim_id="CLM-PAST-001",
            vendor_name="Airtel",
            invoice_number="INV-FRAUD-123",
            amount_inr=799.00,
            billing_start_date="2026-08-01",
            timestamp="2026-08-15T10:00:00Z",
        )

        claim = {
            "claimedAmountINR": 799.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-4", "airtel_bill_799.pdf", claim)
        maker_out.extracted_invoice.vendor_name.value = "Airtel"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.invoice_or_account_number.value = "INV-FRAUD-123"
        maker_out.extracted_invoice.invoice_or_account_number.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 799.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.95
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_REJECT)
        self.assertIn("DUPLICATE_FRAUD", decision.escalation_tags)
        self.assertIn("Rejected (Duplicate)", decision.actionable_user_reason)

    def test_scenario_5_policy_cap_violation_rejection(self):
        """Scenario 5: Claim exceeding ₹5,000 policy cap -> AUTO_REJECT."""
        claim = {
            "claimedAmountINR": 6500.00,
            "category": "broadband",
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-5", "airtel_bill_799.pdf", claim)
        maker_out.extracted_invoice.total_amount_inr.value = 6500.00
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98

        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_REJECT)
        self.assertIn("POLICY_CAP_EXCEEDED", decision.escalation_tags)
        self.assertIn("exceeds company limit of ₹5,000", decision.actionable_user_reason)

    def test_scenario_6_category_mismatch_escalation(self):
        """Scenario 6: User claims Cellphone on Broadband receipt -> ESCALATE_TO_HUMAN."""
        claim = {
            "claimedAmountINR": 1178.82,
            "category": "cellphone",  # User selected Cellphone
            "startDate": "2026-08-01",
            "endDate": "2026-08-28",
        }
        maker_out = self.maker.process("CLM-SCENARIO-6", "airtel_broadband.pdf", claim)
        maker_out.extracted_invoice.vendor_name.value = "Airtel"
        maker_out.extracted_invoice.vendor_name.confidence = 0.95
        maker_out.extracted_invoice.total_amount_inr.value = 1178.82
        maker_out.extracted_invoice.total_amount_inr.confidence = 0.98
        maker_out.extracted_invoice.detected_document_type = "BROADBAND_FIBER_BILL"
        maker_out.extracted_invoice.bill_type.value = "BROADBAND_PLAN"
        maker_out.extracted_invoice.bill_type.confidence = 0.95

        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.ESCALATE_TO_HUMAN)
        self.assertTrue(decision.requires_human_action)
        self.assertIn("CATEGORY_MISMATCH", decision.escalation_tags)
        self.assertIn("Category Mismatch", decision.actionable_user_reason)


if __name__ == "__main__":
    unittest.main()
