"""Schema tests: the database itself must refuse data that would break the ground rules."""

from __future__ import annotations

import hashlib
from datetime import UTC, date

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DataError, IntegrityError, InternalError, StatementError
from sqlalchemy.orm import Session

from app.db.models import (
    EMBEDDING_DIM,
    Case,
    CaseDocument,
    CaseRecord,
    Fact,
    FetchLog,
    Order,
    OrderChunk,
    OrderPage,
)

PAGE_TEXT = "The promoter shall pay interest at the prescribed rate for every month of delay."


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def make_order(db: Session, complaint_no: str = "RERA-GRG-1-2024") -> Order:
    order = Order(
        source="hrera_gurugram",
        complaint_no=complaint_no,
        case_type="HRERA Complaints",
        decided_on=date(2024, 5, 1),
        pdf_url="https://example.invalid/order.pdf",
        pdf_sha256=sha(complaint_no),
        page_count=2,
        text_source="text_layer",
        fetched_at=None,
    )
    order.pages.append(OrderPage(page_no=1, text=PAGE_TEXT, text_source="text_layer"))
    db.add(order)
    db.flush()
    return order


def make_case_with_doc(db: Session, pages: int = 38) -> tuple[Case, CaseDocument]:
    case = Case(title="Test v. Builder", claim_type="delayed_possession")
    doc = CaseDocument(
        filename="bba.pdf", kind="agreement", sha256=sha("bba"), page_count=pages, storage_key="k/bba.pdf"
    )
    case.documents.append(doc)
    db.add(case)
    db.flush()
    return case, doc


def fact(case: Case, doc: CaseDocument, **kw) -> Fact:
    base = dict(
        case_id=case.id,
        document_id=doc.id,
        key="possession_promised",
        label="Promised possession",
        value="30 Jun 2021",
        page_no=17,
        char_start=10,
        char_end=24,
        quote="30th June 2021",
        confidence="high",
    )
    base.update(kw)
    return Fact(**base)


def expect_rejected(
    db: Session, obj, errors=(IntegrityError, InternalError, DataError, StatementError)
) -> None:
    db.add(obj)
    with pytest.raises(errors):
        db.flush()
    db.rollback()


# ── Extensions and happy path ──


def test_extensions_installed(db: Session):
    names = set(db.scalars(text("SELECT extname FROM pg_extension")))
    assert {"vector", "pgcrypto"} <= names


def test_order_page_chunk_round_trip_with_full_text_search(db: Session):
    order = make_order(db)
    start = PAGE_TEXT.index("prescribed rate")
    chunk_text = PAGE_TEXT[start : start + len("prescribed rate")]
    db.add(
        OrderChunk(
            order_id=order.id,
            page_no=1,
            char_start=start,
            char_end=start + len(chunk_text),
            text=chunk_text,
            embedding=[0.0] * EMBEDDING_DIM,
        )
    )
    db.flush()
    hit = db.scalar(
        select(OrderChunk).where(
            OrderChunk.order_id == order.id,
            OrderChunk.tsv.op("@@")(text("plainto_tsquery('simple', 'prescribed rate')")),
        )
    )
    assert hit is not None and hit.text == "prescribed rate"


def test_fact_with_valid_source_is_stored(db: Session):
    case, doc = make_case_with_doc(db)
    db.add(fact(case, doc))
    db.flush()
    assert db.scalar(select(Fact.page_no)) == 17


# ── Order store rules ──


def test_duplicate_decision_rejected(db: Session):
    make_order(db, "RERA-GRG-9-2024")
    dup = Order(
        source="hrera_gurugram",
        complaint_no="RERA-GRG-9-2024",
        case_type="x",
        decided_on=date(2024, 5, 1),
        pdf_url="u",
    )
    expect_rejected(db, dup)


def test_unknown_source_rejected(db: Session):
    expect_rejected(
        db,
        Order(source="somewhere", complaint_no="1", case_type="x", decided_on=date(2024, 1, 1), pdf_url="u"),
    )


def test_fetched_order_must_have_hash(db: Session):
    from datetime import datetime

    expect_rejected(
        db,
        Order(
            source="hrera_gurugram",
            complaint_no="2",
            case_type="x",
            decided_on=date(2024, 1, 1),
            pdf_url="u",
            fetched_at=datetime.now(UTC),
        ),
    )


def test_chunk_offsets_must_match_text_length(db: Session):
    order = make_order(db)
    expect_rejected(
        db, OrderChunk(order_id=order.id, page_no=1, char_start=0, char_end=5, text="longer than five")
    )


def test_chunk_on_missing_page_rejected(db: Session):
    order = make_order(db)
    expect_rejected(db, OrderChunk(order_id=order.id, page_no=2, char_start=0, char_end=3, text="abc"))


def test_embedding_with_wrong_dimension_rejected(db: Session):
    order = make_order(db)
    expect_rejected(
        db,
        OrderChunk(order_id=order.id, page_no=1, char_start=0, char_end=3, text="The", embedding=[0.0] * 3),
    )


def test_ocr_page_must_name_engine(db: Session):
    order = make_order(db)
    expect_rejected(db, OrderPage(order_id=order.id, page_no=2, text="x", text_source="ocr"))


def test_case_record_rejects_unknown_outcome(db: Session):
    order = make_order(db)
    expect_rejected(
        db, CaseRecord(order_id=order.id, claim_type="refund", outcome="won", extracted_by="test")
    )


def test_fetch_log_requires_status_or_error(db: Session):
    expect_rejected(db, FetchLog(url="https://example.invalid"))


# ── Buyer fact sourcing (rule 4) ──


def test_fact_page_beyond_document_rejected(db: Session):
    case, doc = make_case_with_doc(db, pages=5)
    expect_rejected(db, fact(case, doc, page_no=6))


def test_fact_without_page_rejected(db: Session):
    case, doc = make_case_with_doc(db)
    expect_rejected(db, fact(case, doc, page_no=None))


def test_fact_with_empty_span_rejected(db: Session):
    case, doc = make_case_with_doc(db)
    expect_rejected(db, fact(case, doc, char_start=20, char_end=20))


def test_fact_from_another_cases_document_rejected(db: Session):
    case_a, _ = make_case_with_doc(db)
    case_b = Case(title="Other", claim_type="refund")
    doc_b = CaseDocument(
        filename="o.pdf", kind="receipt", sha256=sha("o"), page_count=3, storage_key="k/o.pdf"
    )
    case_b.documents.append(doc_b)
    db.add(case_b)
    db.flush()
    expect_rejected(db, fact(case_a, doc_b, page_no=1))


# ── Migration is reversible ──


def test_downgrade_and_upgrade_again(db_engine):
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = db_engine.url.render_as_string(hide_password=False)
    command.downgrade(cfg, "base")
    with db_engine.connect() as conn:
        assert conn.scalar(text("SELECT to_regclass('public.orders')")) is None
    command.upgrade(cfg, "head")
    with db_engine.connect() as conn:
        assert conn.scalar(text("SELECT to_regclass('public.orders')")) is not None
