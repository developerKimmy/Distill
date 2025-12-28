import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.sensors.base import BaseSensor, Event

logger = logging.getLogger(__name__)


class NewIssueSensor(BaseSensor):
    """신규 핫이슈 감지 센서

    오늘 처음 등장한 이슈 중 기사량이 많은 것
    """

    MIN_ARTICLES = 15  # 최소 15개 이상이어야 핫이슈

    @property
    def sensor_type(self) -> str:
        return "new_issue"

    async def detect(self, db: AsyncSession) -> list[Event]:
        """신규 핫이슈 감지"""
        events = []

        query = text("""
            SELECT
                i.id as issue_id,
                i.name as issue_name,
                i.category,
                s.article_count
            FROM issues i
            JOIN issue_daily_snapshots s ON s.issue_id = i.id
            WHERE i.first_seen_at = CURRENT_DATE
              AND s.date = CURRENT_DATE
              AND s.article_count >= :min_articles
              AND i.status = 'active'
            ORDER BY s.article_count DESC
            LIMIT 5
        """)

        result = await db.execute(query, {"min_articles": self.MIN_ARTICLES})

        for row in result:
            importance = min(row.article_count / 50, 1.0)  # 50개면 max

            events.append(Event(
                type=self.sensor_type,
                issue_id=row.issue_id,
                issue_name=row.issue_name,
                category=row.category,
                importance=importance,
                message=f"🆕 새 이슈! '{row.issue_name}' ({row.category or '기타'}, 기사 {row.article_count}개)",
                data={
                    "article_count": row.article_count,
                }
            ))

        logger.info(f"NewIssueSensor: {len(events)}개 이벤트 감지")
        return events
