"""
Batch 2 Real Document Evaluation Test Suite.

Tests 5 new realistic telecom document profiles:
6. Airtel 8-Page Multi-Service Document (Abhinish Anand - ₹2,416.64 Total / ₹1,767.64 Broadband)
7. Airtel Fiber Infinity 3999 Monthly Statement (Pradnya Bagave - ₹4,718.82 Broadband)
8. Older Airtel Fixedline & Broadband 4-Page Bill (Ravi Kumar - ₹1,178.82 Broadband)
9. PhonePe Jio Prepaid Recharge Screenshot (₹555.00 Recharge)
10. Airtel Prepaid Mobile Recharge Tax Invoice (Ebin Francis - ₹1,199.00 Prepaid)
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


DOC_6_AIRTEL_8PAGE_ABHINISH = """
Bharti Airtel Limited
payment receipt
Receipt No. 7140897191242170368
Customer Name Abhinish Anand
Customer Number 10101012312618
Order Number 7140897131073429504
Line of Business Airtel Xstream Fiber
Payment type Bill payment | Recharging
Payment date & time 14/12/2023 08:26
Payment mode UPI
Paid amount 2416.64
Telemedia 080102747802_kk 1767.64
DTH 3036196282-001 649.00

Black Monthly Statement
Your Plan: Airtel Black Plan
Airtel Black ID 10101012312618
Statement Date 12 Dec 2023
Statement Period 11 Nov 2023 - 10 Dec 2023
Total Amount Payable: 2416.64
Due Date: 22 Dec 2023
This Month's Summary
Services Connections Plan/Pack Charges Other Charges Total
Airtel BlackPlan - 10101012312618 2 2,048.00 0.00 2,048.00
Taxes 368.64
This month's charges 2,416.64
TOTAL 2,416.64

