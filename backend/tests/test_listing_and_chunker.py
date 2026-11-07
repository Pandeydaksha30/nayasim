"""Listing parser and chunker tests (no network, no database)."""

from datetime import date

import pytest

from app.ingestion.chunker import MAX_CHARS, chunk_page
from app.ingestion.hrera_listing import ListingFormatError, parse_decision_date, parse_listing

# Shape of the real table; names are placeholders.
LISTING = """
<table><thead><tr><th>Serial No.</th><th>Complaint No.</th><th>Complainant</th><th>Respondent</th>
<th>Type</th><th>Date of Decision</th><th>View</th><th>Uploaded</th></tr></thead><tbody>
<tr><td>1</td><td>RERA-GRG-100-2024</td><td>A &amp; B Buyer</td><td>X Builders Pvt Ltd</td>
<td>HRERA Complaints</td><td><span hidden>20250304</span> 04-Mar-2025</td>
<td><a href="https://haryanarera.gov.in/assistancecontrol/viewOrderPdf/MTIz"><img></a></td><td>06-Mar-2025</td></tr>
<tr><td>2</td><td>RERA-GRG-101-2024</td><td>C Buyer</td><td>Y Ltd</td>
<td>Execution</td><td>01-Feb-2025</td><td>---</td><td>---</td></tr>
</tbody></table>
"""


def test_parse_listing_reads_rows_and_links():
    rows = parse_listing(LISTING)
    assert len(rows) == 2
    first, second = rows
    assert first.complaint_no == "RERA-GRG-100-2024"
    assert first.complainant == "A & B Buyer"
    assert first.decided_on == date(2025, 3, 4)
    assert first.pdf_url == "https://haryanarera.gov.in/assistancecontrol/viewOrderPdf/MTIz"
    assert second.case_type == "Execution"
    assert second.pdf_url is None


def test_listing_without_rows_raises_instead_of_returning_nothing():
    with pytest.raises(ListingFormatError):
        parse_listing("<html><body>Maintenance</body></html>")


def test_bad_date_raises():
    with pytest.raises(ListingFormatError):
        parse_decision_date("soon")


def _para(i: int) -> str:
    return f"Paragraph {i}. The promoter failed to hand over possession by the agreed date. " * 4


@pytest.mark.parametrize(
    "text",
    [
        "Short order text.",
        "\n\n".join(_para(i) for i in range(30)),
        "x" * 5000,  # no break characters at all
        "प्राधिकरण ने आदेश दिया। " * 200,  # Hindi with Devanagari full stops
        "   \n\n   ",
        "",
    ],
)
def test_chunks_are_exact_slices_covering_all_text(text):
    chunks = chunk_page(text)
    for c in chunks:
        assert text[c.char_start : c.char_end] == c.text
        assert c.text == c.text.strip() and c.text
        assert len(c.text) <= MAX_CHARS
    # Nothing but whitespace is left out, and chunks don't overlap.
    covered = "".join(c.text for c in chunks)
    assert covered.replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", "")
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a.char_end <= b.char_start


def test_chunks_prefer_paragraph_breaks():
    text = "\n\n".join(_para(i) for i in range(10))
    chunks = chunk_page(text)
    assert len(chunks) > 1
    assert all(c.text.endswith(".") for c in chunks[:-1])
