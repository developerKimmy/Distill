"""add_issue_follows_table

Revision ID: b0233696294c
Revises: 2073fbf308e1
Create Date: 2025-12-27 18:10:29.887689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0233696294c'
down_revision: Union[str, None] = '2073fbf308e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('issue_follows',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('issue_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['issue_id'], ['issues.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # 유니크 제약 추가: 한 사용자가 같은 이슈를 중복 팔로우 방지
    op.create_unique_constraint('uq_issue_follows_user_issue', 'issue_follows', ['user_id', 'issue_id'])


def downgrade() -> None:
    op.drop_table('issue_follows')
