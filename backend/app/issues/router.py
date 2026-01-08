from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.issues.service import IssueService
from app.settings.models import UserSettings
from app.issues.schemas import (
    IssueListResponse,
    IssueListItem,
    IssueDetailResponse,
    IssueArticleResponse,
    IssueContentResponse,
    IssueResponse,
    CalendarIssueResponse,
    DailyDigestResponse,
    DigestCategoryGroup,
    DigestIssueItem,
    DailyReportResponse,
    DailyReportIssue,
    EntityResponse,
)
from app.auth.models import User
from app.auth.router import fastapi_users

router = APIRouter(prefix="/issues", tags=["issues"])

# 선택적 인증 (비로그인도 허용)
optional_current_user = fastapi_users.current_user(active=True, optional=True)
# 필수 인증
current_active_user = fastapi_users.current_user(active=True)


def get_categories_from_query(category_param: str | None) -> list[str] | None:
    """카테고리 필터: 항상 쿼리 파라미터 사용"""
    if category_param:
        return [c.strip() for c in category_param.split(",") if c.strip()]
    return None


@router.get("/calendar", response_model=list[CalendarIssueResponse])
async def list_issues_for_calendar(
        categories: str | None = Query(None, description="카테고리 필터 (쉼표 구분)"),
        db: AsyncSession = Depends(get_async_session),
):
    """달력용 경량 이슈 목록 - 비로그인 허용

    display_date: created_at과 first_seen_at 차이가 30일 이상이면 created_at 사용
    """
    category_list = get_categories_from_query(categories)
    service = IssueService(db)
    issues = await service.list_issues_for_calendar(categories=category_list)

    return [
        CalendarIssueResponse(
            id=issue["id"],
            name=issue["name"],
            category=issue["category"],
            first_seen_at=issue["first_seen_at"],
            last_seen_at=issue["last_seen_at"],
            display_date=issue["display_date"],
            article_count=issue["article_count"],
            collected_dates=issue["collected_dates"],
        )
        for issue in issues
    ]


@router.get("", response_model=IssueListResponse)
async def list_issues(
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=500),
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
        # 기사 수
        article_count = len(issue.articles) if issue.articles else 0

        # 콘텐츠 유무
        has_content = bool(issue.contents)

        # 주요 엔티티
        primary_entities = []
        if hasattr(issue, 'issue_entities'):
            for ie in issue.issue_entities:
                if ie.role == "primary" and ie.entity:
                    primary_entities.append(EntityResponse(
                        id=str(ie.entity.id),
                        name=ie.entity.name,
                        type=ie.entity.type,
                        aliases=ie.entity.aliases or []
                    ))

        items.append(IssueListItem(
            id=str(issue.id),
            name=issue.name,
            category=issue.category,
            what_type=issue.what_type,
            what_summary=issue.what_summary,
            first_seen_at=issue.first_seen_at,
            last_seen_at=issue.last_seen_at,
            status=issue.status,
            article_count=article_count,
            has_content=has_content,
            is_following=issue.id in followed_issue_ids,
            primary_entities=primary_entities,
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
    """이슈 상세 조회"""
    service = IssueService(db)
    issue = await service.get_issue(issue_id)

    if not issue:
        raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다")

    # 로그인 사용자의 경우 팔로우 여부 확인
    is_following = False
    if user:
        is_following = await service.is_following(user.id, issue_id)

    # 기사 목록
    articles = [
        IssueArticleResponse(
            id=str(article.id),
            title=article.title,
            description=article.description,
            url=article.url,
            press=article.press,
            source=article.source,
            published_at=article.published_at,
            collected_at=article.collected_at,
            status=article.status,
            entities=article.entities or {}
        )
        for article in sorted(issue.articles, key=lambda a: a.collected_at, reverse=True)
    ]

    # 콘텐츠 목록
    contents = [
        IssueContentResponse(
            id=str(content.id),
            title=content.title,
            content=content.content,
            verified=content.verified,
            confidence_score=content.confidence_score,
            created_at=content.created_at
        )
        for content in sorted(issue.contents, key=lambda c: c.created_at, reverse=True)
    ]

    # 엔티티 목록
    entities = []
    if hasattr(issue, 'issue_entities'):
        for ie in issue.issue_entities:
            if ie.entity:
                entities.append(EntityResponse(
                    id=str(ie.entity.id),
                    name=ie.entity.name,
                    type=ie.entity.type,
                    aliases=ie.entity.aliases or []
                ))

    # 키워드
    keywords = [kw.keyword for kw in issue.keywords if kw.keyword]

    return IssueDetailResponse(
        id=str(issue.id),
        name=issue.name,
        category=issue.category,
        what_type=issue.what_type,
        what_summary=issue.what_summary,
        first_seen_at=issue.first_seen_at,
        last_seen_at=issue.last_seen_at,
        status=issue.status,
        is_following=is_following,
        articles=articles,
        contents=contents,
        entities=entities,
        keywords=keywords,
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
    data = await service.get_daily_report(report_date, categories=category_list)

    return DailyReportResponse(
        date=data["date"],
        issues=[
            DailyReportIssue(
                id=issue["id"],
                name=issue["name"],
                category=issue["category"],
                what_type=issue["what_type"],
                article_count=issue["article_count"],
                articles=[
                    IssueArticleResponse(
                        id=str(a.id),
                        title=a.title,
                        description=a.description,
                        url=a.url,
                        press=a.press,
                        source=a.source,
                        published_at=a.published_at,
                        collected_at=a.collected_at,
                        status=a.status,
                        entities=a.entities or {}
                    )
                    for a in issue["articles"]
                ]
            )
            for issue in data["issues"]
        ],
        total_issues=data["total_issues"],
        total_articles=data["total_articles"]
    )


@report_router.get("/digest/{digest_date}", response_model=DailyDigestResponse)
async def get_daily_digest(
        digest_date: date,
        categories: str | None = Query(None, description="카테고리 필터 (쉼표 구분)"),
        db: AsyncSession = Depends(get_async_session),
        user: User | None = Depends(optional_current_user),
):
    """데일리 다이제스트 조회 - 비로그인 허용, 카테고리 필터 적용"""
    # 쿼리 파라미터 우선, 없으면 로그인한 사용자의 DB 설정 사용
    category_filter = get_categories_from_query(categories)
    if not category_filter and user:
        settings_stmt = select(UserSettings).where(UserSettings.user_id == user.id)
        settings_result = await db.execute(settings_stmt)
        user_settings = settings_result.scalar_one_or_none()
        if user_settings and user_settings.category_filter:
            category_filter = [c.strip() for c in user_settings.category_filter.split(",") if c.strip()]

    service = IssueService(db)
    data = await service.get_daily_digest(digest_date, category_filter=category_filter)

    return DailyDigestResponse(
        date=data["date"],
        total_issues=data["total_issues"],
        total_articles=data["total_articles"],
        new_issues_count=data["new_issues_count"],
        updated_at=data["updated_at"],
        digest_summary=data.get("digest_summary"),
        issue_map=data.get("issue_map"),
        categories=[
            DigestCategoryGroup(
                category=cat["category"],
                total_articles=cat["total_articles"],
                issues=[
                    DigestIssueItem(**issue)
                    for issue in cat["issues"]
                ]
            )
            for cat in data["categories"]
        ]
    )
