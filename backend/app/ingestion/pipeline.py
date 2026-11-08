"""Ingestion pipeline: listing -> orders table -> PDF -> pages -> chunks.

Idempotent: re-running skips orders already fetched, and listing rows already known.
Each order is stored in its own transaction; a failure is recorded in the report (and the
fetch itself in fetch_log) and the run moves on to the next order.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.models import Order, OrderChunk, OrderPage
from app.ingestion.chunker import chunk_page
from app.ingestion.fetcher import FetchError, PoliteFetcher
from app.ingestion.hrera_listing import ListedOrder
from app.ingestion.pdf_text import OcrConfig, OcrUnavailable, extract_pages, overall_source

LOW_OCR_CONFIDENCE = 60.0


@dataclass
class RegisterReport:
    listed: int = 0
    new: int = 0
    already_known: int = 0
    without_pdf: int = 0


@dataclass
class IngestReport:
    attempted: int = 0
    stored: int = 0
    pages: int = 0
    ocr_pages: int = 0
    chunks: int = 0
    low_confidence_pages: list[tuple[str, int, float]] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)


def register_listing(engine: Engine, source: str, rows: list[ListedOrder]) -> RegisterReport:
    report = RegisterReport(listed=len(rows))
    with Session(engine) as s:
        for r in rows:
            if not r.pdf_url:
                report.without_pdf += 1
                continue
            stmt = (
                insert(Order)
                .values(
                    source=source,
                    complaint_no=r.complaint_no,
                    complainant=r.complainant,
                    respondent=r.respondent,
                    case_type=r.case_type,
                    decided_on=r.decided_on,
                    pdf_url=r.pdf_url,
                )
                .on_conflict_do_nothing(constraint="orders_unique_decision")
                .returning(Order.id)
            )
            if s.execute(stmt).first() is None:
                report.already_known += 1
            else:
                report.new += 1
        s.commit()
    return report


def pending_orders(
    engine: Engine, source: str, limit: int, case_type: str | None = None, years: list[int] | None = None
) -> list[int]:
    """Unfetched order ids, spread across the table deterministically (md5 order)."""
    q = select(Order.id).where(Order.source == source, Order.fetched_at.is_(None))
    if case_type:
        q = q.where(Order.case_type == case_type)
    if years:
        q = q.where(func.extract("year", Order.decided_on).in_(years))
    q = q.order_by(func.md5(Order.complaint_no)).limit(limit)
    with Session(engine) as s:
        return list(s.scalars(q))


def ingest_order(
    engine: Engine,
    order_id: int,
    fetcher: PoliteFetcher,
    ocr: OcrConfig | None,
    store_dir: Path,
    report: IngestReport,
) -> None:
    with Session(engine) as s:
        order = s.get(Order, order_id)
        if order is None or order.fetched_at is not None:
            return
        report.attempted += 1
        label = f"{order.complaint_no} ({order.decided_on})"
        pdf_url = order.pdf_url
        s.commit()  # no transaction stays open during the download and OCR (minutes per order)
        try:
            got = fetcher.get(pdf_url)
            if not got.body.startswith(b"%PDF"):
                raise ValueError(f"not a PDF (starts with {got.body[:16]!r})")
            pages = extract_pages(got.body, ocr)
        except (FetchError, OcrUnavailable, ValueError) as e:
            report.failures.append((label, str(e)))
            return
        except Exception as e:  # unexpected parser errors: recorded, never swallowed
            report.failures.append((label, f"{type(e).__name__}: {e}"))
            return

        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / f"{got.sha256}.pdf").write_bytes(got.body)

        order = s.get(Order, order_id)  # reloaded in a fresh transaction
        if order.fetched_at is not None:  # another run stored it meanwhile
            return
        n_chunks = 0
        for p in pages:
            s.add(
                OrderPage(
                    order_id=order.id,
                    page_no=p.page_no,
                    text=p.text,
                    text_source=p.source,
                    ocr_engine=p.ocr_engine,
                    ocr_confidence=p.ocr_confidence,
                )
            )
        s.flush()
        for p in pages:
            for c in chunk_page(p.text):
                s.add(
                    OrderChunk(
                        order_id=order.id,
                        page_no=p.page_no,
                        char_start=c.char_start,
                        char_end=c.char_end,
                        text=c.text,
                    )
                )
                n_chunks += 1
        order.pdf_sha256 = got.sha256
        order.page_count = len(pages)
        order.text_source = overall_source(pages)
        order.fetched_at = datetime.now(UTC)
        s.commit()

        report.stored += 1
        report.pages += len(pages)
        report.chunks += n_chunks
        for p in pages:
            if p.source == "ocr":
                report.ocr_pages += 1
                if (p.ocr_confidence or 0) < LOW_OCR_CONFIDENCE:
                    report.low_confidence_pages.append((label, p.page_no, p.ocr_confidence or 0.0))


class DatabaseUnavailable(RuntimeError):
    """The database stayed unreachable for the whole retry window; the run stops."""


def ingest_pending(
    engine: Engine,
    order_ids: list[int],
    fetcher: PoliteFetcher,
    ocr: OcrConfig | None,
    store_dir: Path,
    progress=print,
    db_retry_s: float = 60.0,
    db_retry_limit: int = 30,
) -> IngestReport:
    """Ingest each order. If the database drops (e.g. Docker restarts), wait and retry the
    same order rather than crashing; an interrupted order's transaction was rolled back, so
    nothing half-written remains. Gives up with DatabaseUnavailable after the retry window."""
    report = IngestReport()
    for i, oid in enumerate(order_ids, 1):
        for attempt in range(db_retry_limit + 1):
            before_failures, before_attempted = len(report.failures), report.attempted
            try:
                ingest_order(engine, oid, fetcher, ocr, store_dir, report)
                break
            except OperationalError as e:
                report.attempted = before_attempted
                del report.failures[before_failures:]
                if attempt == db_retry_limit:
                    raise DatabaseUnavailable(
                        f"database unreachable for {db_retry_limit * db_retry_s / 60:.0f} min "
                        f"at order {oid}: {str(e).splitlines()[0]}"
                    ) from e
                progress(
                    f"[{i}/{len(order_ids)}] order {oid}: database unavailable, retrying in "
                    f"{db_retry_s:.0f} s ({attempt + 1}/{db_retry_limit})"
                )
                time.sleep(db_retry_s)
        status = "FAILED: " + report.failures[-1][1] if len(report.failures) > before_failures else "ok"
        progress(f"[{i}/{len(order_ids)}] order {oid}: {status}")
    return report
