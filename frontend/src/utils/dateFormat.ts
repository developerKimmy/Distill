// Date formatting utilities

/**
 * Format date as M/D (e.g., 12/28)
 */
export const formatShortDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
};

/**
 * Format date as YYYY년 M월 D일 (e.g., 2025년 12월 28일)
 */
export const formatFullDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
};

/**
 * Parse YYYY-MM-DD string to local Date (avoids UTC timezone issues)
 */
export const parseLocalDate = (dateStr: string): Date => {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
};

/**
 * Format date range as M/D ~ M/D (N일)
 */
export const formatDateRange = (startDate: string, endDate: string, days?: number): string => {
  const start = formatShortDate(startDate);
  const end = formatShortDate(endDate);
  return days ? `${start} ~ ${end} (${days}일)` : `${start} ~ ${end}`;
};
