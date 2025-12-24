from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDMixin


class IssueInsight(Base, UUIDMixin):
    """이슈-인사이트 (니즈 + 콘텐츠 방향)"""
    __tablename__ = "issue_insights"

    snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issue_daily_snapshots.id"),
        nullable=False
    )
    verified_angles: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_directions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    snapshot = relationship("IssueDailySnapshot", back_populates="insights")