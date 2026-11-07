"""Page-by-page text extraction with OCR fallback.

For each page: use the PDF's own text layer when it has real text; otherwise render the
page at 300 dpi and OCR it with Tesseract (English + Hindi). Every page records how its
text was obtained, and OCR pages record the engine and mean word confidence, so weak
pages can be sent for human review instead of being trusted silently.
"""

from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

# A page with fewer real characters than this is treated as a scan (stamps and page
# numbers on scanned pages often leave a few characters in the text layer).
MIN_TEXT_LAYER_CHARS = 80
OCR_DPI = 300
OCR_LANGS = "eng+hin"
# Parallel Tesseract processes per document. Each is limited to one thread (OMP_THREAD_LIMIT)
# so N workers use about N cores instead of oversubscribing the CPU.
OCR_WORKERS = max(1, min(6, (os.cpu_count() or 2) // 2))
os.environ.setdefault("OMP_THREAD_LIMIT", "1")


class OcrUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PageText:
    page_no: int
    text: str
    source: str  # "text_layer" | "ocr"
    ocr_engine: str | None = None
    ocr_confidence: float | None = None  # mean word confidence 0-100


@dataclass(frozen=True)
class OcrConfig:
    tesseract_cmd: str
    tessdata_dir: str | None
    langs: str = OCR_LANGS

    def activate(self) -> None:
        """Point pytesseract at this binary and language folder.

        The folder goes through TESSDATA_PREFIX, not --tessdata-dir: on Windows pytesseract
        splits the config string without removing quotes, so a quoted path reached Tesseract
        with the quote characters in it and no language could be loaded.
        """
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        if self.tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = self.tessdata_dir

    @property
    def engine_name(self) -> str:
        import pytesseract

        self.activate()
        return f"tesseract {pytesseract.get_tesseract_version()} ({self.langs})"


def find_ocr() -> OcrConfig | None:
    """Locate tesseract and language data. NYAYASIM_TESSERACT / NYAYASIM_TESSDATA override."""
    cmd = os.environ.get("NYAYASIM_TESSERACT") or shutil.which("tesseract")
    if not cmd:
        default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        cmd = str(default) if default.exists() else None
    if not cmd:
        return None
    tessdata = os.environ.get("NYAYASIM_TESSDATA")
    if not tessdata:
        local = Path(__file__).resolve().parents[3] / "data" / "tessdata"
        tessdata = str(local) if (local / "hin.traineddata").exists() else None
    return OcrConfig(tesseract_cmd=cmd, tessdata_dir=tessdata)


def _visible_chars(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _normalise(text: str) -> str:
    # pdfium uses \r\n; keep one convention so offsets are stable everywhere.
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def text_from_tsv(data: dict) -> tuple[str, float]:
    """Rebuild page text and mean word confidence from one Tesseract TSV result.

    One OCR pass gives both, instead of running Tesseract twice per page. Words on a line
    are joined by spaces, lines by newlines, and paragraphs/blocks by a blank line.
    """
    lines: list[str] = []
    current: list[str] = []
    key = None
    confs: list[float] = []
    for i, word in enumerate(data["text"]):
        word = str(word).strip()
        if not word:
            continue
        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if key is not None and line_key != key:
            lines.append(" ".join(current))
            if line_key[:2] != key[:2]:
                lines.append("")  # new paragraph or block
            current = []
        key = line_key
        current.append(word)
        conf = float(data["conf"][i])
        if conf >= 0:
            confs.append(conf)
    if current:
        lines.append(" ".join(current))
    mean_conf = round(sum(confs) / len(confs), 2) if confs else 0.0
    return "\n".join(lines).strip(), mean_conf


def _ocr_image(image, ocr: OcrConfig) -> tuple[str, float]:
    import pytesseract

    data = pytesseract.image_to_data(image, lang=ocr.langs, output_type=pytesseract.Output.DICT)
    return text_from_tsv(data)


def extract_pages(pdf_bytes: bytes, ocr: OcrConfig | None, workers: int = OCR_WORKERS) -> list[PageText]:
    """Text for every page. Raises OcrUnavailable if a page needs OCR and none is configured.

    Pages are rendered one at a time (pdfium is not thread-safe); the rendered images are
    OCR'd in parallel threads, each running its own Tesseract process.
    """
    doc = pdfium.PdfDocument(pdf_bytes)
    results: dict[int, PageText] = {}
    to_ocr: list[tuple[int, object]] = []
    try:
        for i in range(len(doc)):
            page = doc[i]
            textpage = page.get_textpage()
            layer = _normalise(textpage.get_text_range())
            textpage.close()
            if _visible_chars(layer) >= MIN_TEXT_LAYER_CHARS:
                results[i + 1] = PageText(page_no=i + 1, text=layer, source="text_layer")
            else:
                if ocr is None:
                    raise OcrUnavailable(f"Page {i + 1} has no text layer and Tesseract is not installed.")
                to_ocr.append((i + 1, page.render(scale=OCR_DPI / 72, grayscale=True).to_pil()))
            page.close()
    finally:
        doc.close()

    if to_ocr:
        engine = ocr.engine_name  # also activates the binary and language folder
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {page_no: pool.submit(_ocr_image, img, ocr) for page_no, img in to_ocr}
            for page_no, fut in futures.items():
                text, conf = fut.result()  # an OCR error propagates; it is never swallowed
                results[page_no] = PageText(page_no, text, "ocr", ocr_engine=engine, ocr_confidence=conf)
    return [results[n] for n in sorted(results)]


def extract_image(image_bytes: bytes, ocr: OcrConfig | None) -> list[PageText]:
    """A photo or scan saved as JPG/PNG: one page, always OCR."""
    import io

    from PIL import Image, ImageOps

    if ocr is None:
        raise OcrUnavailable("The image needs OCR and Tesseract is not installed.")
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes))).convert("L")
    engine = ocr.engine_name
    text, conf = _ocr_image(image, ocr)
    return [PageText(1, text, "ocr", ocr_engine=engine, ocr_confidence=conf)]


def overall_source(pages: list[PageText]) -> str:
    kinds = {p.source for p in pages}
    return kinds.pop() if len(kinds) == 1 else "mixed"
