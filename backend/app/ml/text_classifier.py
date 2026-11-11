"""Trained text classifiers on the parties' part of an order (app/backtest/facts.py).

Tasks
- outcome: allowed / partly_allowed / dismissed (decided on the merits);
- claim_type: refund / delayed_possession / other.

Data: labelled orders whose facts part can be cut safely (no authority text). Splits come from the
frozen benchmark (benchmark/split_v1.json): fit on train, choose settings on validation by
macro-F1, refit on train + validation, score once on test. Labels are machine-extracted and not
yet hand-checked (MODEL_EVALUATION.md), so scores are against noisy truth.

Model: TF-IDF (word 1-2 grams, sublinear tf) + logistic regression with balanced class weights —
a strong, transparent baseline for small labelled sets; structured features (claim type, delay
band) are appended as tokens for the outcome task. For claim type, the relief-section rule
(app/ml/claim_rule.py) decides where it finds clear wording and the model decides the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.facts import split_facts
from app.backtest.run import order_text
from app.benchmark.split import split_of
from app.db.models import CaseRecord, Order
from app.ml.claim_rule import relief_claim

OUTCOMES = ["allowed", "partly_allowed", "dismissed"]
CLAIMS = ["delayed_possession", "refund", "other"]


@dataclass
class Item:
    order_id: int
    split: str
    text: str
    outcome: str
    claim_type: str


def _delay_band(due: date | None, decided: date) -> str:
    if due is None:
        return "delay_unknown"
    months = (decided - due).days / 30.44
    return "delay_lt2y" if months < 24 else "delay_2to4y" if months < 48 else "delay_gt4y"


def load_items(s: Session) -> tuple[list[Item], dict[str, int]]:
    rows = s.execute(select(Order, CaseRecord).join(CaseRecord, CaseRecord.order_id == Order.id)).all()
    items, skipped = [], {"no_safe_facts_part": 0}
    for o, r in rows:
        sp = split_facts(order_text(s, o.id))
        if sp is None:
            skipped["no_safe_facts_part"] += 1
            continue
        extra = f" __claim_{r.claim_type} __{_delay_band(r.possession_due, o.decided_on)}"
        items.append(Item(o.id, split_of(o.decided_on), sp.text + extra, r.outcome, r.claim_type))
    return items, skipped


def _pipeline(c: float) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=50000, sublinear_tf=True)),
            ("clf", LogisticRegression(C=c, class_weight="balanced", max_iter=5000)),
        ]
    )


def _scores(truth: list[str], pred: list[str], labels: list[str]) -> dict:
    return {
        "n": len(truth),
        "accuracy": round(accuracy_score(truth, pred), 4) if truth else None,
        "macro_f1": round(f1_score(truth, pred, labels=labels, average="macro", zero_division=0), 4)
        if truth
        else None,
        "confusion": {"labels": labels, "rows_truth": confusion_matrix(truth, pred, labels=labels).tolist()}
        if truth
        else None,
    }


def train_and_evaluate(items: list[Item], task: str) -> dict:
    labels = OUTCOMES if task == "outcome" else CLAIMS

    def target(it: Item) -> str:
        return it.outcome if task == "outcome" else it.claim_type

    def text(it: Item) -> str:
        # The claim-type task must not be given its own answer as a feature token.
        return it.text if task == "outcome" else it.text.split(" __claim_")[0]

    def predict(model: Pipeline, its: list[Item]) -> list[str]:
        """Model prediction; for claim type the relief-section rule decides where it speaks."""
        pred = list(model.predict([text(i) for i in its]))
        if task == "claim_type":
            pred = [relief_claim(text(i)) or p for i, p in zip(its, pred, strict=True)]
        return pred

    usable = [it for it in items if target(it) in labels]
    by = {sp: [it for it in usable if it.split == sp] for sp in ("train", "validation", "test")}
    out: dict = {"task": task, "counts": {sp: len(v) for sp, v in by.items()}}
    if len({target(it) for it in by["train"]}) < 2 or not by["validation"] or not by["test"]:
        out["error"] = "not enough labelled data in every split"
        return out

    grid = []
    for c in (0.1, 0.3, 1.0, 3.0, 10.0, 30.0):
        m = _pipeline(c).fit([text(i) for i in by["train"]], [target(i) for i in by["train"]])
        pred = predict(m, by["validation"])
        grid.append({"C": c, **_scores([target(i) for i in by["validation"]], pred, labels)})
    best = max(grid, key=lambda g: (g["macro_f1"], g["accuracy"]))
    out["validation_grid"] = [{k: g[k] for k in ("C", "accuracy", "macro_f1")} for g in grid]
    out["chosen_C"] = best["C"]

    fit = by["train"] + by["validation"]
    model = _pipeline(best["C"]).fit([text(i) for i in fit], [target(i) for i in fit])
    truth = [target(i) for i in by["test"]]
    pred = predict(model, by["test"])
    out["test"] = _scores(truth, pred, labels)
    if task == "claim_type":
        out["method"] = "relief-section rule, else TF-IDF model"
        out["test_rule_coverage"] = sum(relief_claim(text(i)) is not None for i in by["test"])
        out["test_model_alone"] = _scores(truth, list(model.predict([text(i) for i in by["test"]])), labels)
    majority = max(set(target(i) for i in fit), key=[target(i) for i in fit].count)
    out["test_majority_baseline"] = _scores(truth, [majority] * len(truth), labels)
    out["test_predictions"] = {i.order_id: p for i, p in zip(by["test"], pred, strict=True)}
    out["_model"] = model
    return out
