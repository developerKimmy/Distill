import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getBatchStatus, updateBatchSchedule, startBatch, stopBatch, runBatch } from '../api/batch';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [times, setTimes] = useState<string[]>(['09:00', '18:00']);
  const [newTime, setNewTime] = useState('');

  const { data: batchStatus, isLoading } = useQuery({
    queryKey: ['batchStatus'],
    queryFn: getBatchStatus,
  });

  // 서버 데이터로 초기화
  useEffect(() => {
    if (batchStatus?.schedule?.times) {
      setTimes(batchStatus.schedule.times);
    }
  }, [batchStatus]);

  // 배치 활성화
  const startMutation = useMutation({
    mutationFn: () => startBatch({ times }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batchStatus'] });
    },
  });

  // 배치 비활성화
  const stopMutation = useMutation({
    mutationFn: stopBatch,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batchStatus'] });
    },
  });

  // 스케줄 업데이트
  const scheduleMutation = useMutation({
    mutationFn: (newTimes: string[]) => updateBatchSchedule({ times: newTimes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batchStatus'] });
    },
  });

  // 즉시 실행
  const runMutation = useMutation({
    mutationFn: runBatch,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batchStatus'] });
    },
  });

  const handleAddTime = () => {
    if (newTime && !times.includes(newTime)) {
      const updated = [...times, newTime].sort();
      setTimes(updated);
      setNewTime('');
      scheduleMutation.mutate(updated);
    }
  };

  const handleRemoveTime = (time: string) => {
    const updated = times.filter((t) => t !== time);
    setTimes(updated);
    scheduleMutation.mutate(updated);
  };

  const handleToggle = () => {
    if (batchStatus?.isActive) {
      stopMutation.mutate();
    } else {
      startMutation.mutate();
    }
  };

  const handleRunNow = () => {
    if (confirm('지금 배치를 실행하시겠습니까? (약 2-3분 소요)')) {
      runMutation.mutate();
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">설정</h1>

      {/* 배치 설정 */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-800">배치 설정</h2>

        {/* ON/OFF 토글 */}
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-gray-900">자동 배치 실행</p>
            <p className="text-sm text-gray-500">설정된 시간에 자동으로 이슈를 수집합니다.</p>
          </div>
          <button
            onClick={handleToggle}
            className={`relative w-14 h-8 rounded-full transition-colors ${
              batchStatus?.isActive ? 'bg-blue-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`absolute top-1 w-6 h-6 bg-white rounded-full transition-transform ${
                batchStatus?.isActive ? 'left-7' : 'left-1'
              }`}
            />
          </button>
        </div>

        {/* 실행 시간 목록 */}
        <div>
          <p className="font-medium text-gray-900 mb-3">실행 시간</p>
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
                  ×
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
              disabled={!newTime}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              추가
            </button>
          </div>
        </div>

        {/* 수동 실행 */}
        <div className="pt-4 border-t border-gray-200">
          <p className="font-medium text-gray-900 mb-3">수동 실행</p>
          <button
            onClick={handleRunNow}
            disabled={runMutation.isPending}
            className="w-full py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {runMutation.isPending ? (
              <>
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                실행 중...
              </>
            ) : (
              <>🚀 지금 실행</>
            )}
          </button>
          <p className="text-sm text-gray-500 mt-2">즉시 이슈를 수집합니다. (약 2-3분 소요)</p>
        </div>

        {/* 상태 정보 */}
        <div className="pt-4 border-t border-gray-200">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">마지막 실행</span>
            <span className="text-gray-900">
              {batchStatus?.lastRunAt
                ? new Date(batchStatus.lastRunAt).toLocaleString('ko-KR')
                : '없음'}
            </span>
          </div>
          <div className="flex justify-between text-sm mt-2">
            <span className="text-gray-500">총 실행 횟수</span>
            <span className="text-gray-900">{batchStatus?.totalRuns ?? 0}회</span>
          </div>
        </div>
      </div>
    </div>
  );
}