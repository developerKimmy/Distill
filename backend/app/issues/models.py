from datetime import datetime, date
from uuid import UUID
from sqlalchemy import String, Text, Integer, Float, Date, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, UUIDMixin, TimestampMixin


class Issue(Base, UUIDMixin, TimestampMixin):
    """이슈 마스터 - 클러스터링된 뉴스 이슈"""
    __tablename__ = "issues"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_seen_at: Mapped[date] = mapped_column(Date, nullable=False)
    last_seen_at: Mapped[date] = mapped_column(Date, nullable=False)
    total_snapshots: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Relationships
    snapshots = relationship("IssueDailySnapshot", back_populates="issue", cascade="all, delete-orphan")


class IssueDailySnapshot(Base, UUIDMixin):
    """이슈 일간 스냅샷"""
    __tablename__ = "issue_daily_snapshots"

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id"),
        nullable=False
    )
    batch_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("batch_runs.id"),
        nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="snapshots")
    batch_run = relationship("BatchRun", back_populates="issue_snapshots")
    articles = relationship("IssueArticle", back_populates="snapshot", cascade="all, delete-orphan")
    videos = relationship("IssueVideo", back_populates="snapshot", cascade="all, delete-orphan")
    insights = relationship("IssueInsight", back_populates="snapshot", cascade="all, delete-orphan")


class IssueArticle(Base, UUIDMixin):
    """이슈-기사 매핑"""
    __tablename__ = "issue_articles"

    snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issue_daily_snapshots.id"),
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    press: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    snapshot = relationship("IssueDailySnapshot", back_populates="articles")