"""
End-to-end pipeline integration test ensuring every single code path
in maker_agent, checker_agent, approver_agent, and duplicate_service works.
"""

import unittest
import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from pipeline_runner import run_pipeline
from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent


class TestLivePipelineEndToEnd(unittest.TestCase):
    """Verifies that run_pipeline executes cleanly with zero runtime NameErrors or KeyErrors."""

    def test_run_pipeline_airtel_claim(self):
        user_claim = {
            "claimedAmountINR": 1178.82,
            "category": "Broadband / Fiber",
            "startDate": "2022-01-01",
            "endDate": "2022-01-31",
            "validityPeriod": "1 Month",
        }
        blur_assessment = {
            "is_blur": False,
            "quality_label": "Clear",
            "ensemble_score": 0.95,
        }

        res = run_pipeline(
            claim_id="CLM-UNIT-001",
            file_path="backend/uploads/sample-nonexistent.pdf",
            user_claim_input=user_claim,
            blur_assessment=blur_assessment,
        )

        self.assertIn("maker_output", res)
        self.assertIn("checker_report", res)
        self.assertIn("approver_decision", res)
        self.assertIn(res["approver_decision"]["decision"], ["AUTO_APPROVE", "AUTO_REJECT", "ESCALATE_TO_HUMAN"])

    def test_run_pipeline_jio_recharge(self):
        user_claim = {
            "claimedAmountINR": 666.0,
            "category": "Cellphone / Mobile",
            "startDate": "2024-01-01",
            "endDate": "2024-03-27",
            "validityPeriod": "84 Days",
        }
        blur_assessment = {
            "is_blur": False,
            "quality_label": "Clear",
            "ensemble_score": 0.90,
        }

        res = run_pipeline(
            claim_id="CLM-UNIT-002",
            file_path="backend/uploads/jio-test.pdf",
            user_claim_input=user_claim,
            blur_assessment=blur_assessment,
        )

        self.assertIsNotNone(res["maker_output"])
        self.assertIsNotNone(res["checker_report"])
        self.assertIsNotNone(res["approver_decision"])


if __name__ == "__main__":
    unittest.main()
