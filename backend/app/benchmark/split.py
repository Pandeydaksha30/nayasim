"""Frozen train / validation / test split, by order.

Rule (v1): an order belongs to exactly one split by its decision date —
train < 2024-01-01 <= validation < 2025-01-01 <= test. Splitting by date (not at random) also
stops a model from seeing later decisions when predicting earlier ones.

Leak checks: the same PDF (sha256) or the same complaint number in two splits is reported, and
such orders are moved out of validation/test into train, so no evaluated document has a twin
that a model could have learned from.

The manifest is written once to benchmark/split_v1.json and never overwritten: a changed test set
would make results incomparable. A new rule means a new version file.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order

VERSION = "v1"
VAL_FROM, TEST_FROM = date(2024, 1, 1), date(2025, 1, 1)
MANIFEST = Path(__file__).resolve().parents[3] / "benchmark" / f"split_{VERSION}.json"


def split_of(decided_on: date) -> str:
    if decided_on >= TEST_FROM:
        return "test"
    if decided_on >= VAL_FROM:
        return "validation"
    return "train"


def build(s: Session, source: str = "hrera_gurugram") -> dict:
    rows = s.execute(
        select(Order.id, Order.complaint_no, Order.decided_on, Order.pdf_sha256, CaseRecord.outcome)
        .outerjoin(CaseRecord, CaseRecord.order_id == Order.id)
        .where(Order.source == source, Order.fetched_at.is_not(None))
        .order_by(Order.decided_on, Order.id)
    ).all()
    items = [
        {
            "order_id": r.id,
            "complaint_no": r.complaint_no,
            "decided_on": r.decided_on.isoformat(),
            "pdf_sha256": r.pdf_sha256,
            "labelled": r.outcome is not None,
            "split": split_of(r.decided_on),
        }
        for r in rows
    ]

    # Twins across splits: same file, or same complaint (e.g. an interim and a final order).
    leaks = []
    for key in ("pdf_sha256", "complaint_no"):
        groups: dict[str, list[dict]] = defaultdict(list)
        for it in items:
            if it[key]:
                groups[it[key]].append(it)
        for value, group in groups.items():
            splits = {g["split"] for g in group}
            if len(group) > 1:
                leaks.append(
                    {
                        "by": key,
                        "value": value,
                        "orders": [g["order_id"] for g in group],
                        "splits": sorted(splits),
                        "moved_to_train": len(splits) > 1,
                    }
                )
                if len(splits) > 1:
                    for g in group:
                        g["split"] = "train"
                        g["moved_reason"] = f"same {key} as an order in another split"

    counts = {
        sp: {
            "orders": sum(it["split"] == sp for it in items),
            "labelled": sum(it["split"] == sp and it["labelled"] for it in items),
        }
        for sp in ("train", "validation", "test")
    }
    return {
        "version": VERSION,
        "source": source,
        "rule": f"train < {VAL_FROM} <= validation < {TEST_FROM} <= test, by decision date; "
        "orders with a twin (same PDF or complaint number) in another split are moved to train",
        "counts": counts,
        "duplicates": leaks,
        "orders": items,
    }


def write_once(manifest: dict, path: Path = MANIFEST) -> Path:
    if path.exists():
        raise FileExistsError(f"{path} already exists; a split is never rewritten. Make a new version.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return path


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def order_ids(manifest: dict, split: str) -> list[int]:
    return [it["order_id"] for it in manifest["orders"] if it["split"] == split]
