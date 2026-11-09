"""Cases API: create a case, upload documents, extract verified facts, answer questions."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.deps import CurrentUser, case_for
from app.buyer import documents as documents_mod
from app.buyer.documents import KINDS, UploadRejected, store_document
from app.buyer.facts import FactExtractor, PrivateDataBlocked, extract_case_facts
from app.buyer.questions import questions_for, validate_answer
from app.config import settings
from app.db.models import Case, CaseAnswer, CaseDocument, CaseDocumentPage, Fact
from app.db.session import get_session
from app.ingestion.pdf_text import OcrConfig, find_ocr

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
SessionDep = Annotated[Session, Depends(get_session)]


# At most this many documents are read (OCR) at the same time; each already uses several OCR
# threads. More arrivals get a clear "busy" answer instead of slowing everyone down.
MAX_PARALLEL_UPLOADS = 2
_upload_slots = threading.BoundedSemaphore(MAX_PARALLEL_UPLOADS)


def get_ocr() -> OcrConfig | None:
    return find_ocr()


def get_fact_extractor() -> FactExtractor:
    if settings.gemini_api_key is None:
        raise HTTPException(503, "No model is configured for fact extraction (GEMINI_API_KEY is not set).")
    from app.extraction.gemini import GeminiExtractor

    return GeminiExtractor(
        settings.gemini_api_key.get_secret_value(), settings.gemini_model, min_interval_s=0
    )


class CaseIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    claim_type: Literal["delayed_possession", "refund", "other"] = "delayed_possession"
    is_demo: bool = False


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    kind: str
    page_count: int
    ocr_pages: int
    duplicate: bool = False


class FactOut(BaseModel):
    id: int
    document_id: uuid.UUID
    key: str
    label: str
    value: str
    page_no: int
    char_start: int
    char_end: int
    quote: str
    confidence: str
    confirmed: bool


class QuestionOut(BaseModel):
    id: str
    question: str
    why: str
    options: list[str]
    answer: str | None


class CaseOut(BaseModel):
    id: uuid.UUID
    title: str
    claim_type: str
    status: str
    is_demo: bool
    shared: bool  # read-only demo case that belongs to no account
    created_at: datetime
    documents: list[DocumentOut]
    facts: list[FactOut]
    questions: list[QuestionOut]
    payments_total: str


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=200)


def _case_out(s: Session, case: Case) -> CaseOut:
    facts = s.scalars(
        select(Fact).where(Fact.case_id == case.id).order_by(Fact.document_id, Fact.page_no, Fact.char_start)
    ).all()
    by_key: dict[str, list[str]] = {}
    for f in facts:
        by_key.setdefault(f.key, []).append(f.value)
    answers = {
        a.question_id: a.answer for a in s.scalars(select(CaseAnswer).where(CaseAnswer.case_id == case.id))
    }
    payments_total = sum((Decimal(v.split(";")[1]) for v in by_key.get("payment", [])), Decimal(0))
    docs = s.scalars(
        select(CaseDocument).where(CaseDocument.case_id == case.id).order_by(CaseDocument.uploaded_at)
    ).all()
    return CaseOut(
        id=case.id,
        title=case.title,
        claim_type=case.claim_type,
        status=case.status,
        is_demo=case.is_demo,
        shared=case.user_id is None,
        created_at=case.created_at,
        documents=[
            DocumentOut(
                id=d.id,
                filename=d.filename,
                kind=d.kind,
                page_count=d.page_count,
                ocr_pages=sum(p.text_source == "ocr" for p in d.pages),
            )
            for d in docs
        ],
        facts=[FactOut.model_validate(f, from_attributes=True) for f in facts],
        questions=[
            QuestionOut(
                id=q.id, question=q.question, why=q.why, options=list(q.options), answer=answers.get(q.id)
            )
            for q in questions_for(by_key)
        ],
        payments_total=str(payments_total.quantize(Decimal("0.01"))),
    )


class CaseSummary(BaseModel):
    id: uuid.UUID
    title: str
    claim_type: str
    status: str
    is_demo: bool
    shared: bool  # a read-only demo case that belongs to no account
    created_at: datetime
    documents: int
    facts: int


@router.get("", response_model=list[CaseSummary])
def list_cases(s: SessionDep, user: CurrentUser) -> list[CaseSummary]:
    doc_counts = dict(
        s.execute(select(CaseDocument.case_id, func.count()).group_by(CaseDocument.case_id)).all()
    )
    fact_counts = dict(s.execute(select(Fact.case_id, func.count()).group_by(Fact.case_id)).all())
    return [
        CaseSummary(
            id=c.id,
            title=c.title,
            claim_type=c.claim_type,
            status=c.status,
            is_demo=c.is_demo,
            shared=c.user_id is None,
            created_at=c.created_at,
            documents=doc_counts.get(c.id, 0),
            facts=fact_counts.get(c.id, 0),
        )
        for c in s.scalars(
            select(Case)
            .where((Case.user_id == user.id) | (Case.user_id.is_(None) & Case.is_demo))
            .order_by(Case.created_at.desc())
        )
    ]


@router.post("", status_code=201, response_model=CaseOut)
def create_case(body: CaseIn, s: SessionDep, user: CurrentUser) -> CaseOut:
    if body.is_demo and not settings.allow_demo_cases:
        # Privacy: "demo" lets documents go to a model that may keep them. Users cannot choose it,
        # or real papers could be sent there just by ticking a box.
        raise HTTPException(403, "Demo cases cannot be created on this server. Create a normal case instead.")
    case = Case(title=body.title, claim_type=body.claim_type, is_demo=body.is_demo, user_id=user.id)
    s.add(case)
    s.flush()
    s.refresh(case)
    return _case_out(s, case)


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: uuid.UUID, s: SessionDep, user: CurrentUser) -> CaseOut:
    return _case_out(s, case_for(s, case_id, user))


@router.post("/{case_id}/documents", status_code=201, response_model=DocumentOut)
async def upload_document(
    case_id: uuid.UUID,
    s: SessionDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    ocr: Annotated[OcrConfig | None, Depends(get_ocr)],
) -> DocumentOut:
    case_for(s, case_id, user, write=True)
    if kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    # Read at most one byte past the limit: an oversized upload is rejected without being
    # held in memory in full.
    data = await file.read(documents_mod.MAX_BYTES + 1)
    if len(data) > documents_mod.MAX_BYTES:
        raise HTTPException(413, "Files must be 25 MB or smaller.")
    if not _upload_slots.acquire(blocking=False):
        raise HTTPException(
            503, "NyayaSim is reading other documents right now. Please try again in a minute."
        )
    try:
        # OCR is slow, blocking work: run it on a worker thread so the server keeps answering
        # everyone else meanwhile (this route is async, so calling it inline would stall the API).
        stored = await run_in_threadpool(
            store_document, s, case_id, file.filename or "upload", kind, data, ocr
        )
    except UploadRejected as e:
        raise HTTPException(422, str(e)) from e
    finally:
        _upload_slots.release()
    return DocumentOut(**stored.__dict__)


@router.get("/{case_id}/documents/{document_id}/pages/{page_no}")
def get_page(
    case_id: uuid.UUID, document_id: uuid.UUID, page_no: int, s: SessionDep, user: CurrentUser
) -> dict:
    case_for(s, case_id, user)
    doc = s.get(CaseDocument, document_id)
    if doc is None or doc.case_id != case_id:
        raise HTTPException(404, "Document not found.")
    page = s.get(CaseDocumentPage, (document_id, page_no))
    if page is None:
        raise HTTPException(404, "Page not found.")
    return {
        "page_no": page.page_no,
        "page_count": doc.page_count,
        "text": page.text,
        "text_source": page.text_source,
        "ocr_confidence": page.ocr_confidence,
    }


@router.post("/{case_id}/facts/extract")
def extract_facts(
    case_id: uuid.UUID,
    s: SessionDep,
    user: CurrentUser,
    extractor: Annotated[FactExtractor, Depends(get_fact_extractor)],
) -> dict:
    case_for(s, case_id, user, write=True)
    try:
        summary = extract_case_facts(s, case_id, extractor)
    except PrivateDataBlocked as e:
        raise HTTPException(403, str(e)) from e
    return summary


@router.post("/{case_id}/facts/{fact_id}/confirm", response_model=FactOut)
def confirm_fact(case_id: uuid.UUID, fact_id: int, s: SessionDep, user: CurrentUser) -> FactOut:
    case_for(s, case_id, user, write=True)
    fact = s.get(Fact, fact_id)
    if fact is None or fact.case_id != case_id:
        raise HTTPException(404, "Fact not found.")
    fact.confirmed = True
    s.flush()
    return FactOut.model_validate(fact, from_attributes=True)


@router.put("/{case_id}/answers/{question_id}", response_model=CaseOut)
def answer_question(
    case_id: uuid.UUID, question_id: str, body: AnswerIn, s: SessionDep, user: CurrentUser
) -> CaseOut:
    case = case_for(s, case_id, user, write=True)
    try:
        validate_answer(question_id, body.answer)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    existing = s.get(CaseAnswer, (case_id, question_id))
    if existing:
        existing.answer = body.answer
        existing.answered_at = datetime.now(existing.answered_at.tzinfo)
    else:
        s.add(CaseAnswer(case_id=case_id, question_id=question_id, answer=body.answer))
    s.flush()
    return _case_out(s, case)
