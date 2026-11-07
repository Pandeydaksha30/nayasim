"""Extract verified outcome fields from fetched orders into case_records.

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.extract_fields --check-key     (confirm the key works)
  .\\.venv\\Scripts\\python.exe -m scripts.extract_fields --list-models
  .\\.venv\\Scripts\\python.exe -m scripts.extract_fields --limit 10

Needs GEMINI_API_KEY in backend/.env. Orders whose outcome or claim type cannot be verified
are written to data/extraction/needs_review.jsonl and not retried automatically.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine

from app.config import settings
from app.extraction.runner import (
    ExtractReport,
    extract_order,
    merge_review_logs,
    pending_for_extraction,
    reviewed_ids,
)

REVIEW_LOG = Path(__file__).resolve().parents[2] / "data" / "extraction" / "needs_review.jsonl"
RETRY_LOG = REVIEW_LOG.with_name("needs_review.retry.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="extract up to N pending orders")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--check-key", action="store_true")
    ap.add_argument("--model", default=settings.gemini_model)
    ap.add_argument("--interval", type=float, default=4.0, help="seconds between model calls")
    ap.add_argument(
        "--retry-review",
        action="store_true",
        help="re-run orders in the review file (use with a stronger --model)",
    )
    ap.add_argument(
        "--thinking",
        default="default",
        choices=["minimal", "low", "medium", "high", "default"],
        help="thinking level; 'default' leaves the model's own (use low with gemini-3.8-flash)",
    )
    args = ap.parse_args()

    if settings.gemini_api_key is None:
        print("GEMINI_API_KEY is not set. Add it to backend/.env (see docs/extraction.md).")
        return 2
    key = settings.gemini_api_key.get_secret_value()

    from app.extraction.gemini import GeminiExtractor, list_models, ping

    if args.list_models or args.check_key:
        models = list_models(key)
        print(f"key works: {len(models)} models listed")
        if args.list_models:
            print("\n".join(models))
        if args.model not in models:
            print(f"warning: configured model {args.model!r} is not in this key's list")
        try:
            print(f"test call to {args.model}: replied {ping(key, args.model)!r}")
        except Exception as e:  # reported, and the exit code says it failed
            print(f"test call to {args.model} FAILED: {type(e).__name__}: {str(e)[:200]}")
            return 1
        return 0

    if args.limit:
        engine = create_engine(settings.database_url)
        thinking = None if args.thinking == "default" else args.thinking
        extractor = GeminiExtractor(key, args.model, min_interval_s=args.interval, thinking=thinking)
        if args.retry_review:
            # Second pass: orders the first model sent to review, tried again with --model.
            in_review = reviewed_ids(REVIEW_LOG)
            ids = [i for i in pending_for_extraction(engine, 10**9) if i in in_review][: args.limit]
            log = RETRY_LOG
        else:
            ids = pending_for_extraction(engine, args.limit, skip=reviewed_ids(REVIEW_LOG))
            log = REVIEW_LOG
        mode = "retrying review orders" if args.retry_review else "pending"
        print(f"model: {args.model} (thinking: {args.thinking}); {mode} selected: {len(ids)}")
        report = ExtractReport()
        started = time.monotonic()
        for i, oid in enumerate(ids, 1):
            print(f"[{i}/{len(ids)}] order {oid}: sending...", flush=True)
            extractor.last_call_s = None
            status = extract_order(engine, oid, extractor, log, report)
            took = f" (model {extractor.last_call_s:.0f} s)" if extractor.last_call_s else ""
            print(f"[{i}/{len(ids)}] order {oid}: {status}{took}", flush=True)
        elapsed = time.monotonic() - started
        print(
            f"\nattempted={report.attempted} stored={report.stored} needs_review={report.needs_review} "
            f"errors={len(report.errors)} fields_accepted={report.fields_accepted} "
            f"fields_rejected={report.fields_rejected} pages_sent={report.pages_sent}/{report.pages_total} "
            f"elapsed={elapsed / 60:.1f} min ({elapsed / max(1, report.attempted):.0f} s per order)"
        )
        for label, err in report.errors:
            print(f"  ERROR {label}: {err}")
        if args.retry_review:
            # Stored now -> leaves review. Failed again -> its entry is replaced by the new one.
            # API error -> keeps its old entry (it is in neither set).
            now_stored = set(ids) - set(pending_for_extraction(engine, 10**9))
            resolved = now_stored | reviewed_ids(RETRY_LOG)
            remaining = merge_review_logs(REVIEW_LOG, resolved, RETRY_LOG)
            print(f"stored on retry: {len(now_stored)}; orders still in review: {remaining}")
        return 1 if report.errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
