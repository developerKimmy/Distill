// ===== Entity =====
export interface Entity {
  id: string;
  name: string;
  type: string; // person, org, loc
  aliases: string[];
}

// ===== Article =====
export interface IssueArticle {
  id: string;
  title: string;
  description: string | null;
  url: string;
  press: string | null;
  source: string | null;
  publishedAt: string | null;
  collectedAt: string;
  status: string;
  entities: Record<string, unknown>;
}

// ===== Content =====
export interface IssueContent {
  id: string;
  title: string | null;
  content: string | null;
  verified: boolean;
  confidenceScore: number;
  createdAt: string;
}

// ===== Issue =====
export interface Issue {
  id: string;
  name: string;
  category: string | null;
  whatType: string | null;
  whatSummary: string | null;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  status: string;
}

export interface IssueListItem extends Issue {
  articleCount: number;
  hasContent: boolean;
  isFollowing: boolean;
  primaryEntities: Entity[];
}

export interface IssueDetail extends Issue {
  articles: IssueArticle[];
  contents: IssueContent[];
  entities: Entity[];
  keywords: string[];
  isFollowing: boolean;
}

// ===== Daily Report =====
export interface DailyReportIssue {
  id: string;
  name: string;
  category: string | null;
  whatType: string | null;
  articleCount: number;
  articles: IssueArticle[];
}

export interface DailyReport {
  date: string;
  issues: DailyReportIssue[];
  totalIssues: number;
  totalArticles: number;
}

// ===== Daily Digest =====
export interface DigestIssue {
  id: string;
  name: string;
  category: string | null;
  whatType: string | null;
  articleCount: number;
  summary: string | null;
  contentTitle: string | null;
  contentPreview: string | null;
  isNew: boolean;
  primaryEntities: Entity[];
}

export interface DigestCategory {
  category: string;
  issues: DigestIssue[];
  totalArticles: number;
}

export interface DailyDigest {
  date: string;
  totalIssues: number;
  totalArticles: number;
  newIssuesCount: number;
  categories: DigestCategory[];
  updatedAt: string | null;
  digestSummary: string | null;
  issueMap: Record<string, string> | null;  // 이슈 이름 -> ID 매핑 (브리핑 링크 생성용)
}

// ===== Calendar =====
export interface CalendarIssue {
  id: string;
  name: string;
  category: string | null;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  displayDate: string | null;  // 달력 표시용 날짜 (created_at vs first_seen_at 크로스체크)
  articleCount: number;  // 기사 수
  collectedDates: string[];  // 기사가 실제 수집된 날짜 목록 (캘린더 +N 계산용)
}

// ===== Search =====
export interface IssueSearchResult {
  id: string;
  name: string;
  category: string | null;
  whatType: string | null;
  whatSummary: string | null;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  status: string | null;
  articleCount: number | null;
  hasContent: boolean | null;
  similarity: number | null;
}

export interface ArticleSearchResult {
  id: string;
  title: string;
  description: string | null;
  url: string;
  press: string | null;
  publishedAt: string | null;
  collectedAt: string | null;
  issueId: string;
  issueName: string | null;
}

export interface ContentSearchResult {
  id: string;
  issueId: string;
  issueName: string | null;
  title: string | null;
  contentPreview: string | null;
  verified: boolean | null;
  confidenceScore: number | null;
  createdAt: string | null;
  similarity: number | null;
}

export interface SearchResponse {
  query: string;
  issues: IssueSearchResult[];
  articles: ArticleSearchResult[];
  contents: ContentSearchResult[];
  total: number;
}

export interface SuggestResponse {
  query: string;
  suggestions: string[];
}

// ===== Notification =====
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

// ===== Settings =====
export interface NotificationSettings {
  enabled: boolean;
  times: string[];
  timezone: string;
  categories: string[];
  createdAt: string;
}

// ===== Batch =====
export interface GlobalBatchStatus {
  schedule: string[];
  lastRunAt: string | null;
  totalRuns: number;
  lastIssuesCreated: number;
}

// ===== API Response =====
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

// Re-export for backward compatibility
export { AVAILABLE_CATEGORIES } from '../utils/constants';
