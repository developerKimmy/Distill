import logging
from datetime import datetime, date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.tools.google_news import GoogleNewsProvider
from app.core.agent.tools.naver_news import NaverNewsProvider, NewsItem
from app.core.agent.tools.tavily import TavilyProvider
from app.core.config import settings
from app.issues.models import Issue, IssueArticle

logger = logging.getLogger(__name__)


class NewsCollector:
    """여러 소스에서 뉴스 수집 + 중복 제거"""

    def __init__(self):
        self.google_news = GoogleNewsProvider()
        self.naver = NaverNewsProvider()
        # Tavily는 API 키가 있을 때만 사용
        self.tavily = None
        if settings.TAVILY_API_KEY:
            try:
                self.tavily = TavilyProvider()
            except Exception as e:
                logger.warning(f"Tavily 초기화 실패: {e}")

    async def collect(self, db: AsyncSession) -> list[NewsItem]:
        """모든 소스에서 뉴스 수집 + 중복 제거"""
        all_articles: list[NewsItem] = []

        # 1. Google News RSS (메인 소스 - 카테고리별)
        logger.info("Google News RSS 수집 시작...")
        try:
            google_articles = await self.google_news.fetch_all_categories(limit_per_category=15)
            all_articles.extend(google_articles)
            logger.info(f"Google News: {len(google_articles)}개 수집")
        except Exception as e:
            logger.error(f"Google News 수집 실패: {e}")

        # 2. Naver 검색 (활성 이슈 키워드로 추가 검색)
        logger.info("Naver Search 수집 시작...")
        try:
            active_issues = await self._get_active_issues(db)
            naver_articles = []
            for issue in active_issues[:10]:  # 최대 10개 이슈만
                try:
                    articles = self.naver.search_news(issue.name, display=5, sort="date")
                    naver_articles.extend(articles)
                except Exception as e:
                    logger.warning(f"Naver 검색 실패 ({issue.name}): {e}")
            all_articles.extend(naver_articles)
            logger.info(f"Naver Search: {len(naver_articles)}개 수집")
        except Exception as e:
            logger.error(f"Naver Search 수집 실패: {e}")

        # 3. Tavily (오늘 새로 생성된 이슈만 - 환각 방지용 크로스체크)
        if self.tavily:
            logger.info("Tavily 검색 시작...")
            try:
                new_issues = await self._get_new_issues_today(db)
                tavily_articles = []
                for issue in new_issues:  # 새 이슈 전부 체크
                    try:
                        results = await self.tavily.search(issue.name, max_results=5)
                        for r in results:
                            tavily_articles.append(NewsItem(
                                title=r["title"],
                                url=r["url"],
                                press="",
                                description=r.get("snippet", ""),
                                published_at=None
                            ))
                    except Exception as e:
                        logger.warning(f"Tavily 검색 실패 ({issue.name}): {e}")
                all_articles.extend(tavily_articles)
                logger.info(f"Tavily: {len(tavily_articles)}개 수집 (새 이슈 {len(new_issues)}개)")
            except Exception as e:
                logger.error(f"Tavily 수집 실패: {e}")

        # 4. URL 중복 제거
        unique_articles = self._deduplicate_by_url(all_articles)
        logger.info(f"중복 제거 후: {len(unique_articles)}개")

        # 5. DB에 이미 있는 기사 제외
        new_articles = await self._filter_existing(unique_articles, db)
        logger.info(f"신규 기사: {len(new_articles)}개")

        return new_articles

    async def _get_active_issues(self, db: AsyncSession, limit: int = 20) -> list[Issue]:
        """활성 이슈 조회 (최근 7일 내 업데이트된 것)"""
        query = (
            select(Issue)
            .where(Issue.status == "active")
            .order_by(Issue.last_seen_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def _get_new_issues_today(self, db: AsyncSession) -> list[Issue]:
        """오늘 새로 생성된 이슈 조회 (환각 방지용 크로스체크)"""
        today = date.today()
        query = (
            select(Issue)
            .where(Issue.first_seen_at >= datetime.combine(today, datetime.min.time()))
            .order_by(Issue.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    def _deduplicate_by_url(self, articles: list[NewsItem]) -> list[NewsItem]:
        """URL 기준 중복 제거"""
        seen_urls = set()
        unique = []
        for article in articles:
            # URL 정규화 (쿼리스트링 제거 등)
            url = article.url.split("?")[0].rstrip("/")
            if url not in seen_urls:
                seen_urls.add(url)
                unique.append(article)
        return unique

    async def _filter_existing(
        self,
        articles: list[NewsItem],
        db: AsyncSession
    ) -> list[NewsItem]:
        """DB에 이미 있는 기사 제외"""
        if not articles:
            return []

        # URL 목록 추출
        urls = [a.url.split("?")[0].rstrip("/") for a in articles]

        # DB에서 이미 있는 URL 조회
        query = select(IssueArticle.url).where(IssueArticle.url.in_(urls))
        result = await db.execute(query)
        existing_urls = {row[0].split("?")[0].rstrip("/") for row in result.all()}

        # 새 기사만 필터링
        new_articles = [
            a for a in articles
            if a.url.split("?")[0].rstrip("/") not in existing_urls
        ]

        return new_articles
