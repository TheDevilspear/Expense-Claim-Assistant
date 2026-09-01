import React, { useState, useRef, useMemo } from 'react';
import './ExpenseClaimForm.css';

// Clean, professional SVG Icons
const Icons = {
  Phone: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="14" height="20" x="5" y="2" rx="2" ry="2"/>
      <path d="M12 18h.01"/>
    </svg>
  ),
  Globe: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/>
      <path d="M2 12h20"/>
    </svg>
  ),
  Calendar: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="18" height="18" x="3" y="4" rx="2" ry="2"/>
      <line x1="16" x2="16" y1="2" y2="6"/>
      <line x1="8" x2="8" y1="2" y2="6"/>
      <line x1="3" x2="21" y1="10" y2="10"/>
    </svg>
  ),
  Paperclip: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
    </svg>
  ),
  FilePdf: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
      <polyline points="14 2 14 8 20 8"/>
      <path d="M9 13v-1a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1h-1"/>
      <path d="M9 17v-4"/>
    </svg>
  ),
  FileImage: () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
      <circle cx="9" cy="9" r="2"/>
      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
    </svg>
  ),
  CheckCircle: () => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
      <polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
  ),
  XCircle: () => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="15" y1="9" x2="9" y2="15"/>
      <line x1="9" y1="9" x2="15" y2="15"/>
    </svg>
  ),
  AlertTriangle: () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
      <line x1="12" x2="12" y1="9" y2="13"/>
      <line x1="12" x2="12.01" y1="17" y2="17"/>
    </svg>
  ),
  HelpCircle: () => (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  Copy: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
    </svg>
  ),
  Refresh: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
      <path d="M21 3v5h-5"/>
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
      <path d="M8 16H3v5"/>
    </svg>
  ),
  Bot: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 8V4H8"/>
      <rect width="16" height="12" x="4" y="8" rx="2"/>
      <path d="M2 14h2"/>
      <path d="M20 14h2"/>
      <path d="M15 13v2"/>
      <path d="M9 13v2"/>
    </svg>
  ),
  ShieldCheck: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>
      <path d="m9 12 2 2 4-4"/>
    </svg>
  ),
  Stamp: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 22h14"/>
      <path d="M19.27 13.73A2.5 2.5 0 0 0 17.5 13h-11A2.5 2.5 0 0 0 4 15.5V17h16v-1.5c0-.66-.26-1.3-.73-1.77Z"/>
      <path d="M14 13V8.5C14 7.12 12.88 6 11.5 6S9 7.12 9 8.5V13"/>
    </svg>
  ),
  Plus: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19"/>
      <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>
  ),
  Layers: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 2 7 12 12 22 7 12 2"/>
      <polyline points="2 17 12 22 22 17"/>
      <polyline points="2 12 12 17 22 12"/>
    </svg>
  ),
  Trash: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    </svg>
  ),
};

const CATEGORIES = [
  { id: 'cellphone', label: 'Cellphone Expense', icon: <Icons.Phone />, description: 'Prepaid recharge or postpaid mobile bill' },
  { id: 'broadband', label: 'Broadband / Internet', icon: <Icons.Globe />, description: 'Fiber, Wi-Fi or high-speed internet plan' },
];

function formatDateDDMMYY(dateStr) {
  if (!dateStr) return '';
  const match = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    const [, yyyy, mm, dd] = match;
    return `${dd}/${mm}/${yyyy.slice(2)}`;
  }
  return dateStr;
}

function formatPeriodDDMMYY(periodStr) {
  if (!periodStr) return '';
  return periodStr.replace(/(\d{4})-(\d{2})-(\d{2})/g, (match, yyyy, mm, dd) => `${dd}/${mm}/${yyyy.slice(2)}`);
}



const todayStr = new Date().toISOString().split('T')[0];

