"""add unique constraint on issue_daily_snapshots issue_id date

Revision ID: ed9e4773bb82
Revises: a29a805ba327
Create Date: 2026-01-01 09:56:58.789585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed9e4773bb82'
down_revision: Union[str, None] = 'a29a805ba327'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_issue_daily_snapshots_issue_id_date',
        'issue_daily_snapshots',
        ['issue_id', 'date']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_issue_daily_snapshots_issue_id_date',
        'issue_daily_snapshots',
        type_='unique'
    )
