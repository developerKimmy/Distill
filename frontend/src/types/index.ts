// 이슈 마스터
export interface Issue {
  id: string;
  name: string;
  category: string | null;
  firstSeenAt: string;
  lastSeenAt: string;
  totalSnapshots: number;
  status: string;
  latestArticleCount?: number | null;
  latestSentimentScore?: number | null;
  hasContent?: boolean;
  isFollowing?: boolean;
}

// 일간 스냅샷
export interface IssueDailySnapshot {
  id: string;
  issueId: string;
  date: string;
  articleCount: number;
  sentimentScore: number | null;
  summary: string | null;
}

// 기사
export interface IssueArticle {
  id: string;
  title: string;
  description: string | null;
  url: string;
  press: string | null;
  publishedAt: string | null;
}

// 생성된 콘텐츠
export interface IssueContent {
  id: string;
  title: string;
  content: string;
  verified: boolean;
  confidenceScore: number;
  createdAt: string;
}

// 일간 리포트 (스냅샷 + 기사 포함)
export interface DailyReport {
  date: string;
  snapshots: (IssueDailySnapshot & {
    issue: Issue;
    articles: IssueArticle[];
  })[];
}

// 이슈 상세 (히스토리 포함)
export interface IssueDetail extends Issue {
  snapshots: (IssueDailySnapshot & {
    articles: IssueArticle[];
    contents: IssueContent[];
  })[];
  isFollowing: boolean;
}

// 글로벌 배치 상태
export interface GlobalBatchStatus {
  schedule: string[];  // 서버 배치 시간 ["06:00", "12:00", "18:00"]
  lastRunAt: string | null;
  totalRuns: number;
  lastIssuesCreated: number;
}

// 알림 설정
export interface NotificationSettings {
  enabled: boolean;
  times: string[];
  timezone: string;
  categories: string[];
  createdAt: string;  // 가입 날짜
}

// Re-export for backward compatibility (use utils/constants.ts instead)
export { AVAILABLE_CATEGORIES } from '../utils/constants';

// 알림
export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string | null;
  issueId: string | null;
  isRead: boolean;
  createdAt: string;
  issueName: string | null;
  issueCategory: string | null;
}

export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unreadCount: number;
}

// API 응답
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
