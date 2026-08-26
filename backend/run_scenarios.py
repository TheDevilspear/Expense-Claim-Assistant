"""
Scenario Runner Script for Multi-Agent Expense Claim Assistant.
Executes and displays legible, step-by-step audit logs for all 6 required business scenarios.
"""

import os
import sys
import json

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent
from services.duplicate_service import DuplicateDetectionService


def print_divider(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f" {title.upper()} ".center(80, "="))
        print("=" * 80)


def run_scenario(scenario_num: int, title: str, file_path: str, user_claim: dict, blur_assessment: dict = None, mock_override: dict = None, custom_policy_cap: float = None):
    print_divider(f"Scenario {scenario_num}: {title}")
    print(f"📥 USER CLAIM INPUT:")
    print(f"   - Claimed Amount: ₹{user_claim['claimedAmountINR']:.2f}")
    print(f"   - Category: {user_claim['category']}")
    print(f"   - Billing Period: {user_claim['startDate']} to {user_claim['endDate']}")
    print(f"   - Attachment: {file_path}")

    dup_service = DuplicateDetectionService()
    maker = MakerAgent()
    checker = CheckerAgent(duplicate_service=dup_service)
    if custom_policy_cap:
        checker.POLICY_MAX_REIMBURSABLE_CAP = custom_policy_cap
    approver = ApproverAgent()

    # 1. Maker Agent
    maker_out = maker.process(f"CLM-SCENARIO-{scenario_num}", file_path, user_claim, blur_assessment)
    if mock_override:
        for k, v in mock_override.items():
            if hasattr(maker_out.extracted_invoice, k):
                setattr(maker_out.extracted_invoice, k, v)

    print(f"\n[1] 🤖 MAKER AGENT EXTRACTION:")
    inv = maker_out.extracted_invoice
    print(f"   - Detected Type: {inv.detected_document_type}")
    print(f"   - Vendor: {inv.vendor_name.value} (Confidence: {inv.vendor_name.confidence:.2f})")
    print(f"   - Invoice No: {inv.invoice_or_account_number.value} (Confidence: {inv.invoice_or_account_number.confidence:.2f})")
    print(f"   - Total Amount: ₹{inv.total_amount_inr.value if inv.total_amount_inr.value else 'N/A'} (Confidence: {inv.total_amount_inr.confidence:.2f})")
    print(f"   - Service Dates: {inv.billing_start_date.value} to {inv.billing_end_date.value}")
    print(f"   - Summary: {maker_out.maker_summary}")

    # 2. Checker Agent
    checker_rep = checker.process(maker_out)
    print(f"\n[2] ⚖️ CHECKER AGENT VERIFICATION:")
    print(f"   - Overall Checks Passed: {checker_rep.all_checks_passed}")
    for c in checker_rep.checks:
        status_symbol = "✓" if c.status.value == "PASS" else "⚠️" if "CONFIDENCE" in c.status.value or "POLICY" in c.status.value else "✕"
        print(f"   [{status_symbol}] {c.check_name:<40} -> {c.status.value:<24} | Reason: {c.reason}")
    print(f"   - Summary: {checker_rep.checker_summary}")

    # 3. Approver Agent
    approver_dec = approver.process(maker_out, checker_rep)
    print(f"\n[3] 🏁 APPROVER AGENT DECISION:")
    print(f"   - Final Decision: {approver_dec.decision.value}")
    print(f"   - Approved Amount: {'₹' + str(approver_dec.approved_amount_inr) if approver_dec.approved_amount_inr else 'None'}")
    print(f"   - Risk Score: {approver_dec.risk_score * 100:.0f}%")
    print(f"   - Escalation Tags: {approver_dec.escalation_tags}")
    print(f"   - Actionable User Reason: \"{approver_dec.actionable_user_reason}\"")
    print(f"   - Internal Auditor Rationale: \"{approver_dec.internal_rationale}\"")


def main():
    dup_service = DuplicateDetectionService()
    dup_service.clear_index()

    # Pre-populate 1 past claim for duplicate fraud detection test
    dup_service.register_claim(
        claim_id="CLM-PAST-101",
        vendor_name="Airtel",
        invoice_number="INV-982341",
        amount_inr=799.00,
        billing_start_date="2026-08-01",
        timestamp="2026-08-10T12:00:00Z",
    )

    # Scenario 1: Clean Match (<= ₹2k)
    run_scenario(
        scenario_num=1,
        title="Clean Matching Claim (Auto-Approve)",
        file_path="airtel_broadband_799.pdf",
        user_claim={"claimedAmountINR": 799.00, "category": "broadband", "startDate": "2026-08-01", "endDate": "2026-08-28"},
        blur_assessment={"is_blur": False, "ensemble_score": 0.98},
    )

    # Scenario 2: Amount Mismatch
    run_scenario(
        scenario_num=2,
        title="Amount Mismatch (Escalate to Human)",
        file_path="jio_bill_950.pdf",
        user_claim={"claimedAmountINR": 1200.00, "category": "cellphone", "startDate": "2026-08-01", "endDate": "2026-08-28"},
        blur_assessment={"is_blur": False, "ensemble_score": 0.95},
    )

    # Scenario 3: Blurry / Low-Confidence Extraction
    run_scenario(
        scenario_num=3,
        title="Low-Confidence / Blurry Scan (Escalate, No Guessing)",
        file_path="blurry_receipt.jpg",
        user_claim={"claimedAmountINR": 499.00, "category": "cellphone", "startDate": "2026-08-01", "endDate": "2026-08-28"},
        blur_assessment={"is_blur": True, "ensemble_score": 0.28},
    )

    # Scenario 4: Duplicate Invoice Fraud
    from models.maker_schema import FieldExtraction
    run_scenario(
        scenario_num=4,
        title="Duplicate Invoice Fraud Detection (Auto-Reject)",
        file_path="airtel_bill_799.pdf",
        user_claim={"claimedAmountINR": 799.00, "category": "broadband", "startDate": "2026-08-01", "endDate": "2026-08-28"},
        blur_assessment={"is_blur": False, "ensemble_score": 0.97},
        mock_override={"invoice_or_account_number": FieldExtraction(value="INV-982341", raw_text="Tax Invoice: INV-982341", confidence=0.98)},
    )

    # Scenario 5: Policy Violation (> ₹5,000 Cap)
    run_scenario(
        scenario_num=5,
        title="Policy Cap Violation > ₹5,000 (Auto-Reject)",
        file_path="annual_broadband_6500.pdf",
        user_claim={"claimedAmountINR": 6500.00, "category": "broadband", "startDate": "2026-08-01", "endDate": "2027-07-31"},
        blur_assessment={"is_blur": False, "ensemble_score": 0.96},
        mock_override={"total_amount_inr": FieldExtraction(value=6500.00, raw_text="Total: ₹6500.00", confidence=0.99)},
    )

    # Scenario 6: High-Value Legitimate Claim (> ₹5,000 Auto-Approve Threshold)
    run_scenario(
        scenario_num=6,
        title="High-Value Legitimate Claim > ₹5,000 (Escalate for Managerial Sign-Off)",
        file_path="airtel_broadband_5500.pdf",
        user_claim={"claimedAmountINR": 5500.00, "category": "broadband", "startDate": "2026-08-01", "endDate": "2026-10-31"},
        blur_assessment={"is_blur": False, "ensemble_score": 0.99},
        mock_override={"total_amount_inr": FieldExtraction(value=5500.00, raw_text="Total: ₹5500.00", confidence=0.99)},
        custom_policy_cap=10000.00,
    )


if __name__ == "__main__":
    main()
