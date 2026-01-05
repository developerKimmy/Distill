from datetime import datetime
from pydantic import BaseModel


class IssueSearchResult(BaseModel):
    id: str
    name: str
    category: str | None
    what_type: str | None = None
    what_summary: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    status: str | None = None
    article_count: int | None = None
    has_content: bool | None = None
    similarity: float | None = None


class ArticleSearchResult(BaseModel):
    id: str
    title: str
    description: str | None
    url: str
    press: str | None
    published_at: str | None
    collected_at: str | None
    issue_id: str
    issue_name: str | None


class ContentSearchResult(BaseModel):
    id: str
    issue_id: str
    issue_name: str | None
    title: str | None
    content_preview: str | None
    verified: bool | None = None
    confidence_score: float | None = None
    created_at: str | None
    similarity: float | None = None


class SearchResponse(BaseModel):
    query: str
    issues: list[IssueSearchResult]
    articles: list[ArticleSearchResult]
    contents: list[ContentSearchResult]
    total: int


class SuggestResponse(BaseModel):
    query: str
    suggestions: list[str]
