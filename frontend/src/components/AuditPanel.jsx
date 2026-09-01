import React, { useState } from 'react';
import { Icons } from './icons';

export function AuditPanel({ claimData }) {
  const [activeAuditTab, setActiveAuditTab] = useState('approver');
  const [copiedAudit, setCopiedAudit] = useState(false);

  if (!claimData || (!claimData.maker_output && !claimData.checker_report && !claimData.approver_decision)) {
    return null;
  }

  const handleCopyAudit = () => {
    let targetObj = claimData?.approver_decision;
    if (activeAuditTab === 'checker') targetObj = claimData?.checker_report;
    if (activeAuditTab === 'maker') targetObj = claimData?.maker_output;

    if (targetObj) {
      navigator.clipboard.writeText(JSON.stringify(targetObj, null, 2));
      setCopiedAudit(true);
      setTimeout(() => setCopiedAudit(false), 2000);
    }
  };

  const currentPayload =
    activeAuditTab === 'approver'
      ? claimData.approver_decision
      : activeAuditTab === 'checker'
      ? claimData.checker_report
      : claimData.maker_output;

  return (
    <div className="audit-codebox-container">
      <div className="audit-codebox-header">
        <div className="audit-tabs">
          <button
            type="button"
            className={`audit-tab-btn ${activeAuditTab === 'approver' ? 'active' : ''}`}
            onClick={() => setActiveAuditTab('approver')}
          >
            <Icons.Stamp /> Approver Decision JSON
          </button>
          <button
            type="button"
            className={`audit-tab-btn ${activeAuditTab === 'checker' ? 'active' : ''}`}
            onClick={() => setActiveAuditTab('checker')}
          >
            <Icons.ShieldCheck /> Checker Report JSON
          </button>
          <button
            type="button"
            className={`audit-tab-btn ${activeAuditTab === 'maker' ? 'active' : ''}`}
            onClick={() => setActiveAuditTab('maker')}
          >
            <Icons.Bot /> Maker Output JSON
          </button>
        </div>
        <button type="button" className="btn-copy-audit" onClick={handleCopyAudit}>
          <Icons.Copy /> {copiedAudit ? 'Copied' : 'Copy JSON'}
        </button>
      </div>
      <div className="audit-codebox-body">
        <pre>
          <code>{JSON.stringify(currentPayload, null, 2)}</code>
        </pre>
      </div>
    </div>
  );
}
