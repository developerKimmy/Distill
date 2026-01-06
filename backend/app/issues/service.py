"""이슈 서비스 - 조회 및 팔로우 기능

모니터링 파이프라인은 app.monitoring에서 처리
콘텐츠 생성은 app.content.generator에서 처리
"""
from uuid import UUID
from datetime import date, datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.issues.models import (
    Issue, IssueArticle, IssueContent, IssueFollow,
    Entity, IssueEntity, DailyDigest, UNASSIGNED_ISSUE_ID
)

KST = timezone(timedelta(hours=9))


class IssueService:
    """이슈 조회 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 이슈 목록/상세 조회 ==========

    async def list_issues_for_calendar(
        self,
        categories: list[str] | None = None
    ) -> list[dict]:
        """달력용 경량 이슈 목록 조회

        display_date 계산 로직:
        - created_at과 first_seen_at 차이가 한 달 이상 → created_at 사용
        - 차이가 한 달 이하 → first_seen_at 사용

        정렬: 기사 수 내림차순
        """
        stmt = (
            select(Issue)
            .where(Issue.status == "active")
            .options(selectinload(Issue.articles))
        )

        if categories:
            stmt = stmt.where(Issue.category.in_(categories))

        result = await self.db.execute(stmt)
        issues = list(result.scalars().all())

        # display_date 계산 및 기사 수 포함
        calendar_issues = []
        for issue in issues:
            display_date = self._calculate_display_date(issue)
            article_count = len(issue.articles) if issue.articles else 0
            calendar_issues.append({
                "id": str(issue.id),
                "name": issue.name,
                "category": issue.category,
                "first_seen_at": issue.first_seen_at,
                "last_seen_at": issue.last_seen_at,
                "display_date": display_date,
                "article_count": article_count,
            })

        # 기사 수 내림차순 정렬
        calendar_issues.sort(key=lambda x: x["article_count"], reverse=True)

        return calendar_issues

    def _calculate_display_date(self, issue: Issue) -> date | None:
        """이슈의 달력 표시용 날짜 계산

        - created_at과 first_seen_at 차이가 30일 이상 → created_at.date() 사용
        - 차이가 30일 이하 → first_seen_at 사용

        이는 오래된 키워드가 재등장했을 때 created_at 기준으로 표시하기 위함
        """
        if not issue.first_seen_at:
            return None

        # created_at은 datetime, first_seen_at은 date
        created_date = issue.created_at.date() if issue.created_at else None

        if not created_date:
            return issue.first_seen_at

        # 날짜 차이 계산
        diff_days = (created_date - issue.first_seen_at).days

        # 30일 이상 차이나면 created_at 기준
        if abs(diff_days) >= 30:
            return created_date

        # 30일 이하면 first_seen_at 기준
        return issue.first_seen_at

    async def list_issues(
        self,
        page: int = 1,
        size: int = 20,
        categories: list[str] | None = None
    ) -> tuple[list[Issue], int]:
        """이슈 목록 조회"""
        offset = (page - 1) * size

        # 카운트 쿼리
        count_stmt = select(func.count(Issue.id)).where(Issue.status == "active")
        if categories:
            count_stmt = count_stmt.where(Issue.category.in_(categories))
        result = await self.db.execute(count_stmt)
        total = result.scalar() or 0

        # 이슈 조회
        stmt = (
            select(Issue)
            .where(Issue.status == "active")
            .options(
                selectinload(Issue.articles),
                selectinload(Issue.contents),
                selectinload(Issue.issue_entities).selectinload(IssueEntity.entity)
            )
        )
        if categories:
            stmt = stmt.where(Issue.category.in_(categories))
        stmt = stmt.order_by(Issue.last_seen_at.desc()).offset(offset).limit(size)

        result = await self.db.execute(stmt)
        issues = list(result.scalars().all())

        return issues, total

    async def get_issue(self, issue_id: UUID) -> Issue | None:
        """이슈 상세 조회"""
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.articles),
                selectinload(Issue.contents),
                selectinload(Issue.keywords),
                selectinload(Issue.insights),
                selectinload(Issue.issue_entities).selectinload(IssueEntity.entity)
            )
            .where(Issue.id == issue_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ========== 일간 리포트 ==========

    async def get_daily_report(
        self,
        report_date: date,
        categories: list[str] | None = None
    ) -> dict:
        """일간 리포트 조회

        Returns:
            {
                "date": date,
                "issues": [DailyReportIssue, ...],
                "total_issues": int,
                "total_articles": int
            }
        """
        start_of_day = datetime.combine(report_date, datetime.min.time(), tzinfo=KST)
        end_of_day = datetime.combine(report_date, datetime.max.time(), tzinfo=KST)

        # 해당 날짜에 기사가 수집된 이슈들
        stmt = (
            select(Issue)
            .join(IssueArticle)
            .options(
                selectinload(Issue.articles),
                selectinload(Issue.issue_entities).selectinload(IssueEntity.entity)
            )
            .where(
                IssueArticle.collected_at >= start_of_day,
                IssueArticle.collected_at <= end_of_day,
                Issue.status == "active"
            )
        )
        if categories:
            stmt = stmt.where(Issue.category.in_(categories))
        stmt = stmt.distinct()

        result = await self.db.execute(stmt)
        issues = result.scalars().all()

        # 이슈별 기사 수 계산
        report_issues = []
        total_articles = 0

        for issue in issues:
            # 해당 날짜의 기사만 필터
            day_articles = [
                a for a in issue.articles
                if a.collected_at and start_of_day <= a.collected_at <= end_of_day
            ]
            article_count = len(day_articles)
            total_articles += article_count

            report_issues.append({
                "id": str(issue.id),
                "name": issue.name,
                "category": issue.category,
                "what_type": issue.what_type,
                "article_count": article_count,
                "articles": day_articles
            })

        # 기사 수 기준 정렬
        report_issues.sort(key=lambda x: x["article_count"], reverse=True)

        return {
            "date": report_date,
            "issues": report_issues,
            "total_issues": len(report_issues),
            "total_articles": total_articles
        }

    async def get_batch_dates(
        self,
        year: int,
        month: int,
        categories: list[str] | None = None
    ) -> list[date]:
        """다이제스트가 생성된 날짜 목록"""
        stmt = (
            select(DailyDigest.date)
            .where(
                func.extract('year', DailyDigest.date) == year,
                func.extract('month', DailyDigest.date) == month
            )
            .order_by(DailyDigest.date)
        )

        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    # ========== 팔로우 관련 ==========

    async def follow_issue(self, user_id: UUID, issue_id: UUID) -> IssueFollow:
        """이슈 팔로우"""
        existing = await self.db.execute(
            select(IssueFollow).where(
                IssueFollow.user_id == user_id,
                IssueFollow.issue_id == issue_id
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("이미 팔로우 중인 이슈입니다")

        follow = IssueFollow(user_id=user_id, issue_id=issue_id)
        self.db.add(follow)
        await self.db.commit()
        return follow

    async def unfollow_issue(self, user_id: UUID, issue_id: UUID) -> bool:
        """이슈 언팔로우"""
        result = await self.db.execute(
            select(IssueFollow).where(
                IssueFollow.user_id == user_id,
                IssueFollow.issue_id == issue_id
            )
        )
        follow = result.scalar_one_or_none()
        if not follow:
            return False

        await self.db.delete(follow)
        await self.db.commit()
        return True

    async def is_following(self, user_id: UUID, issue_id: UUID) -> bool:
        """팔로우 여부 확인"""
        result = await self.db.execute(
            select(IssueFollow).where(
                IssueFollow.user_id == user_id,
                IssueFollow.issue_id == issue_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_followed_issues(self, user_id: UUID) -> list[Issue]:
        """팔로우한 이슈 목록 조회"""
        result = await self.db.execute(
            select(Issue)
            .join(IssueFollow)
            .where(IssueFollow.user_id == user_id)
            .order_by(IssueFollow.created_at.desc())
        )
        return list(result.scalars().all())

    # ========== 데일리 다이제스트 ==========

    async def get_daily_digest(self, digest_date: date) -> dict:
        """데일리 다이제스트 데이터 조회

        Returns:
            카테고리별로 그룹핑된 이슈 목록 + 통계
        """
        start_of_day = datetime.combine(digest_date, datetime.min.time(), tzinfo=KST)
        end_of_day = datetime.combine(digest_date, datetime.max.time(), tzinfo=KST)

        # 해당 날짜에 기사가 수집된 이슈들
        stmt = (
            select(Issue)
            .join(IssueArticle)
            .options(
                selectinload(Issue.articles),
                selectinload(Issue.contents),
                selectinload(Issue.issue_entities).selectinload(IssueEntity.entity)
            )
            .where(
                IssueArticle.collected_at >= start_of_day,
                IssueArticle.collected_at <= end_of_day,
                Issue.status == "active"
            )
            .distinct()
        )
        result = await self.db.execute(stmt)
        issues = list(result.scalars().all())

        # 카테고리별 그룹핑
        by_category: dict[str, list] = defaultdict(list)
        total_articles = 0
        new_issues_count = 0

        for issue in issues:
            category = issue.category or "기타"

            # 해당 날짜의 기사만 필터
            day_articles = [
                a for a in issue.articles
                if a.collected_at and start_of_day <= a.collected_at <= end_of_day
            ]
            article_count = len(day_articles)
            total_articles += article_count

            # 오늘 처음 등장한 이슈인지 확인
            is_new = issue.first_seen_at == digest_date
            if is_new:
                new_issues_count += 1

            # 콘텐츠 정보 (최신 콘텐츠)
            content_title = None
            content_preview = None
            if issue.contents:
                latest_content = sorted(issue.contents, key=lambda c: c.created_at, reverse=True)[0]
                content_title = latest_content.title
                if latest_content.content:
                    content_preview = (
                        latest_content.content[:200] + "..."
                        if len(latest_content.content) > 200
                        else latest_content.content
                    )

            # 주요 엔티티
            primary_entities = [
                {
                    "id": str(ie.entity.id),
                    "name": ie.entity.name,
                    "type": ie.entity.type,
                    "aliases": ie.entity.aliases or []
                }
                for ie in issue.issue_entities
                if ie.role == "primary" and ie.entity
            ]

            by_category[category].append({
                "id": str(issue.id),
                "name": issue.name,
                "category": category,
                "what_type": issue.what_type,
                "article_count": article_count,
                "summary": issue.what_summary,
                "content_title": content_title,
                "content_preview": content_preview,
                "is_new": is_new,
                "primary_entities": primary_entities
            })

        # 카테고리별 데이터 구조화
        categories = []
        category_order = ["정치", "경제", "사회", "세계", "IT/과학", "연예", "스포츠", "기타"]

        for cat in category_order:
            if cat in by_category:
                cat_issues = by_category[cat]
                # 기사 수 기준 정렬
                cat_issues.sort(key=lambda x: x["article_count"], reverse=True)
                categories.append({
                    "category": cat,
                    "issues": cat_issues,
                    "total_articles": sum(i["article_count"] for i in cat_issues)
                })

        # 다이제스트 요약 조회
        digest_stmt = select(DailyDigest).where(DailyDigest.date == digest_date)
        digest_result = await self.db.execute(digest_stmt)
        daily_digest = digest_result.scalar_one_or_none()
        digest_summary = daily_digest.summary if daily_digest else None

        # 마지막 업데이트 시간
        updated_at = None
        if issues:
            all_articles = [a for issue in issues for a in issue.articles]
            if all_articles:
                updated_at = max(a.collected_at for a in all_articles if a.collected_at)

        # 이슈 이름 -> ID 매핑 (브리핑 텍스트에서 링크 생성용)
        issue_map = {issue.name: str(issue.id) for issue in issues}

        return {
            "date": digest_date,
            "total_issues": len(issues),
            "total_articles": total_articles,
            "new_issues_count": new_issues_count,
            "categories": categories,
            "updated_at": updated_at,
            "digest_summary": digest_summary,
            "issue_map": issue_map,
        }
