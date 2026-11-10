"""Time-split backtest: train on records decided before the cutoff, predict later ones.

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.backtest --limit 64
  .\\.venv\\Scripts\\python.exe -m scripts.backtest --limit 10 --model gemini-3.8-flash

Writes data/backtest/<timestamp>.json (every prediction) and prints the scores.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.backtest.dataset import load
from app.backtest.metrics import score
from app.backtest.run import as_rows, run_backtest
from app.config import settings
from app.db.session import get_engine

OUT = Path(__file__).resolve().parents[2] / "data" / "backtest"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=date.fromisoformat, default=date(2025, 1, 1))
    ap.add_argument("--limit", type=int, default=64)
    ap.add_argument(
        "--until",
        type=date.fromisoformat,
        default=None,
        help="test only on cases decided before this date (e.g. --cutoff 2024-01-01 --until 2025-01-01 "
        "= the validation year; develop there, keep the 2025+ test set for final numbers)",
    )
    ap.add_argument(
        "--input",
        choices=["summary", "facts"],
        default="summary",
        help="summary = structured facts only; facts = also the parties' part of the order "
        "(before the authority's findings; app/backtest/facts.py)",
    )
    ap.add_argument(
        "--query",
        choices=["current", "legacy"],
        default="current",
        help="precedent search query; legacy = before 10 Nov 2026 (control runs only)",
    )
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--thinking", default="", help="thinking level for models that support it")
    ap.add_argument(
        "--methods",
        default="single,debate",
        help="LLM methods to run, comma-separated (single, debate); the baselines always run",
    )
    ap.add_argument(
        "--summary",
        choices=["current", "legacy"],
        default="current",
        help="case summary wording for the single-call method; legacy = 9 Nov 2026 (control runs only)",
    )
    ap.add_argument(
        "--search",
        choices=["keyword", "hybrid"],
        default="keyword",
        help="precedent search: keyword only (as the 9 Nov run) or hybrid keyword + embeddings",
    )
    args = ap.parse_args()
    faulthandler.dump_traceback_later(900, repeat=True)

    if settings.gemini_api_key is None:
        print("GEMINI_API_KEY is not set")
        return 2
    from app.extraction.gemini import GeminiExtractor

    llm = GeminiExtractor(
        settings.gemini_api_key.get_secret_value(),
        args.model,
        min_interval_s=0,
        thinking=args.thinking or None,
    )
    with Session(get_engine()) as s:
        train = load(s, args.cutoff, split="train")
        test = load(s, args.cutoff, split="test", until=args.until)[: args.limit]
        s.commit()
        print(
            f"cutoff {args.cutoff}: {len(train)} training records, {len(test)} test cases; model {llm.name}"
        )
        llm_methods = tuple(m for m in args.methods.split(",") if m)
        bad = set(llm_methods) - {"single", "debate"}
        if bad:
            print(f"unknown method(s): {sorted(bad)}")
            return 2
        methods = ("majority", "buckets", *llm_methods)
        embedder = None
        if args.search == "hybrid":
            from app.retrieval.embedder import LocalEmbedder

            embedder = LocalEmbedder(
                settings.embedding_model, settings.embedding_query_prefix, settings.embedding_doc_prefix
            )
        print(f"methods: {', '.join(methods)}; search: {args.search}; same precedents for every LLM method\n")
        t = time.monotonic()
        rows = as_rows(
            run_backtest(
                s,
                train,
                test,
                args.cutoff,
                llm,
                embedder=embedder,
                methods=methods,
                summary=args.summary,
                query=args.query,
                input_mode=args.input,
            )
        )
    elapsed = time.monotonic() - t
    result = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "cutoff": args.cutoff.isoformat(),
        "model": llm.name,
        "train_records": len(train),
        "search": args.search,
        "summary": args.summary,
        "query": args.query,
        "input": args.input,
        "until": args.until.isoformat() if args.until else None,
        "elapsed_min": round(elapsed / 60, 1),
        "scores": score(rows, methods),
        "cases": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"backtest_{datetime.now():%Y%m%d_%H%M}.json"
    path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")

    sc = result["scores"]
    print(
        f"\n{sc['scored']} of {sc['cases']} cases scored (errors: {sc['errors']}); truth {sc['truth_counts']}"
    )
    print(f"{'method':10} accuracy (90% range)    macro-F1")
    for m in methods:
        x = sc["methods"][m]
        lo, hi = x["accuracy_90"]
        print(f"{m:10} {x['accuracy']:.3f} ({lo:.2f}-{hi:.2f})    {x['macro_f1']:.3f}")
    if sc["debate_vs_single"] is not None:
        print(f"debate vs single: {sc['debate_vs_single']}")
        print(f"citations: {sc['citations']}")
    print(f"elapsed {elapsed / 60:.1f} min -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
