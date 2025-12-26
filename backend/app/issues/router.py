from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.issues.service import IssueService
from app.issues.schemas import (
    IssueListResponse,
    IssueListItem,
    IssueDetailResponse,
    IssueDailySnapshotDetailResponse,
    IssueArticleResponse,
    IssueContentResponse,
    DailyReportResponse,
    DailySnapshotWithIssue,
    IssueResponse,
)
from app.auth.models import User
from app.auth.router import current_active_user
from app.settings.service import UserSettingsService

router = APIRouter(prefix="/issues", tags=["issues"])


async def get_user_categories(
    db: AsyncSession,
    user: User
) -> list[str] | None:
    """유저의 카테고리 설정 조회 (빈 리스트면 None 반환)"""
    settings_service = UserSettingsService(db)
    settings = await settings_service.get_notification_settings(user.id)
    categories = settings.get("categories", [])
    return categories if categories else None


@router.get("", response_model=IssueListResponse)
async def list_issues(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    """이슈 목록 조회 (유저 관심사 필터링)"""
    categories = await get_user_categories(db, user)
    service = IssueService(db)
    issues, total = await service.list_issues(page=page, size=size, categories=categories)

    items = []
    for issue in issues:
        latest_snapshot = issue.snapshots[0] if issue.snapshots else None

        # Check if any snapshot has content
        has_content = any(
            len(snapshot.contents) > 0
            for snapshot in issue.snapshots
        )

        items.append(IssueListItem(
            id=str(issue.id),
            name=issue.name,
            category=issue.category,
            first_seen_at=issue.first_seen_at,
            last_seen_at=issue.last_seen_at,
            total_snapshots=issue.total_snapshots,
            status=issue.status,
            latest_article_count=latest_snapshot.article_count if latest_snapshot else None,
            latest_sentiment_score=latest_snapshot.sentiment_score if latest_snapshot else None,
            has_content=has_content,
        ))

    return IssueListResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue(
        issue_id: UUID,
        db: AsyncSession = Depends(get_async_session)
):
    """이슈 상세 조회 (스냅샷 히스토리 포함)"""
    service = IssueService(db)
    issue = await service.get_issue(issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다")

    return IssueDetailResponse(
        id=str(issue.id),
        name=issue.name,
        category=issue.category,
        first_seen_at=issue.first_seen_at,
        last_seen_at=issue.last_seen_at,
        total_snapshots=issue.total_snapshots,
        status=issue.status,
        snapshots=[
            IssueDailySnapshotDetailResponse(
                id=str(snapshot.id),
                date=snapshot.date,
                article_count=snapshot.article_count,
                sentiment_score=snapshot.sentiment_score,
                summary=snapshot.summary,
                articles=[
                    IssueArticleResponse(
                        id=str(article.id),
                        title=article.title,
                        description=article.description,
                        url=article.url,
                        press=article.press,
                        published_at=article.published_at
                    )
                    for article in snapshot.articles
                ],
                contents=[
                    IssueContentResponse(
                        id=str(content.id),
                        title=content.title,
                        content=content.content,
                        verified=content.verified,
                        confidence_score=content.confidence_score,
                        created_at=content.created_at
                    )
                    for content in snapshot.contents
                ]
            )
            for snapshot in sorted(issue.snapshots, key=lambda s: s.date, reverse=True)
        ]
    )


# 리포트 관련 엔드포인트
report_router = APIRouter(prefix="/reports", tags=["reports"])


@report_router.get("/dates")
async def get_batch_dates(
        year: int = Query(...),
        month: int = Query(..., ge=1, le=12),
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
) -> list[str]:
    """배치 실행된 날짜 목록 (유저 관심사 필터링)"""
    categories = await get_user_categories(db, user)
    service = IssueService(db)
    dates = await service.get_batch_dates(year, month, categories=categories)
    return [d.isoformat() for d in dates]


@report_router.get("/{report_date}", response_model=DailyReportResponse)
async def get_daily_report(
        report_date: date,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    """일간 리포트 조회 (유저 관심사 필터링)"""
    categories = await get_user_categories(db, user)
    service = IssueService(db)
    snapshots = await service.get_daily_report(report_date, categories=categories)

    return DailyReportResponse(
        date=report_date,
        snapshots=[
            DailySnapshotWithIssue(
                id=str(snapshot.id),
                date=snapshot.date,
                article_count=snapshot.article_count,
                sentiment_score=snapshot.sentiment_score,
                summary=snapshot.summary,
                issue=IssueResponse(
                    id=str(snapshot.issue.id),
                    name=snapshot.issue.name,
                    category=snapshot.issue.category,
                    first_seen_at=snapshot.issue.first_seen_at,
                    last_seen_at=snapshot.issue.last_seen_at,
                    total_snapshots=snapshot.issue.total_snapshots,
                    status=snapshot.issue.status,
                ),
                articles=[
                    IssueArticleResponse(
                        id=str(article.id),
                        title=article.title,
                        description=article.description,
                        url=article.url,
                        press=article.press,
                        published_at=article.published_at
                    )
                    for article in snapshot.articles
                ]
            )
            for snapshot in snapshots
        ],
        total_issues=len(snapshots)
    )