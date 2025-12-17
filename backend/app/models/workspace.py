from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Workspace(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule: Mapped[str] = mapped_column(String(50), nullable=False)  # daily, weekly, monthly
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    topics = relationship("MonitoringTopic", back_populates="workspace")
    sessions = relationship("ResearchSession", back_populates="workspace")
    notifications = relationship("Notification", back_populates="workspace")
    documents = relationship("Document", back_populates="workspace")
    batch_runs = relationship("BatchRun", back_populates="workspace")