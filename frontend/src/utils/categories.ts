const STORAGE_KEY = 'category_filter';

export const getStoredCategories = (): string[] => {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return [];
  try {
    return JSON.parse(stored);
  } catch {
    return [];
  }
};

export const setStoredCategories = (categories: string[]): void => {
  if (categories.length === 0) {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(categories));
  }
};

export const isLoggedIn = (): boolean => {
  return !!localStorage.getItem('access_token');
};
