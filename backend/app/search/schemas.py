from datetime import datetime
from pydantic import BaseModel, Field


class IssueSearchResult(BaseModel):
    id: str
    name: str
    category: str | None
    what_type: str | None = Field(default=None, alias="whatType", serialization_alias="whatType")
    what_summary: str | None = Field(default=None, alias="whatSummary", serialization_alias="whatSummary")
    first_seen_at: str | None = Field(default=None, alias="firstSeenAt", serialization_alias="firstSeenAt")
    last_seen_at: str | None = Field(default=None, alias="lastSeenAt", serialization_alias="lastSeenAt")
    status: str | None = None
    article_count: int | None = Field(default=None, alias="articleCount", serialization_alias="articleCount")
    has_content: bool | None = Field(default=None, alias="hasContent", serialization_alias="hasContent")
    similarity: float | None = None

    model_config = {"populate_by_name": True}


class ArticleSearchResult(BaseModel):
    id: str
    title: str
    description: str | None
    url: str
    press: str | None
    published_at: str | None = Field(default=None, alias="publishedAt", serialization_alias="publishedAt")
    collected_at: str | None = Field(default=None, alias="collectedAt", serialization_alias="collectedAt")
    issue_id: str = Field(alias="issueId", serialization_alias="issueId")
    issue_name: str | None = Field(default=None, alias="issueName", serialization_alias="issueName")

    model_config = {"populate_by_name": True}


class ContentSearchResult(BaseModel):
    id: str
    issue_id: str = Field(alias="issueId", serialization_alias="issueId")
    issue_name: str | None = Field(default=None, alias="issueName", serialization_alias="issueName")
    title: str | None
    content_preview: str | None = Field(default=None, alias="contentPreview", serialization_alias="contentPreview")
    verified: bool | None = None
    confidence_score: float | None = Field(default=None, alias="confidenceScore", serialization_alias="confidenceScore")
    created_at: str | None = Field(default=None, alias="createdAt", serialization_alias="createdAt")
    similarity: float | None = None

    model_config = {"populate_by_name": True}


class SearchResponse(BaseModel):
    query: str
    issues: list[IssueSearchResult]
    articles: list[ArticleSearchResult]
    contents: list[ContentSearchResult]
    total: int


class SuggestResponse(BaseModel):
    query: str
    suggestions: list[str]
