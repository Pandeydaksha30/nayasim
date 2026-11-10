"""Benchmark commands (from backend/):

  .\\.venv\\Scripts\\python.exe -m scripts.benchmark split        # write benchmark/split_v1.json once
  .\\.venv\\Scripts\\python.exe -m scripts.benchmark citations              # on the validation split
  .\\.venv\\Scripts\\python.exe -m scripts.benchmark citations --split test # final, reported number

Blind annotation (two people, then an expert for disagreements):
  ... scripts.benchmark annotate-export --annotators A,B --n 100     # data/annotation/blind_A.csv, _B.csv
  ... scripts.benchmark annotate-agree                              # kappa + data/annotation/adjudication.csv
  ... scripts.benchmark annotate-score                              # extraction accuracy vs gold

Search (pooled, blind relevance judgements) and OCR (hand-typed pages):
  ... scripts.benchmark retrieval-export --n 30    # data/annotation/retrieval_judgements.csv
  ... scripts.benchmark retrieval-score            # MRR, nDCG@10, P@5, recall in pool, per method
  ... scripts.benchmark ocr-export --n 30          # data/annotation/ocr/*.png + empty .txt
  ... scripts.benchmark ocr-score                  # CER / WER

Results are printed and saved to data/benchmark/<name>_<time>.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.benchmark import annotation as ann
from app.benchmark import citations as cit
from app.benchmark import ocr as ocr_eval
from app.benchmark import retrieval as ret
from app.benchmark import split
from app.db.session import get_engine

OUT = Path(__file__).resolve().parents[2] / "data" / "benchmark"


def _save(name: str, result: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return path


def cmd_split() -> int:
    with Session(get_engine()) as s:
        manifest = split.build(s)
    try:
        path = split.write_once(manifest)
    except FileExistsError as e:
        print(e)
        return 1
    print(f"wrote {path}")
    print(json.dumps(manifest["counts"], indent=1))
    moved = sum(d["moved_to_train"] for d in manifest["duplicates"])
    print(f"duplicate groups: {len(manifest['duplicates'])} ({moved} spanning splits, moved to train)")
    return 0


def cmd_citations(pages: int, seed: int, which: str) -> int:
    manifest = split.load_manifest()
    test_ids = split.order_ids(manifest, which)
    with Session(get_engine()) as s:
        cases = cit.build_cases(s, test_ids, n_pages=pages, seed=seed)
        result = cit.evaluate(s, cases)
    result.update(
        {"split_version": manifest["version"], "split": which, "seed": seed, "pages_sampled": pages}
    )
    path = _save("citations", result)
    print(f"split: {which}")
    print(f"{result['cases']} cases ({result['genuine']} genuine, {result['fabricated']} fabricated)")
    print(
        f"precision {result['precision']}  recall {result['recall']}  F1 {result['f1']}  "
        f"fabrications caught {result['fabrication_catch_rate']}"
    )
    print(f"{'kind':26} {'n':>5} {'accepted':>9}")
    for kind, k in result["per_kind"].items():
        print(f"{kind:26} {k['n']:5d} {k['rate']:9.3f}  ({'genuine' if k['genuine'] else 'fabricated'})")
    print(f"-> {path}")
    return 0


def cmd_annotate_export(annotators: list[str], n: int, which: str, seed: int) -> int:
    manifest = split.load_manifest()
    with Session(get_engine()) as s:
        orders = ann.sample(s, split.order_ids(manifest, which), n, seed)
    for a in annotators:
        try:
            print(f"wrote {ann.export(orders, a)}  ({len(orders)} orders from the {which} split)")
        except FileExistsError as e:
            print(e)
            return 1
    print("Give each person only their own sheet. They must not see each other's answers or the model's.")
    return 0


def cmd_annotate_agree(a: str, b: str) -> int:
    report = ann.agree(ann.DIR / f"blind_{a}.csv", ann.DIR / f"blind_{b}.csv")
    path = _save("agreement", report)
    print(json.dumps(report, indent=1))
    print(f"-> {path}")
    return 0


def cmd_annotate_score(a: str, b: str) -> int:
    gold = ann.gold(ann.DIR / f"blind_{a}.csv", ann.DIR / f"blind_{b}.csv", ann.DIR / "adjudication.csv")
    with Session(get_engine()) as s:
        report = ann.score(s, gold)
    path = _save("extraction_vs_gold", report)
    print(json.dumps(report, indent=1))
    print(f"-> {path}")
    return 0


def cmd_retrieval_export(n: int, which: str, seed: int) -> int:
    from app.config import settings
    from app.retrieval.embedder import LocalEmbedder

    manifest = split.load_manifest()
    emb = LocalEmbedder(
        settings.embedding_model, settings.embedding_query_prefix, settings.embedding_doc_prefix
    )
    with Session(get_engine()) as s:
        try:
            path = ret.export(s, split.order_ids(manifest, which), n, seed, emb)
        except FileExistsError as e:
            print(e)
            return 1
    print(f"wrote {path} (judge 0/1/2 per row; method ranks kept apart in retrieval_ranks.csv)")
    return 0


def cmd_retrieval_score() -> int:
    report = ret.score(ret.DIR / "retrieval_judgements.csv", ret.DIR / "retrieval_ranks.csv")
    path = _save("retrieval", report)
    print(json.dumps(report, indent=1))
    print(f"-> {path}")
    return 0


def cmd_ocr_export(n: int, which: str, seed: int) -> int:
    manifest = split.load_manifest()
    with Session(get_engine()) as s:
        made = ocr_eval.export(s, split.order_ids(manifest, which), n, seed)
    print(f"{made} pages exported to {ocr_eval.DIR} (type each page's text into its .txt file)")
    return 0


def cmd_ocr_score() -> int:
    with Session(get_engine()) as s:
        report = ocr_eval.score(s)
    path = _save("ocr", report)
    print(json.dumps({k: v for k, v in report.items() if k != "per_page"}, indent=1))
    print(f"-> {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("split")
    c = sub.add_parser("citations")
    c.add_argument("--pages", type=int, default=150)
    c.add_argument("--seed", type=int, default=20261110)
    c.add_argument(
        "--split",
        choices=["validation", "test"],
        default="validation",
        help="develop on validation; use test only for the final, reported number",
    )
    e = sub.add_parser("annotate-export")
    e.add_argument("--annotators", default="A,B")
    e.add_argument("--n", type=int, default=100)
    e.add_argument("--split", choices=["validation", "test"], default="test")
    e.add_argument("--seed", type=int, default=20261110)
    for name in ("annotate-agree", "annotate-score"):
        x = sub.add_parser(name)
        x.add_argument("--a", default="A")
        x.add_argument("--b", default="B")
    for name in ("retrieval-export", "ocr-export"):
        x = sub.add_parser(name)
        x.add_argument("--n", type=int, default=30)
        x.add_argument("--split", choices=["validation", "test"], default="test")
        x.add_argument("--seed", type=int, default=20261110)
    sub.add_parser("retrieval-score")
    sub.add_parser("ocr-score")
    args = ap.parse_args()
    if args.cmd == "retrieval-export":
        return cmd_retrieval_export(args.n, args.split, args.seed)
    if args.cmd == "retrieval-score":
        return cmd_retrieval_score()
    if args.cmd == "ocr-export":
        return cmd_ocr_export(args.n, args.split, args.seed)
    if args.cmd == "ocr-score":
        return cmd_ocr_score()
    if args.cmd == "split":
        return cmd_split()
    if args.cmd == "annotate-export":
        return cmd_annotate_export(args.annotators.split(","), args.n, args.split, args.seed)
    if args.cmd == "annotate-agree":
        return cmd_annotate_agree(args.a, args.b)
    if args.cmd == "annotate-score":
        return cmd_annotate_score(args.a, args.b)
    return cmd_citations(args.pages, args.seed, args.split)


if __name__ == "__main__":
    sys.exit(main())
