import client from './client';
import type { BatchSchedule, BatchStatus } from '../types';

// 배치 상태 조회
export const getBatchStatus = async (): Promise<BatchStatus> => {
  const { data } = await client.get('/batch/status');
  return data;
};

// 배치 활성화
export const startBatch = async (schedule?: BatchSchedule): Promise<BatchStatus> => {
  const { data } = await client.post('/batch/start', { schedule });
  return data;
};

// 배치 비활성화
export const stopBatch = async (): Promise<BatchStatus> => {
  const { data } = await client.post('/batch/stop');
  return data;
};

// 스케줄 업데이트
export const updateBatchSchedule = async (schedule: BatchSchedule): Promise<BatchStatus> => {
  const { data } = await client.put('/batch/schedule', { schedule });
  return data;
};

// 배치 수동 실행
export const runBatch = async (): Promise<{ batchRunId: string; status: string }> => {
  const { data } = await client.post('/batch/run');
  return data;
};