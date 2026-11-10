"""Scores for the backtest. Every method is scored on the same cases: those where all methods
produced a prediction. Cases with errors are counted and reported separately."""

from __future__ import annotations

from math import comb

from app.backtest.dataset import CLASSES
from app.hearing.stats import wilson

METHODS = ("majority", "buckets", "single", "debate")


def accuracy(truth: list[str], pred: list[str]) -> float:
    return sum(t == p for t, p in zip(truth, pred, strict=True)) / len(truth) if truth else 0.0


def macro_f1(truth: list[str], pred: list[str], classes=CLASSES) -> float:
    """Mean F1 over the merits classes. A prediction outside them (e.g. disposed_of) is simply
    wrong: it lowers recall of the true class and adds no true positive anywhere."""
    f1s = []
    for c in classes:
        tp = sum(t == c and p == c for t, p in zip(truth, pred, strict=True))
        fp = sum(t != c and p == c for t, p in zip(truth, pred, strict=True))
        fn = sum(t == c and p != c for t, p in zip(truth, pred, strict=True))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def confusion(truth: list[str], pred: list[str]) -> dict[str, dict[str, int]]:
    labels = list(CLASSES) + sorted({p for p in pred if p not in CLASSES})
    table = {t: dict.fromkeys(labels, 0) for t in CLASSES}
    for t, p in zip(truth, pred, strict=True):
        table[t][p] = table[t].get(p, 0) + 1
    return table


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value on discordant pairs."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    p = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * p)


def score(rows: list[dict], methods: tuple[str, ...] = METHODS) -> dict:
    """`methods`: the methods that were run (a run may skip the LLM debate to save quota)."""
    complete = [r for r in rows if all(r["predictions"].get(m) for m in methods)]
    truth = [r["truth"] for r in complete]
    out: dict = {
        "cases": len(rows),
        "scored": len(complete),
        "methods_run": list(methods),
        "errors": {m: sum(m in r["errors"] for r in rows) for m in methods},
        "truth_counts": {c: truth.count(c) for c in CLASSES},
        "methods": {},
    }
    for m in methods:
        pred = [r["predictions"][m] for r in complete]
        acc = accuracy(truth, pred)
        lo, hi = wilson(round(acc * len(truth)), len(truth))
        out["methods"][m] = {
            "accuracy": round(acc, 3),
            "accuracy_90": [round(lo, 3), round(hi, 3)],
            "macro_f1": round(macro_f1(truth, pred), 3),
            "confusion": confusion(truth, pred),
        }
    if not {"single", "debate"} <= set(methods):
        out["debate_vs_single"] = None
        out["citations"] = None
        return out
    s_ok = [r["predictions"]["single"] == r["truth"] for r in complete]
    d_ok = [r["predictions"]["debate"] == r["truth"] for r in complete]
    only_single = sum(a and not b for a, b in zip(s_ok, d_ok, strict=True))
    only_debate = sum(b and not a for a, b in zip(s_ok, d_ok, strict=True))
    out["debate_vs_single"] = {
        "both_right": sum(a and b for a, b in zip(s_ok, d_ok, strict=True)),
        "only_single_right": only_single,
        "only_debate_right": only_debate,
        "both_wrong": sum(not a and not b for a, b in zip(s_ok, d_ok, strict=True)),
        "mcnemar_p": round(mcnemar_exact(only_single, only_debate), 3),
    }
    gates = [r["gate"] for r in rows if r.get("gate")]
    cites = sum(g["citations"] for g in gates)
    out["citations"] = {
        "hearings": len(gates),
        "citations": cites,
        "verified": sum(g["citations_verified"] for g in gates),
        "verified_share": round(sum(g["citations_verified"] for g in gates) / cites, 3) if cites else None,
        "arguments_kept": sum(g["arguments_kept"] for g in gates),
        "arguments_removed": sum(g["arguments_removed"] for g in gates),
    }
    return out
