"""add_content_status_to_snapshots

Revision ID: 4f82ea7e995a
Revises: b0233696294c
Create Date: 2025-12-27 19:21:48.797192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f82ea7e995a'
down_revision: Union[str, None] = 'b0233696294c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. nullable로 먼저 추가
    op.add_column('issue_daily_snapshots', sa.Column('content_status', sa.String(length=20), nullable=True))
    # 2. 기존 데이터는 completed로 설정 (이미 처리 완료된 것들)
    op.execute("UPDATE issue_daily_snapshots SET content_status = 'completed'")
    # 3. NOT NULL 제약 추가
    op.alter_column('issue_daily_snapshots', 'content_status', nullable=False)


def downgrade() -> None:
    op.drop_column('issue_daily_snapshots', 'content_status')
