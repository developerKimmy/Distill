from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class ResearchSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "research_sessions"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False
    )
    monitoring_topic_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("monitoring_topics.id"),
        nullable=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50),
                                        nullable=False)  # queued, planning, searching, analyzing, completed, failed
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # realtime, background, scheduled

    # Relationships
    workspace = relationship("Workspace", back_populates="sessions")
    monitoring_topic = relationship("MonitoringTopic", back_populates="sessions")
    agent_logs = relationship("AgentLog", back_populates="session")
    session_sources = relationship("SessionSource", back_populates="session")
    credibility_checks = relationship("CredibilityCheck", back_populates="session")
    report = relationship("Report", back_populates="session", uselist=False)
    notifications = relationship("Notification", back_populates="session")


class AgentLog(Base, UUIDMixin):
    __tablename__ = "agent_logs"

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("research_sessions.id"),
        nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    log_type: Mapped[str] = mapped_column(String(50), nullable=False)  # thinking, action, observation, error
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )

    # Relationships
    session = relationship("ResearchSession", back_populates="agent_logs")