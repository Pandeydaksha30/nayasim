"""Index a buyer's uploaded document for search: split each page into chunks and embed them.

Everything happens on this server: the chunker is the one used for public orders
(app/ingestion/chunker.py) and the embedding model runs locally, so indexing sends nothing out.
Chunks keep the document, page and character offsets, so an answer can point at its source.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import CaseDocument, CaseDocumentChunk, CaseDocumentPage
from app.ingestion.chunker import chunk_page
from app.retrieval.embedder import Embedder

log = logging.getLogger("nyayasim.rag")


def index_document(s: Session, document_id: uuid.UUID, embedder: Embedder | None) -> int:
    """(Re)build the chunks of one document. Returns the number of chunks stored.

    If the embedding model fails, chunks are still stored without vectors: keyword search keeps
    working and the failure is logged, rather than the upload being lost.
    """
    doc = s.get(CaseDocument, document_id)
    if doc is None:
        return 0
    s.execute(delete(CaseDocumentChunk).where(CaseDocumentChunk.document_id == document_id))
    rows: list[CaseDocumentChunk] = []
    pages = s.scalars(
        select(CaseDocumentPage)
        .where(CaseDocumentPage.document_id == document_id)
        .order_by(CaseDocumentPage.page_no)
    )
    for page in pages:
        for c in chunk_page(page.text or ""):
            rows.append(
                CaseDocumentChunk(
                    case_id=doc.case_id,
                    document_id=document_id,
                    page_no=page.page_no,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    text=c.text,
                )
            )
    if rows and embedder is not None:
        try:
            vectors = embedder.embed_documents([r.text for r in rows])
            for r, v in zip(rows, vectors, strict=True):
                r.embedding = v
                r.embedding_model = embedder.name
        except Exception:  # noqa: BLE001 - keyword search still works; logged with traceback
            log.exception("Embedding failed for document %s; stored without vectors", document_id)
    s.add_all(rows)
    s.flush()
    return len(rows)


def ensure_indexed(s: Session, document_id: uuid.UUID, embedder: Embedder | None) -> int:
    """Index the document if it has no chunks yet (documents uploaded before this feature)."""
    n = s.scalar(
        select(func.count())
        .select_from(CaseDocumentChunk)
        .where(CaseDocumentChunk.document_id == document_id)
    )
    return n or index_document(s, document_id, embedder)
