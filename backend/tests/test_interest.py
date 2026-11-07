"""Unit tests for the calculator. Expected figures are worked out by hand in comments."""

from datetime import date
from decimal import Decimal

import pytest

from app.calculator.interest import (
    CalculationError,
    Payment,
    add_months,
    delay_interest,
    refund_with_interest,
)

LAKH = Decimal("100000")
TEN = Decimal("10")


def test_payment_before_due_date_earns_from_due_date():
    # 1,00,000 paid before the due date; 1 Jan 2021 -> 1 Jan 2022 = 365 days at 10% = 10,000.00
    r = delay_interest([Payment(date(2020, 1, 1), LAKH)], date(2021, 1, 1), date(2022, 1, 1), TEN)
    assert r.rows[0].interest_from == date(2021, 1, 1)
    assert r.rows[0].days == 365
    assert r.interest == Decimal("10000.00")


def test_payment_after_due_date_earns_from_payment_date():
    # Paid 1 Jul 2021, after the 1 Jan 2021 due date. 1 Jul 2021 -> 1 Jan 2022 = 184 days.
    # 1,00,000 x 10% x 184/365 = 5,041.0958... -> 5,041.10
    r = delay_interest([Payment(date(2021, 7, 1), LAKH)], date(2021, 1, 1), date(2022, 1, 1), TEN)
    assert r.rows[0].interest_from == date(2021, 7, 1)
    assert r.rows[0].days == 184
    assert r.interest == Decimal("5041.10")


def test_leap_year_counts_366_days_on_365_day_basis():
    # 1 Jan 2024 -> 1 Jan 2025 = 366 days. 1,00,000 x 10% x 366/365 = 10,027.397... -> 10,027.40
    r = delay_interest([Payment(date(2023, 1, 1), LAKH)], date(2024, 1, 1), date(2025, 1, 1), TEN)
    assert r.rows[0].days == 366
    assert r.interest == Decimal("10027.40")


def test_as_of_before_due_date_gives_zero_not_negative():
    r = delay_interest([Payment(date(2020, 1, 1), LAKH)], date(2021, 1, 1), date(2020, 6, 1), TEN)
    assert r.rows[0].days == 0
    assert r.interest == Decimal("0.00")


def test_multiple_payments_total_is_sum_of_rounded_rows():
    payments = [
        Payment(date(2019, 1, 1), Decimal("333333.33")),
        Payment(date(2021, 7, 1), Decimal("250000")),
    ]
    r = delay_interest(payments, date(2021, 1, 1), date(2022, 1, 1), Decimal("10.85"))
    # Row 1: 333333.33 x 10.85% x 365/365 = 36,166.666... -> 36,166.67
    # Row 2: 250000 x 10.85% x 184/365 = 13,673.972... -> 13,673.97
    assert [row.interest for row in r.rows] == [Decimal("36166.67"), Decimal("13673.97")]
    assert r.interest == Decimal("49840.64")
    assert r.principal == Decimal("583333.33")


def test_refund_counts_from_each_payment_date_and_returns_principal():
    # 1 Jan 2020 -> 1 Jan 2022 = 731 days (2020 is a leap year).
    # 1,00,000 x 10% x 731/365 = 20,027.397... -> 20,027.40
    r = refund_with_interest([Payment(date(2020, 1, 1), LAKH)], date(2022, 1, 1), TEN)
    assert r.rows[0].days == 731
    assert r.interest == Decimal("20027.40")
    assert r.total == Decimal("120027.40")


def test_zero_rate_gives_zero_interest():
    r = refund_with_interest([Payment(date(2020, 1, 1), LAKH)], date(2022, 1, 1), Decimal("0"))
    assert r.interest == Decimal("0.00")


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2021, 6, 30), 6, date(2021, 12, 30)),
        (date(2021, 8, 31), 6, date(2022, 2, 28)),
        (date(2023, 8, 31), 6, date(2024, 2, 29)),
        (date(2021, 11, 15), 3, date(2022, 2, 15)),
        (date(2021, 1, 31), 0, date(2021, 1, 31)),
    ],
)
def test_add_months_clamps_to_month_end(start, months, expected):
    assert add_months(start, months) == expected


@pytest.mark.parametrize(
    ("payments", "rate", "message"),
    [
        ([], TEN, "At least one payment"),
        ([Payment(date(2020, 1, 1), Decimal("-5"))], TEN, "positive amount"),
        ([Payment(date(2020, 1, 1), Decimal("0"))], TEN, "positive amount"),
        ([Payment(date(2020, 1, 1), LAKH)], Decimal("-1"), "cannot be negative"),
    ],
)
def test_invalid_inputs_raise(payments, rate, message):
    with pytest.raises(CalculationError, match=message):
        delay_interest(payments, date(2021, 1, 1), date(2022, 1, 1), rate)


def test_negative_extension_rejected():
    with pytest.raises(CalculationError):
        add_months(date(2021, 1, 1), -1)
