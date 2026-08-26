"""
Automated Multi-Invoice Scenario Test Suite
Tests 3 Realistic Telecom Document Profiles across 9 diverse business scenarios:
1. Airtel Xstream Value 999 (Shivanshu Gupta - ₹1,178.82 Broadband)
2. Airtel Xstream Infinity 3999 (Pradnya Bagave - ₹4,718.82 Broadband)
3. JioFiber Postpaid 999 (Sanjay Yadav - ₹1,178.82 Broadband)

Scenarios Covered:
- Clean Auto-Approval <= ₹5,000 (Exact & Partial claims)
- Amount Discrepancy Auto-Rejection (Claimed > Invoice)
- Service Category Mismatch Escalation (Cellphone vs Broadband)
- Policy Cap Rejection (> ₹5,000 limit)
- Duplicate Invoice Fraud Rejection (Re-submitting same invoice)
- Low-Confidence / Blurry Image Escalation
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent
from models.maker_schema import MakerOutput
from models.approver_schema import ApprovalDecisionType
from models.checker_schema import CheckStatus
from services.duplicate_service import DuplicateDetectionService

# Sample Extracted Text Corpora representing the 3 Real Document Data Profiles
AIRTEL_999_TEXT = """
MONTHLY STATEMENT airtel
Shivanshu Gupta
A78 Block A, Rajajipuram, Lucknow, Uttar Pradesh, 226017
Email Address: shivanshu900@gmail.com
Phone Number: 9560927208

Your Plan: Airtel-UL-Xstream Value 999
Unlimited GB (200Mbps/1024Kbps) COMBO Plan
Number of Connections: 1
Statement Date: 09 Feb 2022
Statement Period: 08 Jan 2022 to 07 Feb 2022
Due Date: 20 Feb 2022

Charges for this Month: 1178.82
Amount Payable: 1178.82
Broadband - 052210538983_dsl  1  999.0  0.0  999.00
Taxes (GST): 179.82
Total (Incl. Taxes): 1178.82

Account No: 20001093969
Bill NO: HT2209I001458573
FIXEDLINE AND BROADBAND SERVICES
Bharti Airtel Limited - Tax Invoice
"""

AIRTEL_3999_TEXT = """
FIBER MONTHLY STATEMENT airtel
Pradnya Bagave
Building No 8 Flat No G2, Rakshak Nagar Phase 2, Pune, Maharashtra, 411014
Email Address: pradnya.bagave@gmail.com
Phone Number: 9850261807

Total Amount Payable: 4718.82
Due Date: 16 Feb 2024
Your Plan: Airtel-UL-Xstream Infinity 3999 Unlimited GB (300Mbps/307200Kbps) COMBO SOS Plan
Statement Date: 06 Feb 2024
Statement Period: 05 Jan 2024 to 04 Feb 2024

This Month's Charges Summary:
Fiber - 02010805695_dsl  1  3999.0  0.0  3999.00
Taxes (GST): 719.82
Total (Incl. Taxes): 4718.82
Total: Four Thousand Seven Hundred and Eighteen Rupees and Eighty Two Paise Only

Account No: 40291823901
Bill NO: HT2402P00981234
Bharti Airtel Limited
"""

JIO_999_TEXT = """
JioFiber Bill Summary
Mr. Sanjay Yadav
H-40 Flat 7,8 Siddhi Vinayak Colony Maholi Bhopal India
Registered Mobile Number: +918480953599
Account Number: 410803229618
Statement Number: 257002837375

Activation Date: 16-DEC-2024
Billing Cycle Date: 21-JAN-2023 to 20-FEB-2023
Due Date Current Plan: 30-JAN-2025

Postpaid_999_3M: Unlimited Data @ 150 Mbps Unlimited Voice Subscription to 14 Paid OTT apps
Monthly Plan Charges: 999.00
Taxes: 179.82
Total Current Charges (A+B)
1,178.82

