import React from 'react';
import { Icons } from './icons';

export function renderStatusBadge(status) {
  switch (status) {
    case 'PASS':
      return <span className="status-badge badge-pass">Pass</span>;
    case 'FAIL_MISMATCH':
      return <span className="status-badge badge-fail">Mismatch</span>;
    case 'FAIL_POLICY_VIOLATION':
      return <span className="status-badge badge-violation">Policy Violation</span>;
    case 'FAIL_DUPLICATE_INVOICE':
      return <span className="status-badge badge-fraud">Duplicate Fraud</span>;
    case 'FAIL_IRRELEVANT_DOCUMENT':
      return <span className="status-badge badge-irrelevant">Irrelevant Document</span>;
    case 'FLAGGED_LOW_CONFIDENCE':
      return <span className="status-badge badge-low-conf">Low Confidence</span>;
    default:
      return <span className="status-badge">{status}</span>;
  }
}

export function CheckerMatrix({ checker }) {
  if (!checker || !checker.checks) return null;

  return (
    <div className="checker-matrix-card">
      <div className="matrix-header">
        <div className="matrix-title">
          <Icons.ShieldCheck />
          <span>Checker Agent: Field-by-Field Verification Matrix</span>
        </div>
        <div className={`matrix-status-pill ${checker.all_checks_passed ? 'pill-passed' : 'pill-failed'}`}>
          {checker.all_checks_passed ? 'All Checks Passed' : 'Issues Flagged'}
        </div>
      </div>

      <div className="matrix-table-container">
        <table className="matrix-table">
          <thead>
            <tr>
              <th>Check Name</th>
              <th>Claimed Input</th>
              <th>Invoice</th>
              <th>Status</th>
              <th>Evaluation Details</th>
            </tr>
          </thead>
          <tbody>
            {checker.checks.map((c, i) => (
              <tr key={i} className={`row-status-${(c.status || '').toLowerCase()}`}>
                <td className="cell-name">
                  <strong>{c.check_name}</strong>
                </td>
                <td className="cell-claimed">{String(c.claimed_value || '—')}</td>
                <td className="cell-extracted">{String(c.extracted_value || '—')}</td>
                <td className="cell-badge">{renderStatusBadge(c.status)}</td>
                <td className="cell-reason">{c.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