FIXEDLINE AND BROADBAND SERVICES
Bharti Airtel Limited- Tax Invoice
Broadband ID : 080102747802_kk
Account No 7042732197
Bill Period 11 Nov 2023 to 10 Dec 2023
Bill NO HT2429I006171783
Bill Date 12 Dec 2023
Rental Charges 1498.00
Taxes 269.64
Total Amount 1767.64
Bill Plan Details : Airtel-Xstream Elite 1498 UL COMBO Plan
Speed: 300 Mbps
"""

DOC_7_AIRTEL_FIBER_PRADNYA = """
FIBER MONTHLY STATEMENT airtel
Pradnya Bagave
Building No 8 Flat No G2, Rakshak Nagar Phase 2, Pune, Maharashtra, 411014
Total Amount Payable: 4718.82
Due Date: 16 Feb 2024
Your Plan: Airtel-UL-Xstream Infinity 3999 Unlimited GB (300Mbps/307200Kbps) COMBO SOS Plan
Statement Date: 06 Feb 2024
Statement Period: 05 Jan 2024 to 04 Feb 2024
This Month's Charges Summary
Services Connections Plan/Pack Charges Other Charges Total
Fiber - 02010805695_dsl 1 3999.0 0.0 3999.00
Taxes (GST) 719.82
This month's charges 4718.82
Total (Incl. Taxes) 4718.82
Total : Four Thousand Seven Hundred and Eighteen Rupees and Eighty Two Paise Only
"""

DOC_8_AIRTEL_BROADBAND_RAVI = """
fixedline and broadband services
Original Copy for Recipient - Tax Invoice
Mr Ravi Kumar
Ship To State Code: 33
user id 04112955416_tn
relationship no : 7011489124
bill no : 837270943
bill date : 06-Jan-2018
billing period : 05-Dec-2017 to 04-Jan-2018
pay by date 25-Jan-2018
monthly charges 999.00
call and vas charges 112.50
less total discounts -112.50
net charges 999.00
taxes 179.82
this month's charges 1178.82
amount due on or before 25-Jan-2018 1178.82
your bill in detail
user id 04112955416_tn
your bill plan airtel-ul-zoom 999 200gb (40mbps/1024kbps) combo plan
total charges payable 1178.82
total current charges 1178.82
Bharti Airtel Limited
"""

DOC_9_PHONEPE_JIO_RECHARGE = """
PhonePe
Recharge successful
07:05 pm on 05 Jul 2021
Transaction ID N2107051905128717169458
Jio Prepaid Reference ID 10458907531
Mobile recharged
Jio Prepaid
9066467546
555
Debited from
UTR:118618378662
555
Recharge Amount: 555.00
"""

DOC_10_AIRTEL_PREPAID_EBIN = """
MOBILE SERVICES
Original copy for Recipient - Tax Invoice
Ebin Francis
Phone no: 9159397992
State Code: TAMIL NADU
Type of Service Prepaid Recharge
Transaction Date & Time 18 April 25, 4:42 AM
Transaction ID 7276451795666350896
Invoice Number PA9375B12G53753
Invoice Date 16 April 2025
Payment Received 1199.00
Payment Mode UPI
RECHARGE AMOUNT
Pack MRP 1199
Discount 0
Discounted Price 1199
CGST 107.91
SGST 107.91
Total Tax 215.82
Taxable Value 983.18
Total Charges 1199.0
For Bharti Airtel Limited
Vasim Unissa S, General Manager
Airtel Customer Number 9159397992
"""


class TestBatch2RealDocuments(unittest.TestCase):
    def setUp(self):
        self.maker = MakerAgent()
        self.checker = CheckerAgent()
        self.approver = ApproverAgent()

    def test_doc_6_airtel_8page_abhinish(self):
        """Doc 6: Airtel 8-Page Multi-Service Document (Abhinish Anand)."""
        extracted = self.maker._fallback_rule_extractor("airtel_abhinish.pdf", DOC_6_AIRTEL_8PAGE_ABHINISH, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertIn(extracted.total_amount_inr.value, [2416.64, 1767.64])
        self.assertEqual(extracted.billing_start_date.value, "2023-11-11")
        self.assertEqual(extracted.billing_end_date.value, "2023-12-10")
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        user_claim = {
            "claimedAmountINR": 2416.64,
            "category": "broadband",
            "startDate": "2023-11-11",
            "endDate": "2023-12-10"
        }
        maker_out = self.maker.process("CLM-ABHINISH", "airtel_abhinish.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_7_airtel_fiber_pradnya(self):
        """Doc 7: Airtel Fiber Infinity 3999 Monthly Statement (Pradnya Bagave)."""
        extracted = self.maker._fallback_rule_extractor("airtel_pradnya.pdf", DOC_7_AIRTEL_FIBER_PRADNYA, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 4718.82)
        self.assertEqual(extracted.billing_start_date.value, "2024-01-05")
        self.assertEqual(extracted.billing_end_date.value, "2024-02-04")
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        user_claim = {
            "claimedAmountINR": 4718.82,
            "category": "broadband",
            "startDate": "2024-01-05",
            "endDate": "2024-02-04"
        }
        maker_out = self.maker.process("CLM-PRADNYA", "airtel_pradnya.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_8_airtel_broadband_ravi(self):
        """Doc 8: Older Airtel Fixedline & Broadband 4-Page Bill (Ravi Kumar)."""
        extracted = self.maker._fallback_rule_extractor("airtel_ravi.pdf", DOC_8_AIRTEL_BROADBAND_RAVI, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 1178.82)
        self.assertEqual(extracted.invoice_or_account_number.value, "837270943")
        self.assertEqual(extracted.billing_start_date.value, "2017-12-05")
        self.assertEqual(extracted.billing_end_date.value, "2018-01-04")
        self.assertEqual(extracted.detected_document_type, "BROADBAND_FIBER_BILL")

        user_claim = {
            "claimedAmountINR": 1178.82,
            "category": "broadband",
            "startDate": "2017-12-05",
            "endDate": "2018-01-04"
        }
        maker_out = self.maker.process("CLM-RAVI", "airtel_ravi.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_9_phonepe_jio_recharge(self):
        """Doc 9: PhonePe Jio Prepaid Recharge Screenshot."""
        extracted = self.maker._fallback_rule_extractor("phonepe_jio.pdf", DOC_9_PHONEPE_JIO_RECHARGE, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Jio")
        self.assertEqual(extracted.total_amount_inr.value, 555.0)
        self.assertEqual(extracted.invoice_or_account_number.value, "N2107051905128717169458")
        self.assertEqual(extracted.detected_document_type, "CELLPHONE_PREPAID_RECHARGE")

        user_claim = {
            "claimedAmountINR": 555.00,
            "category": "cellphone",
            "startDate": "2021-07-05",
            "endDate": "2021-08-01"
        }
        maker_out = self.maker.process("CLM-PHONEPE-JIO", "phonepe_jio.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)

    def test_doc_10_airtel_prepaid_ebin(self):
        """Doc 10: Airtel Prepaid Mobile Recharge Tax Invoice (Ebin Francis)."""
        extracted = self.maker._fallback_rule_extractor("airtel_ebin.pdf", DOC_10_AIRTEL_PREPAID_EBIN, is_blur=False)

        self.assertEqual(extracted.vendor_name.value, "Airtel")
        self.assertEqual(extracted.total_amount_inr.value, 1199.0)
        self.assertEqual(extracted.invoice_or_account_number.value, "PA9375B12G53753")
        self.assertEqual(extracted.detected_document_type, "CELLPHONE_PREPAID_RECHARGE")

        user_claim = {
            "claimedAmountINR": 1199.00,
            "category": "cellphone",
            "startDate": "2025-04-16",
            "endDate": "2025-05-13"
        }
        maker_out = self.maker.process("CLM-EBIN", "airtel_ebin.pdf", user_claim)
        maker_out.extracted_invoice = extracted
        checker_rep = self.checker.process(maker_out)
        decision = self.approver.process(maker_out, checker_rep)

        self.assertEqual(decision.decision, ApprovalDecisionType.AUTO_APPROVE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
