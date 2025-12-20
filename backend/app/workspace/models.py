from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDMixin, TimestampMixin


class Workspace(Base, UUIDMixin, TimestampMixin):
    """워크스페이스 - 사용자별 배치 설정"""
    __tablename__ = "workspaces"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True
    )
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Seoul", nullable=False)
    category_filter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="workspace")
    batch_runs = relationship("BatchRun", back_populates="workspace", cascade="all, delete-orphan")