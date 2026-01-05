import httpx
import feedparser
from datetime import datetime
from time import mktime
from dataclasses import dataclass

from app.monitoring.collectors.naver_news import NewsItem


class GoogleNewsProvider:
    """Google News RSS 수집"""

    # 한국어 Google News RSS 피드 (카테고리별)
    CATEGORY_FEEDS = {
        "정치": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFZ4ZERBU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR:ko",
        "경제": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
        "사회": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
        "세계": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
        "IT/과학": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
        "연예": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR:ko",
    }

    # 한국 전체 뉴스 피드
    TOP_NEWS_FEED = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"
        }

    async def fetch_top_news(self, limit: int = 30) -> list[NewsItem]:
        """한국 주요 뉴스 가져오기"""
        return await self._fetch_feed(self.TOP_NEWS_FEED, limit)

    async def fetch_by_category(self, category: str, limit: int = 20) -> list[NewsItem]:
        """카테고리별 뉴스 가져오기"""
        feed_url = self.CATEGORY_FEEDS.get(category)
        if not feed_url:
            return []
        return await self._fetch_feed(feed_url, limit, category=category)

    async def fetch_all_categories(self, limit_per_category: int = 15) -> list[NewsItem]:
        """모든 카테고리 뉴스 가져오기"""
        all_news = []
        for category in self.CATEGORY_FEEDS.keys():
            news = await self.fetch_by_category(category, limit_per_category)
            all_news.extend(news)
        return all_news

    async def _fetch_feed(
        self,
        feed_url: str,
        limit: int,
        category: str | None = None
    ) -> list[NewsItem]:
        """RSS 피드 파싱"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(feed_url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
        except Exception as e:
            print(f"Google News RSS fetch error: {e}")
            return []

        feed = feedparser.parse(response.text)
        news_list = []

        for entry in feed.entries[:limit]:
            # 발행일 파싱
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    pub_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                except Exception:
                    pass

            # 언론사 추출 (Google News는 제목에 " - 언론사" 형식으로 포함)
            title = entry.title
            press = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title = parts[0].strip()
                    press = parts[1].strip()

            # description에서 HTML 제거
            description = None
            if hasattr(entry, 'summary'):
                from bs4 import BeautifulSoup
                description = BeautifulSoup(entry.summary, "html.parser").get_text()
                # 너무 길면 잘라내기
                if description and len(description) > 500:
                    description = description[:500] + "..."

            news_list.append(NewsItem(
                title=title,
                url=entry.link,
                press=press,
                description=description,
                published_at=pub_date
            ))

        return news_list

    async def search(self, query: str, limit: int = 10) -> list[NewsItem]:
        """Google News 검색 (RSS 기반)"""
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        return await self._fetch_feed(search_url, limit)
