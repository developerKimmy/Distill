import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getGlobalBatchStatus } from '../api/batch';
import { getNotificationSettings, updateNotificationSettings } from '../api/settings';
import { AVAILABLE_CATEGORIES } from '../types';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [times, setTimes] = useState<string[]>(['09:00', '18:00']);
  const [enabled, setEnabled] = useState(true);
  const [newTime, setNewTime] = useState('');
  const [categories, setCategories] = useState<string[]>([]);

  // 글로벌 배치 상태 조회 (read-only)
  const { data: batchStatus, isLoading: loadingBatch } = useQuery({
    queryKey: ['globalBatchStatus'],
    queryFn: getGlobalBatchStatus,
  });

  // 알림 설정 조회
  const { data: notificationSettings, isLoading: loadingSettings } = useQuery({
    queryKey: ['notificationSettings'],
    queryFn: getNotificationSettings,
  });

  // 서버 데이터로 초기화
  useEffect(() => {
    if (notificationSettings) {
      setEnabled(notificationSettings.enabled);
      setTimes(notificationSettings.times || []);
      setCategories(notificationSettings.categories || []);
    }
  }, [notificationSettings]);

  // 변경사항 확인
  const hasChanges = useMemo(() => {
    if (!notificationSettings) return false;

    const serverTimes = notificationSettings.times || [];
    const serverCategories = notificationSettings.categories || [];

    const timesChanged =
      times.length !== serverTimes.length ||
      times.some((t) => !serverTimes.includes(t));

    const categoriesChanged =
      categories.length !== serverCategories.length ||
      categories.some((c) => !serverCategories.includes(c));

    const enabledChanged = enabled !== notificationSettings.enabled;

    return timesChanged || categoriesChanged || enabledChanged;
  }, [notificationSettings, times, categories, enabled]);

  // 알림 설정 수정
  const updateMutation = useMutation({
    mutationFn: (data: { enabled?: boolean; times?: string[]; categories?: string[] }) =>
      updateNotificationSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationSettings'] });
    },
  });

  const handleAddTime = () => {
    if (newTime && !times.includes(newTime)) {
      const updated = [...times, newTime].sort();
      setTimes(updated);
      setNewTime('');
    }
  };

  const handleRemoveTime = (time: string) => {
    const updated = times.filter((t) => t !== time);
    setTimes(updated);
  };

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
      times,
      categories,
    });
  };

  const handleReset = () => {
    if (notificationSettings) {
      setEnabled(notificationSettings.enabled);
      setTimes(notificationSettings.times || []);
      setCategories(notificationSettings.categories || []);
    }
  };

  if (loadingBatch || loadingSettings) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">설정</h1>

      {/* 글로벌 배치 상태 (read-only) */}
      <div className="bg-gray-50 rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">배치 실행 정보</h2>
        <p className="text-sm text-gray-600 mb-2">
          이슈는 매일 다음 시간에 자동으로 수집됩니다:
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          {batchStatus?.schedule.map((time) => (
            <span
              key={time}
              className="inline-flex items-center px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm font-medium"
            >
              {time}
            </span>
          ))}
        </div>
        <div className="flex justify-between text-sm text-gray-500">
          <span>마지막 실행</span>
          <span className="text-gray-900">
            {batchStatus?.lastRunAt
              ? new Date(batchStatus.lastRunAt).toLocaleString('ko-KR')
              : '없음'}
          </span>
        </div>
        <div className="flex justify-between text-sm text-gray-500 mt-1">
          <span>총 실행 횟수</span>
          <span className="text-gray-900">{batchStatus?.totalRuns ?? 0}회</span>
        </div>
      </div>

      {/* 알림 설정 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-800">이메일 알림 설정</h2>

        {/* ON/OFF 토글 */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-gray-900">이메일 알림 받기</p>
            <p className="text-sm text-gray-500">
              새로운 이슈가 수집되면 이메일로 알림을 받습니다.
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

        {/* 알림 시간 목록 (enabled일 때만 표시) */}
        {enabled && (
          <div>
            <p className="font-medium text-gray-900 mb-3">알림 받을 시간</p>
            <p className="text-sm text-gray-500 mb-3">
              선택한 시간에 배치 결과 알림을 이메일로 받습니다.
            </p>
            <div className="flex flex-wrap gap-2 mb-4">
              {times.map((time) => (
                <span
                  key={time}
                  className="inline-flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-full text-sm"
                >
                  {time}
                  <button
                    onClick={() => handleRemoveTime(time)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    x
                  </button>
                </span>
              ))}
              {times.length === 0 && (
                <span className="text-sm text-gray-500">설정된 시간이 없습니다.</span>
              )}
            </div>

            {/* 시간 추가 */}
            <div className="flex gap-2">
              <input
                type="time"
                value={newTime}
                onChange={(e) => setNewTime(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
              <button
                onClick={handleAddTime}
                disabled={!newTime}
                className="px-4 py-2 bg-gray-600 text-white text-sm rounded-lg hover:bg-gray-700 disabled:opacity-50"
              >
                추가
              </button>
            </div>
          </div>
        )}

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
