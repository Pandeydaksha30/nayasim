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
from app.extraction.runner import ExtractReport, extract_order, pending_for_extraction, reviewed_ids

REVIEW_LOG = Path(__file__).resolve().parents[2] / "data" / "extraction" / "needs_review.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="extract up to N pending orders")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--check-key", action="store_true")
    ap.add_argument("--model", default=settings.gemini_model)
    ap.add_argument("--interval", type=float, default=4.0, help="seconds between model calls")
    args = ap.parse_args()

    if settings.gemini_api_key is None:
        print("GEMINI_API_KEY is not set. Add it to backend/.env (see docs/extraction.md).")
        return 2
    key = settings.gemini_api_key.get_secret_value()

    from app.extraction.gemini import GeminiExtractor, list_models

    if args.list_models or args.check_key:
        models = list_models(key)
        print(f"key works: {len(models)} models available")
        if args.list_models:
            print("\n".join(models))
        if args.model not in models:
            print(f"warning: configured model {args.model!r} is not in this key's list")
        return 0

    if args.limit:
        engine = create_engine(settings.database_url)
        extractor = GeminiExtractor(key, args.model, min_interval_s=args.interval)
        ids = pending_for_extraction(engine, args.limit, skip=reviewed_ids(REVIEW_LOG))
        print(f"model: {args.model}; pending selected: {len(ids)}")
        report = ExtractReport()
        started = time.monotonic()
        for i, oid in enumerate(ids, 1):
            status = extract_order(engine, oid, extractor, REVIEW_LOG, report)
            print(f"[{i}/{len(ids)}] order {oid}: {status}")
        elapsed = time.monotonic() - started
        print(
            f"\nattempted={report.attempted} stored={report.stored} needs_review={report.needs_review} "
            f"errors={len(report.errors)} fields_accepted={report.fields_accepted} "
            f"fields_rejected={report.fields_rejected} elapsed={elapsed / 60:.1f} min"
        )
        for label, err in report.errors:
            print(f"  ERROR {label}: {err}")
        return 1 if report.errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
