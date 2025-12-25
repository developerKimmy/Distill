from uuid import UUID
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDMixin, TimestampMixin


class UserSettings(Base, UUIDMixin, TimestampMixin):
    """유저 설정 - 이메일 알림 설정"""
    __tablename__ = "user_settings"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True
    )
    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    notification_times: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "09:00,18:00" 형식
    timezone: Mapped[str] = mapped_column(
        String(50), default="Asia/Seoul", nullable=False
    )
    category_filter: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Relationships
    user = relationship("User", back_populates="settings")
