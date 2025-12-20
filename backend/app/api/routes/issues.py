from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import IssueService
from app.schemas import (
    IssueListResponse,
    IssueListItem,
    IssueDetailResponse,
    IssueArticleResponse,
    IssueVideoResponse,
    IssueInsightResponse,
)

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("", response_model=IssueListResponse)
def list_issues(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        db: Session = Depends(get_db)
):
    """이슈 목록 조회"""
    service = IssueService(db)
    issues, total = service.list_issues(page=page, size=size)

    return IssueListResponse(
        items=[
            IssueListItem(
                id=str(issue.id),
                name=issue.name,
                summary=issue.summary,
                category=issue.category,
                article_count=issue.article_count,
                status=issue.status,
                created_at=issue.created_at
            )
            for issue in issues
        ],
        total=total,
        page=page,
        size=size
    )


@router.get("/{issue_id}", response_model=IssueDetailResponse)
def get_issue(
        issue_id: UUID,
        db: Session = Depends(get_db)
):
    """이슈 상세 조회"""
    service = IssueService(db)
    issue = service.get_issue(issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다")

    return IssueDetailResponse(
        id=str(issue.id),
        name=issue.name,
        summary=issue.summary,
        category=issue.category,
        article_count=issue.article_count,
        status=issue.status,
        created_at=issue.created_at,
        articles=[
            IssueArticleResponse(
                id=str(article.id),
                title=article.title,
                description=article.description,
                url=article.url,
                press=article.press,
                published_at=article.published_at
            )
            for article in issue.articles
        ],
        videos=[
            IssueVideoResponse(
                id=str(video.id),
                video_id=video.video_id,
                title=video.title,
                channel=video.channel,
                view_count=video.view_count,
                angle=video.angle,
                url=video.url,
                published_at=video.published_at
            )
            for video in issue.videos
        ],
        insights=[
            IssueInsightResponse(
                id=str(insight.id),
                verified_angles=insight.verified_angles,
                content_directions=insight.content_directions,
                raw_analysis=insight.raw_analysis
            )
            for insight in issue.insights
        ]
    )