"""Alembic environment: runs migrations against NYAYASIM_DATABASE_URL (or an explicit URL
passed by tests via config attributes)."""

from alembic import context
from sqlalchemy import create_engine

from app.config import settings

config = context.config


def run_migrations_online() -> None:
    url = config.attributes.get("database_url") or settings.database_url
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline SQL generation is not supported; run against a database.")
run_migrations_online()
