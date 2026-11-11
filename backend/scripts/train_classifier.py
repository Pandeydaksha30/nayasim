"""Train and evaluate the text classifiers (app/ml/text_classifier.py).

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.train_classifier            # both tasks
  .\\.venv\\Scripts\\python.exe -m scripts.train_classifier --task outcome

Prints validation and test scores; saves the model to data/models/<task>_tfidf_lr.joblib and the
report to data/benchmark/train_<task>_<time>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.ml.text_classifier import load_items, train_and_evaluate

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["outcome", "claim_type", "both"], default="both")
    args = ap.parse_args()
    with Session(get_engine()) as s:
        items, skipped = load_items(s)
    print(f"labelled orders with a safe facts part: {len(items)} (skipped {skipped})")
    for task in ("outcome", "claim_type") if args.task == "both" else (args.task,):
        rep = train_and_evaluate(items, task)
        model = rep.pop("_model", None)
        print(f"\n== {task}: train / validation / test = {rep['counts']}")
        if "error" in rep:
            print(rep["error"])
            continue
        for g in rep["validation_grid"]:
            print(f"   validation C={g['C']:<5} accuracy {g['accuracy']:.3f}  macro-F1 {g['macro_f1']:.3f}")
        t, b = rep["test"], rep["test_majority_baseline"]
        print(
            f"   chosen C={rep['chosen_C']}; TEST accuracy {t['accuracy']:.3f}  macro-F1 {t['macro_f1']:.3f}"
        )
        print(f"   test majority baseline: accuracy {b['accuracy']:.3f}  macro-F1 {b['macro_f1']:.3f}")
        print(f"   confusion {t['confusion']['labels']}: {t['confusion']['rows_truth']}")
        if "test_model_alone" in rep:
            a = rep["test_model_alone"]
            print(
                f"   rule spoke on {rep['test_rule_coverage']} of {t['n']} test orders; model alone: "
                f"accuracy {a['accuracy']:.3f}  macro-F1 {a['macro_f1']:.3f}"
            )
        (ROOT / "data" / "models").mkdir(parents=True, exist_ok=True)
        joblib.dump(model, ROOT / "data" / "models" / f"{task}_tfidf_lr.joblib")
        out = ROOT / "data" / "benchmark" / f"train_{task}_{datetime.now():%Y%m%d_%H%M%S}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
        print(f"   -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
