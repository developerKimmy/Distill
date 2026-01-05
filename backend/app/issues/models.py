from datetime import datetime, date
from uuid import UUID
from sqlalchemy import String, Text, Integer, Float, Date, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.base import Base, UUIDMixin, TimestampMixin


# System issue ID for unassigned articles
UNASSIGNED_ISSUE_ID = UUID('00000000-0000-0000-0000-000000000000')


class Entity(Base, UUIDMixin):
    """엔티티 마스터 (Who, Where)"""
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint('name', 'type', name='uq_entities_name_type'),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # person, org, loc
    aliases: Mapped[dict] = mapped_column(JSONB, server_default='[]')
    metadata_: Mapped[dict] = mapped_column('metadata', JSONB, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    issue_entities = relationship("IssueEntity", back_populates="entity", cascade="all, delete-orphan")


class Issue(Base, UUIDMixin, TimestampMixin):
    """이슈 마스터 (Mother Table)"""
    __tablename__ = "issues"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    what_type: Mapped[str | None] = mapped_column(String(50))  # IMPEACHMENT, TRIAL, etc.
    what_summary: Mapped[str | None] = mapped_column(String(255))
    first_seen_at: Mapped[date | None] = mapped_column(Date)
    last_seen_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), server_default='active')  # active, archived, system
    name_embedding = mapped_column(Vector(384), nullable=True)

    # Relationships
    articles = relationship("IssueArticle", back_populates="issue", cascade="all, delete-orphan")
    contents = relationship("IssueContent", back_populates="issue", cascade="all, delete-orphan")
    embeddings = relationship("IssueEmbedding", back_populates="issue", cascade="all, delete-orphan")
    keywords = relationship("IssueKeyword", back_populates="issue", cascade="all, delete-orphan")
    insights = relationship("IssueInsight", back_populates="issue", cascade="all, delete-orphan")
    issue_entities = relationship("IssueEntity", back_populates="issue", cascade="all, delete-orphan")
    followers = relationship("IssueFollow", back_populates="issue", cascade="all, delete-orphan")


class IssueEntity(Base, UUIDMixin):
    """이슈 ↔ 엔티티 매핑"""
    __tablename__ = "issue_entities"
    __table_args__ = (
        UniqueConstraint('issue_id', 'entity_id', name='uq_issue_entities'),
    )

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # primary, secondary, related
    first_seen_at: Mapped[date | None] = mapped_column(Date)
    last_seen_at: Mapped[date | None] = mapped_column(Date)
    mention_count: Mapped[int] = mapped_column(Integer, server_default='1')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="issue_entities")
    entity = relationship("Entity", back_populates="issue_entities")


class IssueArticle(Base, UUIDMixin):
    """이슈에 귀속된 기사"""
    __tablename__ = "issue_articles"
    __table_args__ = (
        UniqueConstraint('url', name='uq_issue_articles_url'),
    )

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    press: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(50))  # google_news, naver, tavily
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    entities: Mapped[dict] = mapped_column(JSONB, server_default='{}')  # NER 결과
    status: Mapped[str] = mapped_column(String(20), server_default='pending')  # pending, matched
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="articles")


class IssueContent(Base, UUIDMixin):
    """생성된 콘텐츠"""
    __tablename__ = "issue_contents"

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(default=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="contents")


class IssueEmbedding(Base, UUIDMixin):
    """이슈 임베딩 (RAG용)"""
    __tablename__ = "issue_embeddings"

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False
    )
    content_type: Mapped[str | None] = mapped_column(String(50))  # article, keyword, summary
    content: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(Vector(384))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="embeddings")


class IssueKeyword(Base, UUIDMixin):
    """이슈 키워드"""
    __tablename__ = "issue_keywords"

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False
    )
    keyword: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="keywords")


class IssueInsight(Base, UUIDMixin):
    """이슈 인사이트"""
    __tablename__ = "issue_insights"

    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False
    )
    verified_angles: Mapped[dict | None] = mapped_column(JSONB)
    content_directions: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    issue = relationship("Issue", back_populates="insights")


class IssueFollow(Base, UUIDMixin):
    """이슈 팔로우"""
    __tablename__ = "issue_follows"
    __table_args__ = (
        UniqueConstraint('user_id', 'issue_id', name='uq_issue_follows'),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    issue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="followed_issues")
    issue = relationship("Issue", back_populates="followers")


class DailyDigest(Base, UUIDMixin):
    """일간 다이제스트 요약"""
    __tablename__ = "daily_digests"

    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
