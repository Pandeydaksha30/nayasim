"""The parties' part of an order, cut before the authority's own reasoning (backtest --input facts)."""

from __future__ import annotations

from app.backtest.facts import MIN_CHARS, split_facts

FACTS = "B. Facts of the complaint\n" + ("The complainant booked a unit and paid the instalments. " * 40)
REPLY = "D. Reply by the respondent\nThe respondent contends that the delay was due to force majeure.\n"


def test_cut_at_line_heading():
    text = (
        FACTS + REPLY + "E. Jurisdiction of the authority\nThe authority observes that it has jurisdiction."
    )
    sp = split_facts(text)
    assert sp is not None and sp.text.endswith("force majeure.")
    assert "observes" not in sp.text


def test_cut_at_ocr_damaged_heading_and_authority_voice():
    # "furisdiction" (OCR) and the authority's own words with no heading at all.
    for tail in (
        "F. furisdiction ofthe authority 34. The authority observed that it has territorial jurisdiction.",
        "Arguments heard at length. On consideration of the circumstances, the complaint succeeds.",
        "the authority is of the view that complainant cannot be refunded the amount at this point.",
    ):
        sp = split_facts(FACTS + REPLY + tail)
        assert sp is not None, tail
        assert "authority" not in sp.text.split("force majeure.")[-1]
        assert "refunded" not in sp.text and "succeeds" not in sp.text


def test_inline_heading_in_older_orders():
    text = (
        FACTS + "Findings and directions of the authority 22. Jurisdiction of the authority- The project is"
    )
    sp = split_facts(text)
    assert sp is not None and "Findings" not in sp.text


def test_no_boundary_or_too_short_or_decision_wording_is_refused():
    assert split_facts(FACTS + REPLY) is None  # no authority part found: cannot know where it starts
    assert split_facts("Short facts.\nE. Jurisdiction of the authority\n...") is None
    assert len("Short facts.") < MIN_CHARS
    leaked = FACTS + "Hence the complaint is allowed. " + REPLY + "E. Jurisdiction of the authority\n"
    assert split_facts(leaked) is None


def test_long_parties_part_keeps_start_and_end():
    text = "A. Unit details\n" + ("x " * 20000) + REPLY + "E. Jurisdiction of the authority\n"
    sp = split_facts(text)
    assert sp is not None and sp.truncated
    assert sp.text.startswith("A. Unit details") and sp.text.endswith("force majeure.")
    assert "omitted for length" in sp.text
