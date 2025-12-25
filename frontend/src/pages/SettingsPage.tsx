import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getGlobalBatchStatus } from '../api/batch';
import { getNotificationSettings, updateNotificationSettings } from '../api/settings';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [times, setTimes] = useState<string[]>(['09:00', '18:00']);
  const [enabled, setEnabled] = useState(true);
  const [newTime, setNewTime] = useState('');

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
    }
  }, [notificationSettings]);

  // 알림 설정 수정
  const updateMutation = useMutation({
    mutationFn: (data: { enabled?: boolean; times?: string[] }) =>
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
      updateMutation.mutate({ times: updated });
    }
  };

  const handleRemoveTime = (time: string) => {
    const updated = times.filter((t) => t !== time);
    setTimes(updated);
    updateMutation.mutate({ times: updated });
  };

  const handleToggle = () => {
    const newEnabled = !enabled;
    setEnabled(newEnabled);
    updateMutation.mutate({ enabled: newEnabled });
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
              className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium"
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
            disabled={updateMutation.isPending}
            className={`relative w-14 h-8 rounded-full transition-colors ${
              enabled ? 'bg-blue-600' : 'bg-gray-300'
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
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleAddTime}
                disabled={!newTime || updateMutation.isPending}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                추가
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
