"""Export a hand-check sheet for extracted case records (the plan's 200-record check).

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.export_review --sample 200

Writes data/review/review_<date>.csv: one row per stored field, with the value, the exact
quoted text from the stored page, the page number and the local PDF path. Fill the
"correct" column (Y / N) and "correct_value" when N; accuracy is computed from that
sheet later. Records are sampled evenly across decision years.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import CaseRecord, Order, OrderPage

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("claim_type", "outcome", "possession_due", "amount_paid", "award_amount", "interest_rate_pct")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200)
    args = ap.parse_args()

    engine = create_engine(settings.database_url)
    out = ROOT / "data" / "review" / f"review_{date.today().isoformat()}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    with Session(engine) as s:
        # Spread across years: order by a per-year row number, then take the first N.
        ranked = (
            select(CaseRecord.order_id)
            .join(Order, Order.id == CaseRecord.order_id)
            .order_by(
                func.row_number().over(
                    partition_by=func.extract("year", Order.decided_on), order_by=func.md5(Order.complaint_no)
                ),
                Order.decided_on,
            )
            .limit(args.sample)
        )
        ids = list(s.scalars(ranked))
        rows = 0
        with out.open("w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel shows Hindi correctly
            w = csv.writer(f)
            w.writerow(
                [
                    "complaint_no",
                    "decided_on",
                    "field",
                    "value",
                    "page_no",
                    "quoted_text",
                    "pdf_file",
                    "correct (Y/N)",
                    "correct_value",
                    "notes",
                ]
            )
            for oid in ids:
                rec = s.get(CaseRecord, oid)
                order = s.get(Order, oid)
                pdf = ROOT / "data" / "orders" / order.source / f"{order.pdf_sha256}.pdf"
                items = [(name, getattr(rec, name)) for name in FIELDS]
                items += [(f"defences[{i}]", d) for i, d in enumerate(rec.defences)]
                for name, value in items:
                    src = rec.field_sources.get(name)
                    if value is None or src is None:
                        continue
                    page = s.get(OrderPage, (oid, src["page_no"]))
                    quoted = page.text[src["char_start"] : src["char_end"]] if page else "(page missing)"
                    w.writerow(
                        [
                            order.complaint_no,
                            order.decided_on,
                            name,
                            value,
                            src["page_no"],
                            " ".join(quoted.split()),
                            str(pdf),
                            "",
                            "",
                            "",
                        ]
                    )
                    rows += 1
    print(f"{len(ids)} records, {rows} fields -> {out}")


if __name__ == "__main__":
    main()
