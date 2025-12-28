"""add unique constraints for issue_articles and issue_follows

Revision ID: 7e9e4c2781c3
Revises: d3be486b2589
Create Date: 2025-12-29 03:29:49.010120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e9e4c2781c3'
down_revision: Union[str, None] = 'd3be486b2589'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # issue_articles: 인덱스 + 유니크 제약조건 추가
    op.create_index(op.f('ix_issue_articles_snapshot_id'), 'issue_articles', ['snapshot_id'], unique=False)
    op.create_index(op.f('ix_issue_articles_url'), 'issue_articles', ['url'], unique=False)
    op.create_unique_constraint('uq_issue_article_snapshot_url', 'issue_articles', ['snapshot_id', 'url'])

    # issue_follows: 인덱스 + 유니크 제약조건 (기존 것 교체)
    op.drop_constraint('uq_issue_follows_user_issue', 'issue_follows', type_='unique')
    op.create_index(op.f('ix_issue_follows_issue_id'), 'issue_follows', ['issue_id'], unique=False)
    op.create_index(op.f('ix_issue_follows_user_id'), 'issue_follows', ['user_id'], unique=False)
    op.create_unique_constraint('uq_issue_follow_user_issue', 'issue_follows', ['user_id', 'issue_id'])


def downgrade() -> None:
    # issue_follows 롤백
    op.drop_constraint('uq_issue_follow_user_issue', 'issue_follows', type_='unique')
    op.drop_index(op.f('ix_issue_follows_user_id'), table_name='issue_follows')
    op.drop_index(op.f('ix_issue_follows_issue_id'), table_name='issue_follows')
    op.create_unique_constraint('uq_issue_follows_user_issue', 'issue_follows', ['user_id', 'issue_id'])

    # issue_articles 롤백
    op.drop_constraint('uq_issue_article_snapshot_url', 'issue_articles', type_='unique')
    op.drop_index(op.f('ix_issue_articles_url'), table_name='issue_articles')
    op.drop_index(op.f('ix_issue_articles_snapshot_id'), table_name='issue_articles')
