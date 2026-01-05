"""schema redesign - clean slate for issues

Revision ID: 001_schema_redesign
Revises:
Create Date: 2024-01-01

Drop all issue-related tables and recreate with new schema.
Preserves: users, user_settings, notifications, agent_runs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


# revision identifiers
revision = '001_schema_redesign'
down_revision = 'ed9e4773bb82'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================
    # 1. DROP EXISTING TABLES
    # =====================
    op.execute("DROP TABLE IF EXISTS issue_insights CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_keywords CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_contents CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_articles CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_follows CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_daily_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS batch_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS issues CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_digests CASCADE")

    # =====================
    # 2. CREATE ENTITIES TABLE
    # =====================
    op.create_table(
        'entities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),  # person, org, loc
        sa.Column('aliases', JSONB, server_default='[]'),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('name', 'type', name='uq_entities_name_type')
    )

    # =====================
    # 3. CREATE ISSUES TABLE
    # =====================
    op.create_table(
        'issues',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(50)),
        sa.Column('what_type', sa.String(50)),
        sa.Column('what_summary', sa.String(255)),
        sa.Column('first_seen_at', sa.Date),
        sa.Column('last_seen_at', sa.Date),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('name_embedding', Vector(384)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # Create UNASSIGNED system issue
    op.execute("""
        INSERT INTO issues (id, name, category, status, what_type, first_seen_at, last_seen_at)
        VALUES (
            '00000000-0000-0000-0000-000000000000',
            'UNASSIGNED',
            'system',
            'system',
            'UNASSIGNED',
            CURRENT_DATE,
            CURRENT_DATE
        )
    """)

    # =====================
    # 4. CREATE ISSUE_ENTITIES TABLE
    # =====================
    op.create_table(
        'issue_entities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_id', UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),  # primary, secondary, related
        sa.Column('first_seen_at', sa.Date),
        sa.Column('last_seen_at', sa.Date),
        sa.Column('mention_count', sa.Integer, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('issue_id', 'entity_id', name='uq_issue_entities')
    )

    # =====================
    # 5. CREATE ISSUE_ARTICLES TABLE
    # =====================
    op.create_table(
        'issue_articles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('press', sa.String(100)),
        sa.Column('source', sa.String(50)),  # google_news, naver, tavily
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('entities', JSONB, server_default='{}'),
        sa.Column('status', sa.String(20), server_default='pending'),  # pending, matched
        sa.Column('matched_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('url', name='uq_issue_articles_url')
    )

    # =====================
    # 6. CREATE ISSUE_CONTENTS TABLE
    # =====================
    op.create_table(
        'issue_contents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500)),
        sa.Column('content', sa.Text),
        sa.Column('verified', sa.Boolean, server_default='false'),
        sa.Column('confidence_score', sa.Float, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # =====================
    # 7. CREATE ISSUE_EMBEDDINGS TABLE
    # =====================
    op.create_table(
        'issue_embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_type', sa.String(50)),  # article, keyword, summary
        sa.Column('content', sa.Text),
        sa.Column('embedding', Vector(384)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # =====================
    # 8. CREATE ISSUE_KEYWORDS TABLE
    # =====================
    op.create_table(
        'issue_keywords',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('keyword', sa.String(200)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # =====================
    # 9. CREATE ISSUE_INSIGHTS TABLE
    # =====================
    op.create_table(
        'issue_insights',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('verified_angles', JSONB),
        sa.Column('content_directions', JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # =====================
    # 10. CREATE ISSUE_FOLLOWS TABLE
    # =====================
    op.create_table(
        'issue_follows',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('issue_id', UUID(as_uuid=True), sa.ForeignKey('issues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('user_id', 'issue_id', name='uq_issue_follows')
    )

    # =====================
    # 11. CREATE DAILY_DIGESTS TABLE
    # =====================
    op.create_table(
        'daily_digests',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('date', sa.Date, nullable=False, unique=True),
        sa.Column('summary', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # =====================
    # 12. CREATE INDEXES
    # =====================
    op.create_index('ix_issue_articles_issue_id', 'issue_articles', ['issue_id'])
    op.create_index('ix_issue_articles_status', 'issue_articles', ['status'])
    op.create_index('ix_issue_entities_issue_id', 'issue_entities', ['issue_id'])
    op.create_index('ix_issue_entities_entity_id', 'issue_entities', ['entity_id'])
    op.create_index('ix_issues_status', 'issues', ['status'])
    op.create_index('ix_issues_category', 'issues', ['category'])


def downgrade() -> None:
    # Drop new tables
    op.execute("DROP TABLE IF EXISTS daily_digests CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_follows CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_insights CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_keywords CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_contents CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_articles CASCADE")
    op.execute("DROP TABLE IF EXISTS issue_entities CASCADE")
    op.execute("DROP TABLE IF EXISTS issues CASCADE")
    op.execute("DROP TABLE IF EXISTS entities CASCADE")

    # Note: Original tables are not restored in downgrade
    # A backup should be made before running this migration
