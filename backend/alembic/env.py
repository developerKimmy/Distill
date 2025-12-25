from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import sys
from pathlib import Path

# backend 경로 추가
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pgvector.sqlalchemy

from app.core.base import Base
from app.core.config import settings
from app.auth.models import User
from app.settings.models import UserSettings
from app.batch.models import BatchRun
from app.issues.models import (
    Issue, IssueDailySnapshot, IssueArticle,
    IssueKeyword, IssueEmbedding, IssueContent
)
from app.insights.models import IssueInsight


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# .env에서 DATABASE_URL 가져오기 (sync 드라이버로 변환)
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
# asyncpg 제거하고 psycopg2 사용
db_url = db_url.replace("+asyncpg", "")
db_url = db_url.replace("postgres://", "postgresql://")
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()