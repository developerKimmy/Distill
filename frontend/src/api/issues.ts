import client from './client';
import type { Issue, IssueDetail, DailyReport, PaginatedResponse } from '../types';

// 이슈 목록 조회
export const getIssues = async (page = 1, size = 20): Promise<PaginatedResponse<Issue>> => {
  const { data } = await client.get('/issues', {
    params: { page, size },
  });
  return data;
};

// 이슈 상세 조회 (히스토리 포함)
export const getIssue = async (issueId: string): Promise<IssueDetail> => {
  const { data } = await client.get(`/issues/${issueId}`);
  return data;
};

// 일간 리포트 조회
export const getDailyReport = async (date: string): Promise<DailyReport> => {
  const { data } = await client.get(`/reports/${date}`);
  return data;
};

// 배치 실행된 날짜 목록 조회
export const getBatchDates = async (year: number, month: number): Promise<string[]> => {
  const { data } = await client.get('/reports/dates', {
    params: { year, month },
  });
  return data;
};