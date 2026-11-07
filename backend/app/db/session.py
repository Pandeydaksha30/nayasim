"""Database engine and per-request sessions for the API."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """One session per request: committed if the handler succeeds, rolled back otherwise."""
    with Session(get_engine()) as s:
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
