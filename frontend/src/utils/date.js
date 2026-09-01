/**
 * Date formatting and billing period calculation utilities.
 */

export const todayStr = new Date().toISOString().split('T')[0];

export function formatDateDDMMYY(dateStr) {
  if (!dateStr) return '';
  const match = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) {
    const [, yyyy, mm, dd] = match;
    return `${dd}/${mm}/${yyyy.slice(2)}`;
  }
  return dateStr;
}

export function formatPeriodDDMMYY(periodStr) {
  if (!periodStr) return '';
  return periodStr.replace(
    /(\d{4})-(\d{2})-(\d{2})/g,
    (match, yyyy, mm, dd) => `${dd}/${mm}/${yyyy.slice(2)}`
  );
}

export function calculateValidityPeriod(startDateStr, endDateStr) {
  if (!startDateStr || !endDateStr) return null;

  if (startDateStr > todayStr) {
    return { error: `Start date cannot be in the future (Max allowed: ${formatDateDDMMYY(todayStr)}).` };
  }
  if (endDateStr > todayStr) {
    return { error: `End date cannot be in the future (Max allowed: ${formatDateDDMMYY(todayStr)}).` };
  }

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
    if (monthDiff === 12) return { label: `12 Months (Annual, ${totalDays} Days)`, days: totalDays };
  }

  return { label: `${totalDays} Days (${formatDateDDMMYY(startDateStr)} to ${formatDateDDMMYY(endDateStr)})`, days: totalDays };
}
