from datetime import datetime
from pydantic import BaseModel


class ContentResponse(BaseModel):
    id: str
    snapshot_id: str
    title: str
    content: str
    created_at: datetime


class SimilarItem(BaseModel):
    id: str
    snapshot_id: str
    content_type: str
    content: str
    similarity: float


class SearchResultResponse(BaseModel):
    results: list[SimilarItem]