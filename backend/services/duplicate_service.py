"""
Duplicate Invoice & Fraud Detection Service with Concurrency Protection.
Maintains an index of previously approved and processed claims to catch:
1. Exact Invoice Number reuse across different claims.
2. Fingerprint match (Same Vendor + Same Amount + Same Billing Start Date).
"""

import os
import json
import threading
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from contextlib import contextmanager
import policy

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INDEX_FILE = DATA_DIR / "claims_index.json"
LOCK_FILE = DATA_DIR / "claims_index.lock"

try:
    import fcntl
except ImportError:
    fcntl = None

# Thread-level reentrant lock
_THREAD_LOCK = threading.RLock()


@contextmanager
def _process_lock():
    """Acquires a process-level file lock on Unix systems to guarantee concurrency safety."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK:
        if fcntl is not None:
            with open(LOCK_FILE, "a") as lock_f:
                try:
                    fcntl.flock(lock_f, fcntl.LOCK_EX)
                    yield
                finally:
                    try:
                        fcntl.flock(lock_f, fcntl.LOCK_UN)
                    except Exception:
                        pass
        else:
            yield


class DuplicateDetectionService:
    """Service to record and detect duplicate invoice submissions."""

    def __init__(self):
        self._ensure_storage()

    def _ensure_storage(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX_FILE.exists():
            with _process_lock():
                if not INDEX_FILE.exists():
                    self._write_raw([])

    def _read_raw(self) -> list:
        try:
            if not INDEX_FILE.exists():
                return []
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            return data.get("claims", [])
        except Exception:
            return []

    def _write_raw(self, claims: list):
        try:
            temp_file = INDEX_FILE.with_suffix(".tmp")
            temp_file.write_text(json.dumps({"claims": claims}, indent=2), encoding="utf-8")
            temp_file.replace(INDEX_FILE)
        except Exception:
            pass

    def _load_index(self) -> list:
        with _process_lock():
            return self._read_raw()

    def _save_index(self, claims: list):
        with _process_lock():
            self._write_raw(claims)

    def check_duplicate(
        self,
        current_claim_id: str,
        vendor_name: Optional[str],
        invoice_number: Optional[str],
        amount_inr: Optional[float],
        billing_start_date: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if the invoice was already claimed.
        Returns: (is_duplicate: bool, reason: Optional[str])
        """
        claims = self._load_index()

        clean_inv = str(invoice_number).strip().upper() if invoice_number else ""
        clean_vendor = str(vendor_name).strip().upper() if vendor_name else ""
        clean_date = str(billing_start_date).strip() if billing_start_date else ""

        for past in claims:
            if past.get("claim_id") == current_claim_id:
                continue

            past_inv = str(past.get("invoice_number") or "").strip().upper()
            past_vendor = str(past.get("vendor_name") or "").strip().upper()
            past_amount = float(past.get("amount_inr") or 0.0)
            past_date = str(past.get("billing_start_date") or "").strip()

            # Rule 1: Exact Invoice Number Match
            min_len = policy.MIN_INVOICE_NUMBER_LENGTH
            if clean_inv and past_inv and clean_inv == past_inv and len(clean_inv) >= min_len:
                return True, f"Invoice number '{clean_inv}' was already claimed in previous Claim #{past.get('claim_id')} on {past.get('timestamp', 'past submission')}."

            # Rule 2: Fingerprint Match (Same Vendor + Same Amount + Same Billing Date)
            if (
                clean_vendor
                and past_vendor
                and clean_vendor == past_vendor
                and amount_inr is not None
                and abs(amount_inr - past_amount) < 0.01
                and clean_date
                and clean_date == past_date
            ):
                return True, f"Identical bill fingerprint (Vendor: {clean_vendor}, Amount: ₹{amount_inr:.2f}, Period: {clean_date}) was already claimed in Claim #{past.get('claim_id')}."

        return False, None

    def register_claim(
        self,
        claim_id: str,
        vendor_name: Optional[str],
        invoice_number: Optional[str],
        amount_inr: Optional[float],
        billing_start_date: Optional[str],
        timestamp: str,
    ):
        """Records an approved/processed claim in the index with non-nested lock protection."""
        with _process_lock():
            claims = self._read_raw()
            # Avoid duplicate entries for same claim_id
            claims = [c for c in claims if c.get("claim_id") != claim_id]

            claims.append({
                "claim_id": claim_id,
                "vendor_name": vendor_name,
                "invoice_number": invoice_number,
                "amount_inr": amount_inr,
                "billing_start_date": billing_start_date,
                "timestamp": timestamp,
            })
            self._write_raw(claims)

    def clear_index(self):
        """Clears index (used for unit test setup/teardown)."""
        with _process_lock():
            self._write_raw([])
