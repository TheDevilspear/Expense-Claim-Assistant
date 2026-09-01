import { useState } from 'react';
import { formatDateDDMMYY } from '../utils/date';

export function useClaimQueue() {
  const [queuedClaims, setQueuedClaims] = useState([]);
  const [activeClaimIndex, setActiveClaimIndex] = useState(0);

  const addClaimToQueue = (draftClaim) => {
    setQueuedClaims((prev) => [...prev, draftClaim]);
  };

  const removeClaimFromQueue = (indexToRemove) => {
    setQueuedClaims((prev) => {
      const removed = prev[indexToRemove];
      if (removed && removed.attachments) {
        removed.attachments.forEach((a) => {
          if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
        });
      }
      return prev.filter((_, idx) => idx !== indexToRemove);
    });
  };

  const clearQueue = () => {
    queuedClaims.forEach((q) => {
      q.attachments?.forEach((a) => {
        if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
      });
    });
    setQueuedClaims([]);
    setActiveClaimIndex(0);
  };

  const validateBatchCrossChecks = (claimsList) => {
    if (!claimsList || claimsList.length <= 1) return null;

    for (let i = 0; i < claimsList.length; i++) {
      for (let j = i + 1; j < claimsList.length; j++) {
        const c1 = claimsList[i];
        const c2 = claimsList[j];

        // Disallow identical periods within the exact same category
        if (c1.category === c2.category && c1.startDate === c2.startDate && c1.endDate === c2.endDate) {
          const catLabel = c1.category === 'broadband' ? 'Broadband' : 'Cellphone';
          return `Batch Conflict: Claim #${i + 1} and Claim #${j + 1} have the exact same ${catLabel} billing period (${formatDateDDMMYY(c1.startDate)} to ${formatDateDDMMYY(c1.endDate)}).`;
        }
      }
    }
    return null;
  };

  return {
    queuedClaims,
    setQueuedClaims,
    activeClaimIndex,
    setActiveClaimIndex,
    addClaimToQueue,
    removeClaimFromQueue,
    clearQueue,
    validateBatchCrossChecks,
  };
}
