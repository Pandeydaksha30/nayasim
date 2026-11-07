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


@pytest.mark.parametrize(
    "quote",
    [
        "interest at the prescribed rate of 10.8% p.a.",  # altered number
        "the promoter shall pay interest",  # paraphrase
        "pay ... interest",  # ellipsis
        "rate",  # too short to be meaningful
        "",
    ],
)
def test_locate_rejects_anything_not_verbatim(quote):
    assert locate(quote, PAGE) is None
