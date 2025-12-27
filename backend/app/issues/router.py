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
    CalendarIssueResponse,
)
from app.auth.models import User
from app.auth.router import fastapi_users

router = APIRouter(prefix="/issues", tags=["issues"])

# 선택적 인증 (비로그인도 허용)
optional_current_user = fastapi_users.current_user(active=True, optional=True)
# 필수 인증
current_active_user = fastapi_users.current_user(active=True)


def get_categories_from_query(category_param: str | None) -> list[str] | None:
    """카테고리 필터: 항상 쿼리 파라미터 사용 (헤더 필터 = 화면 조절)

    Note: 설정 페이지의 카테고리는 이메일 알림용으로만 사용
    """
    if category_param:
        return [c.strip() for c in category_param.split(",") if c.strip()]
    return None


@router.get("/calendar", response_model=list[CalendarIssueResponse])
async def list_issues_for_calendar(
        categories: str | None = Query(None, description="카테고리 필터 (쉼표 구분)"),
        db: AsyncSession = Depends(get_async_session),
):
    """달력용 경량 이슈 목록 (빠른 응답) - 비로그인 허용"""
    category_list = get_categories_from_query(categories)
    service = IssueService(db)
    issues = await service.list_issues_for_calendar(categories=category_list)

    return [
        CalendarIssueResponse(
            id=str(issue.id),
            name=issue.name,
            category=issue.category,
            first_seen_at=issue.first_seen_at,
            last_seen_at=issue.last_seen_at,
        )
        for issue in issues
    ]


@router.get("", response_model=IssueListResponse)
async def list_issues(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        categories: str | None = Query(None, description="카테고리 필터 (쉼표 구분)"),
        db: AsyncSession = Depends(get_async_session),
        user: User | None = Depends(optional_current_user)
):
    """이슈 목록 조회 - 비로그인 허용"""
    category_list = get_categories_from_query(categories)
    service = IssueService(db)
    issues, total = await service.list_issues(page=page, size=size, categories=category_list)

    # 로그인한 사용자의 팔로우한 이슈 ID 목록 조회
    followed_issue_ids = set()
    if user:
        followed_issues = await service.get_followed_issues(user.id)
        followed_issue_ids = {issue.id for issue in followed_issues}

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
            is_following=issue.id in followed_issue_ids,
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
        db: AsyncSession = Depends(get_async_session),
        user: User | None = Depends(optional_current_user)
):
    """이슈 상세 조회 (스냅샷 히스토리 포함)"""
    service = IssueService(db)
    issue = await service.get_issue(issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다")

    # 로그인 사용자의 경우 팔로우 여부 확인
    is_following = False
    if user:
        is_following = await service.is_following(user.id, issue_id)

    return IssueDetailResponse(
        id=str(issue.id),
        name=issue.name,
        category=issue.category,
        first_seen_at=issue.first_seen_at,
        last_seen_at=issue.last_seen_at,
        total_snapshots=issue.total_snapshots,
        status=issue.status,
        is_following=is_following,
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


@router.post("/{issue_id}/follow")
async def follow_issue(
        issue_id: UUID,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    """이슈 팔로우"""
    service = IssueService(db)

    # 이슈 존재 확인
    issue = await service.get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다")

    try:
        await service.follow_issue(user.id, issue_id)
        return {"message": "팔로우 완료", "is_following": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{issue_id}/follow")
async def unfollow_issue(
        issue_id: UUID,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    """이슈 언팔로우"""
    service = IssueService(db)

    success = await service.unfollow_issue(user.id, issue_id)
    if not success:
        raise HTTPException(status_code=404, detail="팔로우 중인 이슈가 아닙니다")

    return {"message": "언팔로우 완료", "is_following": False}


# 리포트 관련 엔드포인트
report_router = APIRouter(prefix="/reports", tags=["reports"])


@report_router.get("/dates")
async def get_batch_dates(
        year: int = Query(...),
        month: int = Query(..., ge=1, le=12),
        categories: str | None = Query(None, description="카테고리 필터 (쉼표 구분)"),
        db: AsyncSession = Depends(get_async_session),
) -> list[str]:
    """배치 실행된 날짜 목록 - 비로그인 허용"""
    category_list = get_categories_from_query(categories)
    service = IssueService(db)
    dates = await service.get_batch_dates(year, month, categories=category_list)
    return [d.isoformat() for d in dates]


@report_router.get("/{report_date}", response_model=DailyReportResponse)
async def get_daily_report(
        report_date: date,
        categories: str | None = Query(None, description="카테고리 필터 (쉼표 구분)"),
        db: AsyncSession = Depends(get_async_session),
):
    """일간 리포트 조회 - 비로그인 허용"""
    category_list = get_categories_from_query(categories)
    service = IssueService(db)
    snapshots = await service.get_daily_report(report_date, categories=category_list)

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