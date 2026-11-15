"""The uploaded page as the buyer filed it: a picture of the page, and where a quote sits on it.

The Facts screen shows this next to the extracted text, so a fact can be compared with the real
document, not only with what the reader produced.

- `render_page` draws one page of the stored file as a PNG (PDF pages through pdfium; an uploaded
  photo is re-encoded, which also drops its metadata).
- `quote_rects` returns rectangles (fractions of the page, origin top-left) covering the characters
  [char_start, char_end) of the stored page text. It works only where the mapping is certain: a
  PDF page whose text layer, rebuilt character by character, equals the stored text. For OCR pages
  and photos it returns None and the screen shows the page without a highlight; a wrong highlight
  would be worse than none.
"""

from __future__ import annotations

import io
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

MAX_WIDTH_PX = 1400
MAX_QUOTE_CHARS = 4000


class PageNotAvailable(LookupError):
    """The stored file is missing or has no such page."""


def _png(image) -> bytes:
    if image.width > MAX_WIDTH_PX:
        image = image.resize((MAX_WIDTH_PX, round(image.height * MAX_WIDTH_PX / image.width)))
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_page(path: Path, page_no: int) -> bytes:
    if not path.is_file():
        raise PageNotAvailable("The uploaded file is no longer stored.")
    if path.suffix.lower() != ".pdf":
        from PIL import Image, ImageOps

        if page_no != 1:
            raise PageNotAvailable("An image has one page.")
        with Image.open(path) as im:
            return _png(ImageOps.exif_transpose(im).convert("RGB"))
    doc = pdfium.PdfDocument(str(path))
    try:
        if not 1 <= page_no <= len(doc):
            raise PageNotAvailable(f"Page {page_no} does not exist.")
        page = doc[page_no - 1]
        width_pt = page.get_width() or 595
        image = page.render(scale=min(2.0, MAX_WIDTH_PX / width_pt)).to_pil().convert("RGB")
        page.close()
        return _png(image)
    finally:
        doc.close()


def normalised_with_map(raw: str) -> tuple[str, list[int]]:
    """Apply app.ingestion.pdf_text._normalise and remember, for every kept character, its index
    in the raw text (which is pdfium's character index)."""
    chars: list[str] = []
    idx: list[int] = []
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\r":
            chars.append("\n")
            idx.append(i)
            i += 2 if i + 1 < n and raw[i + 1] == "\n" else 1
            continue
        chars.append(ch)
        idx.append(i)
        i += 1
    text = "".join(chars)
    lead = len(text) - len(text.lstrip())
    end = len(text.rstrip())
    return text[lead:end], idx[lead:end]


def quote_rects(
    path: Path, page_no: int, stored_text: str, char_start: int, char_end: int
) -> list[dict] | None:
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return None
    if not (0 <= char_start < char_end <= len(stored_text)) or char_end - char_start > MAX_QUOTE_CHARS:
        return None
    lines: list[list[float]] = []  # [left, bottom, right, top] per visual line
    doc = pdfium.PdfDocument(str(path))
    try:
        if not 1 <= page_no <= len(doc):
            return None
        page = doc[page_no - 1]
        try:
            if page.get_rotation() != 0:
                return None
            width, height = page.get_size()
            tp = page.get_textpage()
            try:
                n = tp.count_chars()
                raw = "".join(chr(pdfium_c.FPDFText_GetUnicode(tp, i)) for i in range(n))
                text, index = normalised_with_map(raw)
                if text != stored_text:
                    return None  # not the text the fact was checked against: no highlight
                for pos in range(char_start, char_end):
                    if stored_text[pos].isspace():
                        continue
                    left, bottom, right, top = tp.get_charbox(index[pos])
                    if right <= left or top <= bottom:
                        continue
                    last = lines[-1] if lines else None
                    mid = (bottom + top) / 2
                    if last and last[1] <= mid <= last[3] and left >= last[0] - 1:
                        last[2] = max(last[2], right)
                        last[1], last[3] = min(last[1], bottom), max(last[3], top)
                    else:
                        lines.append([left, bottom, right, top])
            finally:
                tp.close()
        finally:
            page.close()
    finally:
        doc.close()
    if not lines or width <= 0 or height <= 0:
        return None
    return [
        {
            "x": round(max(0.0, left / width), 5),
            "y": round(max(0.0, 1 - top / height), 5),
            "w": round(min(1.0, (right - left) / width), 5),
            "h": round(min(1.0, (top - bottom) / height), 5),
        }
        for left, bottom, right, top in lines
    ]
