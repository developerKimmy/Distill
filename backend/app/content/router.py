from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.core.database import get_async_session
from app.content.service import ContentService
from app.content.schemas import ContentResponse, SearchResultResponse

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/issue/{issue_id}", response_model=ContentResponse)
async def get_content_by_issue(
    issue_id: UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """이슈의 최신 콘텐츠 조회"""
    service = ContentService(db)
    content = await service.get_content(issue_id)

    if not content:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")

    return ContentResponse(
        id=str(content.id),
        issue_id=str(content.issue_id),
        title=content.title,
        content=content.content,
        verified=content.verified,
        confidence_score=content.confidence_score,
        created_at=content.created_at
    )


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """콘텐츠 ID로 조회"""
    service = ContentService(db)
    content = await service.get_content_by_id(content_id)

    if not content:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")

    return ContentResponse(
        id=str(content.id),
        issue_id=str(content.issue_id),
        title=content.title,
        content=content.content,
        verified=content.verified,
        confidence_score=content.confidence_score,
        created_at=content.created_at
    )


@router.get("/{content_id}/download")
async def download_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """콘텐츠 마크다운 파일 다운로드"""
    service = ContentService(db)
    content = await service.get_content_by_id(content_id)

    if not content:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")

    # 마크다운 파일 생성
    md_content = f"# {content.title or 'Untitled'}\n\n{content.content or ''}"
    title = content.title or "content"
    filename = f"{title.replace(' ', '_')}.md"

    buffer = io.BytesIO(md_content.encode("utf-8"))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.get("/search/similar", response_model=SearchResultResponse)
async def search_similar(
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session)
):
    """벡터 유사도 검색"""
    service = ContentService(db)
    results = await service.search_similar(query, limit)
    return SearchResultResponse(results=results)
