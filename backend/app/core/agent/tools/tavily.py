from tavily import TavilyClient
from app.core.agent.tools.base import SearchProvider, SearchResult
from app.core.config import settings
import time


class TavilySearchError(Exception):
    """Tavily 검색 에러"""
    pass


class TavilyProvider(SearchProvider):
    """Tavily 검색 Provider"""

    def __init__(self):
        if not settings.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY가 설정되지 않았습니다.")
        self.client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    @property
    def source_type(self) -> str:
        return "web"

    async def search(
            self,
            query: str,
            max_results: int = 5,
            max_retries: int = 3
    ) -> list[SearchResult]:
        """Tavily 검색 실행"""

        if not query or not query.strip():
            print("검색어가 비어있습니다.")
            return []

        for attempt in range(max_retries):
            try:
                response = self.client.search(
                    query=query,
                    max_results=max_results,
                    search_depth="basic"
                )

                results = response.get("results", [])

                if not results:
                    print(f"검색 결과 없음: {query}")
                    return []

                return [
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("content", ""),
                        source_type=self.source_type,
                        score=r.get("score", 0.0),
                        published_date=r.get("published_date")
                    )
                    for r in results
                ]

            except Exception as e:
                error_msg = str(e).lower()

                # Rate Limit
                if "rate" in error_msg or "limit" in error_msg or "429" in error_msg:
                    wait_time = (attempt + 1) * 5
                    print(f"Rate limited. {wait_time}초 대기... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                # API 키 에러
                if "api key" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
                    print("Tavily API 키가 유효하지 않습니다.")
                    raise TavilySearchError("Invalid API key")

                # 네트워크 에러
                if "connection" in error_msg or "timeout" in error_msg:
                    wait_time = (attempt + 1) * 2
                    print(f"네트워크 에러. {wait_time}초 후 재시도... (시도 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue

                # 기타 에러
                print(f"Tavily 검색 에러: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return []

        print(f"Tavily 검색 실패: 최대 재시도 횟수 초과 ({max_retries}회)")
        return []