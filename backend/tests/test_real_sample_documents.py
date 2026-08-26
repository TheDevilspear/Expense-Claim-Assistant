"""
End-to-End Real Sample Document Test Suite.

Evaluates the 5 real telecom document profiles provided:
1. Airtel Black 7-Page Statement (Akshay Kumar - ₹1,579.82 Total, ₹960.52 Broadband)
2. Airtel Prepaid Recharge Receipt (Ramya Saravanan - ₹2,499.00 Prepaid)
3. Airtel Black Negative Balance Statement (M Jagadeesh - ₹512.07 Current Charges, ₹339.84 Broadband)
4. Tikona Home Broadband Bill (Shahrukh Jamil - ₹2,001.22 Broadband)
5. Older Airtel 6-Page Mobile Bill (Damireddy Ravi Kiran - ₹400.72 Current / ₹349.78 Due, ₹122.92 Roaming)
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


DOC_1_AIRTEL_BLACK_AKSHAY = """
Black Monthly Statement
Akshay Kumar
Registered Email: akshaykharola@gmail.com
Registered Telephone Number (RTN): 7895771543
Your Plan: Airtel Black 1099 Plan
Airtel Black ID 10101016441602
Number of connections 2
Statement Date 27 Nov 2023
Statement Period 26 Oct 2023 - 25 Nov 2023
Total Amount Payable: 1579.82
Due Date: 7 Dec 2023
Last bill amount Payment made Credits This Month's Charges Total Amount
₹1,579.82 - ₹1,579.82 - ₹0.00 + ₹1,579.82 = ₹1,579.82
This Month's Summary (Amounts in ₹)
Services Connections Plan/Pack Charges Other Charges Total
Airtel BlackPlan - 10101016441602 2 1,099.00 239.83 1,338.83
Taxes 240.99
This month's charges 1,579.82
TOTAL ₹1,579.82

FIXEDLINE AND BROADBAND SERVICES
Bharti Airtel Limited- Tax Invoice
Broadband ID : 013546854994_dsl
Account No 20009549589
Bill Period 26 Oct 2023 to 25 Nov 2023
Bill NO HT2405I000591921
Bill Date 27 Nov 2023
Rental Charges 814.00
Taxes 146.52
Total Amount 960.52
Bill Plan Details : Airtel-UL-Xstream Ultra 999 Unlimited GB (200Mbps/1024Kbps) COMBO Plan
"""

DOC_2_AIRTEL_PREPAID_RAMYA = """
MOBILE SERVICES
Original copy for Recipient - Tax Invoice
Ramya Saravanan
State Code: TAMIL NADU
Phone no: 9790792024
Type of Service Prepaid Recharge
Transaction Date & Time 03 Aug 21, 08:31 AM
Transaction ID 7631715465756969365
Invoice Number AT3318A20179032
Invoice Date 03 Aug 2021
Airtel Customer Number 9790792024
Payment Received 2499.00
Payment Mode Debit Card
RECHARGE AMOUNT
Pack MRP 2499
Discount 0
Discounted Price 2499
CGST 190.60
SGST 190.60
Total Tax 381.20
Taxable Value 2117.80
Total Charges 2499.0
"""

DOC_3_AIRTEL_BLACK_JAGADEESH = """
Black Monthly Statement
M Jagadeesh
Your Plan: Airtel Black 699 Plan
Airtel Black ID 10101019108912
Number of connections 2
Statement Date 18 Mar 2024
Statement Period 17 Feb 2024 - 16 Mar 2024
This month's charges 512.07
Payment made -3,300.00
TOTAL -2787.93

