from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDMixin


class BatchRun(Base, UUIDMixin):
    """글로벌 배치 실행 기록"""
    __tablename__ = "batch_runs"

    status: Mapped[str] = mapped_column(String(50), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)  # "scheduled", "manual"
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issues_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    issue_snapshots = relationship("IssueDailySnapshot", back_populates="batch_run", cascade="all, delete-orphan")