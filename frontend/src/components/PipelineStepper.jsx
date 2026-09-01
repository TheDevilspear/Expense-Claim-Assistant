import React from 'react';
import { Icons } from './icons';

export function PipelineStepper({ pipelineStage, pipelineLogs, batchProgress }) {
  const steps = [
    { title: '1. Ingestion & Quality Analysis', sub: 'OpenCV blur & edge detection' },
    { title: '2. Maker Agent', sub: 'Spatial extraction & candidate discovery' },
    { title: '3. Checker Agent', sub: 'Policy gates, compliance & duplicate ledger' },
    { title: '4. Approver Agent', sub: 'Risk score synthesis & audit trail' },
  ];

  return (
    <div className="pipeline-overlay">
      <div className="pipeline-modal">
        <div className="pipeline-modal-header">
          <div className="pipeline-spinner-ring"></div>
          <div>
            <h3>Processing Expense Claim</h3>
            <p>Evaluating claim with Multi-Agent Pipeline</p>
          </div>
        </div>

        {batchProgress && (
          <div className="batch-progress-box">
            <div className="batch-progress-text">
              <span>
                Processing Claim {batchProgress.current} of {batchProgress.total} ({batchProgress.category} - ₹{batchProgress.amount})
              </span>
              <span>{batchProgress.percent}%</span>
            </div>
            <div className="batch-progress-bar-bg">
              <div className="batch-progress-bar-fill" style={{ width: `${batchProgress.percent}%` }}></div>
            </div>
          </div>
        )}

        <div className="pipeline-stepper">
          {steps.map((st, idx) => {
            const isCompleted = pipelineStage > idx;
            const isCurrent = pipelineStage === idx;
            return (
              <div
                key={idx}
                className={`stepper-step ${isCompleted ? 'step-completed' : ''} ${isCurrent ? 'step-active' : ''}`}
              >
                <div className="stepper-circle">
                  {isCompleted ? <Icons.CheckCircle /> : <span>{idx + 1}</span>}
                </div>
                <div className="stepper-content">
                  <strong>{st.title}</strong>
                  <span>{st.sub}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="pipeline-terminal">
          <div className="terminal-header">
            <span>LIVE PIPELINE LOGS</span>
            <div className="terminal-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
          <div className="terminal-body">
            {pipelineLogs.map((log, idx) => (
              <div key={idx} className="terminal-log-line">
                <span className="terminal-prompt">&gt;</span> {log}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
