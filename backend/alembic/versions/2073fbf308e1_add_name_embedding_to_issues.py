"""add name_embedding to issues

Revision ID: 2073fbf308e1
Revises: global_batch_001
Create Date: 2025-12-27 01:11:53.396822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '2073fbf308e1'
down_revision: Union[str, None] = 'global_batch_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('issues', sa.Column('name_embedding', Vector(384), nullable=True))


def downgrade() -> None:
    op.drop_column('issues', 'name_embedding')
