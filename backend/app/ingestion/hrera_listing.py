"""Parser for the HRERA public decisions table (no login, no CAPTCHA).

Gurugram: https://haryanarera.gov.in/admincontrol/judgements/2
Columns: S.No | Complaint No. | Complainant | Respondent | Complaint Type | Date of Decision |
         View Judgement (PDF link) | Judgement Uploading Date
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime

GURUGRAM_LIST_URL = "https://haryanarera.gov.in/admincontrol/judgements/2"

_ROW = re.compile(r"<tr.*?</tr>", re.S | re.I)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_HREF = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)
_TAG = re.compile(r"<[^>]+>")
_DATE = re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})")


@dataclass(frozen=True)
class ListedOrder:
    complaint_no: str
    complainant: str
    respondent: str
    case_type: str
    decided_on: date
    pdf_url: str | None


class ListingFormatError(ValueError):
    """The page no longer looks like the table we know; stop rather than guess."""


def _clean(cell: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", cell))).strip()


def parse_decision_date(raw: str) -> date:
    """'03-Nov-2026' (sometimes preceded by a hidden sort key like '20261103 ')."""
    m = _DATE.search(raw)
    if not m:
        raise ListingFormatError(f"Unrecognised decision date: {raw!r}")
    return datetime.strptime(m.group(1), "%d-%b-%Y").date()


def parse_listing(page_html: str) -> list[ListedOrder]:
    rows: list[ListedOrder] = []
    for tr in _ROW.findall(page_html):
        cells = _CELL.findall(tr)
        if len(cells) < 7:
            continue  # header or layout rows
        links = _HREF.findall(cells[6])
        rows.append(
            ListedOrder(
                complaint_no=_clean(cells[1]),
                complainant=_clean(cells[2]),
                respondent=_clean(cells[3]),
                case_type=_clean(cells[4]),
                decided_on=parse_decision_date(_clean(cells[5])),
                pdf_url=html.unescape(links[0]) if links else None,
            )
        )
    if not rows:
        raise ListingFormatError("No decision rows found; the page layout may have changed.")
    return rows
