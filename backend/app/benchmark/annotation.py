"""Blind, independent annotation of orders, agreement, adjudication, and scoring against gold.

Protocol (MODEL_TRAINING_GUIDE.md / MODEL_EVALUATION.md):
1. `export`: one sheet per annotator for the same sample of benchmark orders. Each row gives the
   order and its PDF and has EMPTY answer columns. The model's value is never shown, so
   annotators are not anchored by it.
2. Two people fill their sheets independently.
3. `agree`: per field, raw agreement and Cohen's kappa (categorical fields); every disagreement is
   written to an adjudication sheet with both answers side by side.
4. An expert fills the adjudication sheet's `final` column.
5. Gold = the agreed answer, or the adjudicated one. `score` compares the stored extraction with
   gold: accuracy with a 90% Wilson interval per field, coverage (share of gold the model gave
   an answer for), and a confusion table for outcome.
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseRecord, Order
from app.hearing.stats import wilson

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data" / "annotation"
ORDERS_DIR = ROOT / "data" / "orders" / "hrera_gurugram"

OUTCOMES = ("allowed", "partly_allowed", "dismissed", "disposed_of", "withdrawn")
CLAIMS = ("delayed_possession", "refund", "other")
FIELDS = {
    "outcome": "one of: " + ", ".join(OUTCOMES),
    "claim_type": "one of: " + ", ".join(CLAIMS),
    "possession_due": "date YYYY-MM-DD, or blank if the order does not state it",
    "amount_paid": "rupees, digits only (e.g. 7200000), or blank",
    "interest_rate_pct": "e.g. 10.85, or blank",
}
CATEGORICAL = ("outcome", "claim_type")
HEAD = ["complaint_no", "decided_on", "pdf_file", *FIELDS, "notes"]


def sample(s: Session, order_ids: list[int], n: int, seed: int) -> list[Order]:
    ids = sorted(order_ids)
    random.Random(seed).shuffle(ids)
    chosen = sorted(ids[:n])
    return list(s.scalars(select(Order).where(Order.id.in_(chosen)).order_by(Order.decided_on, Order.id)))


def export(orders: list[Order], annotator: str, out_dir: Path = DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"blind_{annotator}.csv"
    if path.exists():
        raise FileExistsError(f"{path} exists; it may hold answers. Use another annotator name.")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        w.writerow(["(instructions)", "", "", *FIELDS.values(), "anything unclear"])
        for o in orders:
            pdf = ORDERS_DIR / f"{o.pdf_sha256}.pdf" if o.pdf_sha256 else ""
            w.writerow([o.complaint_no, o.decided_on.isoformat(), str(pdf), *[""] * len(FIELDS), ""])
    return path


def read_sheet(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["complaint_no"] and not r["complaint_no"].startswith("(")]
    return {f"{r['complaint_no']}|{r['decided_on']}": r for r in rows}


def normalise(field: str, value: str | None) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    if field in CATEGORICAL:
        return v.lower().replace(" ", "_")
    if field == "possession_due":
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            return v
    try:
        return str(Decimal(v.replace(",", "").replace("%", "")).normalize())
    except InvalidOperation:
        return v


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agree(sheet_a: Path, sheet_b: Path, out_dir: Path = DIR) -> dict:
    a, b = read_sheet(sheet_a), read_sheet(sheet_b)
    keys = sorted(set(a) & set(b))
    report: dict = {"orders_in_both": len(keys), "fields": {}}
    disagreements = []
    for field in FIELDS:
        pairs = [
            (k, normalise(field, a[k].get(field)), normalise(field, b[k].get(field)))
            for k in keys
            if (a[k].get(field) or "").strip() or (b[k].get(field) or "").strip()
        ]
        same = sum(x == y for _, x, y in pairs)
        entry = {"rows": len(pairs), "agreement": round(same / len(pairs), 4) if pairs else None}
        if field in CATEGORICAL:
            both = [(x or "(blank)", y or "(blank)") for _, x, y in pairs]
            entry["cohen_kappa"] = (
                round(k, 4)
                if (k := cohen_kappa([x for x, _ in both], [y for _, y in both])) is not None
                else None
            )
        report["fields"][field] = entry
        disagreements += [(k, field, x, y) for k, x, y in pairs if x != y]
    out_dir.mkdir(parents=True, exist_ok=True)
    adj = out_dir / "adjudication.csv"
    with adj.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "complaint_no",
                "decided_on",
                "pdf_file",
                "field",
                "annotator_a",
                "annotator_b",
                "final",
                "reason",
            ]
        )
        for k, field, x, y in disagreements:
            cno, dec = k.split("|")
            w.writerow([cno, dec, a[k]["pdf_file"], field, x or "", y or "", "", ""])
    report["disagreements"] = len(disagreements)
    report["adjudication_sheet"] = str(adj)
    return report


def gold(sheet_a: Path, sheet_b: Path, adjudication: Path | None) -> dict[str, dict[str, str | None]]:
    """Agreed answers, plus adjudicated ones. Unresolved disagreements are left out (not guessed)."""
    a, b = read_sheet(sheet_a), read_sheet(sheet_b)
    decided: dict[tuple[str, str], str | None] = {}
    if adjudication and adjudication.exists():
        with adjudication.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r["final"].strip():
                    final = "" if r["final"].strip().lower() == "blank" else r["final"]
                    decided[(f"{r['complaint_no']}|{r['decided_on']}", r["field"])] = normalise(
                        r["field"], final
                    )
    out: dict[str, dict[str, str | None]] = {}
    for k in sorted(set(a) & set(b)):
        row = {}
        for field in FIELDS:
            x, y = normalise(field, a[k].get(field)), normalise(field, b[k].get(field))
            if x == y:
                row[field] = x
            elif (k, field) in decided:
                row[field] = decided[(k, field)]
        out[k] = row
    return out


def score(s: Session, gold_rows: dict[str, dict[str, str | None]]) -> dict:
    """Stored extraction vs gold. A gold value the model did not give counts as wrong (missed)."""
    model: dict[str, dict[str, str | None]] = {}
    for o, r in s.execute(select(Order, CaseRecord).outerjoin(CaseRecord, CaseRecord.order_id == Order.id)):
        k = f"{o.complaint_no}|{o.decided_on.isoformat()}"
        if k in gold_rows:
            model[k] = {
                f: (normalise(f, str(getattr(r, f))) if r is not None and getattr(r, f) is not None else None)
                for f in FIELDS
            }
    report: dict = {"orders": len(gold_rows), "fields": {}}
    for field in FIELDS:
        rows = [(k, g[field]) for k, g in gold_rows.items() if field in g]
        correct = sum(model.get(k, {}).get(field) == gv for k, gv in rows)
        answered = sum(model.get(k, {}).get(field) is not None for k, _ in rows)
        lo, hi = wilson(correct, len(rows)) if rows else (None, None)
        report["fields"][field] = {
            "gold_rows": len(rows),
            "accuracy": round(correct / len(rows), 4) if rows else None,
            "accuracy_90": [round(lo, 3), round(hi, 3)] if rows else None,
            "model_answered": answered,
        }
    conf: dict[str, Counter] = {}
    for k, g in gold_rows.items():
        if g.get("outcome"):
            conf.setdefault(g["outcome"], Counter())[model.get(k, {}).get("outcome") or "(none)"] += 1
    report["outcome_confusion"] = {t: dict(c) for t, c in conf.items()}
    return report
