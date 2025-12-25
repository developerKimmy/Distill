"""global batch refactor - remove per-user batch, add notification settings

Revision ID: global_batch_001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'global_batch_001'
down_revision: Union[str, None] = 'f774c2ccd38a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. batch_runs에서 workspace_id FK 및 컬럼 제거
    op.drop_constraint('batch_runs_workspace_id_fkey', 'batch_runs', type_='foreignkey')
    op.drop_column('batch_runs', 'workspace_id')

    # 2. workspaces 테이블을 user_settings로 이름 변경
    op.rename_table('workspaces', 'user_settings')

    # 3. user_settings에서 배치 관련 컬럼 제거
    op.drop_column('user_settings', 'schedule')
    op.drop_column('user_settings', 'is_active')
    op.drop_column('user_settings', 'last_run_at')

    # 4. notification_enabled -> email_notifications_enabled 컬럼 이름 변경
    op.alter_column('user_settings', 'notification_enabled',
                    new_column_name='email_notifications_enabled')

    # 5. notification_times 컬럼 추가
    op.add_column('user_settings', sa.Column(
        'notification_times',
        sa.String(100),
        nullable=True
    ))

    # 6. users에서 has_workspace 컬럼 제거
    op.drop_column('users', 'has_workspace')

    # 7. 인덱스/제약조건 이름 변경 (workspaces -> user_settings)
    # user_id unique 제약조건
    op.drop_constraint('workspaces_user_id_key', 'user_settings', type_='unique')
    op.create_unique_constraint('user_settings_user_id_key', 'user_settings', ['user_id'])

    # FK 제약조건 (users.id 참조)
    op.drop_constraint('workspaces_user_id_fkey', 'user_settings', type_='foreignkey')
    op.create_foreign_key(
        'user_settings_user_id_fkey',
        'user_settings',
        'users',
        ['user_id'],
        ['id']
    )


def downgrade() -> None:
    # 역순으로 롤백

    # 7. 제약조건 이름 복원
    op.drop_constraint('user_settings_user_id_fkey', 'user_settings', type_='foreignkey')
    op.create_foreign_key('workspaces_user_id_fkey', 'user_settings', 'users', ['user_id'], ['id'])

    op.drop_constraint('user_settings_user_id_key', 'user_settings', type_='unique')
    op.create_unique_constraint('workspaces_user_id_key', 'user_settings', ['user_id'])

    # 6. users에 has_workspace 복원
    op.add_column('users', sa.Column('has_workspace', sa.Boolean(), nullable=True, server_default='false'))

    # 5. notification_times 제거
    op.drop_column('user_settings', 'notification_times')

    # 4. email_notifications_enabled -> notification_enabled 컬럼 이름 복원
    op.alter_column('user_settings', 'email_notifications_enabled',
                    new_column_name='notification_enabled')

    # 3. user_settings에 배치 관련 컬럼 복원
    op.add_column('user_settings', sa.Column('schedule', sa.String(100), nullable=True))
    op.add_column('user_settings', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('user_settings', sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True))

    # 2. user_settings를 workspaces로 이름 변경
    op.rename_table('user_settings', 'workspaces')

    # 1. batch_runs에 workspace_id 복원
    op.add_column('batch_runs', sa.Column(
        'workspace_id',
        sa.UUID(),
        nullable=True
    ))
    op.create_foreign_key(
        'batch_runs_workspace_id_fkey',
        'batch_runs',
        'workspaces',
        ['workspace_id'],
        ['id']
    )