function calculateValidityPeriod(startDateStr, endDateStr) {
  if (!startDateStr || !endDateStr) return null;

  if (startDateStr > todayStr) return { error: `Start date cannot be in the future (Max allowed: ${formatDateDDMMYY(todayStr)}).` };
  if (endDateStr > todayStr) return { error: `End date cannot be in the future (Max allowed: ${formatDateDDMMYY(todayStr)}).` };

  const start = new Date(startDateStr);
  const end = new Date(endDateStr);
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return null;
  if (end < start) return { error: 'End date cannot be earlier than start date.' };

  const diffTime = end.getTime() - start.getTime();
  const totalDays = Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1;

  if (totalDays > 366) return { error: 'Billing period cannot exceed 1 year (366 days).' };
  if (totalDays === 28) return { label: '28 Days (Standard 4-Week Cycle)', days: 28 };
  if (totalDays === 56) return { label: '56 Days (8 Weeks)', days: 56 };
  if (totalDays === 84) return { label: '84 Days (~3 Months / 12 Weeks)', days: 84 };
  if (totalDays === 365 || totalDays === 366) return { label: `1 Year (${totalDays} Days)`, days: totalDays };

  const monthDiff = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
  if (monthDiff > 0 && Math.abs(end.getDate() - start.getDate()) <= 2) {
    if (monthDiff === 1) return { label: `1 Month (${totalDays} Days)`, days: totalDays };
    if (monthDiff === 3) return { label: `3 Months (Quarterly, ${totalDays} Days)`, days: totalDays };
    if (monthDiff === 6) return { label: `6 Months (Half-Yearly, ${totalDays} Days)`, days: totalDays };
    if (monthDiff === 12) return { label: `1 Year (Annual, ${totalDays} Days)`, days: totalDays };
  }

  return { label: `${totalDays} Days`, days: totalDays };
}

function validateBatchCrossChecks(claimsList) {
  for (let i = 0; i < claimsList.length; i++) {
    for (let j = i + 1; j < claimsList.length; j++) {
      const a = claimsList[i];
      const b = claimsList[j];

      // 1. Overlapping Billing Period Check for same category
      if (a.category === b.category) {
        if (a.startDate <= b.endDate && b.startDate <= a.endDate) {
          const catLabel = a.category === 'broadband' ? 'Broadband' : 'Cellphone';
          return `Overlapping billing cycle detected: Claim #${i + 1} (${formatDateDDMMYY(a.startDate)} to ${formatDateDDMMYY(a.endDate)}) overlaps with Claim #${j + 1} (${formatDateDDMMYY(b.startDate)} to ${formatDateDDMMYY(bEndSafe(b))}) for ${catLabel}. Telecom policies do not allow overlapping cycles in the same category.`;
        }
      }

      // 2. Duplicate attachment check across claims
      for (const fileA of a.attachments || []) {
        for (const fileB of b.attachments || []) {
          if (fileA.file?.name === fileB.file?.name && fileA.file?.size === fileB.file?.size) {
            return `Duplicate file attached: "${fileA.name}" is attached to both Claim #${i + 1} and Claim #${j + 1}. Each claim must have unique invoice receipts.`;
          }
        }
      }
    }
  }
  return null;
}

function bEndSafe(claim) {
  return claim.endDate || '';
}

function renderStatusBadge(status) {
  switch (status) {
    case 'PASS':
      return <span className="status-badge status-pass">✓ PASS</span>;
    case 'FAIL_MISMATCH':
      return <span className="status-badge status-mismatch">✕ MISMATCH</span>;
    case 'FAIL_POLICY_VIOLATION':
      return <span className="status-badge status-policy">⚠️ POLICY CAP EXCEEDED</span>;
    case 'FAIL_DUPLICATE_INVOICE':
      return <span className="status-badge status-duplicate">🚫 DUPLICATE FRAUD</span>;
    case 'FLAGGED_LOW_CONFIDENCE':
      return <span className="status-badge status-confidence">⚠️ LOW CONFIDENCE</span>;
    case 'FAIL_IRRELEVANT_DOCUMENT':
      return <span className="status-badge status-mismatch">✕ IRRELEVANT</span>;
    default:
      return <span className="status-badge">{status}</span>;
  }
}

