from uuid import UUID
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.issues.models import Issue, IssueDailySnapshot, IssueArticle
from app.core.agent.tools import NaverNewsProvider, ClusteringProvider


class IssueService:
    """이슈 수집 + 조회 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.news_provider = NaverNewsProvider()
        self.clustering_provider = ClusteringProvider()

    def collect_issues(self, batch_run_id: UUID | None = None) -> list[Issue]:
        """이슈 수집 (스크래핑 → 클러스터링 → 검색 → 저장)"""
        today = date.today()

        # 1. 랭킹 뉴스 스크래핑
        news_list = self.news_provider.get_ranking_news()
        titles = [news.title for news in news_list]

        # 2. LLM 클러스터링
        clustered = self.clustering_provider.cluster_news(titles)

        # 3. 이슈별 저장
        issues = []
        for item in clustered:
            # 기존 이슈 찾기 (이름으로 매칭)
            existing_issue = self.db.execute(
                select(Issue).where(Issue.name == item.name)
            ).scalar_one_or_none()

            if existing_issue:
                # 기존 이슈 업데이트
                issue = existing_issue
                issue.last_seen_at = today
                issue.total_snapshots += 1
            else:
                # 새 이슈 생성
                issue = Issue(
                    name=item.name,
                    category=item.category,
                    first_seen_at=today,
                    last_seen_at=today,
                    total_snapshots=1,
                    status="active"
                )
                self.db.add(issue)
                self.db.flush()

            # 일간 스냅샷 생성
            snapshot = IssueDailySnapshot(
                issue_id=issue.id,
                batch_run_id=batch_run_id,
                date=today,
                article_count=len(item.article_indices),
                sentiment_score=None,
                summary=item.summary
            )
            self.db.add(snapshot)
            self.db.flush()

            # 네이버 API로 기사 상세 검색
            articles = self.news_provider.search_news(item.name, display=5)
            for article in articles:
                issue_article = IssueArticle(
                    snapshot_id=snapshot.id,
                    title=article.title,
                    description=article.description,
                    url=article.url,
                    press=article.press,
                    published_at=None
                )
                self.db.add(issue_article)

            issues.append(issue)

        self.db.commit()
        return issues

    def list_issues(self, page: int = 1, size: int = 20) -> tuple[list[Issue], int]:
        """이슈 목록 조회"""
        offset = (page - 1) * size

        total = self.db.execute(select(func.count(Issue.id))).scalar()

        stmt = (
            select(Issue)
            .options(selectinload(Issue.snapshots))
            .order_by(Issue.last_seen_at.desc())
            .offset(offset)
            .limit(size)
        )
        issues = list(self.db.execute(stmt).scalars().all())

        return issues, total

    def get_issue(self, issue_id: UUID) -> Issue | None:
        """이슈 상세 조회 (스냅샷 + 기사 포함)"""
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.snapshots).selectinload(IssueDailySnapshot.articles)
            )
            .where(Issue.id == issue_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_daily_report(self, report_date: date) -> list[IssueDailySnapshot]:
        """일간 리포트 조회"""
        stmt = (
            select(IssueDailySnapshot)
            .options(
                selectinload(IssueDailySnapshot.issue),
                selectinload(IssueDailySnapshot.articles)
            )
            .where(IssueDailySnapshot.date == report_date)
            .order_by(IssueDailySnapshot.article_count.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_batch_dates(self, year: int, month: int) -> list[date]:
        """배치 실행된 날짜 목록"""
        stmt = (
            select(IssueDailySnapshot.date)
            .where(
                func.extract('year', IssueDailySnapshot.date) == year,
                func.extract('month', IssueDailySnapshot.date) == month
            )
            .distinct()
            .order_by(IssueDailySnapshot.date)
        )
        return list(self.db.execute(stmt).scalars().all())