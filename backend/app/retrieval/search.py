"""Hybrid search over order chunks, restricted to orders decided before a cutoff.

* Keyword: Postgres full text (english stemming), words of the query OR-ed, ranked by
  ts_rank_cd. Exact legal terms ("Section 18", "force majeure") matter in this domain.
* Vector: cosine distance on embeddings from the *configured* model only.
* Fusion: Reciprocal Rank Fusion, score = sum over lists of 1 / (RRF_K + rank). It needs no
  score calibration between the two lists and is easy to explain.

The cutoff is a required argument and every returned hit is checked against it again: a
time-split backtest is only honest if no later order can ever be retrieved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.embedder import Embedder

RRF_K = 60
POOL = 60  # candidates taken from each list before fusion
MAX_PER_ORDER = 2

_STOP = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "and",
    "or",
    "in",
    "on",
    "for",
    "by",
    "with",
    "is",
    "was",
    "be",
    "as",
    "at",
    "that",
    "this",
    "it",
    "from",
    "are",
    "has",
    "have",
    "had",
    "not",
    "no",
    "shall",
    "which",
}


class CutoffLeak(AssertionError):
    """A hit decided on/after the cutoff reached the results: a bug, never silently dropped."""


@dataclass(frozen=True)
class Hit:
    chunk_id: int
    order_id: int
    complaint_no: str
    decided_on: date
    page_no: int
    char_start: int
    char_end: int
    text: str
    score: float
    keyword_rank: int | None = None
    vector_rank: int | None = None


@dataclass
class SearchResult:
    hits: list[Hit]
    mode: str  # "hybrid" | "keyword" (no embeddings for the configured model)
    notes: list[str] = field(default_factory=list)


def keyword_query(query: str) -> str:
    """Natural-language query -> websearch syntax with OR between content words."""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", query.lower()) if w not in _STOP and len(w) > 1]
    return " or ".join(dict.fromkeys(words))


_BASE = """
    FROM order_chunks c
    JOIN orders o ON o.id = c.order_id
    WHERE o.decided_on < :before
      AND o.source = :source
      AND (CAST(:case_type AS text) IS NULL OR o.case_type = :case_type)
"""


def keyword_ranks(
    s: Session, query: str, before: date, source: str, case_type: str | None, limit: int = POOL
) -> list[int]:
    q = keyword_query(query)
    if not q:
        return []
    rows = s.execute(
        text(f"""
            SELECT c.id {_BASE}
              AND c.tsv @@ websearch_to_tsquery('english', :q)
            ORDER BY ts_rank_cd(c.tsv, websearch_to_tsquery('english', :q)) DESC, c.id
            LIMIT :limit
        """),
        {"q": q, "before": before, "source": source, "case_type": case_type, "limit": limit},
    )
    return [r[0] for r in rows]


def vector_ranks(
    s: Session,
    embedding: list[float],
    model: str,
    before: date,
    source: str,
    case_type: str | None,
    limit: int = POOL,
) -> list[int]:
    rows = s.execute(
        text(f"""
            SELECT c.id {_BASE}
              AND c.embedding IS NOT NULL AND c.embedding_model = :model
            ORDER BY c.embedding <=> CAST(:vec AS vector), c.id
            LIMIT :limit
        """),
        {
            "vec": str(embedding),
            "model": model,
            "before": before,
            "source": source,
            "case_type": case_type,
            "limit": limit,
        },
    )
    return [r[0] for r in rows]


def has_embeddings(s: Session, model: str) -> bool:
    return bool(
        s.scalar(text("SELECT EXISTS (SELECT 1 FROM order_chunks WHERE embedding_model = :m)"), {"m": model})
    )


def search(
    s: Session,
    query: str,
    *,
    before: date,
    embedder: Embedder | None = None,
    k: int = 10,
    source: str = "hrera_gurugram",
    case_type: str | None = "HRERA Complaints",
) -> SearchResult:
    if not isinstance(before, date):
        raise TypeError("search() needs a cutoff date: only orders decided before it are searched")
    notes: list[str] = []
    kw = keyword_ranks(s, query, before, source, case_type)
    vec: list[int] = []
    mode = "keyword"
    if embedder is not None:
        if has_embeddings(s, embedder.name):
            vec = vector_ranks(s, embedder.embed_query(query), embedder.name, before, source, case_type)
            mode = "hybrid"
        else:
            notes.append(f"no stored embeddings for {embedder.name}; keyword search only")

    scores: dict[int, float] = {}
    kw_rank = {cid: i + 1 for i, cid in enumerate(kw)}
    vec_rank = {cid: i + 1 for i, cid in enumerate(vec)}
    for ranks in (kw_rank, vec_rank):
        for cid, r in ranks.items():
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + r)
    if not scores:
        return SearchResult([], mode, notes)

    rows = s.execute(
        text("""
            SELECT c.id, c.order_id, o.complaint_no, o.decided_on, c.page_no, c.char_start, c.char_end, c.text
            FROM order_chunks c JOIN orders o ON o.id = c.order_id
            WHERE c.id = ANY(:ids)
        """),
        {"ids": list(scores)},
    ).all()
    by_id = {r[0]: r for r in rows}

    hits: list[Hit] = []
    per_order: dict[int, int] = {}
    for cid in sorted(scores, key=lambda c: (-scores[c], c)):
        r = by_id[cid]
        if r[3] >= before:  # defence in depth: the SQL already filtered; this must never happen
            raise CutoffLeak(f"chunk {cid} decided {r[3]} is not before cutoff {before}")
        if per_order.get(r[1], 0) >= MAX_PER_ORDER:
            continue
        per_order[r[1]] = per_order.get(r[1], 0) + 1
        hits.append(
            Hit(
                cid,
                r[1],
                r[2],
                r[3],
                r[4],
                r[5],
                r[6],
                r[7],
                round(scores[cid], 6),
                kw_rank.get(cid),
                vec_rank.get(cid),
            )
        )
        if len(hits) == k:
            break
    return SearchResult(hits, mode, notes)
