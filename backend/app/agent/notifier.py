import logging
from datetime import date
from uuid import UUID
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.sensors.base import Event
from app.common.utils import EmailService
from app.core.config import settings
from app.notifications.models import Notification
from app.auth.models import User
from app.settings.models import UserSettings
from app.issues.models import IssueFollow

logger = logging.getLogger(__name__)


class Notifier:
    """알림 발송 관리자"""

    def __init__(self):
        self.email_service = None
        if settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
            self.email_service = EmailService(
                gmail_user=settings.GMAIL_USER,
                gmail_app_password=settings.GMAIL_APP_PASSWORD
            )
        # 이메일 버퍼: user_email -> list of issue data
        self._email_buffer: dict[str, list[dict]] = defaultdict(list)

    async def notify(self, event: Event, db: AsyncSession) -> int:
        """이벤트에 대한 알림 발송 (이메일은 버퍼에 저장)

        Returns:
            발송된 인앱 알림 수
        """
        notifications_sent = 0

        # 이벤트 타입별 처리
        if event.type == "followed_update":
            # 특정 유저에게만 알림
            notifications_sent = await self._notify_followed_update(event, db)
        else:
            # 카테고리 구독자에게 알림
            notifications_sent = await self._notify_category_subscribers(event, db)

        return notifications_sent

    def flush_emails(self) -> int:
        """버퍼에 모인 이메일을 한번에 발송

        Returns:
            발송된 이메일 수
        """
        if not self.email_service:
            self._email_buffer.clear()
            return 0

        emails_sent = 0
        for user_email, issues in self._email_buffer.items():
            if not issues:
                continue
            try:
                self.email_service.send_followed_issues_update(
                    recipient=user_email,
                    issues=issues
                )
                emails_sent += 1
                logger.info(f"[EMAIL] 팔로우 이슈 업데이트 발송: {user_email} ({len(issues)}개 이슈)")
            except Exception as e:
                logger.error(f"이메일 발송 실패: {user_email}, {e}")

        self._email_buffer.clear()
        return emails_sent

    async def _notify_followed_update(self, event: Event, db: AsyncSession) -> int:
        """팔로우 이슈 업데이트 알림"""
        user_id = event.data.get("user_id")
        user_email = event.data.get("user_email")

        if not user_id:
            return 0

        # 중복 체크 (오늘 같은 이슈로 알림 보냈는지)
        if await self._already_notified(UUID(user_id), event.issue_id, event.type, db):
            logger.debug(f"이미 알림 보냄: user={user_id}, issue={event.issue_id}")
            return 0

        # 인앱 알림 저장
        await self._save_notification(UUID(user_id), event, db)

        # 이메일은 버퍼에 저장 (나중에 flush_emails()에서 한번에 발송)
        if user_email:
            self._email_buffer[user_email].append({
                "name": event.issue_name,
                "category": event.category,
                "summary": event.data.get("summary", ""),
                "article_count": event.data.get("article_count", 0),
            })

        return 1

    async def _notify_category_subscribers(self, event: Event, db: AsyncSession) -> int:
        """카테고리 구독자에게 알림"""
        notifications_sent = 0

        # 해당 카테고리를 구독하고 알림 활성화된 유저 조회
        users = await self._get_category_subscribers(event.category, db)

        for user in users:
            # 중복 체크
            if await self._already_notified(user.id, event.issue_id, event.type, db):
                continue

            # 인앱 알림 저장
            await self._save_notification(user.id, event, db)
            notifications_sent += 1

            # 중요한 이벤트만 이메일 버퍼에 추가
            if event.importance >= 0.7:
                self._email_buffer[user.email].append({
                    "name": event.issue_name,
                    "category": event.category,
                    "summary": event.message,
                    "article_count": event.data.get("today_count", 0),
                })

        return notifications_sent

    async def _get_category_subscribers(
        self,
        category: str | None,
        db: AsyncSession
    ) -> list[User]:
        """카테고리 구독자 조회"""
        # UserSettings를 미리 로드하여 lazy load 방지
        query = (
            select(User)
            .join(UserSettings, User.id == UserSettings.user_id)
            .options(selectinload(User.settings))
            .where(
                User.is_active == True,
                UserSettings.email_notifications_enabled == True
            )
        )

        result = await db.execute(query)
        users = list(result.scalars().all())

        # 카테고리 필터링
        if category:
            filtered_users = []
            for user in users:
                # settings가 이미 로드되어 있으므로 안전하게 접근 가능
                settings = getattr(user, 'settings', None)
                if settings:
                    category_filter = settings.category_filter
                    if not category_filter or category in category_filter.split(","):
                        filtered_users.append(user)
                else:
                    filtered_users.append(user)
            return filtered_users

        return users

    async def _already_notified(
        self,
        user_id: UUID,
        issue_id: UUID | None,
        event_type: str,
        db: AsyncSession
    ) -> bool:
        """오늘 이미 알림 보냈는지 확인"""
        from sqlalchemy import func

        query = (
            select(Notification.id)
            .where(
                Notification.user_id == user_id,
                Notification.type == event_type,
                func.date(Notification.created_at) == date.today()
            )
        )

        if issue_id:
            query = query.where(Notification.issue_id == issue_id)

        result = await db.execute(query)
        return result.scalar() is not None

    async def _save_notification(
        self,
        user_id: UUID,
        event: Event,
        db: AsyncSession
    ) -> Notification:
        """인앱 알림 저장"""
        notification = Notification(
            user_id=user_id,
            type=event.type,
            title=event.message,
            message=event.data.get("summary", ""),
            issue_id=event.issue_id,
            is_read=False
        )
        db.add(notification)
        await db.flush()

        logger.info(f"알림 저장: user={user_id}, type={event.type}, issue={event.issue_name}")
        return notification
