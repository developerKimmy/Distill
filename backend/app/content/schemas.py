from datetime import datetime
from pydantic import BaseModel


class ContentResponse(BaseModel):
    id: str
    issue_id: str
    title: str | None
    content: str | None
    verified: bool = False
    confidence_score: float = 0.0
    created_at: datetime


class SimilarItem(BaseModel):
    id: str
    issue_id: str
    content_type: str
    content: str
    similarity: float


class SearchResultResponse(BaseModel):
    results: list[SimilarItem]
