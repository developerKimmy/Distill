import client from './client';
import type { GlobalBatchStatus } from '../types';

// 글로벌 배치 상태 조회
export const getGlobalBatchStatus = async (): Promise<GlobalBatchStatus> => {
  const { data } = await client.get('/batch/status');
  return data;
};

// 배치 수동 실행 (개발/테스트용)
export const runBatch = async (): Promise<{ taskId: string; status: string }> => {
  const { data } = await client.post('/batch/run');
  return data;
};
