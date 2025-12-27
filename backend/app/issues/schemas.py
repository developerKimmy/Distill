# app/issues/schemas.py
from datetime import datetime, date

from app.common.schema import BaseSchema


# 기사
class IssueArticleResponse(BaseSchema):
    id: str
    title: str
    description: str | None
    url: str
    press: str | None
    published_at: datetime | None


# 생성된 콘텐츠
class IssueContentResponse(BaseSchema):
    id: str
    title: str
    content: str
    verified: bool
    confidence_score: float
    created_at: datetime


# 일간 스냅샷
class IssueDailySnapshotResponse(BaseSchema):
    id: str
    date: date
    article_count: int
    sentiment_score: float | None
    summary: str | None


# 스냅샷 + 기사 포함
class IssueDailySnapshotDetailResponse(IssueDailySnapshotResponse):
    articles: list[IssueArticleResponse]
    contents: list[IssueContentResponse] = []


# 이슈 기본 정보
class IssueResponse(BaseSchema):
    id: str
    name: str
    category: str | None
    first_seen_at: date
    last_seen_at: date
    total_snapshots: int
    status: str


# 달력용 경량 이슈 정보
class CalendarIssueResponse(BaseSchema):
    id: str
    name: str
    category: str | None
    first_seen_at: date
    last_seen_at: date


# 이슈 목록 아이템 (최신 스냅샷 정보 포함)
class IssueListItem(IssueResponse):
    latest_article_count: int | None = None
    latest_sentiment_score: float | None = None
    has_content: bool = False
    is_following: bool = False


# 이슈 목록 응답
class IssueListResponse(BaseSchema):
    items: list[IssueListItem]
    total: int
    page: int
    size: int


# 이슈 상세 (스냅샷 히스토리 포함)
class IssueDetailResponse(IssueResponse):
    snapshots: list[IssueDailySnapshotDetailResponse]
    is_following: bool = False


# 일간 리포트용 스냅샷 (이슈 정보 포함)
class DailySnapshotWithIssue(IssueDailySnapshotResponse):
    issue: IssueResponse
    articles: list[IssueArticleResponse]


# 일간 리포트 응답
class DailyReportResponse(BaseSchema):
    date: date
    snapshots: list[DailySnapshotWithIssue]
    total_issues: int