"""
Final Sample Documents Evaluation Test Suite.

Tests the 2 final sample documents:
11. Airtel Xstream Value 999 2-Page Digital Statement (Shivanshu Gupta - ₹1,178.82 Broadband)
12. JioFiber Bill Summary with Advance Credits / NIL Payable (Sanjay Yadav - ₹1,178.82 Broadband)
"""

import os
import sys
import unittest
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent
from models.approver_schema import ApprovalDecisionType


DOC_11_AIRTEL_SHIVANSHU = """
MONTHLY STATEMENT airtel
Shivanshu Gupta
A78 Block A,Rajajipuram,Behind Lucknow Public School,Lucknow,,Lucknow,Uttar Pradesh,226017
Email Address: shivanshu900@gmail.com
Phone Number: 9560927208
Your Plan: Airtel-UL-Xstream Value 999 Unlimited GB (200Mbps/1024Kbps) COMBO Plan
Number of Connections: 1
Statement Date: 09 Feb 2022
Statement Period: 08 Jan 2022 to 07 Feb 2022
Amount Payable: 1178.82
Due Date: 20 Feb 2022
Previous Dues Payments Credits Charges for this Month Amount Payable
0.00 0.00 0.00 1178.82 1178.82
This Month's Summary
Services No. of Connections Plan/Pack Charges Other Charges Total
Broadband - 052210538983_dsl 1 999.0 0.0 999.00
Taxes (GST) 179.82
Total (Incl. Taxes) 1178.82
Total : One Thousand One Hundred Seventy Eight Rupees and Eighty Two Paise Only
Relationship No. 20001093969 Bill No. HT2209I001458573 Amount Due : 1178.82 LoB : Telemedia
"""

DOC_12_JIOFIBER_SANJAY = """
JioFiber Bill Summary
Mr. Sanjay Yadav ,
H-40 Flat 7,8 Siddhi Vinayak Colony Maholi Bhopal India
Registered Mobile Number: +918480953599 || Email: dasekant@outlook.com
Jio Number : 918319326003
Account Number : 410803229618
Statement Number : 257002837375
Activation Date : 16-DEC-2024
Billing Cycle Date : 21-JAN-2023 to 20-FEB-2023
Due Date Current Plan : 30-JAN-2025
Total Payable : NIL
Total Current Charges (A+B) 1,178.82
Plan Charges (excluding taxes)
Monthly Plan Charges Connectivity 21-JAN-2023 20-FEB-2023 880.00
Monthly Plan Charges Platform 21-JAN-2023 20-FEB-2023 119.00
Total Plan Charges 999.00
Taxes
CGST 89.91
SGST 89.91
Total Tax 179.82
Total Current Charges (A+B) 1178.82
Your Plan Details : Postpaid_999_3M: Unlimited Data @ 150 Mbps Unlimited Voice Subscription to 14 Paid OTT apps
"""


class TestFinalSampleDocuments(unittest.TestCase):
    def setUp(self):
        self.maker = MakerAgent()
        self.checker = CheckerAgent()
        self.approver = ApproverAgent()

    def test_doc_11_airtel_shivanshu(self):
        """Doc 11: Airtel Xstream Value 999 Statement (Shivanshu Gupta)."""
        extracted = self.maker._fallback_rule_extractor("airtel_shivanshu.pdf", DOC_11_AIRTEL_SHIVANSHU, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 1178.82)
        self.assertIn(extracted.invoice_or_account_number.value, ["HT2209I001458573", "20001093969"])
        self.assertEqual(extracted.billing_start_date.value, "2022-01-08")
        self.assertEqual(extracted.billing_end_date.value, "2022-02-07")
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        user_claim = {
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2022-01-08",
            "endDate": "2022-02-07"
        }
        maker_out = self.maker.process("CLM-SHIVANSHU", "airtel_shivanshu.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)
        self.assertEqual(decision.approved_amount_inr, 1178.82)

    def test_doc_12_jiofiber_sanjay(self):
        """Doc 12: JioFiber Advance Balance Bill Summary (Sanjay Yadav)."""
        extracted = self.maker._fallback_rule_extractor("jiofiber_sanjay.pdf", DOC_12_JIOFIBER_SANJAY, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Jio")
        self.assertEqual(extracted.total_amount_inr.value, 1178.82)
        self.assertEqual(extracted.invoice_or_account_number.value, "410803229618")
        self.assertEqual(extracted.billing_start_date.value, "2023-01-21")
        self.assertEqual(extracted.billing_end_date.value, "2023-02-20")
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        user_claim = {
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2023-01-21",
            "endDate": "2023-02-20"
        }
        maker_out = self.maker.process("CLM-SANJAY", "jiofiber_sanjay.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)
        self.assertEqual(decision.approved_amount_inr, 1178.82)


if __name__ == "__main__":
    unittest.main(verbosity=2)
