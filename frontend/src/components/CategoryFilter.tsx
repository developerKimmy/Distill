import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AVAILABLE_CATEGORIES } from '../types';
import { getStoredCategories, setStoredCategories, isLoggedIn } from '../utils/categories';

export default function CategoryFilter() {
  const [categories, setCategories] = useState<string[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    setCategories(getStoredCategories());
  }, []);

  const handleToggle = (category: string) => {
    const updated = categories.includes(category)
      ? categories.filter((c) => c !== category)
      : [...categories, category];
    setCategories(updated);
    setStoredCategories(updated);
    // 데이터 새로고침
    queryClient.invalidateQueries({ queryKey: ['issues'] });
    queryClient.invalidateQueries({ queryKey: ['issues-calendar'] });
    queryClient.invalidateQueries({ queryKey: ['batchDates'] });
    queryClient.invalidateQueries({ queryKey: ['dailyReport'] });
  };

  const handleSelectAll = () => {
    const allSelected = categories.length === AVAILABLE_CATEGORIES.length;
    const updated = allSelected ? [] : [...AVAILABLE_CATEGORIES];
    setCategories(updated);
    setStoredCategories(updated);
    queryClient.invalidateQueries({ queryKey: ['issues'] });
    queryClient.invalidateQueries({ queryKey: ['issues-calendar'] });
    queryClient.invalidateQueries({ queryKey: ['batchDates'] });
    queryClient.invalidateQueries({ queryKey: ['dailyReport'] });
  };

  const displayText = categories.length === 0
    ? '전체'
    : categories.length === AVAILABLE_CATEGORIES.length
    ? '전체'
    : categories.join(', ');

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg border border-gray-200 hover:border-gray-300"
      >
        <span className="text-gray-400">필터:</span>
        <span className="max-w-32 truncate">{displayText}</span>
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 z-20 p-3">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">카테고리</span>
              <button
                onClick={handleSelectAll}
                className="text-xs text-amber-600 hover:text-amber-700"
              >
                {categories.length === AVAILABLE_CATEGORIES.length ? '전체 해제' : '전체 선택'}
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_CATEGORIES.map((category) => (
                <button
                  key={category}
                  onClick={() => handleToggle(category)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                    categories.includes(category)
                      ? 'bg-amber-100 text-amber-700 border border-amber-300'
                      : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
            {!isLoggedIn() && (
              <p className="mt-3 pt-2 border-t text-xs text-gray-500">
                로그인하면 설정이 저장됩니다
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
