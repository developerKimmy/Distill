from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class MonitoringTopic(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "monitoring_topics"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[dict] = mapped_column(JSONB, nullable=False)  # ["AI", "에이전트", ...]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="topics")
    sessions = relationship("ResearchSession", back_populates="monitoring_topic")
    session_sources = relationship("SessionSource", back_populates="topic")