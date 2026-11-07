"""ORM mappings for the tables created in migrations/versions/0001_order_store.py.

The migration is the source of truth for constraints; these classes map the same columns
for application code. tests/test_schema.py writes through these models, so a mismatch
between the two fails the tests.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, BigInteger, Computed, ForeignKey, ForeignKeyConstraint, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 1024


class Base(DeclarativeBase):
    pass


class FetchLog(Base):
    __tablename__ = "fetch_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(server_default="now()")
    http_status: Mapped[int | None]
    bytes: Mapped[int | None]
    sha256: Mapped[str | None]
    error: Mapped[str | None] = mapped_column(Text)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    complaint_no: Mapped[str] = mapped_column(Text)
    complainant: Mapped[str | None] = mapped_column(Text)
    respondent: Mapped[str | None] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(Text)
    decided_on: Mapped[date]
    pdf_url: Mapped[str] = mapped_column(Text)
    pdf_sha256: Mapped[str | None]
    page_count: Mapped[int | None]
    text_source: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    pages: Mapped[list[OrderPage]] = relationship(back_populates="order", cascade="all, delete-orphan")
    record: Mapped[CaseRecord | None] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderPage(Base):
    __tablename__ = "order_pages"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    page_no: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    text_source: Mapped[str] = mapped_column(Text)
    ocr_engine: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    order: Mapped[Order] = relationship(back_populates="pages")


class OrderChunk(Base):
    __tablename__ = "order_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "page_no"], ["order_pages.order_id", "order_pages.page_no"], ondelete="CASCADE"
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int]
    page_no: Mapped[int]
    char_start: Mapped[int]
    char_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True))


class CaseRecord(Base):
    __tablename__ = "case_records"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)
    claim_type: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    possession_due: Mapped[date | None]
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    award_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    interest_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    defences: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    field_sources: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    extracted_by: Mapped[str] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(server_default="now()")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None]

    order: Mapped[Order] = relationship(back_populates="record")


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    title: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    # Fictional demo case: the only kind that may go to a model that can retain data.
    is_demo: Mapped[bool] = mapped_column(server_default="false")
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(server_default="now()")

    documents: Mapped[list[CaseDocument]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CaseDocument(Base):
    __tablename__ = "case_documents"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str]
    page_count: Mapped[int]
    storage_key: Mapped[str] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(server_default="now()")

    case: Mapped[Case] = relationship(back_populates="documents")
    pages: Mapped[list[CaseDocumentPage]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="CaseDocumentPage.page_no"
    )


class CaseDocumentPage(Base):
    __tablename__ = "case_document_pages"
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_documents.id", ondelete="CASCADE"), primary_key=True
    )
    page_no: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    text_source: Mapped[str] = mapped_column(Text)
    ocr_engine: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    document: Mapped[CaseDocument] = relationship(back_populates="pages")


class CaseAnswer(Base):
    __tablename__ = "case_answers"
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[str] = mapped_column(Text, primary_key=True)
    answer: Mapped[str] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(server_default="now()")


class Fact(Base):
    __tablename__ = "facts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_documents.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    page_no: Mapped[int]
    char_start: Mapped[int]
    char_end: Mapped[int]
    quote: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(Text)
    confirmed: Mapped[bool] = mapped_column(server_default="false")
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
