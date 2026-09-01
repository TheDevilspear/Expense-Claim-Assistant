import React from 'react';
import { Icons } from './icons';
import { CheckerMatrix } from './CheckerMatrix';
import { AuditPanel } from './AuditPanel';
import { formatPeriodDDMMYY } from '../utils/date';

export function ResultsView({
  submittedBatchResults,
  activeClaimIndex,
  setActiveClaimIndex,
  blurryWarning,
  handleReupload,
  handleResetAll,
}) {
  if (!submittedBatchResults || submittedBatchResults.length === 0) return null;

  const currentClaimData = submittedBatchResults[activeClaimIndex] || submittedBatchResults[0];
  const maker = currentClaimData?.maker_output;
  const checker = currentClaimData?.checker_report;
  const approver = currentClaimData?.approver_decision;

  const isApproved = approver?.decision === 'AUTO_APPROVE';
  const isRejected = approver?.decision === 'AUTO_REJECT';
  const isEscalated = approver?.decision === 'ESCALATE_TO_HUMAN';

  const passedChecksCount = checker?.checks?.filter((c) => c.status === 'PASS').length || 0;
  const totalChecksCount = checker?.checks?.length || 0;

  const autoApproveCount = submittedBatchResults.filter((c) => c.approver_decision?.decision === 'AUTO_APPROVE').length;
  const escalatedCount = submittedBatchResults.filter((c) => c.approver_decision?.decision === 'ESCALATE_TO_HUMAN').length;
  const rejectedCount = submittedBatchResults.filter((c) => c.approver_decision?.decision === 'AUTO_REJECT').length;

  return (
    <div className="claim-card success-card">
      {/* Multi-Claim Batch Overview Header */}
      {submittedBatchResults.length > 1 && (
        <div className="batch-overview-card">
          <div className="batch-stat">
            <span className="batch-stat-label">Total Claims Submitted</span>
            <span className="batch-stat-val">{submittedBatchResults.length} Claims</span>
          </div>
          <div className="batch-stat-group">
            <div className="batch-stat">
              <span className="batch-stat-label" style={{ color: '#16a34a' }}>Approved</span>
              <span className="batch-stat-val">{autoApproveCount}</span>
            </div>
            <div className="batch-stat">
              <span className="batch-stat-label" style={{ color: '#2563eb' }}>Escalated</span>
              <span className="batch-stat-val">{escalatedCount}</span>
            </div>
            <div className="batch-stat">
              <span className="batch-stat-label" style={{ color: '#dc2626' }}>Rejected</span>
              <span className="batch-stat-val">{rejectedCount}</span>
            </div>
          </div>
        </div>
      )}

      {/* Batch Claims Navigation Tabs */}
      {submittedBatchResults.length > 1 && (
        <div className="batch-claims-nav">
          {submittedBatchResults.map((item, idx) => {
            const itemDec = item.approver_decision?.decision;
            return (
              <button
                key={idx}
                type="button"
                className={`batch-claim-tab ${activeClaimIndex === idx ? 'active' : ''}`}
                onClick={() => setActiveClaimIndex(idx)}
              >
                <span
                  className={`tab-status-dot ${
                    itemDec === 'AUTO_APPROVE'
                      ? 'dot-approved'
                      : itemDec === 'AUTO_REJECT'
                      ? 'dot-rejected'
                      : 'dot-escalated'
                  }`}
                ></span>
                <span>
                  Claim #{idx + 1}: ₹{item.claimedAmountINR} ({item.category?.split(' ')[0]})
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Blurry Notice */}
      {blurryWarning && (
        <div className="blur-alert-banner">
          <div className="blur-alert-icon">
            <Icons.AlertTriangle />
          </div>
          <div className="blur-alert-content">
            <strong>Action Required: Blurry Attachment Detected</strong>
            <p>{blurryWarning.message}</p>
            <button type="button" className="btn-reupload" onClick={handleReupload}>
              <Icons.Refresh /> Re-upload Clear Attachment
            </button>
          </div>
        </div>
      )}

      {/* Approver Agent Final Decision Banner */}
      {approver ? (
        <div
          className={`decision-banner ${
            isApproved ? 'banner-approved' : isRejected ? 'banner-rejected' : 'banner-escalated'
          }`}
        >
          <div className="decision-banner-icon">
            {isApproved && <Icons.CheckCircle />}
            {isRejected && <Icons.XCircle />}
            {isEscalated && <Icons.HelpCircle />}
          </div>
          <div className="decision-banner-text">
            <div className="decision-status-title">
              {isApproved && 'Claim Approved'}
              {isRejected && 'Claim Rejected'}
              {isEscalated && 'Claim Escalated to Human Review'}
            </div>
            <p className="decision-user-reason">{approver.actionable_user_reason}</p>
            <div className="decision-meta-tags">
              <span className="decision-tag">Risk Score: {(approver.risk_score * 100).toFixed(0)}%</span>
              {approver.escalation_tags?.map((t, idx) => (
                <span key={idx} className="decision-tag tag-detail">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="server-error-banner">
          <strong>Warning:</strong> Agent pipeline decision data was not returned by the backend.
        </div>
      )}

      {/* Visual Multi-Agent Handoff Pipeline */}
      {(maker || checker || approver) && (
        <div className="pipeline-card">
          <div className="pipeline-header">
            <div className="pipeline-title">
              <Icons.Bot />
              <span>Multi-Agent Handoff & Processing Pipeline</span>
            </div>
          </div>
          <div className="pipeline-steps-grid">
            {/* 1. Maker Agent */}
            <div className="pipeline-stage-box">
              <div className="stage-badge-row">
                <span className="stage-role-tag">
                  <Icons.Bot /> 1. Maker
                </span>
                <span className="stage-status-chip chip-success">Extracted</span>
              </div>
              <div className="stage-details">
                <div><strong>Vendor:</strong> {maker?.extracted_invoice?.vendor_name?.value || '—'}</div>
                <div><strong>Extracted Amt:</strong> ₹{maker?.extracted_invoice?.total_amount_inr?.value != null ? Number(maker.extracted_invoice.total_amount_inr.value).toFixed(2) : '—'}</div>
                <div><strong>Confidence:</strong> {maker?.extracted_invoice?.total_amount_inr?.confidence != null ? `${Math.round(maker.extracted_invoice.total_amount_inr.confidence * 100)}%` : '—'}</div>
                {maker?.extracted_invoice?.international_roaming_charges?.value != null && (
                  <div style={{ color: '#d97706' }}><strong>Int'l Roaming:</strong> ₹{Number(maker.extracted_invoice.international_roaming_charges.value).toFixed(2)}</div>
                )}
              </div>
            </div>

            <div className="pipeline-arrow">➔</div>

            {/* 2. Checker Agent */}
            <div className="pipeline-stage-box">
              <div className="stage-badge-row">
                <span className="stage-role-tag">
                  <Icons.ShieldCheck /> 2. Checker
                </span>
                <span className={`stage-status-chip ${checker?.all_checks_passed ? 'chip-success' : 'chip-danger'}`}>
                  {checker?.all_checks_passed ? 'Passed' : 'Flagged'}
                </span>
              </div>
              <div className="stage-details">
                <div><strong>Compliance:</strong> {passedChecksCount} / {totalChecksCount} Checks</div>
                <div><strong>Cap Check:</strong> {checker?.has_policy_violation ? 'Exceeded' : 'Under ₹5k'}</div>
                <div><strong>Duplicate:</strong> {checker?.has_duplicate_fraud ? 'Flagged' : 'Clean'}</div>
              </div>
            </div>

            <div className="pipeline-arrow">➔</div>

            {/* 3. Approver Agent */}
            <div className="pipeline-stage-box">
              <div className="stage-badge-row">
                <span className="stage-role-tag">
                  <Icons.Stamp /> 3. Approver
                </span>
                <span className={`stage-status-chip ${isApproved ? 'chip-success' : isRejected ? 'chip-danger' : 'chip-warning'}`}>
                  {approver?.decision || 'Evaluated'}
                </span>
              </div>
              <div className="stage-details">
                <div><strong>Verdict:</strong> {isApproved ? 'Auto-Approved' : isRejected ? 'Rejected' : 'Escalated'}</div>
                <div><strong>Risk Score:</strong> {approver?.risk_score != null ? `${Math.round(approver.risk_score * 100)}%` : '—'}</div>
                <div><strong>Human Review:</strong> {approver?.requires_human_action ? 'Yes' : 'No'}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Claim Summary */}
      <div className="summary-box">
        <div className="summary-row">
          <span className="summary-label">Claim Reference ID:</span>
          <span className="summary-value highlight">{currentClaimData.id}</span>
        </div>
        <div className="summary-row">
          <span className="summary-label">Claimed Amount:</span>
          <span className="summary-value">₹{currentClaimData.claimedAmountINR}</span>
        </div>
        <div className="summary-row">
          <span className="summary-label">Claimed Category:</span>
          <span className="summary-value">{currentClaimData.category}</span>
        </div>
        <div className="summary-row">
          <span className="summary-label">Invoice Verified Plan:</span>
          <span className="summary-value" style={{ color: '#4f46e5', fontWeight: 700 }}>
            {(() => {
              const val = String(maker?.extracted_invoice?.bill_type?.value || maker?.extracted_invoice?.bill_type?.raw_text || '').toUpperCase();
              if (val.includes('PREPAID')) return 'Prepaid';
              if (val.includes('POSTPAID') || val.includes('BROADBAND') || val.includes('FIBER')) return 'Postpaid';
              return maker?.extracted_invoice?.bill_type?.raw_text || maker?.extracted_invoice?.bill_type?.value || 'Unspecified';
            })()}
          </span>
        </div>
        {maker?.extracted_invoice?.international_roaming_charges?.value != null && (
          <div className="summary-row">
            <span className="summary-label">International Roaming / Calling:</span>
            <span className="summary-value" style={{ color: '#d97706', fontWeight: 700 }}>
              ₹{Number(maker.extracted_invoice.international_roaming_charges.value).toFixed(2)}
              {maker.extracted_invoice.international_roaming_charges.raw_text ? ` (${maker.extracted_invoice.international_roaming_charges.raw_text})` : ''}
            </span>
          </div>
        )}
        <div className="summary-row">
          <span className="summary-label">Billing Period:</span>
          <span className="summary-value">{formatPeriodDDMMYY(currentClaimData.billingPeriod)}</span>
        </div>
        <div className="summary-row">
          <span className="summary-label">Validity:</span>
          <span className="summary-value validity-badge">{currentClaimData.validity}</span>
        </div>
      </div>

      {/* Verification Matrix */}
      <CheckerMatrix checker={checker} />

      {/* Audit Panel */}
      <AuditPanel claimData={currentClaimData} />

      <div className="form-actions">
        <button type="button" className="btn-primary" onClick={handleResetAll}>
          Submit Another Claim
        </button>
      </div>
    </div>
  );
}
