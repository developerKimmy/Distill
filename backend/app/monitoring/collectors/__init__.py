"""뉴스 수집기"""
from app.monitoring.collectors.google_news import GoogleNewsProvider
from app.monitoring.collectors.naver_news import NaverNewsProvider, NewsItem

__all__ = [
    "GoogleNewsProvider",
    "NaverNewsProvider",
    "NewsItem",
]
