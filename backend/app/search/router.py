from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.search.service import SearchService
from app.search.schemas import (
    SearchResponse,
    IssueSearchResult,
    ArticleSearchResult,
    ContentSearchResult,
    SuggestResponse,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_all(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(20, ge=1, le=50, description="결과 수"),
    db: AsyncSession = Depends(get_async_session)
):
    """통합 검색 - 이슈, 기사, 콘텐츠 모두 검색"""
    service = SearchService(db)
    results = await service.search_all(q, limit=limit)

    return SearchResponse(
        query=q,
        issues=[IssueSearchResult(**i) for i in results["issues"]],
        articles=[ArticleSearchResult(**a) for a in results["articles"]],
        contents=[ContentSearchResult(**c) for c in results["contents"]],
        total=results["total"]
    )


@router.get("/issues", response_model=list[IssueSearchResult])
async def search_issues(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session)
):
    """이슈 벡터 검색"""
    service = SearchService(db)
    results = await service.search_issues(q, limit=limit)
    return [IssueSearchResult(**r) for r in results]


@router.get("/articles", response_model=list[ArticleSearchResult])
async def search_articles(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365, description="검색 기간 (일)"),
    db: AsyncSession = Depends(get_async_session)
):
    """기사 텍스트 검색"""
    service = SearchService(db)
    results = await service.search_articles(q, limit=limit, days=days)
    return [ArticleSearchResult(**r) for r in results]


@router.get("/contents", response_model=list[ContentSearchResult])
async def search_contents(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session)
):
    """콘텐츠 벡터 검색"""
    service = SearchService(db)
    results = await service.search_contents(q, limit=limit)
    return [ContentSearchResult(**r) for r in results]


@router.get("/category/{category}", response_model=list[IssueSearchResult])
async def search_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session)
):
    """카테고리별 이슈 검색"""
    service = SearchService(db)
    results = await service.search_by_category(category, limit=limit)
    return [IssueSearchResult(**r) for r in results]


@router.get("/suggest", response_model=SuggestResponse)
async def suggest(
    q: str = Query(..., min_length=1, description="검색어"),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_async_session)
):
    """검색어 자동완성 제안"""
    service = SearchService(db)
    suggestions = await service.suggest(q, limit=limit)
    return SuggestResponse(query=q, suggestions=suggestions)
