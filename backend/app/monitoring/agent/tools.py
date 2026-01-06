"""Agent 도구 래퍼 - 모든 Provider를 Agent에서 사용할 수 있게 래핑"""
import logging
from datetime import datetime, timezone, timedelta

from app.core.agent.tools import TavilyProvider, EmbeddingProvider
from app.core.agent.tools.gap_analyzer import GapAnalyzer, GapAnalysisResult
from app.monitoring.collectors import GoogleNewsProvider, NaverNewsProvider
from app.monitoring.agent.state import SupplementaryData

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))


class AgentToolkit:
    """Agent가 사용할 도구 모음

    도구 목록:
    - search_tavily: 웹 검색 (팩트 검증, 추가 정보)
    - search_naver: 한국 뉴스 검색
    - search_google: Google News RSS 검색
    - analyze_gaps: 정보 부족 분석
    """

    def __init__(self):
        self.tavily = TavilyProvider()
        self.google = GoogleNewsProvider()
        self.naver = NaverNewsProvider()
        self.gap_analyzer = GapAnalyzer()
        self.embedding = EmbeddingProvider()

    async def search_tavily(
        self,
        query: str,
        max_results: int = 5
    ) -> list[SupplementaryData]:
        """Tavily 웹 검색 - 팩트 검증, 추가 정보 수집

        Args:
            query: 검색어
            max_results: 최대 결과 수

        Returns:
            SupplementaryData 리스트
        """
        try:
            results = await self.tavily.search(query, max_results)
            return [
                SupplementaryData(
                    source="tavily",
                    query=query,
                    title=r["title"],
                    url=r["url"],
                    content=r["snippet"]
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"[AgentToolkit] Tavily 검색 실패: {e}")
            return []

    async def search_naver(
        self,
        query: str,
        display: int = 5
    ) -> list[dict]:
        """Naver 뉴스 검색 - 한국 로컬 뉴스

        Args:
            query: 검색어
            display: 결과 수

        Returns:
            ArticleData 호환 dict 리스트
        """
        try:
            results = self.naver.search_news(query, display=display, sort="date")
            return [
                {
                    "title": r.title,
                    "url": r.url,
                    "description": r.description,
                    "press": r.press or "",
                    "source": "naver",
                    "published_at": r.published_at,
                    "embedding": None
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[AgentToolkit] Naver 검색 실패: {e}")
            return []

    async def search_google(
        self,
        query: str,
        limit: int = 5
    ) -> list[dict]:
        """Google News RSS 검색

        Args:
            query: 검색어
            limit: 결과 수

        Returns:
            ArticleData 호환 dict 리스트
        """
        try:
            results = await self.google.search(query, limit=limit)
            return [
                {
                    "title": r.title,
                    "url": r.url,
                    "description": r.description,
                    "press": r.press or "",
                    "source": "google_news",
                    "published_at": r.published_at,
                    "embedding": None
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[AgentToolkit] Google 검색 실패: {e}")
            return []

    def analyze_gaps(
        self,
        issue_name: str,
        articles: list[dict],
        keywords: list[str] | None = None
    ) -> GapAnalysisResult:
        """정보 부족 분석

        Args:
            issue_name: 이슈명
            articles: 기사 리스트
            keywords: 키워드 (선택)

        Returns:
            GapAnalysisResult (confidence, gaps, key_claims)
        """
        try:
            return self.gap_analyzer.analyze(issue_name, articles, keywords)
        except Exception as e:
            logger.error(f"[AgentToolkit] Gap 분석 실패: {e}")
            from app.core.agent.tools.gap_analyzer import GapAnalysisResult
            return GapAnalysisResult(gaps=[], key_claims=[], confidence=0.5)


# 싱글톤 인스턴스
toolkit = AgentToolkit()
