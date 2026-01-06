# app/issues/schemas.py
from datetime import datetime, date

from app.common.schema import BaseSchema


# ===== Entity =====

class EntityResponse(BaseSchema):
    id: str
    name: str
    type: str  # person, org, loc
    aliases: list[str] = []


class EntityCreate(BaseSchema):
    name: str
    type: str
    aliases: list[str] = []


# ===== Article =====

class IssueArticleResponse(BaseSchema):
    id: str
    title: str
    description: str | None
    url: str
    press: str | None
    source: str | None
    published_at: datetime | None
    collected_at: datetime
    status: str
    entities: dict = {}


class IssueArticleCreate(BaseSchema):
    title: str
    url: str
    description: str | None = None
    press: str | None = None
    source: str | None = None
    published_at: datetime | None = None


# ===== Content =====

class IssueContentResponse(BaseSchema):
    id: str
    title: str | None
    content: str | None
    verified: bool
    confidence_score: float
    created_at: datetime


# ===== Issue =====

class IssueResponse(BaseSchema):
    id: str
    name: str
    category: str | None
    what_type: str | None
    what_summary: str | None
    first_seen_at: date | None
    last_seen_at: date | None
    status: str


class IssueCreate(BaseSchema):
    name: str
    category: str | None = None
    what_type: str | None = None
    what_summary: str | None = None


class IssueListItem(IssueResponse):
    article_count: int = 0
    has_content: bool = False
    is_following: bool = False
    primary_entities: list[EntityResponse] = []


class IssueListResponse(BaseSchema):
    items: list[IssueListItem]
    total: int
    page: int
    size: int


class IssueDetailResponse(IssueResponse):
    articles: list[IssueArticleResponse] = []
    contents: list[IssueContentResponse] = []
    entities: list[EntityResponse] = []
    keywords: list[str] = []
    is_following: bool = False


# ===== Daily Report =====

class DailyReportIssue(BaseSchema):
    id: str
    name: str
    category: str | None
    what_type: str | None
    article_count: int
    articles: list[IssueArticleResponse] = []


class DailyReportResponse(BaseSchema):
    date: date
    issues: list[DailyReportIssue]
    total_issues: int
    total_articles: int


# ===== Daily Digest =====

class DigestIssueItem(BaseSchema):
    id: str
    name: str
    category: str | None
    what_type: str | None
    article_count: int
    summary: str | None = None
    content_title: str | None = None
    content_preview: str | None = None
    is_new: bool = False
    primary_entities: list[EntityResponse] = []


class DigestCategoryGroup(BaseSchema):
    category: str
    issues: list[DigestIssueItem]
    total_articles: int


class DailyDigestResponse(BaseSchema):
    date: date
    total_issues: int
    total_articles: int
    new_issues_count: int
    categories: list[DigestCategoryGroup]
    updated_at: datetime | None = None
    digest_summary: str | None = None
    issue_map: dict[str, str] | None = None  # 이슈 이름 -> ID 매핑 (브리핑 링크 생성용)


# ===== Calendar =====

class CalendarIssueResponse(BaseSchema):
    id: str
    name: str
    category: str | None
    first_seen_at: date | None
    last_seen_at: date | None
    display_date: date | None  # 달력 표시용 날짜 (created_at vs first_seen_at 크로스체크)
    article_count: int = 0  # 기사 수


# ===== NER Result =====

class NERResult(BaseSchema):
    who: list[dict] = []  # [{"name": "윤석열", "role": "대통령"}]
    where: list[str] = []
    what_type: str | None = None
    what_summary: str | None = None
