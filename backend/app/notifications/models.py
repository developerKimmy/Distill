from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDMixin, TimestampMixin


class Notification(Base, UUIDMixin, TimestampMixin):
    """인앱 알림"""
    __tablename__ = "notifications"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # article_surge, sentiment_shift, followed_update, new_issue
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id"),
        nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")
    issue = relationship("Issue")


class AgentRun(Base, UUIDMixin):
    """Agent 실행 기록"""
    __tablename__ = "agent_runs"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="running",
        nullable=False
    )  # running, completed, failed
    articles_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issues_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    events_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notifications_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
