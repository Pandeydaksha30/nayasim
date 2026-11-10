"""Trained text classifier: delay bands and that the training loop separates clear classes."""

from __future__ import annotations

from datetime import date

from app.ml.text_classifier import Item, _delay_band, train_and_evaluate


def test_delay_bands():
    assert _delay_band(None, date(2025, 1, 1)) == "delay_unknown"
    assert _delay_band(date(2024, 1, 1), date(2025, 1, 1)) == "delay_lt2y"
    assert _delay_band(date(2021, 1, 1), date(2025, 1, 1)) == "delay_2to4y"
    assert _delay_band(date(2019, 1, 1), date(2025, 1, 1)) == "delay_gt4y"


def test_training_uses_splits_and_learns_a_separable_task():
    def item(i, split, claim):
        words = "refund withdraw return amount" if claim == "refund" else "possession delay interest month"
        return Item(
            i, split, f"{words} {words} unit allottee __claim_{claim} __delay_unknown", "allowed", claim
        )

    items = [
        item(i, sp, c)
        for i, (sp, c) in enumerate(
            [
                (sp, c)
                for sp in ("train",) * 6 + ("validation",) * 3 + ("test",) * 3
                for c in ("refund", "delayed_possession")
            ]
        )
    ]
    rep = train_and_evaluate(items, "claim_type")
    assert rep["counts"] == {"train": 12, "validation": 6, "test": 6}
    assert rep["test"]["accuracy"] == 1.0  # the claim token is removed for this task; words alone suffice
