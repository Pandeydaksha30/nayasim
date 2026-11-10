"""Benchmark tooling: split rule, agreement maths, gold building, blind export."""

from __future__ import annotations

import csv
from datetime import date

import pytest

from app.benchmark import annotation as ann
from app.benchmark import split


def test_split_by_decision_date():
    assert split.split_of(date(2023, 12, 31)) == "train"
    assert split.split_of(date(2024, 1, 1)) == "validation"
    assert split.split_of(date(2024, 12, 31)) == "validation"
    assert split.split_of(date(2025, 1, 1)) == "test"


def test_manifest_is_never_overwritten(tmp_path):
    path = tmp_path / "split.json"
    split.write_once({"version": "x", "orders": []}, path)
    with pytest.raises(FileExistsError):
        split.write_once({"version": "y", "orders": []}, path)


def test_cohen_kappa_known_values():
    assert ann.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    # Agreement no better than chance -> 0.
    assert ann.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)
    # Textbook example: po = 0.7, pe = 0.5 -> kappa 0.4.
    a = ["y"] * 25 + ["y"] * 25 + ["n"] * 10 + ["n"] * 40
    b = ["y"] * 25 + ["n"] * 25 + ["y"] * 10 + ["n"] * 40
    po = 0.65
    pe = (50 * 35 + 50 * 65) / 100**2
    assert ann.cohen_kappa(a, b) == pytest.approx((po - pe) / (1 - pe))


def _sheet(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(ann.HEAD)
        w.writerow(["(instructions)", "", "", *ann.FIELDS.values(), ""])
        for r in rows:
            w.writerow([r[0], r[1], "x.pdf", *r[2:], ""])


def test_agreement_gold_and_adjudication(tmp_path):
    a, b = tmp_path / "blind_A.csv", tmp_path / "blind_B.csv"
    _sheet(
        a,
        [
            ("C-1", "2025-01-02", "allowed", "refund", "2021-06-30", "72,00,000", "10.85"),
            ("C-2", "2025-02-03", "dismissed", "other", "", "", ""),
        ],
    )
    _sheet(
        b,
        [
            ("C-1", "2025-01-02", "Allowed", "refund", "2021-06-30", "7200000", "10.85%"),
            ("C-2", "2025-02-03", "partly_allowed", "other", "", "", ""),
        ],
    )
    report = ann.agree(a, b, out_dir=tmp_path)
    assert report["orders_in_both"] == 2
    assert report["fields"]["outcome"]["agreement"] == 0.5  # case and formatting are normalised
    assert report["fields"]["amount_paid"]["agreement"] == 1.0
    assert report["disagreements"] == 1

    # Before adjudication the disputed outcome is left out, not guessed.
    g = ann.gold(a, b, tmp_path / "adjudication.csv")
    assert g["C-1|2025-01-02"]["outcome"] == "allowed"
    assert "outcome" not in g["C-2|2025-02-03"]

    rows = list(csv.DictReader((tmp_path / "adjudication.csv").open(encoding="utf-8-sig")))
    rows[0]["final"] = "dismissed"
    with (tmp_path / "adjudication.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    g = ann.gold(a, b, tmp_path / "adjudication.csv")
    assert g["C-2|2025-02-03"]["outcome"] == "dismissed"


def test_blind_export_shows_no_model_values(tmp_path):
    class FakeOrder:
        complaint_no, decided_on, pdf_sha256 = "C-9", date(2025, 3, 1), "abc"

    path = ann.export([FakeOrder()], "Z", out_dir=tmp_path)
    rows = list(csv.reader(path.open(encoding="utf-8-sig")))
    assert rows[0] == ann.HEAD
    assert rows[2][3:] == [""] * (len(ann.FIELDS) + 1)  # every answer column empty
    with pytest.raises(FileExistsError):
        ann.export([FakeOrder()], "Z", out_dir=tmp_path)


def test_retrieval_metrics():
    from app.benchmark.retrieval import mrr, ndcg

    assert mrr([0, 0, 2, 1]) == pytest.approx(1 / 3)
    assert mrr([0, 0]) == 0.0
    assert ndcg([2, 1, 0], [2, 1, 0]) == pytest.approx(1.0)  # ideal order
    assert ndcg([0, 1, 2], [2, 1, 0]) < ndcg([2, 1, 0], [2, 1, 0])
    assert ndcg([0, 0], [0, 0]) == 0.0


def test_ocr_error_rates():
    from app.benchmark.ocr import error_rates, levenshtein

    assert levenshtein("kitten", "sitting") == 3
    cer, wer = error_rates("The  complaint is alowed", "The complaint is allowed")
    assert cer == pytest.approx(1 / len("The complaint is allowed"))
    assert wer == pytest.approx(1 / 4)
