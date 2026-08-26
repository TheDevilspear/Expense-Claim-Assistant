import sys
import os
import json

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from agents.maker_agent import MakerAgent
from agents.checker_agent import CheckerAgent
from agents.approver_agent import ApproverAgent
from services.duplicate_service import DuplicateDetectionService

def run_pipeline(claim_id, file_path, user_claim_input, blur_assessment):
    maker = MakerAgent()
    checker = CheckerAgent()
    approver = ApproverAgent()
    dup_service = DuplicateDetectionService()

    # 1. Maker Agent
    maker_out = maker.process(claim_id, file_path, user_claim_input, blur_assessment)

    # 2. Checker Agent
    checker_rep = checker.process(maker_out)

    # 3. Approver Agent
    approver_dec = approver.process(maker_out, checker_rep)

    # Register in duplicate index if not auto-rejected
    dec_val = approver_dec.decision.value if hasattr(approver_dec.decision, 'value') else str(approver_dec.decision)
    if dec_val != 'AUTO_REJECT':
        inv = maker_out.extracted_invoice
        dup_service.register_claim(
            claim_id=claim_id,
            vendor_name=inv.vendor_name.value if inv.vendor_name else None,
            invoice_number=inv.invoice_or_account_number.value if inv.invoice_or_account_number else None,
            amount_inr=inv.total_amount_inr.value if inv.total_amount_inr else None,
            billing_start_date=(inv.billing_start_date.value if inv.billing_start_date else None) or maker_out.normalized_claim.claimed_start_date,
            timestamp=maker_out.timestamp,
        )

    return {
        'maker_output': maker_out.model_dump(),
        'checker_report': checker_rep.model_dump(),
        'approver_decision': approver_dec.model_dump(),
    }

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            with open(sys.argv[1], 'r', encoding='utf-8') as f:
                input_data = json.load(f)
        else:
            input_data = json.load(sys.stdin)

        result = run_pipeline(
            input_data.get('claimId', 'CLM-UNKNOWN'),
            input_data.get('filePath', ''),
            input_data.get('userClaimInput', {}),
            input_data.get('blurAssessment', {}),
        )
        print('__AGENT_JSON_START__')
        print(json.dumps(result))
        print('__AGENT_JSON_END__')
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
