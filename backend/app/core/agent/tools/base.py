from abc import ABC, abstractmethod
from typing import TypedDict


class SearchResult(TypedDict):
    """검색 결과 구조"""
    title: str
    url: str
    snippet: str
    source_type: str
    score: float
    published_date: str | None


class TrendItem(TypedDict):
    """트렌드 아이템 구조"""
    title: str
    url: str
    channel_name: str
    channel_id: str
    video_id: str
    view_count: int
    like_count: int
    comment_count: int
    published_at: str
    thumbnail_url: str
    description: str
    tags: list[str]


class CommentItem(TypedDict):
    """댓글 구조"""
    text: str
    like_count: int
    author: str
    published_at: str


class SearchProvider(ABC):
    """검색 Provider 인터페이스"""

    @property
    @abstractmethod
    def source_type(self) -> str:
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        pass


class TrendProvider(ABC):
    """트렌드 Provider 인터페이스"""

    @property
    @abstractmethod
    def source_type(self) -> str:
        pass

    @abstractmethod
    async def get_trending(self, country: str, max_results: int = 50) -> list[TrendItem]:
        pass