import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getNotificationSettings, updateNotificationSettings } from '../api/settings';
import { AVAILABLE_CATEGORIES } from '../types';
import { setStoredCategories } from '../utils/categories';
import { useInvalidateCategoryQueries } from '../hooks';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const invalidateCategoryQueries = useInvalidateCategoryQueries();
  const [enabled, setEnabled] = useState(true);
  const [categories, setCategories] = useState<string[]>([]);

  // 알림 설정 조회
  const { data: notificationSettings, isLoading: loadingSettings } = useQuery({
    queryKey: ['notificationSettings'],
    queryFn: getNotificationSettings,
  });

  // 서버 데이터로 초기화
  useEffect(() => {
    if (notificationSettings) {
      setEnabled(notificationSettings.enabled);
      setCategories(notificationSettings.categories || []);
    }
  }, [notificationSettings]);

  // 변경사항 확인
  const hasChanges = useMemo(() => {
    if (!notificationSettings) return false;

    const serverCategories = notificationSettings.categories || [];

    const categoriesChanged =
      categories.length !== serverCategories.length ||
      categories.some((c) => !serverCategories.includes(c));

    const enabledChanged = enabled !== notificationSettings.enabled;

    return categoriesChanged || enabledChanged;
  }, [notificationSettings, categories, enabled]);

  // 알림 설정 수정
  const updateMutation = useMutation({
    mutationFn: (data: { enabled?: boolean; categories?: string[] }) =>
      updateNotificationSettings(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['notificationSettings'] });
      // 카테고리 변경 시 localStorage와 관련 쿼리 동기화
      if (variables.categories !== undefined) {
        setStoredCategories(variables.categories);
        invalidateCategoryQueries();
      }
    },
  });

  const handleToggle = () => {
    setEnabled(!enabled);
  };

  const handleCategoryToggle = (category: string) => {
    const updated = categories.includes(category)
      ? categories.filter((c) => c !== category)
      : [...categories, category];
    setCategories(updated);
  };

  const handleSelectAllCategories = () => {
    const allSelected = categories.length === AVAILABLE_CATEGORIES.length;
    const updated = allSelected ? [] : [...AVAILABLE_CATEGORIES];
    setCategories(updated);
  };

  const handleSave = () => {
    updateMutation.mutate({
      enabled,
      categories,
    });
  };

  const handleReset = () => {
    if (notificationSettings) {
      setEnabled(notificationSettings.enabled);
      setCategories(notificationSettings.categories || []);
    }
  };

  if (loadingSettings) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">설정</h1>

      {/* 알림 설정 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-800">이메일 알림 설정</h2>

        {/* ON/OFF 토글 */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-gray-900">이메일 알림 받기</p>
            <p className="text-sm text-gray-500">
              새로운 이슈가 발견되면 이메일로 알림을 받습니다.
            </p>
          </div>
          <button
            onClick={handleToggle}
            className={`relative w-14 h-8 rounded-full transition-colors ${
              enabled ? 'bg-amber-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-transform ${
                enabled ? 'left-7' : 'left-1'
              }`}
            />
          </button>
        </div>

        {/* 카테고리 선택 (enabled일 때만 표시) */}
        {enabled && (
          <div className="border-t border-gray-200 pt-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="font-medium text-gray-900">알림 받을 카테고리</p>
                <p className="text-sm text-gray-500">
                  선택한 카테고리의 이슈만 알림을 받습니다.
                </p>
              </div>
              <button
                onClick={handleSelectAllCategories}
                className="text-sm text-amber-600 hover:text-amber-700 font-medium"
              >
                {categories.length === AVAILABLE_CATEGORIES.length ? '전체 해제' : '전체 선택'}
              </button>
            </div>
            <div className="flex flex-wrap gap-3">
              {AVAILABLE_CATEGORIES.map((category) => (
                <button
                  key={category}
                  onClick={() => handleCategoryToggle(category)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    categories.includes(category)
                      ? 'bg-amber-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
            {categories.length === 0 && (
              <p className="text-sm text-amber-600 mt-3">
                카테고리를 선택하지 않으면 모든 카테고리의 알림을 받습니다.
              </p>
            )}
          </div>
        )}

        {/* 저장 버튼 */}
        {hasChanges && (
          <div className="border-t border-gray-200 pt-6 flex items-center justify-between">
            <p className="text-sm text-gray-500">변경사항이 있습니다.</p>
            <div className="flex gap-3">
              <button
                onClick={handleReset}
                disabled={updateMutation.isPending}
                className="px-4 py-2 text-gray-600 text-sm rounded-lg hover:bg-gray-100 disabled:opacity-50"
              >
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="px-6 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                {updateMutation.isPending ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        )}

        {/* 저장 성공 메시지 */}
        {updateMutation.isSuccess && !hasChanges && (
          <div className="border-t border-gray-200 pt-6">
            <p className="text-sm text-green-600">설정이 저장되었습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