Total Payable: NIL
Reliance Jio Infocomm Limited
"""


class TestMultiInvoiceScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maker = MakerAgent()
        cls.checker = CheckerAgent()
        cls.approver = ApproverAgent()

    def setUp(self):
        # Reset duplicate ledger for clean test runs
        dup_service = DuplicateDetectionService()
        dup_service._save_index([])

    def _assemble_maker_output(self, claim_id, extracted, normalized, filename):
        return MakerOutput(
            claim_id=claim_id,
            invoice_metadata={"filename": filename, "stored_path": filename, "blur_assessment": {}},
            extracted_invoice=extracted,
            cleaned_claim=normalized,
            maker_summary=f"Extraction for {claim_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # -------------------------------------------------------------------------
    # 1. CLEAN AUTO-APPROVAL TESTS (<= ₹5,000)
    # -------------------------------------------------------------------------
    def test_scenario_1_airtel_999_clean_auto_approval(self):
        """Scenario 1: Airtel Xstream 999 clean claim (₹1,178.82) -> AUTO_APPROVE"""
        extracted = self.maker._fallback_rule_extractor("airtel_999.pdf", AIRTEL_999_TEXT, is_blur=False)
        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 1178.82)
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2022-01-08",
            "endDate": "2022-02-07"
        })
        maker_out = self._assemble_maker_output("CLM-AIRTEL-999", extracted, normalized, "airtel_999.pdf")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.all_checks_passed)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)
        self.assertEqual(decision.approved_amount_inr, 1178.82)
        self.assertIn("AUTO_APPROVED_CLEAN", decision.escalation_tags)

    def test_scenario_2_airtel_3999_clean_auto_approval(self):
        """Scenario 2: Airtel Infinity 3999 high-tier claim (₹4,718.82 <= ₹5,000) -> AUTO_APPROVE"""
        extracted = self.maker._fallback_rule_extractor("airtel_3999.pdf", AIRTEL_3999_TEXT, is_blur=False)
        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 4718.82)
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 4718.82,
            "category": "broadband",
            "startDate": "2024-01-05",
            "endDate": "2024-02-04"
        })
        maker_out = self._assemble_maker_output("CLM-AIRTEL-3999", extracted, normalized, "airtel_3999.pdf")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.all_checks_passed)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)
        self.assertEqual(decision.approved_amount_inr, 4718.82)
        self.assertIn("AUTO_APPROVED_CLEAN", decision.escalation_tags)

    def test_scenario_3_jio_fiber_partial_claim_auto_approval(self):
        """Scenario 3: JioFiber 999 partial claim (Claimed ₹1,100 <= Invoice ₹1,178.82) -> AUTO_APPROVE"""
        extracted = self.maker._fallback_rule_extractor("jio_999.pdf", JIO_999_TEXT, is_blur=False)
        self.assertEqual(extracted.vendor_name.value, "Jio")
        self.assertEqual(extracted.total_amount_inr.value, 1178.82)
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 1100.00,
            "category": "broadband",
            "startDate": "2023-01-21",
            "endDate": "2023-02-20"
        })
        maker_out = self._assemble_maker_output("CLM-JIO-PARTIAL", extracted, normalized, "jio_999.pdf")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.all_checks_passed)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)
        self.assertEqual(decision.approved_amount_inr, 1178.82)
        self.assertIn("AUTO_APPROVED_CLEAN", decision.escalation_tags)

    # -------------------------------------------------------------------------
    # 2. AMOUNT DISCREPANCY REJECTION TESTS (Claimed > Invoice)
    # -------------------------------------------------------------------------
    def test_scenario_4_airtel_amount_higher_than_invoice_rejected(self):
        """Scenario 4: Claimed ₹1,500 on Airtel ₹1,178.82 -> AUTO_REJECT (AMOUNT_HIGHER_THAN_INVOICE)"""
        extracted = self.maker._fallback_rule_extractor("airtel_999.pdf", AIRTEL_999_TEXT, is_blur=False)
        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 1500.00,
            "category": "broadband",
            "startDate": "2022-01-08",
            "endDate": "2022-02-07"
        })
        maker_out = self._assemble_maker_output("CLM-AIRTEL-OVERCLAIM", extracted, normalized, "airtel_999.pdf")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.has_mismatch)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_REJECT)
        self.assertIsNone(decision.approved_amount_inr)
        self.assertIn("AMOUNT_HIGHER_THAN_INVOICE", decision.escalation_tags)
        self.assertIn("exceeds invoice amount", decision.actionable_user_reason)

    # -------------------------------------------------------------------------
    # 3. SERVICE CATEGORY MISMATCH ESCALATION TESTS
    # -------------------------------------------------------------------------
    def test_scenario_5_jio_cellphone_vs_broadband_mismatch_escalated(self):
        """Scenario 5: Claimed Cellphone on JioFiber Broadband -> ESCALATE_TO_HUMAN (CATEGORY_MISMATCH)"""
        extracted = self.maker._fallback_rule_extractor("jio_999.pdf", JIO_999_TEXT, is_blur=False)
        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 1178.82,
            "category": "cellphone",  # User claimed Cellphone
            "startDate": "2023-01-21",
            "endDate": "2023-02-20"
        })
        maker_out = self._assemble_maker_output("CLM-JIO-CAT-MISMATCH", extracted, normalized, "jio_999.pdf")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.has_mismatch)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.ESCALATE_TO_HUMAN)
        self.assertIn("CATEGORY_MISMATCH", decision.escalation_tags)
        self.assertIn("Category Mismatch", decision.actionable_user_reason)

    # -------------------------------------------------------------------------
    # 4. POLICY CAP VIOLATION REJECTION TESTS (> ₹5,000)
    # -------------------------------------------------------------------------
    def test_scenario_6_policy_cap_exceeded_auto_reject(self):
        """Scenario 6: Claimed ₹6,500 > ₹5,000 Policy Cap -> AUTO_REJECT (POLICY_CAP_EXCEEDED)"""
        extracted = self.maker._fallback_rule_extractor("airtel_3999.pdf", AIRTEL_3999_TEXT, is_blur=False)
        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 6500.00,  # Exceeds 5k cap
            "category": "broadband",
            "startDate": "2024-01-05",
            "endDate": "2024-02-04"
        })
        maker_out = self._assemble_maker_output("CLM-POLICY-CAP", extracted, normalized, "airtel_3999.pdf")
        checker_rep = self.checker.process(maker_out)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_REJECT)
        self.assertIn("POLICY_CAP_EXCEEDED", decision.escalation_tags)
        self.assertIn("exceeds company limit of ₹5,000", decision.actionable_user_reason)

    # -------------------------------------------------------------------------
    # 5. DUPLICATE INVOICE FRAUD REJECTION TESTS
    # -------------------------------------------------------------------------
    def test_scenario_7_duplicate_invoice_fraud_auto_reject(self):
        """Scenario 7: Re-submitting same invoice number (HT2209I001458573) -> AUTO_REJECT (DUPLICATE_FRAUD)"""
        # Register first submission
        dup_service = DuplicateDetectionService()
        dup_service.register_claim(
            claim_id="CLM-INITIAL-001",
            vendor_name="Airtel",
            invoice_number="HT2209I001458573",
            amount_inr=1178.82,
            billing_start_date="2022-01-08",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        extracted = self.maker._fallback_rule_extractor("airtel_999.pdf", AIRTEL_999_TEXT, is_blur=False)
        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2022-01-08",
            "endDate": "2022-02-07"
        })
        maker_out = self._assemble_maker_output("CLM-DUPLICATE-002", extracted, normalized, "airtel_999.pdf")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.has_duplicate_fraud)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_REJECT)
        self.assertIn("DUPLICATE_FRAUD", decision.escalation_tags)
        self.assertIn("Rejected (Duplicate)", decision.actionable_user_reason)

    # -------------------------------------------------------------------------
    # 6. BLURRY / DEGRADED ATTACHMENT ESCALATION TESTS
    # -------------------------------------------------------------------------
    def test_scenario_8_blurry_document_escalation(self):
        """Scenario 8: Degraded image with is_blur=True -> ESCALATE_TO_HUMAN (LOW_CONFIDENCE_BLUR)"""
        extracted = self.maker._fallback_rule_extractor("blurry_receipt.jpg", "", is_blur=True)
        self.assertTrue(extracted.is_blurry_or_unreadable)

        normalized = self.maker.normalize_user_claim({
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2023-01-21",
            "endDate": "2023-02-20"
        })
        maker_out = self._assemble_maker_output("CLM-BLURRY-001", extracted, normalized, "blurry_receipt.jpg")
        checker_rep = self.checker.process(maker_out)
        self.assertTrue(checker_rep.has_low_confidence)

        decision = self.approver.process(maker_out, checker_rep)
        self.assertEqual(decision.decision, ApprovalDecisionType.ESCALATE_TO_HUMAN)
        self.assertIn("LOW_CONFIDENCE_BLUR", decision.escalation_tags)
        self.assertIn("Manual Review (Blurry Image)", decision.actionable_user_reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
