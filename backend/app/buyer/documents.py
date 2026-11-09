"""Store a buyer's uploaded document and the text of each page.

Files are private: they are kept under data/uploads/<case id>/ (git-ignored) and their text
is read locally (PDF text layer, or Tesseract OCR). Nothing here sends anything to a model.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Case, CaseDocument, CaseDocumentPage
from app.ingestion.pdf_text import OcrConfig, extract_image, extract_pages, pdf_page_count

UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "data" / "uploads"
MAX_BYTES = 25 * 1024 * 1024
# A buyer's papers are rarely over 60 pages (agreements run 30-80). The cap stops one upload from
# keeping OCR busy for hours: a 25 MB file could otherwise hold thousands of scanned pages.
MAX_PAGES = 100
KINDS = ("agreement", "allotment_letter", "receipt", "builder_letter", "hearing_order", "other")
_TYPES = {b"%PDF": ".pdf", b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg"}


class UploadRejected(ValueError):
    """The upload cannot be accepted; the message is safe to show to the user."""


@dataclass(frozen=True)
class StoredDocument:
    id: uuid.UUID
    filename: str
    kind: str
    page_count: int
    ocr_pages: int
    duplicate: bool


def _detect_type(data: bytes) -> str:
    for magic, ext in _TYPES.items():
        if data.startswith(magic):
            return ext
    raise UploadRejected("Only PDF, PNG and JPG files can be read.")


def store_document(
    session: Session,
    case_id: uuid.UUID,
    filename: str,
    kind: str,
    data: bytes,
    ocr: OcrConfig | None,
    upload_root: Path | None = None,
) -> StoredDocument:
    if kind not in KINDS:
        raise UploadRejected(f"Unknown document type {kind!r}.")
    if not data:
        raise UploadRejected("The file is empty.")
    if len(data) > MAX_BYTES:
        raise UploadRejected("Files must be 25 MB or smaller.")
    if session.get(Case, case_id) is None:
        raise UploadRejected("Case not found.")
    ext = _detect_type(data)  # by content, not by the file name
    digest = hashlib.sha256(data).hexdigest()

    existing = session.scalar(
        select(CaseDocument).where(CaseDocument.case_id == case_id, CaseDocument.sha256 == digest)
    )
    if existing is not None:
        ocr_pages = sum(1 for p in existing.pages if p.text_source == "ocr")
        return StoredDocument(
            existing.id, existing.filename, existing.kind, existing.page_count, ocr_pages, True
        )

    if ext == ".pdf":
        try:
            n = pdf_page_count(data)
        except Exception as e:  # damaged PDF: shown to the user
            raise UploadRejected(f"Could not read the file: {type(e).__name__}: {e}") from e
        if n > MAX_PAGES:
            raise UploadRejected(
                f"This PDF has {n} pages; the limit is {MAX_PAGES}. Split it into smaller files "
                "(for example, the agreement and the receipts separately) and upload each one."
            )

    session.commit()  # no transaction stays open during OCR, which can take minutes for scans

    # Read the text first: an unreadable file is rejected before anything is saved.
    try:
        pages = extract_pages(data, ocr) if ext == ".pdf" else extract_image(data, ocr)
    except Exception as e:  # damaged PDF, unreadable image, OCR missing: shown to the user
        raise UploadRejected(f"Could not read the file: {type(e).__name__}: {e}") from e
    if not pages:
        raise UploadRejected("The file has no pages.")

    upload_root = upload_root or UPLOAD_ROOT  # read at call time so tests can redirect it
    folder = upload_root / str(case_id)
    folder.mkdir(parents=True, exist_ok=True)
    storage_key = f"{case_id}/{digest}{ext}"
    (upload_root / storage_key).write_bytes(data)

    doc = CaseDocument(
        case_id=case_id,
        filename=Path(filename).name[:200] or "upload",
        kind=kind,
        sha256=digest,
        page_count=len(pages),
        storage_key=storage_key,
    )
    for p in pages:
        doc.pages.append(
            CaseDocumentPage(
                page_no=p.page_no,
                text=p.text,
                text_source=p.source,
                ocr_engine=p.ocr_engine,
                ocr_confidence=p.ocr_confidence,
            )
        )
    session.add(doc)
    session.flush()
    return StoredDocument(
        doc.id, doc.filename, kind, len(pages), sum(p.source == "ocr" for p in pages), False
    )
