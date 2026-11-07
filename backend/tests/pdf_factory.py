"""Builds small test PDFs: one with a text layer, one that is only an image (like a scan)."""

from __future__ import annotations

import io

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont


def text_pdf(pages: list[str]) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for body in pages:
        pdf.add_page()
        pdf.multi_cell(0, 6, body)
    return bytes(pdf.output())


def scanned_pdf(*lines: str) -> bytes:
    """One page per line, each a picture of the text with no text layer (like a scan)."""
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except OSError:
        font = ImageFont.load_default(size=64)
    pdf = FPDF()
    for line in lines:
        img = Image.new("L", (1700, 400), 255)
        ImageDraw.Draw(img).text((60, 150), line, fill=0, font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pdf.add_page()
        pdf.image(io.BytesIO(buf.getvalue()), x=10, y=20, w=190)
    return bytes(pdf.output())
