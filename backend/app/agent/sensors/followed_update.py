import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.sensors.base import BaseSensor, Event

logger = logging.getLogger(__name__)


class FollowedUpdateSensor(BaseSensor):
    """팔로우 이슈 업데이트 감지 센서

    사용자가 팔로우한 이슈에 새 스냅샷이 생기면 감지
    오늘 이미 알림 보낸 것은 제외
    """

    @property
    def sensor_type(self) -> str:
        return "followed_update"

    async def detect(self, db: AsyncSession) -> list[Event]:
        """팔로우 이슈 업데이트 감지"""
        events = []

        # 팔로우한 이슈 중 오늘 새 스냅샷이 있고, 아직 알림 안 보낸 것
        query = text("""
            SELECT DISTINCT ON (f.user_id, i.id)
                f.user_id,
                u.email as user_email,
                i.id as issue_id,
                i.name as issue_name,
                i.category,
                s.article_count,
                s.summary
            FROM issue_follows f
            JOIN issues i ON i.id = f.issue_id
            JOIN users u ON u.id = f.user_id
            JOIN issue_daily_snapshots s ON s.issue_id = i.id
            LEFT JOIN notifications n ON
                n.user_id = f.user_id
                AND n.issue_id = i.id
                AND n.type = 'followed_update'
                AND DATE(n.created_at) = CURRENT_DATE
            WHERE s.date = CURRENT_DATE
              AND n.id IS NULL
              AND u.is_active = true
        """)

        result = await db.execute(query)

        for row in result:
            events.append(Event(
                type=self.sensor_type,
                issue_id=row.issue_id,
                issue_name=row.issue_name,
                category=row.category,
                importance=0.8,  # 팔로우한 건 항상 중요
                message=f"🔔 '{row.issue_name}' 새 소식! (기사 {row.article_count}개)",
                data={
                    "user_id": str(row.user_id),
                    "user_email": row.user_email,
                    "article_count": row.article_count,
                    "summary": row.summary,
                }
            ))

        logger.info(f"FollowedUpdateSensor: {len(events)}개 이벤트 감지")
        return events
