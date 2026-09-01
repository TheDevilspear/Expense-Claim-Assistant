"""
Shared Pytest & Unittest Test Fixtures.
Provides standard mock claims, document evidence helpers, and ledger management.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from services.duplicate_service import DuplicateDetectionService
from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent


def create_sample_claim_input(
    amount: float = 799.00,
    category: str = "broadband",
    start_date: str = "2026-08-01",
    end_date: str = "2026-08-28",
) -> Dict[str, Any]:
    """Helper to generate standardized claim inputs for tests."""
    return {
        "claimedAmountINR": amount,
        "category": category,
        "startDate": start_date,
        "endDate": end_date,
    }


def reset_test_duplicate_ledger():
    """Clears the duplicate ledger between test runs."""
    dup_service = DuplicateDetectionService()
    dup_service.clear_index()
