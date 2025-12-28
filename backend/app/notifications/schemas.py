"""Notification Schemas"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationBase(BaseModel):
    """알림 기본 스키마"""

    type: str
    title: str
    message: str | None = None
    issue_id: UUID | None = None


class NotificationResponse(NotificationBase):
    """알림 응답 스키마"""

    id: UUID
    is_read: bool
    created_at: datetime

    # 이슈 정보 (있는 경우)
    issue_name: str | None = None
    issue_category: str | None = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """알림 목록 응답"""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """읽지 않은 알림 개수 응답"""

    count: int
