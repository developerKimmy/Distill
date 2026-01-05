"""Collect 노드 - 뉴스 수집 + 중복 필터링 + 임베딩 생성"""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# 한국 시간대
KST = timezone(timedelta(hours=9))

from app.monitoring.state import MonitoringState, ArticleData
from app.monitoring.collectors import GoogleNewsProvider, NaverNewsProvider, NewsItem
from app.core.agent.tools import EmbeddingProvider
from app.issues.models import Issue, IssueArticle, IssueEmbedding

logger = logging.getLogger(__name__)

# 유사도 임계값 (이 값 이상이면 중복으로 판단)
SIMILARITY_THRESHOLD = 0.85


class CollectNode:
    """뉴스 수집 노드"""

    def __init__(self):
        self.google_news = GoogleNewsProvider()
        self.naver = NaverNewsProvider()
        self.embedding_provider = EmbeddingProvider()

    async def __call__(
        self,
        state: MonitoringState,
        db: AsyncSession
    ) -> dict:
        """Collect 노드 실행

        1. 여러 소스에서 뉴스 수집
        2. URL 중복 제거
        3. DB에 있는 기사 필터링
        4. 임베딩 생성
        5. 유사도 기반 중복 제거
        """
        errors = list(state.get("errors", []))
        collected: list[ArticleData] = []

        try:
            # 1. Google News RSS 수집
            logger.info("Google News RSS 수집 시작...")
            google_articles = await self._collect_google_news()
            logger.info(f"Google News: {len(google_articles)}개 수집")

            # 2. Naver 검색 (활성 이슈 키워드)
            logger.info("Naver Search 수집 시작...")
            naver_articles = await self._collect_naver_news(db)
            logger.info(f"Naver Search: {len(naver_articles)}개 수집")

            # 3. 합치기
            all_articles = google_articles + naver_articles
            logger.info(f"총 수집: {len(all_articles)}개")

            # 4. URL 중복 제거
            unique_articles = self._deduplicate_by_url(all_articles)
            logger.info(f"URL 중복 제거 후: {len(unique_articles)}개")

            # 5. DB에 이미 있는 기사 필터링
            new_articles = await self._filter_existing(unique_articles, db)
            logger.info(f"신규 기사: {len(new_articles)}개")

            # 6. 임베딩 생성
            if new_articles:
                embeddings = self._generate_embeddings(new_articles)

                # 7. 유사도 기반 중복 제거
                filtered_articles, filtered_embeddings = await self._filter_similar(
                    new_articles, embeddings, db
                )
                logger.info(f"유사도 필터 후: {len(filtered_articles)}개")

                # ArticleData로 변환
                collected = self._to_article_data(filtered_articles, filtered_embeddings)

        except Exception as e:
            logger.error(f"Collect 실패: {e}")
            errors.append(f"Collect: {str(e)}")

        logger.info(f"=== Collect 완료: {len(collected)}개 기사 ===")

        return {
            "collected_articles": collected,
            "errors": errors,
            "current_step": "collected",
        }

    async def _collect_google_news(self) -> list[NewsItem]:
        """Google News RSS에서 수집"""
        try:
            articles = await self.google_news.fetch_all_categories(
                limit_per_category=15
            )
            return articles
        except Exception as e:
            logger.error(f"Google News 수집 실패: {e}")
            return []

    async def _collect_naver_news(self, db: AsyncSession) -> list[NewsItem]:
        """Naver 검색 API로 활성 이슈 관련 뉴스 수집"""
        articles = []
        try:
            # 활성 이슈 조회
            active_issues = await self._get_active_issues(db)

            for issue in active_issues[:10]:  # 최대 10개 이슈
                try:
                    results = self.naver.search_news(
                        issue.name, display=5, sort="date"
                    )
                    articles.extend(results)
                except Exception as e:
                    logger.warning(f"Naver 검색 실패 ({issue.name}): {e}")

        except Exception as e:
            logger.error(f"Naver 수집 실패: {e}")

        return articles

    async def _get_active_issues(
        self, db: AsyncSession, limit: int = 20
    ) -> list[Issue]:
        """활성 이슈 조회"""
        query = (
            select(Issue)
            .where(Issue.status == "active")
            .order_by(Issue.last_seen_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    def _deduplicate_by_url(self, articles: list[NewsItem]) -> list[NewsItem]:
        """URL 기준 중복 제거"""
        seen_urls = set()
        unique = []
        for article in articles:
            url = article.url.split("?")[0].rstrip("/")
            if url not in seen_urls:
                seen_urls.add(url)
                unique.append(article)
        return unique

    async def _filter_existing(
        self, articles: list[NewsItem], db: AsyncSession
    ) -> list[NewsItem]:
        """DB에 이미 있는 기사 제외"""
        if not articles:
            return []

        urls = [a.url.split("?")[0].rstrip("/") for a in articles]
        query = select(IssueArticle.url).where(IssueArticle.url.in_(urls))
        result = await db.execute(query)
        existing_urls = {
            row[0].split("?")[0].rstrip("/") for row in result.all()
        }

        return [
            a for a in articles
            if a.url.split("?")[0].rstrip("/") not in existing_urls
        ]

    def _generate_embeddings(self, articles: list[NewsItem]) -> list[list[float]]:
        """기사 제목 임베딩 생성"""
        titles = [a.title for a in articles]
        return self.embedding_provider.embed_batch(titles)

    async def _filter_similar(
        self,
        articles: list[NewsItem],
        embeddings: list[list[float]],
        db: AsyncSession
    ) -> tuple[list[NewsItem], list[list[float]]]:
        """임베딩 유사도로 중복 기사 제거 (최근 7일)"""
        if not articles:
            return [], []

        week_ago = datetime.now(KST) - timedelta(days=7)

        # 기존 임베딩 조회 (최근 7일, article_title 타입)
        query = (
            select(IssueEmbedding.embedding)
            .where(IssueEmbedding.content_type == "article_title")
            .where(IssueEmbedding.created_at > week_ago)
        )
        result = await db.execute(query)
        existing_embeddings = [list(row[0]) for row in result.fetchall() if row[0] is not None]

        if not existing_embeddings:
            # 기존 임베딩이 없으면 모든 기사 통과
            logger.info("기존 임베딩 없음 - 유사도 필터 스킵")
            return articles, embeddings

        logger.info(f"기존 임베딩 {len(existing_embeddings)}개와 비교")

        filtered_articles = []
        filtered_embeddings = []

        for article, embedding in zip(articles, embeddings):
            # Python에서 코사인 유사도 계산
            max_similarity = 0.0
            for existing_emb in existing_embeddings:
                sim = self._cosine_similarity(embedding, existing_emb)
                if sim > max_similarity:
                    max_similarity = sim

            if max_similarity < SIMILARITY_THRESHOLD:
                filtered_articles.append(article)
                filtered_embeddings.append(embedding)
            else:
                logger.debug(
                    f"유사 기사로 제외 (sim={max_similarity:.2f}): {article.title[:50]}"
                )

        return filtered_articles, filtered_embeddings

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """코사인 유사도 계산"""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _to_article_data(
        self,
        articles: list[NewsItem],
        embeddings: list[list[float]]
    ) -> list[ArticleData]:
        """NewsItem을 ArticleData로 변환"""
        result = []
        for article, embedding in zip(articles, embeddings):
            # source 추론 (press가 있으면 naver, 없으면 google)
            source = "naver" if article.press else "google_news"

            result.append(ArticleData(
                title=article.title,
                url=article.url,
                description=article.description,
                press=article.press or None,
                source=source,
                published_at=article.published_at,
                embedding=embedding,
            ))
        return result


# 싱글톤 인스턴스
collect_node = CollectNode()
