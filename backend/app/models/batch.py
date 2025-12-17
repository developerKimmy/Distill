from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class BatchRun(Base, UUIDMixin):
    __tablename__ = "batch_runs"

    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # started, completed, failed
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)  # schedule, manual
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sessions_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="batch_runs")