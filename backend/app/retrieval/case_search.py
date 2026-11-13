"""Hybrid search over ONE case's uploaded documents (table case_document_chunks).

Same method as the public-order search (app/retrieval/search.py): Postgres full text + vector
similarity, fused by reciprocal rank. The case id is a required argument and is part of every
SQL statement, and each returned row is checked against it again: a passage from another case
must never be returned. Callers must have checked that the user may read the case.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.embedder import Embedder
from app.retrieval.search import RRF_K, keyword_query

POOL = 40


class CaseLeak(AssertionError):
    """A chunk of another case reached the result list. Must never happen."""


@dataclass(frozen=True)
class Passage:
    chunk_id: int
    document_id: uuid.UUID
    filename: str
    kind: str
    page_no: int
    char_start: int
    char_end: int
    text: str
    score: float


def search_case(
    s: Session, case_id: uuid.UUID, query: str, embedder: Embedder | None = None, k: int = 6
) -> tuple[list[Passage], str]:
    if not isinstance(case_id, uuid.UUID):
        raise TypeError("search_case() needs the case id: only that case's documents are searched")
    kw: list[int] = []
    tsq = keyword_query(query)
    if tsq:
        kw = [
            r[0]
            for r in s.execute(
                text("""
                    SELECT id FROM case_document_chunks
                    WHERE case_id = :case AND tsv @@ websearch_to_tsquery('english', :q)
                    ORDER BY ts_rank_cd(tsv, websearch_to_tsquery('english', :q)) DESC, id
                    LIMIT :limit
                """),
                {"case": case_id, "q": tsq, "limit": POOL},
            )
        ]
    vec: list[int] = []
    mode = "keyword"
    if embedder is not None:
        has = s.scalar(
            text("""SELECT EXISTS (SELECT 1 FROM case_document_chunks
                    WHERE case_id = :case AND embedding_model = :m)"""),
            {"case": case_id, "m": embedder.name},
        )
        if has:
            # No HNSW shortcut: a case has few chunks, and an exact scan can never miss one
            # because of the index's candidate limit.
            vec = [
                r[0]
                for r in s.execute(
                    text("""
                        SELECT id FROM case_document_chunks
                        WHERE case_id = :case AND embedding IS NOT NULL AND embedding_model = :m
                        ORDER BY embedding <=> CAST(:vec AS vector), id
                        LIMIT :limit
                    """),
                    {
                        "case": case_id,
                        "m": embedder.name,
                        "vec": str(embedder.embed_query(query)),
                        "limit": POOL,
                    },
                )
            ]
            mode = "hybrid"

    scores: dict[int, float] = {}
    for ranks in (kw, vec):
        for i, cid in enumerate(ranks):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + i + 1)
    if not scores:
        return [], mode
    rows = s.execute(
        text("""
            SELECT c.id, c.case_id, c.document_id, d.filename, d.kind, c.page_no,
                   c.char_start, c.char_end, c.text
            FROM case_document_chunks c JOIN case_documents d ON d.id = c.document_id
            WHERE c.id = ANY(:ids) AND c.case_id = :case
        """),
        {"ids": list(scores), "case": case_id},
    ).all()
    by_id = {r[0]: r for r in rows}
    out: list[Passage] = []
    for cid in sorted(scores, key=lambda c: (-scores[c], c)):
        r = by_id.get(cid)
        if r is None:
            continue
        if r[1] != case_id:  # defence in depth: the SQL already filtered
            raise CaseLeak(f"chunk {cid} belongs to case {r[1]}, not {case_id}")
        out.append(Passage(r[0], r[2], r[3], r[4], r[5], r[6], r[7], r[8], round(scores[cid], 5)))
        if len(out) >= k:
            break
    return out, mode
