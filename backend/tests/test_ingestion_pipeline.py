"""End-to-end ingestion against a local HTTP server and the test database."""

from __future__ import annotations

import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import FetchLog, Order, OrderChunk, OrderPage
from app.ingestion.fetcher import FetchError, PoliteFetcher
from app.ingestion.hrera_listing import ListedOrder
from app.ingestion.pipeline import ingest_pending, pending_orders, register_listing
from tests.pdf_factory import text_pdf

PARA = "The promoter shall pay interest at the prescribed rate for every month of delay till possession. "
GOOD_PDF = text_pdf([PARA * 30, PARA * 12])
FILES = {"/good.pdf": GOOD_PDF, "/notpdf.pdf": b"<html>Session expired</html>"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = FILES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def clean_db(db_engine):
    """Pipeline code commits through its own sessions, so clean before and after each test."""
    wipe = text("TRUNCATE orders, fetch_log RESTART IDENTITY CASCADE")
    with db_engine.begin() as c:
        c.execute(wipe)
    yield db_engine
    with db_engine.begin() as c:
        c.execute(wipe)


def listed(no: str, url: str | None) -> ListedOrder:
    return ListedOrder(no, "Buyer", "Builder", "HRERA Complaints", date(2024, 6, 1), url)


def test_fetcher_logs_success_and_failure(clean_db, server):
    f = PoliteFetcher(clean_db, min_delay_s=0)
    assert f.get(f"{server}/good.pdf").body.startswith(b"%PDF")
    with pytest.raises(FetchError):
        f.get(f"{server}/missing.pdf")
    with Session(clean_db) as s:
        logs = s.scalars(select(FetchLog).order_by(FetchLog.id)).all()
    assert [(log.http_status, log.error is None) for log in logs] == [(200, True), (404, False)]
    assert logs[0].sha256 and logs[0].bytes == len(GOOD_PDF)


def test_fetcher_waits_between_requests(clean_db, server):
    import time

    f = PoliteFetcher(clean_db, min_delay_s=0.4)
    t0 = time.monotonic()
    f.get(f"{server}/good.pdf")
    f.get(f"{server}/good.pdf")
    assert time.monotonic() - t0 >= 0.4


def test_pipeline_stores_pages_and_exact_chunks_and_reports_failures(clean_db, server, tmp_path):
    rows = [
        listed("RERA-GRG-1-2024", f"{server}/good.pdf"),
        listed("RERA-GRG-2-2024", f"{server}/notpdf.pdf"),
        listed("RERA-GRG-3-2024", f"{server}/missing.pdf"),
        listed("RERA-GRG-4-2024", None),
    ]
    reg = register_listing(clean_db, "hrera_gurugram", rows)
    assert (reg.new, reg.without_pdf, reg.already_known) == (3, 1, 0)

    ids = pending_orders(clean_db, "hrera_gurugram", limit=10)
    report = ingest_pending(
        clean_db, ids, PoliteFetcher(clean_db, min_delay_s=0), None, tmp_path, progress=lambda _: None
    )

    assert report.attempted == 3 and report.stored == 1
    failed = dict(report.failures)
    assert any("not a PDF" in e for e in failed.values())
    assert any("HTTP 404" in e for e in failed.values())

    with Session(clean_db) as s:
        order = s.scalar(select(Order).where(Order.complaint_no == "RERA-GRG-1-2024"))
        assert order.page_count == 2 and order.text_source == "text_layer" and order.fetched_at is not None
        assert (tmp_path / f"{order.pdf_sha256}.pdf").exists()
        assert (
            s.scalar(select(func.count()).select_from(OrderPage).where(OrderPage.order_id == order.id)) == 2
        )
        # Every chunk is an exact slice of its stored page.
        mismatches = s.execute(
            text("""
            SELECT count(*) FROM order_chunks c JOIN order_pages p USING (order_id, page_no)
            WHERE substr(p.text, c.char_start + 1, c.char_end - c.char_start) <> c.text
        """)
        ).scalar()
        assert mismatches == 0
        assert s.scalar(select(func.count()).select_from(OrderChunk)) == report.chunks > 2
        # The failed orders stay pending so a later run can retry them.
        assert s.scalar(select(func.count()).select_from(Order).where(Order.fetched_at.is_(None))) == 2
        # Three PDF requests, all logged.
        assert s.scalar(select(func.count()).select_from(FetchLog)) == 3


def test_rerun_is_idempotent(clean_db, server, tmp_path):
    rows = [listed("RERA-GRG-1-2024", f"{server}/good.pdf")]
    register_listing(clean_db, "hrera_gurugram", rows)
    fetcher = PoliteFetcher(clean_db, min_delay_s=0)
    ingest_pending(
        clean_db, pending_orders(clean_db, "hrera_gurugram", 10), fetcher, None, tmp_path, lambda _: None
    )

    again = register_listing(clean_db, "hrera_gurugram", rows)
    assert (again.new, again.already_known) == (0, 1)
    assert pending_orders(clean_db, "hrera_gurugram", 10) == []
    with Session(clean_db) as s:
        assert s.scalar(select(func.count()).select_from(OrderPage)) == 2
