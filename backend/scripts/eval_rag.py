"""Evaluate document question answering on the fictional demo documents (eval/doc_qa.jsonl).

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.eval_rag dev              # retrieval only, no model
  .\\.venv\\Scripts\\python.exe -m scripts.eval_rag dev --answer     # also answers with Gemini
  .\\.venv\\Scripts\\python.exe -m scripts.eval_rag heldout --answer # final report only: never tune on it

A temporary fictional demo case is created, the three demo documents are uploaded and indexed
exactly as in the app, the questions are run, and the case is deleted again.

Measures:
  retrieval: hit@1, recall@5 (gold document+page among the passages), MRR
  answers:   accuracy (answerable: not 'insufficient' and an expected value appears in the answer),
             citation accuracy (a verified citation names the gold document and page),
             abstention (unanswerable: 'insufficient')
Limit: invented documents measure the pipeline, not performance on real agreements.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.buyer.chunks import index_document
from app.buyer.documents import store_document
from app.config import settings
from app.db.models import Case
from app.db.session import get_engine
from app.ingestion.pdf_text import find_ocr
from app.rag.answer import answer_question
from app.retrieval.case_search import search_case
from scripts.demo_buyer_case import AGREEMENT, LETTER, RECEIPTS, pdf

HERE = Path(__file__).resolve().parents[1] / "eval"


def main() -> None:
    split = sys.argv[1] if len(sys.argv) > 1 else "dev"
    with_answers = "--answer" in sys.argv
    rows = [json.loads(x) for x in (HERE / "doc_qa.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r["split"] == split]
    from app.api.hearing import _embedder

    embedder = _embedder()
    llm = None
    if with_answers:
        from app.api.hearing import get_hearing_llm

        llm = get_hearing_llm()

    with Session(get_engine()) as s:
        case = Case(title="RAG evaluation (DEMO, temporary)", claim_type="delayed_possession", is_demo=True)
        s.add(case)
        s.flush()
        case_id = case.id
        try:
            for name, kind, pages in (
                ("agreement.pdf", "agreement", AGREEMENT),
                ("receipts.pdf", "receipt", RECEIPTS),
                ("builder_letter.pdf", "builder_letter", LETTER),
            ):
                d = store_document(s, case_id, name, kind, pdf(pages), find_ocr())
                index_document(s, d.id, embedder)
            s.commit()
            results = []
            for r in rows:
                hits, mode = search_case(s, case_id, r["question"], embedder, k=5)
                found = [(h.filename, h.page_no) for h in hits]
                rank = None
                if r["answerable"]:
                    gold = (r["document_id"], r["page_no"])
                    rank = next((i + 1 for i, f in enumerate(found) if f == gold), None)
                out = {"id": r["id"], "answerable": r["answerable"], "rank": rank, "retrieved": found, "mode": mode}
                if llm is not None:
                    t = time.monotonic()
                    try:
                        a = answer_question(s, case_id, r["question"], llm, embedder)
                    except Exception as e:  # noqa: BLE001 - recorded as an error, counted as wrong
                        a = {"insufficient": True, "answer": "", "citations": [], "error": f"{type(e).__name__}: {e}"}
                    text = a["answer"].lower()
                    out.update(
                        {
                            "answer": a["answer"],
                            "insufficient": a["insufficient"],
                            "correct": (not a["insufficient"])
                            and any(k.lower() in text for k in r["answer_keys"])
                            if r["answerable"]
                            else a["insufficient"],
                            "citation_ok": any(
                                (c["filename"], c["page_no"]) == (r["document_id"], r["page_no"])
                                for c in a["citations"]
                            )
                            if r["answerable"]
                            else not a["citations"],
                            "removed_citations": len(a.get("rejected_citations", [])),
                            "seconds": round(time.monotonic() - t, 1),
                            "error": a.get("error"),
                        }
                    )
                results.append(out)
                print(json.dumps({k: v for k, v in out.items() if k != "retrieved"}, ensure_ascii=False)[:220])
        finally:
            s.rollback()
            s.execute(delete(Case).where(Case.id == case_id))
            s.commit()

    ans = [x for x in results if x["answerable"]]
    una = [x for x in results if not x["answerable"]]
    summary = {
        "split": split,
        "questions": len(results),
        "answerable": len(ans),
        "unanswerable": len(una),
        "embedding_model": settings.embedding_model,
        "retrieval_hit_at_1": round(sum(x["rank"] == 1 for x in ans) / len(ans), 3),
        "retrieval_recall_at_5": round(sum(x["rank"] is not None for x in ans) / len(ans), 3),
        "retrieval_mrr": round(sum(1 / x["rank"] for x in ans if x["rank"]) / len(ans), 3),
    }
    if llm is not None:
        summary.update(
            {
                "model": llm.name,
                "answer_accuracy": round(sum(x["correct"] for x in ans) / len(ans), 3),
                "citation_accuracy": round(sum(x["citation_ok"] for x in ans) / len(ans), 3),
                "abstention_accuracy": round(sum(x["correct"] for x in una) / len(una), 3) if una else None,
                "citations_removed_by_check": sum(x["removed_citations"] for x in results),
                "errors": sum(1 for x in results if x.get("error")),
            }
        )
    print(json.dumps(summary, indent=1))
    out = HERE / f"results_{split}{'_answers' if llm else ''}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
