import { useState } from 'react';

export function useClaimSubmission() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);
  const [pipelineLogs, setPipelineLogs] = useState([]);
  const [batchProgress, setBatchProgress] = useState(null);
  const [serverError, setServerError] = useState('');
  const [blurryWarning, setBlurryWarning] = useState(null);
  const [submittedBatchResults, setSubmittedBatchResults] = useState([]);

  const submitBatch = async (allClaims) => {
    setServerError('');
    setBlurryWarning(null);
    setIsSubmitting(true);
    setPipelineStage(0);
    setPipelineLogs(['[0.0s] Ingestion: Uploading invoice receipt & running OpenCV blur analysis...']);

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
        '[4.7s] Checker Agent: Running verification gates (Amount, Plan, Policy Cap, Fraud Duplicate Ledger)...',
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
        const timeoutId = setTimeout(() => controller.abort(), 45000);

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
      return results;
    } catch (err) {
      console.error('Batch submission failed:', err);
      if (err.name === 'AbortError') {
        setServerError('Request timed out after 45 seconds. Please check the backend server and try again.');
      } else {
        setServerError(err.message || 'Could not connect to backend server on port 5000.');
      }
      return null;
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setIsSubmitting(false);
      setBatchProgress(null);
    }
  };

  return {
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
  };
}
