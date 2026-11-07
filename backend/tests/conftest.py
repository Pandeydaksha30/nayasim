"""Shared fixtures. Database tests run against a throwaway database `<name>_test` on the
configured server, migrated from scratch and dropped afterwards.

If Postgres is not reachable the database tests are skipped with a visible reason
(pytest is configured with -rs). Set NYAYASIM_REQUIRE_DB=1 to make that a failure instead.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.config import settings


def _admin_and_test_urls() -> tuple[str, str]:
    url = make_url(settings.database_url)
    test_url = url.set(database=f"{url.database}_test")
    admin_url = url.set(database="postgres")
    return admin_url.render_as_string(hide_password=False), test_url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    admin_url, test_url = _admin_and_test_urls()
    test_db = make_url(test_url).database
    try:
        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    except Exception as e:  # noqa: BLE001 - reported, not swallowed
        msg = (
            f"Postgres not reachable ({type(e).__name__}: {e}). "
            "Start it: docker compose -f infra/docker-compose.yml up -d"
        )
        if os.environ.get("NYAYASIM_REQUIRE_DB") == "1":
            pytest.fail(msg)
        pytest.skip(msg)

    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = test_url
    command.upgrade(cfg, "head")

    engine = create_engine(test_url)
    yield engine
    engine.dispose()

    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after each test."""
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    conn.close()
