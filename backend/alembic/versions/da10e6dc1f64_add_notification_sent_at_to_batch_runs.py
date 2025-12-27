"""add_notification_sent_at_to_batch_runs

Revision ID: da10e6dc1f64
Revises: 4f82ea7e995a
Create Date: 2025-12-28 01:20:21.563149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da10e6dc1f64'
down_revision: Union[str, None] = '4f82ea7e995a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('batch_runs', sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('batch_runs', 'notification_sent_at')
