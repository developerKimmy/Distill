// 이슈 마스터
export interface Issue {
  id: string;
  name: string;
  category: string | null;
  firstSeenAt: string;
  lastSeenAt: string;
  totalSnapshots: number;
  status: string;
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
  })[];
}

// 배치 스케줄
export interface BatchSchedule {
  times: string[];
  timezone?: string;
}

// 수정 (camelCase) - 백엔드 응답이랑 일치
export interface BatchStatus {
  isActive: boolean;
  schedule: BatchSchedule | null;
  lastRunAt: string | null;
  nextRunAt: string | null;
  totalRuns: number;
}

// API 응답
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}