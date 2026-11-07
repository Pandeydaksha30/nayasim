"""Deterministic readers for money, rates and dates as Indian orders write them.

Used to *verify* model output: a value is accepted only if it can be read from the
quoted text by this code. They return every candidate in the text, not a guess at one.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_NUM = r"\d[\d,]*(?:\.\d+)?"
_CURRENCY = r"(?:rs\.?|inr|₹|rupees)"

# "Rs. 72,00,000/-", "₹ 57,60,000", "INR 5760000", "Rs 57.6 lakh", "Rs. 1.25 crores"
_AMOUNT = re.compile(
    rf"{_CURRENCY}\s*({_NUM})\s*(?:/-)?\s*(lakhs?|lacs?|crores?)?|({_NUM})\s*(lakhs?|lacs?|crores?)",
    re.I,
)
# "10.85%", "10.85 % per annum", "@10.85% p.a."
_RATE = re.compile(rf"({_NUM})\s*%", re.I)

_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
_MON = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_NUMERIC = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
_DATE_DMY_WORDS = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON})[a-z]*\.?,?\s+(\d{{4}})\b", re.I
)
_DATE_MDY_WORDS = re.compile(rf"\b({_MON})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I)

_SCALE = {"lakh": Decimal(100_000), "lac": Decimal(100_000), "crore": Decimal(10_000_000)}


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def amounts_in(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for m in _AMOUNT.finditer(text):
        raw, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        value = _to_decimal(raw)
        if value is None:
            continue
        if unit:
            key = next(k for k in _SCALE if unit.lower().startswith(k))
            value *= _SCALE[key]
        out.append(value.quantize(Decimal("0.01")))
    return out


def rates_in(text: str) -> list[Decimal]:
    out = []
    for m in _RATE.finditer(text):
        value = _to_decimal(m.group(1))
        if value is not None and Decimal(0) <= value <= Decimal(50):
            out.append(value)
    return out


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def dates_in(text: str) -> list[date]:
    """All dates in the text. Numeric dates are read day-first (Indian convention)."""
    found: list[date] = []
    for d, m, y in _DATE_NUMERIC.findall(text):
        if (v := _safe_date(int(y), int(m), int(d))) is not None:
            found.append(v)
    # The month group captures exactly one key of _MONTHS (full name or abbreviation).
    for d, mon, y in _DATE_DMY_WORDS.findall(text):
        if (v := _safe_date(int(y), _MONTHS[mon.lower()], int(d))) is not None:
            found.append(v)
    for mon, d, y in _DATE_MDY_WORDS.findall(text):
        if (v := _safe_date(int(y), _MONTHS[mon.lower()], int(d))) is not None:
            found.append(v)
    return found
