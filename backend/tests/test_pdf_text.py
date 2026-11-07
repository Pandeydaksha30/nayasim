"""Text extraction tests. OCR tests need Tesseract; without it they are skipped with a
printed reason, or fail when NYAYASIM_REQUIRE_OCR=1."""

import os

import pytest

from app.ingestion.pdf_text import OcrUnavailable, extract_pages, find_ocr, overall_source, text_from_tsv
from tests.pdf_factory import scanned_pdf, text_pdf

ORDER_TEXT = (
    "ORDER. The respondent promoter is directed to pay interest at the prescribed rate on the amount "
    "paid by the complainant from the due date of possession till the valid offer of possession."
)


def require_ocr():
    ocr = find_ocr()
    if ocr is None:
        msg = "Tesseract not installed (see README: OCR)"
        if os.environ.get("NYAYASIM_REQUIRE_OCR") == "1":
            pytest.fail(msg)
        pytest.skip(msg)
    return ocr


def test_text_layer_pages_are_read_without_ocr():
    pages = extract_pages(text_pdf([ORDER_TEXT, ORDER_TEXT + " Second page."]), ocr=None)
    assert [p.page_no for p in pages] == [1, 2]
    assert all(p.source == "text_layer" for p in pages)
    assert "prescribed rate" in pages[0].text
    assert "\r" not in pages[0].text
    assert overall_source(pages) == "text_layer"


def test_scanned_page_without_ocr_raises_instead_of_storing_empty_text():
    with pytest.raises(OcrUnavailable, match="Page 1"):
        extract_pages(scanned_pdf("Interest at prescribed rate"), ocr=None)


def test_scanned_page_is_read_by_ocr_with_confidence():
    ocr = require_ocr()
    pages = extract_pages(scanned_pdf("Interest at prescribed rate"), ocr=ocr)
    assert pages[0].source == "ocr"
    assert pages[0].ocr_engine and "tesseract" in pages[0].ocr_engine
    assert "prescribed" in pages[0].text.lower()
    assert pages[0].ocr_confidence is not None and pages[0].ocr_confidence > 50


def test_parallel_ocr_keeps_page_order():
    ocr = require_ocr()
    words = ["Complaint", "Possession", "Interest", "Refund"]
    pages = extract_pages(scanned_pdf(*words), ocr=ocr, workers=4)
    assert [p.page_no for p in pages] == [1, 2, 3, 4]
    for word, page in zip(words, pages, strict=True):
        assert word.lower() in page.text.lower()


def test_text_from_tsv_rebuilds_lines_and_paragraphs():
    data = {
        "text": ["", "Interest", "at", "MCLR", "", "plus", "two", "Order"],
        "conf": [-1, 90, 80, 70, -1, 60, 50, 95],
        "block_num": [1, 1, 1, 1, 1, 1, 1, 2],
        "par_num": [1, 1, 1, 1, 1, 1, 1, 1],
        "line_num": [0, 1, 1, 1, 1, 2, 2, 1],
    }
    text, conf = text_from_tsv(data)
    assert text == "Interest at MCLR\nplus two\n\nOrder"
    assert conf == round((90 + 80 + 70 + 60 + 50 + 95) / 6, 2)


def test_text_from_tsv_of_blank_page():
    assert text_from_tsv(
        {"text": ["", " "], "conf": [-1, -1], "block_num": [0, 0], "par_num": [0, 0], "line_num": [0, 0]}
    ) == ("", 0.0)


def test_hindi_language_data_is_installed():
    import pytesseract

    ocr = require_ocr()
    ocr.activate()
    assert "hin" in ocr.langs
    assert "hin" in pytesseract.get_languages()
