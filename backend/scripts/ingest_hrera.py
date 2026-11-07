"""Ingest HRERA Gurugram orders into the order store.

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.ingest_hrera --register    (fetch listing, add new orders)
  .\\.venv\\Scripts\\python.exe -m scripts.ingest_hrera --fetch 50    (download + extract 50 orders)
  .\\.venv\\Scripts\\python.exe -m scripts.ingest_hrera --fetch 50 --years 2024 2025

Every request is logged in fetch_log; PDFs are kept in data/orders/hrera_gurugram/<sha256>.pdf.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine

from app.config import settings
from app.ingestion.fetcher import PoliteFetcher
from app.ingestion.hrera_listing import GURUGRAM_LIST_URL, parse_listing
from app.ingestion.pdf_text import find_ocr
from app.ingestion.pipeline import ingest_pending, pending_orders, register_listing

SOURCE = "hrera_gurugram"
STORE = Path(__file__).resolve().parents[2] / "data" / "orders" / SOURCE


def keep_awake() -> None:
    """Ask Windows not to idle-sleep while this process runs (released when it exits).

    Uses SetThreadExecutionState; it changes no power settings. A closed lid or a manual
    Sleep still suspends the machine.
    """
    if sys.platform != "win32":
        return
    import ctypes

    es_continuous, es_system_required = 0x80000000, 0x00000001
    if ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required) == 0:
        print("warning: could not ask Windows to stay awake; the run stops if the PC sleeps")
    else:
        print("keeping the PC awake while this run lasts (closing the lid still sleeps it)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", action="store_true", help="fetch the public listing and add new orders")
    ap.add_argument("--fetch", type=int, default=0, metavar="N", help="download and extract N pending orders")
    ap.add_argument("--years", type=int, nargs="*", help="only orders decided in these years")
    ap.add_argument("--all-types", action="store_true", help="include execution/adjudication orders")
    ap.add_argument("--delay", type=float, default=2.5, help="seconds between requests (minimum 2.5)")
    args = ap.parse_args()
    if args.delay < 2.5:
        ap.error("--delay must be at least 2.5 seconds")

    engine = create_engine(settings.database_url)
    fetcher = PoliteFetcher(engine, min_delay_s=args.delay)

    if args.register:
        listing = fetcher.get(GURUGRAM_LIST_URL)
        rows = parse_listing(listing.body.decode("utf-8", errors="replace"))
        r = register_listing(engine, SOURCE, rows)
        print(
            f"listing rows={r.listed} new={r.new} already_known={r.already_known} without_pdf={r.without_pdf}"
        )

    if args.fetch:
        keep_awake()
        ocr = find_ocr()
        missing = "NOT AVAILABLE - scanned orders will be reported as failures"
        print(f"OCR: {ocr.engine_name if ocr else missing}")
        ids = pending_orders(
            engine, SOURCE, args.fetch, None if args.all_types else "HRERA Complaints", args.years
        )
        print(f"pending selected: {len(ids)}")
        started = time.monotonic()
        rep = ingest_pending(engine, ids, fetcher, ocr, STORE)
        elapsed = time.monotonic() - started
        print(f"\nelapsed {elapsed / 60:.1f} min ({elapsed / max(1, rep.attempted):.0f} s per order)")
        print(
            f"\nattempted={rep.attempted} stored={rep.stored} failed={len(rep.failures)} pages={rep.pages} "
            f"ocr_pages={rep.ocr_pages} chunks={rep.chunks} low_conf_pages={len(rep.low_confidence_pages)}"
        )
        for label, err in rep.failures:
            print(f"  FAILED {label}: {err}")
        for label, page, conf in rep.low_confidence_pages:
            print(f"  LOW OCR CONFIDENCE {label} page {page}: {conf}")
        return 1 if rep.failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