FIXEDLINE AND BROADBAND SERVICES
Bharti Airtel Limited- Tax Invoice
Broadband ID : 04017879722_wifi
Account No 20015984431
Bill Period 17 Feb 2024 to 16 Mar 2024
Bill NO HT2436I004796012
Bill Date 18 Mar 2024
Rental Charges 288.00
Taxes 51.84
Total Amount 339.84
Bill Plan Details : Airtel-Xstream Fiber + Entertainment 498 UL COMBO Plan
"""

DOC_4_TIKONA_BROADBAND_SHAHRUKH = """
MR. SHAHRUKH JAMIL SHIKALGAR
Account Number: 139141816
User ID: 1127369547
Bill Date: 31-May-2021
Bill Number: MH0520B108767930
Your Plan: STDULH_VAR
Usage Period: 26-APR-21 to 26-May-21
Recurring Charges: 679.00
One Time Charge: Installation Fees_Rs.1200 1200.00
Taxes: 122.22
(SGST 9.00 %) 61.11
(CGST 9.00 %) 61.11
Current Bill Amount 2001.22
Tikona Infinet Private Limited
"""

DOC_5_AIRTEL_MOBILE_RAMIREDDY = """
Mr Damireddy Ravi Kiran Reddy P
Airtel number 8892227891
Relationship number 1171855048
Bill number 289317442
Bill date 28-Jan-2016
Bill period 26-Dec-2015 to 25-Jan-2016
Pay by date 15-Feb-2016
MOBILE SERVICES
YOUR ACCOUNT SUMMARY
Previous balance 209.06
Payments 260.00
Adjustments 0.00
This month's charges 400.72
Amount due on or before 15-Feb-2016 349.78
THIS MONTH'S CHARGES
1 One time charges 0.00
2 Monthly charges 225.00
3 Usage charges
Call charges 94.00
Value added services 4.80
Mobile internet usage 0.00
Roaming 122.92
4 Discounts -96.73
5 Last bill period late fee 0.00
6 Taxes 50.73
This month's charges 400.72
International Roaming: 122.92
"""


class TestRealSampleDocuments(unittest.TestCase):
    def setUp(self):
        self.maker = MakerAgent()
        self.checker = CheckerAgent()
        self.approver = ApproverAgent()

    def test_doc_1_airtel_black_akshay(self):
        """Doc 1: Airtel Black 1099 Combo Statement (Akshay Kumar)."""
        extracted = self.maker._fallback_rule_extractor("airtel_black.pdf", DOC_1_AIRTEL_BLACK_AKSHAY, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertIn(extracted.total_amount_inr.value, [1579.82, 960.52])
        self.assertGreaterEqual(extracted.total_amount_inr.confidence, 0.90)
        self.assertEqual(extracted.billing_start_date.value, "2023-10-26")
        self.assertEqual(extracted.billing_end_date.value, "2023-11-25")

        # Claim ₹1,579.82 for broadband
        user_claim = {
            "claimedAmountINR": 1579.82,
            "category": "broadband",
            "startDate": "2023-10-26",
            "endDate": "2023-11-25"
        }
        maker_out = self.maker.process("CLM-AKSHAY", "airtel_black.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_2_airtel_prepaid_ramya(self):
        """Doc 2: Airtel Prepaid Recharge Receipt (Ramya Saravanan)."""
        extracted = self.maker._fallback_rule_extractor("airtel_prepaid.pdf", DOC_2_AIRTEL_PREPAID_RAMYA, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 2499.0)
        self.assertEqual(extracted.invoice_or_account_number.value, "AT3318A20179032")
        self.assertEqual(extracted.detected_document_type, "CELLPHONE_PREPAID_RECHARGE")

        user_claim = {
            "claimedAmountINR": 2499.00,
            "category": "cellphone",
            "startDate": "2021-08-03",
            "endDate": "2021-08-30"
        }
        maker_out = self.maker.process("CLM-RAMYA", "airtel_prepaid.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_3_airtel_black_jagadeesh(self):
        """Doc 3: Airtel Black Advance Payment Statement (M Jagadeesh)."""
        extracted = self.maker._fallback_rule_extractor("airtel_jagadeesh.pdf", DOC_3_AIRTEL_BLACK_JAGADEESH, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        # Should extract positive charges for this month: 512.07 or 339.84
        self.assertIn(extracted.total_amount_inr.value, [512.07, 339.84])
        self.assertEqual(extracted.billing_start_date.value, "2024-02-17")
        self.assertEqual(extracted.billing_end_date.value, "2024-03-16")

    def test_doc_4_tikona_broadband_shahrukh(self):
        """Doc 4: Tikona Home Broadband Bill (Shahrukh Jamil Shikalgar)."""
        extracted = self.maker._fallback_rule_extractor("tikona_bill.pdf", DOC_4_TIKONA_BROADBAND_SHAHRUKH, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Tikona")
        self.assertEqual(extracted.total_amount_inr.value, 2001.22)
        self.assertEqual(extracted.invoice_or_account_number.value, "MH0520B108767930")
        self.assertEqual(extracted.billing_start_date.value, "2021-04-26")
        self.assertEqual(extracted.billing_end_date.value, "2021-05-26")
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        user_claim = {
            "claimedAmountINR": 2001.22,
            "category": "broadband",
            "startDate": "2021-04-26",
            "endDate": "2021-05-26"
        }
        maker_out = self.maker.process("CLM-TIKONA", "tikona_bill.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_5_airtel_mobile_ramireddy(self):
        """Doc 5: Older Airtel Postpaid Mobile Bill (Damireddy Ravi Kiran Reddy)."""
        extracted = self.maker._fallback_rule_extractor("airtel_mobile.pdf", DOC_5_AIRTEL_MOBILE_RAMIREDDY, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertIn(extracted.total_amount_inr.value, [400.72, 349.78])
        self.assertEqual(extracted.invoice_or_account_number.value, "289317442")
        self.assertEqual(extracted.billing_start_date.value, "2015-12-26")
        self.assertEqual(extracted.billing_end_date.value, "2016-01-25")
        # International / National Roaming charges extraction
        self.assertIsNotNone(extracted.international_roaming_charges)
        self.assertEqual(extracted.international_roaming_charges.value, 122.92)


if __name__ == "__main__":
    unittest.main(verbosity=2)
