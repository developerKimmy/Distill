from datetime import datetime
from uuid import UUID
from sqlalchemy import Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class CredibilityCheck(Base, UUIDMixin):
    __tablename__ = "credibility_checks"

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
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 ~ 1.0
    evaluation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )

    # Relationships
    session = relationship("ResearchSession", back_populates="credibility_checks")
    source = relationship("Source", back_populates="credibility_checks")