"""drop_unused_tables_and_columns

Revision ID: f774c2ccd38a
Revises: 0e41028ae527
Create Date: 2025-12-25 00:01:43.870287

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f774c2ccd38a'
down_revision: Union[str, None] = '0e41028ae527'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop issue_comments first (FK to issue_videos)
    op.drop_table('issue_comments')

    # Drop issue_videos table
    op.drop_table('issue_videos')

    # Drop raw_analysis column from issue_insights
    op.drop_column('issue_insights', 'raw_analysis')


def downgrade() -> None:
    # Re-add raw_analysis column
    op.add_column('issue_insights', sa.Column('raw_analysis', sa.Text(), nullable=True))

    # Re-create issue_videos table
    op.create_table(
        'issue_videos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('snapshot_id', sa.UUID(), nullable=False),
        sa.Column('video_id', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('channel', sa.String(255), nullable=True),
        sa.Column('view_count', sa.Integer(), default=0, nullable=False),
        sa.Column('angle', sa.String(255), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['issue_daily_snapshots.id'])
    )

    # Re-create issue_comments table
    op.create_table(
        'issue_comments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('video_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('like_count', sa.Integer(), default=0, nullable=False),
        sa.Column('intent', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['video_id'], ['issue_videos.id'])
    )
