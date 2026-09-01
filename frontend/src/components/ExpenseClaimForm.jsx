import React, { useState, useRef, useMemo } from 'react';
import './ExpenseClaimForm.css';
import { Icons } from './icons';
import { PipelineStepper } from './PipelineStepper';
import { ResultsView } from './ResultsView';
import { useClaimQueue } from '../hooks/useClaimQueue';
import { useClaimSubmission } from '../hooks/useClaimSubmission';
import { todayStr, formatDateDDMMYY, calculateValidityPeriod } from '../utils/date';

const CATEGORIES = [
  { id: 'cellphone', label: 'Cellphone Expense', icon: <Icons.Phone />, description: 'Prepaid recharge or postpaid mobile bill' },
  { id: 'broadband', label: 'Broadband / Internet', icon: <Icons.Globe />, description: 'Fiber, Wi-Fi or high-speed internet plan' },
];

export default function ExpenseClaimForm() {
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('cellphone');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [errors, setErrors] = useState({});
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef(null);

  const {
    queuedClaims,
    setQueuedClaims,
    activeClaimIndex,
    setActiveClaimIndex,
    addClaimToQueue,
    removeClaimFromQueue,
    clearQueue,
    validateBatchCrossChecks,
  } = useClaimQueue();

  const {
    isSubmitting,
    pipelineStage,
    pipelineLogs,
    batchProgress,
    serverError,
    setServerError,
    blurryWarning,
    setBlurryWarning,
    submittedBatchResults,
    setSubmittedBatchResults,
    submitBatch,
  } = useClaimSubmission();

  const validityPeriod = useMemo(() => {
    return calculateValidityPeriod(startDate, endDate);
  }, [startDate, endDate]);

  const validateAndAddFiles = (newFiles) => {
    const validFiles = [];
    const newErrors = { ...errors };
    delete newErrors.attachments;
    setBlurryWarning(null);

    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    const maxFileSize = 10 * 1024 * 1024;

    if (attachments.length + newFiles.length > 2) {
      setErrors((prev) => ({
        ...prev,
        attachments: `Maximum 2 attachments allowed. You already have ${attachments.length}.`,
      }));
      return;
    }

    for (const file of newFiles) {
      if (!allowedTypes.includes(file.type)) {
        setErrors((prev) => ({
          ...prev,
          attachments: `"${file.name}" is not supported. Please upload Images (JPG, PNG, WEBP) or PDF.`,
        }));
        return;
      }
      if (file.size > maxFileSize) {
        setErrors((prev) => ({ ...prev, attachments: `"${file.name}" exceeds 10MB limit.` }));
        return;
      }

      const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : null;
      validFiles.push({
        id: `${file.name}-${Date.now()}-${Math.random()}`,
        file,
        name: file.name,
        size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
        type: file.type,
        previewUrl,
      });
    }

    setAttachments((prev) => [...prev, ...validFiles]);
    setErrors(newErrors);
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndAddFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const handleRemoveAttachment = (idToRemove) => {
    setBlurryWarning(null);
    setAttachments((prev) => {
      const removed = prev.find((item) => item.id === idToRemove);
      if (removed && removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return prev.filter((item) => item.id !== idToRemove);
    });
  };

  const validateForm = () => {
    const errs = {};
    if (!amount || parseFloat(amount) <= 0) {
      errs.amount = 'Please enter a valid claim amount in INR (> ₹0.00).';
    }
    if (!category) errs.category = 'Please select an expense category.';

    if (!startDate) {
      errs.startDate = 'Please select the start date.';
    } else if (startDate > todayStr) {
      errs.startDate = `Start date cannot be in the future (today is ${formatDateDDMMYY(todayStr)}).`;
    }

    if (!endDate) {
      errs.endDate = 'Please select the end date.';
    } else if (endDate > todayStr) {
      errs.endDate = `End date cannot be in the future (today is ${formatDateDDMMYY(todayStr)}).`;
    } else if (startDate && endDate < startDate) {
      errs.endDate = 'End date cannot be prior to start date.';
    }

    if (validityPeriod && validityPeriod.error) {
      errs.endDate = validityPeriod.error;
    }

    if (attachments.length < 1) {
      errs.attachments = 'At least 1 invoice attachment is required.';
    } else if (attachments.length > 2) {
      errs.attachments = 'Maximum 2 attachments allowed.';
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleAddClaimToQueue = () => {
    setServerError('');
    if (!validateForm()) return;

    const newClaimDraft = {
      id: `DRAFT-${Date.now()}`,
      amount: parseFloat(amount).toFixed(2),
      category,
      startDate,
      endDate,
      validityPeriod: validityPeriod ? validityPeriod.label : '',
      attachments: [...attachments],
    };

    const combinedList = [...queuedClaims, newClaimDraft];
    const crossCheckError = validateBatchCrossChecks(combinedList);
    if (crossCheckError) {
      setServerError(crossCheckError);
      return;
    }

    addClaimToQueue(newClaimDraft);

    // Reset current form fields
    setAmount('');
    setCategory('cellphone');
    setStartDate('');
    setEndDate('');
    setAttachments([]);
    setErrors({});
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setServerError('');
    setBlurryWarning(null);

    let allClaims = [...queuedClaims];
    const isCurrentFormPartiallyFilled = amount || startDate || endDate || attachments.length > 0;
    if (isCurrentFormPartiallyFilled) {
      if (!validateForm()) return;
      const currentClaimDraft = {
        id: `DRAFT-${Date.now()}`,
        amount: parseFloat(amount).toFixed(2),
        category,
        startDate,
        endDate,
        validityPeriod: validityPeriod ? validityPeriod.label : '',
        attachments: [...attachments],
      };
      allClaims = [...queuedClaims, currentClaimDraft];
    }

    if (allClaims.length === 0) {
      validateForm();
      return;
    }

    const batchValidationError = validateBatchCrossChecks(allClaims);
    if (batchValidationError) {
      setServerError(batchValidationError);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
    await submitBatch(allClaims);
  };

  const handleResetAll = () => {
    attachments.forEach((a) => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
    });
    clearQueue();
    setAmount('');
    setCategory('cellphone');
    setStartDate('');
    setEndDate('');
    setAttachments([]);
    setErrors({});
    setServerError('');
    setBlurryWarning(null);
    setSubmittedBatchResults([]);
  };

  const handleReupload = () => {
    attachments.forEach((a) => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
    });
    setAttachments([]);
    setBlurryWarning(null);
    setSubmittedBatchResults([]);
  };

  if (submittedBatchResults.length > 0) {
    return (
      <ResultsView
        submittedBatchResults={submittedBatchResults}
        activeClaimIndex={activeClaimIndex}
        setActiveClaimIndex={setActiveClaimIndex}
        blurryWarning={blurryWarning}
        handleReupload={handleReupload}
        handleResetAll={handleResetAll}
      />
    );
  }

  return (
    <div className="claim-card">
      <div className="card-header">
        <h2>Submit Expense Claim</h2>
        <p className="subtitle">
          Submit your cellphone recharge or broadband bill for automated multi-agent policy verification and reimbursement.
        </p>
      </div>

      {serverError && (
        <div className="server-error-banner">
          <Icons.XCircle />
          <span>{serverError}</span>
        </div>
      )}

      {queuedClaims.length > 0 && (
        <div className="queued-claims-banner">
          <div className="queued-header">
            <div className="queued-title">
              <Icons.Layers />
              <span>Multi-Claim Batch Queue ({queuedClaims.length} queued)</span>
            </div>
            <button type="button" className="btn-clear-queue" onClick={clearQueue}>
              Clear Batch
            </button>
          </div>
          <div className="queued-list">
            {queuedClaims.map((q, idx) => (
              <div key={idx} className="queued-item">
                <div className="queued-item-info">
                  <span className="queued-tag">#{idx + 1}</span>
                  <strong>₹{q.amount}</strong>
                  <span className="queued-category">
                    {q.category === 'broadband' ? 'Broadband' : 'Cellphone'}
                  </span>
                  <span className="queued-period">
                    {formatDateDDMMYY(q.startDate)} - {formatDateDDMMYY(q.endDate)}
                  </span>
                  <span className="queued-files">({q.attachments.length} attachment)</span>
                </div>
                <button
                  type="button"
                  className="btn-remove-queued"
                  onClick={() => removeClaimFromQueue(idx)}
                >
                  <Icons.Trash />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        {/* Category Selection */}
        <div className="form-group">
          <label className="form-label">Expense Category</label>
          <div className="category-grid">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                type="button"
                className={`category-card ${category === cat.id ? 'active' : ''}`}
                onClick={() => setCategory(cat.id)}
              >
                <div className="category-icon-wrapper">{cat.icon}</div>
                <div className="category-text">
                  <span className="category-title">{cat.label}</span>
                  <span className="category-desc">{cat.description}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Claim Amount */}
        <div className="form-group">
          <label htmlFor="amount" className="form-label">
            Claim Amount (INR)
          </label>
          <div className={`input-wrapper ${errors.amount ? 'has-error' : ''}`}>
            <span className="input-prefix">₹</span>
            <input
              id="amount"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="e.g. 799.00"
              value={amount}
              onChange={(e) => {
                setAmount(e.target.value);
                if (errors.amount) setErrors((prev) => ({ ...prev, amount: null }));
              }}
              className="form-input with-prefix"
            />
          </div>
          {errors.amount && <span className="field-error">{errors.amount}</span>}
        </div>

        {/* Billing Period */}
        <div className="form-group">
          <label className="form-label">Billing Period</label>
          <div className="date-grid">
            <div className="date-field">
              <label htmlFor="startDate" className="date-sublabel">
                Start Date
              </label>
              <div className={`input-wrapper ${errors.startDate ? 'has-error' : ''}`}>
                <input
                  id="startDate"
                  type="date"
                  max={todayStr}
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value);
                    if (errors.startDate) setErrors((prev) => ({ ...prev, startDate: null }));
                  }}
                  className="form-input"
                />
              </div>
              {errors.startDate && <span className="field-error">{errors.startDate}</span>}
            </div>

            <div className="date-field">
              <label htmlFor="endDate" className="date-sublabel">
                End Date
              </label>
              <div className={`input-wrapper ${errors.endDate ? 'has-error' : ''}`}>
                <input
                  id="endDate"
                  type="date"
                  max={todayStr}
                  min={startDate}
                  value={endDate}
                  onChange={(e) => {
                    setEndDate(e.target.value);
                    if (errors.endDate) setErrors((prev) => ({ ...prev, endDate: null }));
                  }}
                  className="form-input"
                />
              </div>
              {errors.endDate && <span className="field-error">{errors.endDate}</span>}
            </div>
          </div>

          {validityPeriod && !validityPeriod.error && (
            <div className="validity-banner">
              <Icons.Calendar />
              <span>
                Computed Validity: <strong>{validityPeriod.label}</strong>
              </span>
            </div>
          )}
        </div>

        {/* Attachment Upload */}
        <div className="form-group">
          <label className="form-label">Invoice Attachment (Max 2 files)</label>
          <div
            className={`dropzone ${isDragging ? 'dragging' : ''} ${errors.attachments ? 'has-error' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                validateAndAddFiles(Array.from(e.dataTransfer.files));
              }
            }}
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png,.webp"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <div className="dropzone-icon">
              <Icons.Paperclip />
            </div>
            <div className="dropzone-text">
              <strong>Click to upload</strong> or drag and drop invoice receipts here
            </div>
            <div className="dropzone-hint">Supported formats: PDF, JPG, PNG, WEBP (Max 10MB per file)</div>
          </div>
          {errors.attachments && <span className="field-error">{errors.attachments}</span>}

          {attachments.length > 0 && (
            <div className="attachments-list">
              {attachments.map((att) => (
                <div key={att.id} className="attachment-item">
                  <div className="attachment-meta">
                    {att.type === 'application/pdf' ? <Icons.FilePdf /> : <Icons.FileImage />}
                    <div className="attachment-info">
                      <span className="attachment-name">{att.name}</span>
                      <span className="attachment-size">{att.size}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-remove-file"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveAttachment(att.id);
                    }}
                  >
                    <Icons.Trash />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="form-actions-bar">
          <button type="button" className="btn-add-queue" onClick={handleAddClaimToQueue}>
            <Icons.Plus /> Add Another Claim to Batch
          </button>
          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting
              ? 'Processing Pipeline...'
              : queuedClaims.length > 0
              ? `Submit All ${queuedClaims.length + (amount ? 1 : 0)} Claims`
              : 'Submit for Approval'}
          </button>
        </div>
      </form>

      {/* Real-time Pipeline Progress Stepper Modal */}
      {isSubmitting && (
        <PipelineStepper
          pipelineStage={pipelineStage}
          pipelineLogs={pipelineLogs}
          batchProgress={batchProgress}
        />
      )}
    </div>
  );
}
