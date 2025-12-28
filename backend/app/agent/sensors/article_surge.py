import logging
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.sensors.base import BaseSensor, Event

logger = logging.getLogger(__name__)


class ArticleSurgeSensor(BaseSensor):
    """기사량 급증 감지 센서

    7일 평균 대비 2배 이상이면 급증으로 판단
    """

    SURGE_THRESHOLD = 2.0  # 평균의 2배 이상
    MIN_ARTICLES = 10  # 최소 기사 수

    @property
    def sensor_type(self) -> str:
        return "article_surge"

    async def detect(self, db: AsyncSession) -> list[Event]:
        """기사량 급증 이슈 감지"""
        events = []

        query = text("""
            WITH today_snapshots AS (
                SELECT
                    s.issue_id,
                    s.article_count,
                    i.name as issue_name,
                    i.category
                FROM issue_daily_snapshots s
                JOIN issues i ON i.id = s.issue_id
                WHERE s.date = CURRENT_DATE
                  AND i.status = 'active'
            ),
            weekly_avg AS (
                SELECT
                    issue_id,
                    AVG(article_count) as avg_count,
                    STDDEV(article_count) as std_count
                FROM issue_daily_snapshots
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                  AND date < CURRENT_DATE
                GROUP BY issue_id
                HAVING COUNT(*) >= 3
            )
            SELECT
                t.issue_id,
                t.issue_name,
                t.category,
                t.article_count as today_count,
                COALESCE(w.avg_count, 0) as avg_count,
                COALESCE(w.std_count, 0) as std_count
            FROM today_snapshots t
            LEFT JOIN weekly_avg w ON w.issue_id = t.issue_id
            WHERE t.article_count > GREATEST(COALESCE(w.avg_count, 0) * :threshold, :min_articles)
        """)

        result = await db.execute(query, {
            "threshold": self.SURGE_THRESHOLD,
            "min_articles": self.MIN_ARTICLES
        })

        for row in result:
            ratio = row.today_count / max(row.avg_count, 1)
            importance = min(ratio / 5, 1.0)  # 5배면 importance=1.0

            events.append(Event(
                type=self.sensor_type,
                issue_id=row.issue_id,
                issue_name=row.issue_name,
                category=row.category,
                importance=importance,
                message=f"📈 '{row.issue_name}' 기사 급증! (평소 {row.avg_count:.0f}개 → 오늘 {row.today_count}개)",
                data={
                    "today_count": row.today_count,
                    "avg_count": float(row.avg_count),
                    "ratio": ratio,
                }
            ))

        logger.info(f"ArticleSurgeSensor: {len(events)}개 이벤트 감지")
        return events
