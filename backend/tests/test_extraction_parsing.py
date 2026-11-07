"""Parsers and quote locator used to verify model output."""

from datetime import date
from decimal import Decimal

import pytest

from app.extraction.parsing import amounts_in, dates_in, rates_in
from app.extraction.quotes import locate


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("paid a sum of Rs. 72,00,000/- to the respondent", Decimal("7200000.00")),
        ("an amount of ₹ 57,60,000 has been paid", Decimal("5760000.00")),
        ("INR 5760000 was received", Decimal("5760000.00")),
        ("total Rs 57.6 lakh", Decimal("5760000.00")),
        ("a sum of Rs. 1.25 crores", Decimal("12500000.00")),
        ("Rupees 4,50,000.50 only", Decimal("450000.50")),
        ("paid 48 lakhs towards the unit", Decimal("4800000.00")),
    ],
)
def test_amounts(text, expected):
    assert expected in amounts_in(text)


def test_plain_numbers_are_not_amounts():
    assert amounts_in("Section 18 of the Act, para 14, 2019") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("interest at the prescribed rate i.e. 10.85% per annum", Decimal("10.85")),
        ("@ 9.30 % p.a.", Decimal("9.30")),
        ("MCLR + 2% i.e. 11.10%", Decimal("11.10")),
    ],
)
def test_rates(text, expected):
    assert expected in rates_in(text)


def test_rate_out_of_range_ignored():
    assert rates_in("100% of the amount") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("due date of possession is 30.06.2021", date(2021, 6, 30)),
        ("on or before 30-06-2021", date(2021, 6, 30)),
        ("by 30/06/2021", date(2021, 6, 30)),
        ("by 30th June 2021", date(2021, 6, 30)),
        ("on 2nd of May, 2018", date(2018, 5, 2)),
        ("June 30, 2021", date(2021, 6, 30)),
        ("Sept. 5 2019", date(2019, 9, 5)),
        ("05.09.2019", date(2019, 9, 5)),  # day first, Indian convention
    ],
)
def test_dates(text, expected):
    assert expected in dates_in(text)


def test_impossible_date_ignored():
    assert dates_in("31.02.2021") == []


PAGE = (
    "The respondent is directed to pay\ninterest  at the prescribed rate\nof 10.85% p.a. on the amount paid."
)


def test_locate_ignores_whitespace_and_case_and_returns_exact_offsets():
    span = locate("INTEREST AT THE PRESCRIBED RATE of 10.85% p.a.", PAGE)
    assert span is not None
    original = PAGE[span.char_start : span.char_end]
    assert original.startswith("interest") and original.endswith("p.a.")
    assert " ".join(original.split()).lower() == "interest at the prescribed rate of 10.85% p.a."


def test_exact_match_is_marked_exact():
    assert locate("interest at the prescribed rate", PAGE).match == "exact"


@pytest.mark.parametrize(
    "quote",
    [
        "the promoter shall pay interest",  # paraphrase
        "Interest is payable by the builder at MCLR plus two percent.",  # different sentence
        "pay ... interest",  # ellipsis, too short for a near match
        "10.8% p.a.",  # short and not exact: no near match allowed
        "rate",  # too short to be meaningful
        "",
    ],
)
def test_locate_rejects_paraphrase_and_short_inexact_quotes(quote):
    assert locate(quote, PAGE) is None


# Real case (order RERA-GRG-76-2018): the PDF's own text layer has OCR typos, and the model
# quietly fixed "alreacly" to "already".
OCR_PAGE = (
    "As alreacly decided in complaint no. 141 of 2018\ntitled as Brihmjeet versus ll/s. Lanclmark "
    "Apartments Pvt.\nLtii, no case is made out. Learned counsel for the"
)


def test_near_match_tolerates_a_corrected_ocr_typo_and_points_at_stored_text():
    quote = (
        "As already decided in complaint no. 141 of 2018 titled as Brihmjeet versus ll/s. "
        "Lanclmark Apartments Pvt. Ltii, no case is made out."
    )
    span = locate(quote, OCR_PAGE)
    assert span is not None and span.match.startswith("fuzzy:")
    stored = OCR_PAGE[span.char_start : span.char_end]
    assert "alreacly" in stored and stored.rstrip(".").endswith("made out")


def test_near_match_still_points_at_the_stored_number():
    # One digit changed in a long quote still aligns, but the span holds the stored 10.85%.
    span = locate("interest at the prescribed rate of 10.8% p.a. on the amount paid", PAGE)
    assert span is not None and "10.85%" in PAGE[span.char_start : span.char_end]
