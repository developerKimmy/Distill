import client from './client';
import type {
  IssueListItem,
  IssueDetail,
  DailyReport,
  DailyDigest,
  CalendarIssue,
  PaginatedResponse
} from '../types';
import { getStoredCategories } from '../utils/categories';

// 카테고리 파라미터 생성
const getCategoryParams = (): { categories?: string } => {
  const stored = getStoredCategories();
  if (stored.length > 0) {
    return { categories: stored.join(',') };
  }
  return {};
};

// 달력용 이슈 목록 조회 (빠른 응답)
export const getIssuesForCalendar = async (): Promise<CalendarIssue[]> => {
  const { data } = await client.get('/issues/calendar', {
    params: getCategoryParams(),
  });
  return data;
};

// 이슈 목록 조회
export const getIssues = async (page = 1, size = 20): Promise<PaginatedResponse<IssueListItem>> => {
  const { data } = await client.get('/issues', {
    params: { page, size, ...getCategoryParams() },
  });
  return data;
};

// 이슈 상세 조회
export const getIssue = async (issueId: string): Promise<IssueDetail> => {
  const { data } = await client.get(`/issues/${issueId}`);
  return data;
};

// 일간 리포트 조회
export const getDailyReport = async (date: string): Promise<DailyReport> => {
  const { data } = await client.get(`/reports/${date}`, {
    params: getCategoryParams(),
  });
  return data;
};

// 배치 실행된 날짜 목록 조회
export const getBatchDates = async (year: number, month: number): Promise<string[]> => {
  const { data } = await client.get('/reports/dates', {
    params: { year, month, ...getCategoryParams() },
  });
  return data;
};

// 이슈 팔로우
export const followIssue = async (issueId: string): Promise<{ message: string; is_following: boolean }> => {
  const { data } = await client.post(`/issues/${issueId}/follow`);
  return data;
};

// 이슈 언팔로우
export const unfollowIssue = async (issueId: string): Promise<{ message: string; is_following: boolean }> => {
  const { data } = await client.delete(`/issues/${issueId}/follow`);
  return data;
};

// 데일리 다이제스트 조회
export const getDailyDigest = async (date: string): Promise<DailyDigest> => {
  const { data } = await client.get(`/reports/digest/${date}`);
  return data;
};

// Re-export types for convenience
export type { CalendarIssue, DailyDigest, DigestCategory, DigestIssue } from '../types';
