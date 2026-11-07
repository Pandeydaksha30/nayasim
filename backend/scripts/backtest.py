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
from app.backtest.metrics import METHODS, score
from app.backtest.run import as_rows, run_backtest
from app.config import settings
from app.db.session import get_engine

OUT = Path(__file__).resolve().parents[2] / "data" / "backtest"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=date.fromisoformat, default=date(2025, 1, 1))
    ap.add_argument("--limit", type=int, default=64)
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    ap.add_argument("--thinking", default="", help="thinking level for models that support it")
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
        test = load(s, args.cutoff, split="test")[: args.limit]
        s.commit()
        print(
            f"cutoff {args.cutoff}: {len(train)} training records, {len(test)} test cases; model {llm.name}"
        )
        print(
            "search: keyword only (embeddings are not complete yet), same precedents for single and debate\n"
        )
        t = time.monotonic()
        rows = as_rows(run_backtest(s, train, test, args.cutoff, llm, embedder=None))
    elapsed = time.monotonic() - t
    result = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "cutoff": args.cutoff.isoformat(),
        "model": llm.name,
        "train_records": len(train),
        "elapsed_min": round(elapsed / 60, 1),
        "scores": score(rows),
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
    for m in METHODS:
        x = sc["methods"][m]
        lo, hi = x["accuracy_90"]
        print(f"{m:10} {x['accuracy']:.3f} ({lo:.2f}-{hi:.2f})    {x['macro_f1']:.3f}")
    print(f"debate vs single: {sc['debate_vs_single']}")
    print(f"citations: {sc['citations']}")
    print(f"elapsed {elapsed / 60:.1f} min -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
