import requests
from datetime import datetime
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class NewsItem:
    """뉴스 아이템"""
    title: str
    url: str
    press: str
    description: str | None = None
    published_at: datetime | None = None


class NaverNewsProvider:
    """네이버 뉴스 스크래핑 + 검색 API"""

    RANKING_URL = "https://news.naver.com/main/ranking/popularDay.naver"
    SEARCH_API_URL = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self):
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def get_ranking_news(self) -> list[NewsItem]:
        """랭킹 페이지에서 뉴스 제목 + URL 스크래핑"""
        response = requests.get(self.RANKING_URL, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        boxes = soup.select("div.rankingnews_box")

        news_list = []
        for box in boxes:
            press_elem = box.select_one("strong.rankingnews_name")
            if not press_elem:
                continue
            press_name = press_elem.text.strip()

            articles = box.select("a.list_title")
            for article in articles:
                news_list.append(NewsItem(
                    title=article.text.strip(),
                    url=article["href"],
                    press=press_name
                ))

        return news_list

    def search_news(self, query: str, display: int = 3, sort: str = "date") -> list[NewsItem]:
        """네이버 검색 API로 뉴스 검색

        Args:
            query: 검색어
            display: 결과 개수 (기본 3개)
            sort: 정렬 방식 - "date" (최신순) 또는 "sim" (관련도순)
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 환경변수 필요")

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        params = {
            "query": query,
            "display": display,
            "sort": sort
        }

        response = requests.get(self.SEARCH_API_URL, headers=headers, params=params)
        response.raise_for_status()

        items = response.json().get("items", [])

        news_list = []
        for item in items:
            # HTML 태그 제거
            title = BeautifulSoup(item["title"], "html.parser").get_text()
            description = BeautifulSoup(item["description"], "html.parser").get_text()

            # pubDate 파싱 (RFC 822 형식: "Mon, 01 Jan 2024 12:00:00 +0900")
            pub_date = None
            if item.get("pubDate"):
                try:
                    pub_date = parsedate_to_datetime(item["pubDate"])
                except Exception:
                    pass

            news_list.append(NewsItem(
                title=title,
                url=item["link"],
                press="",
                description=description,
                published_at=pub_date
            ))

        return news_list