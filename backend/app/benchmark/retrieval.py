"""Precedent search evaluation with human relevance judgements (pooled, blind to the method).

1. `export`: for sample benchmark orders, the facts a buyer would have (as in the backtest) form
   the query; keyword-only and hybrid search each return their top 10 orders decided before the
   query order. The union is written, shuffled, to one sheet, without saying which method found
   which result. The query order itself can never be returned (cutoff = its decision date).
2. A person marks each candidate: 2 = on point (same claim and similar facts), 1 = related,
   0 = not relevant, reading the query summary and the candidate's PDF.
3. `score`: per method, MRR (first result judged >= 1), nDCG@10 (graded), precision@5, and
   recall@10 within the judged pool (share of all relevant pooled results the method found).
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.dataset import Example, case_input
from app.db.models import CaseRecord, Order
from app.hearing.inputs import search_query, summary_text
from app.retrieval.embedder import Embedder
from app.retrieval.search import search

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data" / "annotation"
ORDERS_DIR = ROOT / "data" / "orders" / "hrera_gurugram"
K = 10


def _top_orders(s: Session, query: str, before, embedder: Embedder | None, k: int = K) -> list[int]:
    res = search(s, query, before=before, embedder=embedder, k=k * 3)
    seen: list[int] = []
    for h in res.hits:
        if h.order_id not in seen:
            seen.append(h.order_id)
        if len(seen) == k:
            break
    return seen


def export(
    s: Session, order_ids: list[int], n: int, seed: int, embedder: Embedder, out_dir: Path = DIR
) -> Path:
    path = out_dir / "retrieval_judgements.csv"
    if path.exists():
        raise FileExistsError(f"{path} exists; it may hold judgements.")
    rows = s.execute(
        select(Order, CaseRecord)
        .join(CaseRecord, CaseRecord.order_id == Order.id)
        .where(Order.id.in_(order_ids))
    ).all()
    rng = random.Random(seed)
    rng.shuffle(rows)
    out = []
    pdfs = {}
    for o, r in rows[:n]:
        e = Example(
            o.id, o.complaint_no, o.decided_on, r.claim_type, r.possession_due, r.amount_paid, r.outcome
        )
        ci = case_input(e, o.decided_on)
        q = search_query(ci)
        kw = _top_orders(s, q, o.decided_on, None)
        hy = _top_orders(s, q, o.decided_on, embedder)
        pool = list(dict.fromkeys(kw + hy))
        rng.shuffle(pool)
        for oid in pool:
            if oid not in pdfs:
                cand = s.get(Order, oid)
                pdfs[oid] = (cand.complaint_no, str(ORDERS_DIR / f"{cand.pdf_sha256}.pdf"))
            out.append(
                {
                    "query_order": o.complaint_no,
                    "query_summary": summary_text(ci).replace("\n", " | "),
                    "candidate": pdfs[oid][0],
                    "candidate_pdf": pdfs[oid][1],
                    "relevance (0/1/2)": "",
                    "_kw_rank": kw.index(oid) + 1 if oid in kw else "",
                    "_hy_rank": hy.index(oid) + 1 if oid in hy else "",
                }
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    blind = [{k: v for k, v in r.items() if not k.startswith("_")} for r in out]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(blind[0]))
        w.writeheader()
        w.writerows(blind)
    # Ranks are kept apart from the sheet, so the judge cannot see which method found what.
    key = out_dir / "retrieval_ranks.csv"
    with key.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query_order", "candidate", "keyword_rank", "hybrid_rank"])
        w.writeheader()
        for r in out:
            w.writerow(
                {
                    "query_order": r["query_order"],
                    "candidate": r["candidate"],
                    "keyword_rank": r["_kw_rank"],
                    "hybrid_rank": r["_hy_rank"],
                }
            )
    return path


def mrr(rels_by_rank: list[int]) -> float:
    for i, rel in enumerate(rels_by_rank, 1):
        if rel >= 1:
            return 1 / i
    return 0.0


def ndcg(rels_by_rank: list[int], all_rels: list[int], k: int = K) -> float:
    dcg = sum((2**r - 1) / math.log2(i + 1) for i, r in enumerate(rels_by_rank[:k], 1))
    ideal = sorted(all_rels, reverse=True)[:k]
    idcg = sum((2**r - 1) / math.log2(i + 1) for i, r in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def score(judgements: Path, ranks: Path) -> dict:
    with judgements.open(encoding="utf-8-sig", newline="") as f:
        rel = {
            (r["query_order"], r["candidate"]): int(r["relevance (0/1/2)"])
            for r in csv.DictReader(f)
            if r["relevance (0/1/2)"].strip()
        }
    with ranks.open(encoding="utf-8", newline="") as f:
        rank_rows = list(csv.DictReader(f))
    queries = sorted({q for q, _ in rel})
    out: dict = {"queries_judged": len(queries), "methods": {}}
    for method in ("keyword", "hybrid"):
        m = {"mrr": [], "ndcg@10": [], "precision@5": [], "recall@10_in_pool": []}
        for q in queries:
            pool = {c: rel[(q, c)] for qq, c in rel if qq == q}
            ranked = sorted(
                (int(r[f"{method}_rank"]), r["candidate"])
                for r in rank_rows
                if r["query_order"] == q and r[f"{method}_rank"] and (q, r["candidate"]) in rel
            )
            rels = [pool[c] for _, c in ranked]
            relevant = sum(v >= 1 for v in pool.values())
            m["mrr"].append(mrr(rels))
            m["ndcg@10"].append(ndcg(rels, list(pool.values())))
            m["precision@5"].append(sum(v >= 1 for v in rels[:5]) / 5)
            if relevant:
                m["recall@10_in_pool"].append(sum(v >= 1 for v in rels[:K]) / relevant)
        out["methods"][method] = {k: round(sum(v) / len(v), 4) if v else None for k, v in m.items()}
    return out
