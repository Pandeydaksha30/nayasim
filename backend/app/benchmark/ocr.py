"""OCR evaluation: character and word error rate against hand-typed pages.

1. `export`: sample OCR'd pages from benchmark orders; each page is rendered to a PNG next to an
   empty .txt file. A person types exactly what the page says into the .txt (Hindi as Hindi).
2. `score`: CER and WER of the stored OCR text against each transcription (Levenshtein distance
   divided by the length of the transcription), overall and per page. Whitespace is normalised.
"""

from __future__ import annotations

import random
from pathlib import Path

import pypdfium2 as pdfium
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderPage

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data" / "annotation" / "ocr"
ORDERS_DIR = ROOT / "data" / "orders" / "hrera_gurugram"


def export(s: Session, order_ids: list[int], n: int, seed: int, out_dir: Path = DIR) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = s.execute(
        select(OrderPage.order_id, OrderPage.page_no)
        .where(OrderPage.order_id.in_(order_ids), OrderPage.text_source == "ocr")
        .order_by(OrderPage.order_id, OrderPage.page_no)
    ).all()
    random.Random(seed).shuffle(pages)
    made = 0
    for order_id, page_no in pages[:n]:
        o = s.get(Order, order_id)
        stem = out_dir / f"{o.complaint_no}_p{page_no}"
        if stem.with_suffix(".txt").exists():
            continue  # never overwrite a transcription
        doc = pdfium.PdfDocument(str(ORDERS_DIR / f"{o.pdf_sha256}.pdf"))
        try:
            doc[page_no - 1].render(scale=2).to_pil().save(stem.with_suffix(".png"))
        finally:
            doc.close()
        stem.with_suffix(".txt").write_text("", encoding="utf-8")
        made += 1
    return made


def levenshtein(a: list | str, b: list | str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def _norm(t: str) -> str:
    return " ".join(t.split())


def error_rates(ocr_text: str, truth: str) -> tuple[float, float]:
    o, t = _norm(ocr_text), _norm(truth)
    cer = levenshtein(o, t) / max(1, len(t))
    wer = levenshtein(o.split(), t.split()) / max(1, len(t.split()))
    return cer, wer


def score(s: Session, out_dir: Path = DIR) -> dict:
    per_page = []
    char_err = char_len = word_err = word_len = 0
    for txt in sorted(out_dir.glob("*.txt")):
        truth = txt.read_text(encoding="utf-8")
        if not truth.strip():
            continue
        complaint, page = txt.stem.rsplit("_p", 1)
        o = s.scalar(select(Order).where(Order.complaint_no == complaint))
        stored = s.get(OrderPage, (o.id, int(page))) if o else None
        if stored is None:
            continue
        o_n, t_n = _norm(stored.text), _norm(truth)
        ce, we = levenshtein(o_n, t_n), levenshtein(o_n.split(), t_n.split())
        char_err, char_len = char_err + ce, char_len + len(t_n)
        word_err, word_len = word_err + we, word_len + len(t_n.split())
        per_page.append(
            {
                "page": txt.stem,
                "cer": round(ce / max(1, len(t_n)), 4),
                "wer": round(we / max(1, len(t_n.split())), 4),
                "tesseract_confidence": float(stored.ocr_confidence) if stored.ocr_confidence else None,
            }
        )
    return {
        "pages": len(per_page),
        "cer": round(char_err / char_len, 4) if char_len else None,
        "wer": round(word_err / word_len, 4) if word_len else None,
        "per_page": per_page,
    }
