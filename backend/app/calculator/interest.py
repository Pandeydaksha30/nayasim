"""Deterministic delay-interest and refund calculator.

All money figures in NyayaSim come from here, never from an LLM.

Method (simple interest, computed payment by payment):

* Delay interest (RERA Act s.18(1) proviso, buyer keeps the unit): each payment earns
  interest from the later of its payment date and the possession due date, up to the
  as-of date.
* Refund (s.18(1)(a)/(b), buyer withdraws): each payment earns interest from its own
  payment date up to the as-of date, and the principal is returned.

The annual rate and any extension of the possession date are *inputs* with a stated
source, not constants: both change over time (e.g. the rate is tied to SBI's MCLR
under the state rules) and must be checked against the rule or order in force.

Money uses Decimal. Each row's interest is rounded to the paisa (half-up); totals are
the sum of rounded rows, so the table always adds up.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")
DAYS_IN_YEAR = Decimal(365)


class CalculationError(ValueError):
    """Raised for inputs that cannot produce a meaningful figure."""


@dataclass(frozen=True)
class Payment:
    paid_on: date
    amount: Decimal
    reference: str = ""


@dataclass(frozen=True)
class InterestRow:
    payment: Payment
    interest_from: date
    days: int
    interest: Decimal


@dataclass(frozen=True)
class InterestResult:
    rows: tuple[InterestRow, ...]
    principal: Decimal
    interest: Decimal

    @property
    def total(self) -> Decimal:
        return self.principal + self.interest


def add_months(d: date, months: int) -> date:
    """Calendar month arithmetic, clamping to the last day of the month.

    31 Aug 2023 + 6 months -> 29 Feb 2024; 30 Jun 2021 + 6 months -> 30 Dec 2021.
    """
    if months < 0:
        raise CalculationError("Extension months cannot be negative.")
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _validate(payments: list[Payment], annual_rate_pct: Decimal) -> None:
    if not payments:
        raise CalculationError("At least one payment is required.")
    if annual_rate_pct < 0:
        raise CalculationError("Interest rate cannot be negative.")
    for p in payments:
        if p.amount <= 0:
            raise CalculationError(f"Payment on {p.paid_on.isoformat()} must be a positive amount.")


def _simple_interest(amount: Decimal, annual_rate_pct: Decimal, days: int) -> Decimal:
    raw = amount * annual_rate_pct * Decimal(days) / (Decimal(100) * DAYS_IN_YEAR)
    return raw.quantize(PAISA, rounding=ROUND_HALF_UP)


def _summarise(rows: list[InterestRow]) -> InterestResult:
    return InterestResult(
        rows=tuple(rows),
        principal=sum((r.payment.amount for r in rows), Decimal(0)),
        interest=sum((r.interest for r in rows), Decimal(0)),
    )


def delay_interest(
    payments: list[Payment], possession_due: date, as_of: date, annual_rate_pct: Decimal
) -> InterestResult:
    """Interest owed for delayed possession, up to ``as_of``."""
    _validate(payments, annual_rate_pct)
    rows = []
    for p in payments:
        start = max(p.paid_on, possession_due)
        days = max(0, (as_of - start).days)
        rows.append(InterestRow(p, start, days, _simple_interest(p.amount, annual_rate_pct, days)))
    return _summarise(rows)


def refund_with_interest(payments: list[Payment], as_of: date, annual_rate_pct: Decimal) -> InterestResult:
    """Refund of every payment plus interest from each payment date, up to ``as_of``."""
    _validate(payments, annual_rate_pct)
    rows = []
    for p in payments:
        days = max(0, (as_of - p.paid_on).days)
        rows.append(InterestRow(p, p.paid_on, days, _simple_interest(p.amount, annual_rate_pct, days)))
    return _summarise(rows)
