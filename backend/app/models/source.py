from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Source(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # web, document, scholar, youtube
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )
    seen_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    session_sources = relationship("SessionSource", back_populates="source")
    credibility_checks = relationship("CredibilityCheck", back_populates="source")


class SessionSource(Base, UUIDMixin):
    __tablename__ = "session_sources"
    __table_args__ = (
        UniqueConstraint("session_id", "source_id", name="uq_session_source"),
    )

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        nullable=False
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=False
    )
    topic_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("monitoring_topics.id"),
        nullable=True
    )
    is_new: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )

    # Relationships
    session = relationship("ResearchSession", back_populates="session_sources")
    source = relationship("Source", back_populates="session_sources")
    topic = relationship("MonitoringTopic", back_populates="session_sources")