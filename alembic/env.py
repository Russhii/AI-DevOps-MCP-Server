"""Alembic environment: the database URL comes from DATABASE_URL (never hardcoded)."""

from sqlalchemy import create_engine

import app.models.task  # noqa: F401  (registers tables on Base.metadata)
from alembic import context
from app.config import get_settings
from app.database import Base

target_metadata = Base.metadata
url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