export default function ExpenseClaimForm() {
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('cellphone');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [attachments, setAttachments] = useState([]);
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0); // 0: Ingestion/OpenCV, 1: Maker, 2: Checker, 3: Approver
  const [pipelineLogs, setPipelineLogs] = useState([]);
  const [serverError, setServerError] = useState('');
  const [blurryWarning, setBlurryWarning] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // Multi-claim batching state
  const [queuedClaims, setQueuedClaims] = useState([]);
  const [batchProgress, setBatchProgress] = useState(null);
  const [submittedBatchResults, setSubmittedBatchResults] = useState([]);
  const [activeClaimIndex, setActiveClaimIndex] = useState(0);

  const [activeAuditTab, setActiveAuditTab] = useState('approver'); // 'approver' | 'checker' | 'maker'
  const [copiedAudit, setCopiedAudit] = useState(false);

  const fileInputRef = useRef(null);

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

    setQueuedClaims(combinedList);

    // Reset current form fields
    setAmount('');
    setCategory('cellphone');
    setStartDate('');
    setEndDate('');
    setAttachments([]);
    setErrors({});
  };

  const handleRemoveFromQueue = (indexToRemove) => {
    setServerError('');
    setQueuedClaims((prev) => {
      const removed = prev[indexToRemove];
      if (removed) {
        removed.attachments.forEach((a) => {
          if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
        });
      }
      return prev.filter((_, idx) => idx !== indexToRemove);
    });
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setServerError('');
    setBlurryWarning(null);

    // Build list of claims to process
    let allClaims = [...queuedClaims];

    // If user filled current form without pressing (+), check if it's valid to include
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

    // Run Pre-Submission Batch Validation
    const batchValidationError = validateBatchCrossChecks(allClaims);
    if (batchValidationError) {
      setServerError(batchValidationError);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
    setIsSubmitting(true);
    setPipelineStage(0);
    setPipelineLogs(['[0.0s] Ingestion: Uploading invoice receipt & running OpenCV blur analysis...']);

    // Timed pipeline stage simulator for real-time visual feedback
    const t1 = setTimeout(() => {
      setPipelineStage(1);
      setPipelineLogs((prev) => [
        ...prev,
        '[0.8s] Quality check passed: Sharpness clear (Laplacian > 100).',
        '[1.0s] Maker Agent: Extracting structured fields (Vendor, Dates, Amount, Plan nature)...',
      ]);
    }, 1000);

    const t2 = setTimeout(() => {
      setPipelineStage(2);
      setPipelineLogs((prev) => [
        ...prev,
        '[4.5s] Maker Agent complete: Extracted invoice data with per-field confidence.',
        '[4.7s] Checker Agent: Running 7 verification gates (Amount, Plan, Policy Cap, Fraud Duplicate Ledger)...',
      ]);
    }, 4500);

    const t3 = setTimeout(() => {
      setPipelineStage(3);
      setPipelineLogs((prev) => [
        ...prev,
        '[8.0s] Checker Agent complete: Verification report compiled.',
        '[8.2s] Approver Agent: Synthesizing risk score & constructing audit trail...',
      ]);
    }, 8000);

    const results = [];

    try {
      // Execute multi-claim pipeline one by one sequentially
      for (let i = 0; i < allClaims.length; i++) {
        const claim = allClaims[i];
        setBatchProgress({
          current: i + 1,
          total: allClaims.length,
          category: claim.category === 'broadband' ? 'Broadband' : 'Cellphone',
          amount: claim.amount,
          percent: Math.round(((i + 1) / allClaims.length) * 100),
        });

        const formData = new FormData();
        formData.append('claimedAmountINR', claim.amount);
        formData.append('category', claim.category);
        formData.append('startDate', claim.startDate);
        formData.append('endDate', claim.endDate);
        formData.append('validityPeriod', claim.validityPeriod || '');
        claim.attachments.forEach((item) => formData.append('invoices', item.file));

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 75000);

        const response = await fetch('/api/claims', {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        const json = await response.json();
        if (!response.ok) throw new Error(json.message || `Server failed to process Claim #${i + 1}`);

        results.push(json.data);
      }

      setSubmittedBatchResults(results);
      setActiveClaimIndex(0);
    } catch (err) {
      console.error('Batch submission failed:', err);
      if (err.name === 'AbortError') {
        setServerError('Request timed out. The document processing took longer than expected. Please retry or upload a clearer file.');
      } else {
        setServerError(err.message || 'Could not connect to backend server on port 5000.');
      }
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setIsSubmitting(false);
      setBatchProgress(null);
    }
  };

  const handleResetAll = () => {
    attachments.forEach((a) => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
    });
    queuedClaims.forEach((q) => {
      q.attachments.forEach((a) => {
        if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
      });
    });

    setAmount('');
    setCategory('cellphone');
    setStartDate('');
    setEndDate('');
    setAttachments([]);
    setErrors({});
    setQueuedClaims([]);
    setServerError('');
    setBlurryWarning(null);
    setSubmittedBatchResults([]);
    setActiveClaimIndex(0);
  };

  const handleReupload = () => {
    attachments.forEach((a) => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
    });
    setAttachments([]);
    setBlurryWarning(null);
    setSubmittedBatchResults([]);
  };

  const handleCopyAudit = (currentClaimData) => {
    let targetObj = currentClaimData?.approver_decision;
    if (activeAuditTab === 'checker') targetObj = currentClaimData?.checker_report;
    if (activeAuditTab === 'maker') targetObj = currentClaimData?.maker_output;

    if (targetObj) {
      navigator.clipboard.writeText(JSON.stringify(targetObj, null, 2));
      setCopiedAudit(true);
      setTimeout(() => setCopiedAudit(false), 2000);
    }
  };

  // -------------------------------------------------------------
  // RESULTS SCREEN: Renders Batch Overview and Active Claim Audit
  // -------------------------------------------------------------
  if (submittedBatchResults.length > 0) {
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

              {/* Handoff Arrow */}
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

              {/* Handoff Arrow */}
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

        {/* Checker Agent Verification Matrix Table */}
        {checker && checker.checks && (
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
                    <tr key={i} className={`row-status-${c.status.toLowerCase()}`}>
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
        )}

        {/* 3-Tab Live Audit Trail Code Box */}
        {(currentClaimData.maker_output || currentClaimData.checker_report || currentClaimData.approver_decision) && (
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
              <button type="button" className="btn-copy-audit" onClick={() => handleCopyAudit(currentClaimData)}>
                <Icons.Copy /> {copiedAudit ? 'Copied' : 'Copy JSON'}
              </button>
            </div>
            <div className="audit-codebox-body">
              <pre>
                <code>
                  {JSON.stringify(
                    activeAuditTab === 'approver'
                      ? currentClaimData.approver_decision
                      : activeAuditTab === 'checker'
                      ? currentClaimData.checker_report
                      : currentClaimData.maker_output,
                    null,
                    2
                  )}
                </code>
              </pre>
            </div>
          </div>
        )}

        <button type="button" className="btn-primary" onClick={handleResetAll}>
          Submit Another Claim
        </button>
      </div>
    );
  }

  // -------------------------------------------------------------
  // FORM VIEW: Submission Form + Queued Claims Section
  // -------------------------------------------------------------
  const totalClaimsReadyCount = queuedClaims.length + (amount || startDate || endDate || attachments.length > 0 ? 1 : 0);

  return (
    <div className="claim-card">
      <div className="card-header">
        <span className="badge">Telecom Reimbursement</span>
        <h1>Submit Expense Claim</h1>
        <p className="subtitle">Submit mobile or broadband bills in Indian Rupees (INR) with 1–2 invoice receipts.</p>
      </div>

      {serverError && (
        <div className="server-error-banner">
          <strong>Validation / Server Error:</strong> {serverError}
        </div>
      )}

      {/* Real-Time Agent Stepper during submission */}
      {isSubmitting && (
        <div className="agent-stepper-overlay">
          <div className="agent-stepper-box">
            {batchProgress && (
              <div className="batch-progress-header">
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600 }}>
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

            <div className="stepper-title">
              <span className="stepper-spinner"></span>
              <strong>Multi-Agent Pipeline Live (Maker ➔ Checker ➔ Approver)</strong>
            </div>

            <div className="stepper-steps">
              {/* Stage 0 */}
              <div className={`step-item ${pipelineStage === 0 ? 'active' : pipelineStage > 0 ? 'completed' : 'upcoming'}`}>
                <span className={`step-dot ${pipelineStage === 0 ? 'active' : pipelineStage > 0 ? 'completed' : ''}`}>
                  {pipelineStage > 0 ? '✓' : ''}
                </span>
                <div className="step-content">
                  <div className="step-label">
                    1. OpenCV Pre-Processing & Quality Check
                    {pipelineStage === 0 && <span className="stage-live-badge">RUNNING</span>}
                    {pipelineStage > 0 && <span className="stage-done-badge">PASSED</span>}
                  </div>
                  <div className="step-desc">Laplacian variance sharpness test & glare detection ensemble...</div>
                </div>
              </div>

              {/* Stage 1 */}
              <div className={`step-item ${pipelineStage === 1 ? 'active' : pipelineStage > 1 ? 'completed' : 'upcoming'}`}>
                <span className={`step-dot ${pipelineStage === 1 ? 'active' : pipelineStage > 1 ? 'completed' : ''}`}>
                  {pipelineStage > 1 ? '✓' : ''}
                </span>
                <div className="step-content">
                  <div className="step-label">
                    2. Maker Agent: Structured Extraction
                    {pipelineStage === 1 && <span className="stage-live-badge">EXTRACTING</span>}
                    {pipelineStage > 1 && <span className="stage-done-badge">DONE</span>}
                  </div>
                  <div className="step-desc">Extracting Vendor, Dates, Amount & Plan Nature (Prepaid vs Postpaid vs Broadband)...</div>
                </div>
              </div>

              {/* Stage 2 */}
              <div className={`step-item ${pipelineStage === 2 ? 'active' : pipelineStage > 2 ? 'completed' : 'upcoming'}`}>
                <span className={`step-dot ${pipelineStage === 2 ? 'active' : pipelineStage > 2 ? 'completed' : ''}`}>
                  {pipelineStage > 2 ? '✓' : ''}
                </span>
                <div className="step-content">
                  <div className="step-label">
                    3. Checker Agent: Policy & Fraud Verification
                    {pipelineStage === 2 && <span className="stage-live-badge">EVALUATING</span>}
                    {pipelineStage > 2 && <span className="stage-done-badge">CHECKED</span>}
                  </div>
                  <div className="step-desc">7 deterministic gates: Amount match, Category/Plan check, ₹5k policy cap, & Duplicate fraud ledger...</div>
                </div>
              </div>

              {/* Stage 3 */}
              <div className={`step-item ${pipelineStage === 3 ? 'active' : pipelineStage > 3 ? 'completed' : 'upcoming'}`}>
                <span className={`step-dot ${pipelineStage === 3 ? 'active' : pipelineStage > 3 ? 'completed' : ''}`}>
                  {pipelineStage > 3 ? '✓' : ''}
                </span>
                <div className="step-content">
                  <div className="step-label">
                    4. Approver Agent: Final Decision & Audit
                    {pipelineStage === 3 && <span className="stage-live-badge">DECIDING</span>}
                  </div>
                  <div className="step-desc">Synthesizing risk score, assembling audit rationale & generating approval status...</div>
                </div>
              </div>
            </div>

            {/* Live Activity Terminal Feed */}
            {pipelineLogs.length > 0 && (
              <div className="live-terminal-feed">
                <div className="terminal-feed-header">
                  <span>⚡ LIVE EXECUTION LOGS</span>
                </div>
                <div className="terminal-feed-body">
                  {pipelineLogs.map((log, idx) => (
                    <div key={idx} className="terminal-log-line">
                      <span className="log-arrow">›</span> {log}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Queued Draft Claims Section */}
      {queuedClaims.length > 0 && (
        <div className="queue-section">
          <div className="queue-header">
            <span className="queue-title">
              <Icons.Layers /> Ready Claims
            </span>
            <span className="queue-badge">{queuedClaims.length} queued</span>
          </div>

          <div className="queue-list">
            {queuedClaims.map((item, idx) => (
              <div key={item.id || idx} className="queue-item-card">
                <div className="queue-item-main">
                  <div className="queue-item-icon">
                    {item.category === 'broadband' ? <Icons.Globe /> : <Icons.Phone />}
                  </div>
                  <div className="queue-item-details">
                    <div className="queue-item-title">
                      <span>Claim #{idx + 1}: {item.category === 'broadband' ? 'Broadband / Internet' : 'Cellphone Expense'}</span>
                      <span className="queue-item-amount">₹{item.amount}</span>
                    </div>
                    <div className="queue-item-sub">
                      <span>Period: {formatDateDDMMYY(item.startDate)} to {formatDateDDMMYY(item.endDate)} ({item.validityPeriod})</span>
                      <span>• {item.attachments.length} attachment(s)</span>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  className="btn-remove-queue"
                  title="Remove claim"
                  onClick={() => handleRemoveFromQueue(idx)}
                >
                  <Icons.Trash /> Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="form-container">
        {/* Category Selector */}
        <div className="form-group">
          <label className="form-label">
            Expense Category <span className="req">*</span>
          </label>
          <div className="category-grid">
            {CATEGORIES.map((cat) => (
              <div
                key={cat.id}
                className={`category-card ${category === cat.id ? 'active' : ''}`}
                onClick={() => setCategory(cat.id)}
              >
                <span className="cat-icon">{cat.icon}</span>
                <div>
                  <div className="cat-title">{cat.label}</div>
                  <div className="cat-desc">{cat.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Claimed Amount (INR) */}
        <div className="form-group">
          <label htmlFor="claimedAmount" className="form-label">
            Claimed Amount (in INR ₹) <span className="req">*</span>
          </label>
          <div className="input-prefix-wrapper">
            <span className="prefix">₹</span>
            <input
              id="claimedAmount"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="e.g. 499.00"
              value={amount}
              onWheel={(e) => e.currentTarget.blur()}
              onChange={(e) => setAmount(e.target.value)}
              className={`form-input with-prefix ${errors.amount ? 'input-error' : ''}`}
            />
          </div>
          {errors.amount ? (
            <span className="error-text">{errors.amount}</span>
          ) : (
            <span className="helper-text">Enter total billed amount in Indian Rupees (₹). Policy cap: ₹5,000.00</span>
          )}
        </div>

        {/* Billing Period */}
        <div className="form-group period-box">
          <label className="form-label">
            Billing Period <span className="req">*</span>
          </label>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="startDate" className="form-sublabel">
                Start Date <span className="req">*</span>
              </label>
              <input
                id="startDate"
                type="date"
                max={todayStr}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className={`form-input ${errors.startDate ? 'input-error' : ''}`}
              />
              {errors.startDate && <span className="error-text">{errors.startDate}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="endDate" className="form-sublabel">
                End Date <span className="req">*</span>
              </label>
              <input
                id="endDate"
                type="date"
                max={todayStr}
                min={startDate || undefined}
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className={`form-input ${errors.endDate ? 'input-error' : ''}`}
              />
              {errors.endDate && <span className="error-text">{errors.endDate}</span>}
            </div>
          </div>

          {validityPeriod && !validityPeriod.error && (
            <div className="validity-banner">
              <span className="validity-icon"><Icons.Calendar /></span>
              <div className="validity-content">
                <span className="validity-title">Validity:</span>
                <span className="validity-highlight">{validityPeriod.label}</span>
              </div>
            </div>
          )}

          {validityPeriod && validityPeriod.error && (
            <span className="error-text">{validityPeriod.error}</span>
          )}
        </div>

        {/* Attachments Section */}
        <div className="form-group">
          <div className="label-with-count">
            <label className="form-label">
              Invoice Attachments (1 – 2 files) <span className="req">*</span>
            </label>
            <span className={`counter ${attachments.length > 2 ? 'counter-danger' : ''}`}>
              {attachments.length} / 2 attached
            </span>
          </div>

          {attachments.length < 2 && (
            <div
              className={`dropzone ${isDragging ? 'dragging' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files) validateAndAddFiles(Array.from(e.dataTransfer.files));
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept="image/jpeg,image/png,image/webp,application/pdf"
                multiple
                onChange={handleFileChange}
              />
              <div className="dropzone-icon"><Icons.Paperclip /></div>
              <div className="dropzone-text">
                <strong>Click to browse</strong> or drag & drop invoice receipts here
              </div>
              <div className="dropzone-hint">Supports Images (PNG, JPG, WEBP) & PDF (Max 10MB each)</div>
            </div>
          )}

          {errors.attachments && <span className="error-text">{errors.attachments}</span>}

          {attachments.length > 0 && (
            <div className="attachment-list">
              {attachments.map((item) => (
                <div key={item.id} className="attachment-item">
                  <div className="preview-container">
                    {item.previewUrl ? (
                      <img src={item.previewUrl} alt={item.name} className="img-thumbnail" />
                    ) : (
                      <span className="pdf-icon-badge"><Icons.FilePdf /></span>
                    )}
                  </div>
                  <div className="attachment-info">
                    <div className="attachment-name" title={item.name}>{item.name}</div>
                    <div className="attachment-size">{item.size}</div>
                  </div>
                  <button
                    type="button"
                    className="btn-remove"
                    title="Remove attachment"
                    onClick={() => handleRemoveAttachment(item.id)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Action Buttons: Add to Batch (+) & Submit Claims */}
        <div className="form-actions-grid">
          <button
            type="button"
            className="btn-secondary"
            disabled={isSubmitting}
            onClick={handleAddClaimToQueue}
          >
            <Icons.Plus /> Add Claim
          </button>

          <button
            type="submit"
            className="btn-primary submit-btn"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? `Processing (${batchProgress ? `${batchProgress.current}/${batchProgress.total}` : '...'})`
              : totalClaimsReadyCount > 1
              ? 'Submit Claims'
              : 'Submit Claim'}
          </button>
        </div>
      </form>
    </div>
  );
}

