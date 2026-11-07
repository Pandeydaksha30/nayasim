"""A database outage mid-run must not crash ingestion or double-count anything."""

import pytest
from sqlalchemy.exc import OperationalError

from app.ingestion import pipeline


def _drop(*_args, **_kwargs):
    raise OperationalError("INSERT ...", {}, Exception("server closed the connection unexpectedly"))


def test_order_is_retried_after_database_drop(monkeypatch):
    calls = []

    def flaky(engine, oid, fetcher, ocr, store_dir, report):
        calls.append(oid)
        report.attempted += 1
        if len(calls) == 1:
            _drop()
        report.stored += 1

    monkeypatch.setattr(pipeline, "ingest_order", flaky)
    lines: list[str] = []
    report = pipeline.ingest_pending(None, [7], None, None, None, progress=lines.append, db_retry_s=0)
    assert calls == [7, 7]
    assert (report.attempted, report.stored, report.failures) == (1, 1, [])
    assert "database unavailable" in lines[0] and lines[-1].endswith("ok")


def test_run_stops_cleanly_when_database_stays_down(monkeypatch):
    monkeypatch.setattr(pipeline, "ingest_order", lambda *a, **k: _drop())
    with pytest.raises(pipeline.DatabaseUnavailable, match="order 9"):
        pipeline.ingest_pending(
            None, [9], None, None, None, progress=lambda _: None, db_retry_s=0, db_retry_limit=2
        )
