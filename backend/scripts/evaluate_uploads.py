"""
Automated Uploads Evaluation & Bug Hunter Script.

Iterates through all uploaded documents in `backend/uploads/`,
runs the complete Maker -> Checker -> Approver pipeline,
and audits the JSON handoffs for discrepancies, formatting bugs,
and edge-case failures.
"""

import os
import sys
import json
from pathlib import Path

# Add backend root to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent
from models.maker_schema import MakerOutput
from extraction import document_inspector


def audit_uploads():
    uploads_dir = backend_dir / "uploads"
    if not uploads_dir.exists():
        print("Uploads directory not found.")
        return

    files = sorted(list(uploads_dir.glob("*.pdf")) + list(uploads_dir.glob("*.png")) + list(uploads_dir.glob("*.jpg")))
    print(f"\n=======================================================", flush=True)
    print(f"AUDITING {len(files)} REAL FILES IN {uploads_dir}", flush=True)
    print(f"=======================================================\n", flush=True)

    maker = MakerAgent()
    checker = CheckerAgent()
    approver = ApproverAgent()

    results = []

    for idx, file_path in enumerate(files, start=1):
        filename = file_path.name
        print(f"[{idx}/{len(files)}] Processing: {filename}...", flush=True)

        doc_profile = document_inspector.inspect(str(file_path))

        try:
            # Single extraction pass
            extracted_inv = maker.extract_invoice(str(file_path))
            
            # Formulate simulated claim based on invoice findings
            cat = "cellphone" if "PREPAID" in extracted_inv.detected_document_type or "POSTPAID" in extracted_inv.detected_document_type else "broadband"
            amt = extracted_inv.total_amount_inr.value or 1000.0
            start = extracted_inv.billing_start_date.value or "2023-01-01"
            end = extracted_inv.billing_end_date.value or "2023-01-31"

            raw_claim = {
                "claimedAmountINR": amt,
                "category": cat,
                "startDate": start,
                "endDate": end,
            }
            cleaned_claim = maker.clean_user_claim(raw_claim)
            claim_id = f"CLM-TEST-{idx:03d}"

            maker_out = MakerOutput(
                claim_id=claim_id,
                cleaned_claim=cleaned_claim,
                extracted_invoice=extracted_inv,
            )

            checker_rep = checker.process(maker_out)
            decision = approver.process(maker_out, checker_rep)

            bugs = []
            
            # 1. Invoice Number Quality Audit
            inv_no = extracted_inv.invoice_or_account_number.value
            if inv_no:
                if inv_no.upper() in ["INVOICE", "NUMBER", "STATEMENT", "BILL", "DETAILS", "DATE", "SERVICES", "ORIGINAL"]:
                    bugs.append(f"INVOICE_NUMBER_IS_STOPWORD: '{inv_no}'")
                elif not any(c.isdigit() for c in inv_no):
                    bugs.append(f"INVOICE_NUMBER_NO_DIGITS: '{inv_no}'")

            # 2. Date Span Quality Audit
            d_start = extracted_inv.billing_start_date.value
            d_end = extracted_inv.billing_end_date.value
            if d_start and d_end:
                try:
                    from datetime import datetime
                    dt1 = datetime.strptime(d_start, "%Y-%m-%d")
                    dt2 = datetime.strptime(d_end, "%Y-%m-%d")
                    span = (dt2 - dt1).days
                    if span > 120:
                        bugs.append(f"LONG_BILLING_SPAN: {span} days ({d_start} to {d_end})")
                    elif span < 0:
                        bugs.append(f"NEGATIVE_SPAN: {d_start} > {d_end}")
                except Exception as e:
                    bugs.append(f"DATE_PARSE_ERROR: {e}")

            # 3. Amount & Confidence Audit
            if extracted_inv.total_amount_inr.value is None or extracted_inv.total_amount_inr.value <= 0:
                bugs.append(f"INVALID_OR_ZERO_AMOUNT: {extracted_inv.total_amount_inr.value}")

            # 4. Vendor Audit
            if not extracted_inv.vendor_name.value:
                bugs.append("MISSING_VENDOR")

            results.append({
                "filename": filename,
                "pages": doc_profile.page_count,
                "doc_type": extracted_inv.detected_document_type,
                "vendor": extracted_inv.vendor_name.value,
                "amount": extracted_inv.total_amount_inr.value,
                "amount_conf": extracted_inv.total_amount_inr.confidence,
                "invoice_no": inv_no,
                "dates": f"{d_start} to {d_end}",
                "decision": decision.decision.value,
                "approved_amount": decision.approved_amount_inr,
                "all_checks_passed": checker_rep.all_checks_passed,
                "bugs": bugs
            })

        except Exception as err:
            results.append({
                "filename": filename,
                "pages": doc_profile.page_count,
                "error": str(err),
                "bugs": [f"PIPELINE_CRASH: {err}"]
            })

    print("\n\n=======================================================", flush=True)
    print("DETAILED RESULTS & BUG AUDIT FOR ALL 12 UPLOADED FILES", flush=True)
    print("=======================================================\n", flush=True)

    for r in results:
        print(f"File: {r['filename']} ({r.get('pages', 1)} pages)", flush=True)
        if "error" in r:
            print(f"  ❌ CRASH: {r['error']}", flush=True)
        else:
            status_icon = "✅" if not r["bugs"] and r["decision"] == "AUTO_APPROVE" else ("⚠️" if not r["bugs"] else "🚨")
            print(f"  {status_icon} Vendor: {r['vendor']} | Amount: ₹{r['amount']} (conf: {r['amount_conf']:.2f}) | Type: {r['doc_type']}", flush=True)
            print(f"     Invoice #: {r['invoice_no']} | Period: {r['dates']}", flush=True)
            print(f"     Decision: {r['decision']} (Approved: ₹{r['approved_amount']})", flush=True)
            if r["bugs"]:
                for b in r["bugs"]:
                    print(f"     🚨 BUG DETECTED: {b}", flush=True)
        print("-------------------------------------------------------", flush=True)


if __name__ == "__main__":
    audit_uploads()
