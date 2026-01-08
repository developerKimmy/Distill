import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AVAILABLE_CATEGORIES } from '../utils/constants';
import { getStoredCategories, setStoredCategories, isLoggedIn } from '../utils/categories';
import { useInvalidateCategoryQueries } from '../hooks';
import { getNotificationSettings, updateNotificationSettings } from '../api/settings';

export default function CategoryFilter() {
  const [categories, setCategories] = useState<string[]>([]);
  const [tempCategories, setTempCategories] = useState<string[]>([]); // 임시 선택 상태
  const [isOpen, setIsOpen] = useState(false);
  const [synced, setSynced] = useState(false);
  const invalidateQueries = useInvalidateCategoryQueries();
  const queryClient = useQueryClient();
  const loggedIn = isLoggedIn();

  // 로그인 사용자: DB에서 설정 가져오기
  const { data: serverSettings } = useQuery({
    queryKey: ['notificationSettings'],
    queryFn: getNotificationSettings,
    enabled: loggedIn,
    staleTime: 1000 * 60 * 5, // 5분
  });

  // 로그인 사용자의 경우 DB 업데이트
  const updateDbMutation = useMutation({
    mutationFn: (newCategories: string[]) =>
      updateNotificationSettings({ categories: newCategories }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationSettings'] });
    },
  });

  // 초기화: 로그인 사용자는 서버 설정으로 동기화, 비로그인은 localStorage
  useEffect(() => {
    if (loggedIn && serverSettings && !synced) {
      const serverCategories = serverSettings.categories || [];
      setCategories(serverCategories);
      setStoredCategories(serverCategories);
      setSynced(true);
    } else if (!loggedIn) {
      setCategories(getStoredCategories());
    }
  }, [loggedIn, serverSettings, synced]);

  const applyCategories = (updated: string[]) => {
    setCategories(updated);
    setStoredCategories(updated);
    invalidateQueries();
    // 로그인 사용자면 DB도 업데이트
    if (isLoggedIn()) {
      updateDbMutation.mutate(updated);
    }
  };

  const handleToggle = (category: string) => {
    setTempCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const handleSelectAll = () => {
    const allSelected = tempCategories.length === AVAILABLE_CATEGORIES.length;
    setTempCategories(allSelected ? [] : [...AVAILABLE_CATEGORIES]);
  };

  const handleApply = () => {
    applyCategories(tempCategories);
    setIsOpen(false);
  };

  const toggleOpen = () => {
    if (!isOpen) {
      // 열 때 현재 값으로 임시 상태 초기화
      setTempCategories([...categories]);
    }
    setIsOpen((prev) => !prev);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  // 변경사항 있는지 확인
  const hasChanges =
    tempCategories.length !== categories.length ||
    tempCategories.some((c) => !categories.includes(c));

  const displayText =
    categories.length === 0 || categories.length === AVAILABLE_CATEGORIES.length
      ? '전체'
      : categories.join(', ');

  return (
    <div className="relative">
      <button
        onClick={toggleOpen}
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
          <div className="fixed inset-0 z-10" onClick={closeDropdown} />
          <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 z-20 p-3">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">카테고리</span>
              <button
                onClick={handleSelectAll}
                className="text-xs text-amber-600 hover:text-amber-700"
              >
                {tempCategories.length === AVAILABLE_CATEGORIES.length ? '전체 해제' : '전체 선택'}
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {AVAILABLE_CATEGORIES.map((category) => (
                <button
                  key={category}
                  onClick={() => handleToggle(category)}
                  className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                    tempCategories.includes(category)
                      ? 'bg-amber-100 text-amber-700 border border-amber-300'
                      : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
            {/* 확인 버튼 */}
            <div className="mt-3 pt-2 border-t">
              {!loggedIn && (
                <p className="text-xs text-gray-500 mb-2">로그인하면 설정이 저장됩니다</p>
              )}
              <button
                onClick={handleApply}
                disabled={!hasChanges}
                className={`w-full py-1.5 text-xs font-medium rounded transition-colors ${
                  hasChanges
                    ? 'bg-amber-500 text-white hover:bg-amber-600'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                확인
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
