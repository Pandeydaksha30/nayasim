# Order ingestion (step 4)

Turns the HRERA Gurugram public decisions table into searchable, citable text in the
order store. Outcome/award extraction into `case_records` is a separate step (it needs an
LLM and the 200-record hand check).

## Flow

1. **Register** (`--register`): one request for the public listing; every row with a PDF
   link becomes an `orders` row (unique per source + complaint no. + decision date).
2. **Fetch** (`--fetch N`): pending orders, spread across the table, are downloaded one at
   a time at least 2.5 s apart. Every request goes to `fetch_log` (status, size, SHA-256,
   or the error). A response that is not a PDF is rejected, not stored.
3. **Read pages** (`app/ingestion/pdf_text.py`): each page uses the PDF's text layer if it
   has at least 80 visible characters; otherwise it is rendered at 300 dpi and read by
   Tesseract 5.4 with English + Hindi. OCR pages store the engine and mean word
   confidence; pages under 60 are listed in the run summary for review.
4. **Chunk** (`app/ingestion/chunker.py`): each page is split into ~1,000-character chunks
   at paragraph / sentence (including the Devanagari "।") / word breaks. Every chunk is
   exactly `page_text[char_start:char_end]`, which the database also checks.
5. **Store**: pages, chunks and the order's hash, page count and text source are saved in
   one transaction per order. The PDF is kept at `data/orders/hrera_gurugram/<sha256>.pdf`.

Failures (HTTP errors, non-PDF responses, unreadable PDFs) are printed in the summary and
leave the order pending, so the next run retries it. The script exits with code 1 if any
order failed.

## Pilot result (7 Nov 2026)

Listing registered **13,992** orders with PDFs (18,087 rows; 4,095 without a PDF). A pilot
fetched **30 complaint orders** spread across 2019–2026:

| Measure | Result |
|---|---|
| Orders stored / failed | 30 / 0 |
| Requests logged / errors | 32 / 0 |
| Pages | 580: 427 text layer, 153 OCR (152 in fully scanned orders, 1 in the mixed order) |
| Orders by source | 19 text layer, 10 scanned, 1 mixed |
| OCR confidence | mean 85.6, min 61.7, no page below 60 |
| Chunks | 1,006, mean 925 chars; **0** whose text differs from its page slice |
| Page counts matching stored pages | 30 / 30; all 30 PDFs on disk |
| Speed (parallel OCR, 6 workers) | 19 orders in 3.7 min, **12 s per order** incl. the 2.5 s delay |

At 12 s per order the full 13,992 orders take about **47 hours** on this laptop, so run in
batches (e.g. `--fetch 2000` overnight). Re-runs resume where they stopped. `--fetch` asks
Windows not to idle-sleep while it runs (no power settings change; closing the lid still sleeps).

Findings:

* Gurugram orders are written in **English**; Hindi appears in the letterhead
  ("हरियाणा भू-संपदा विनियामक प्राधिकरण, गुरुग्राम"), which OCR reads correctly. Devanagari is
  under 1% of OCR text.
* **OCR noise**: the logo and stamps produce garbage such as "GHUARRUYGARNAA" or stray
  Devanagari ("/१रि-"). It sits in letterheads, not in the operative text, but extraction
  must not treat it as content. Confidence alone does not flag it (those pages score 82–87).
* Text-layer pages need no OCR and are read in milliseconds.

The first 11 pilot orders were OCR'd by the earlier two-pass method (same engine and
languages); their text differs from the current method only in whitespace layout.

## Setup (once, Windows)

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

Hindi data is not in the installer's default set. Put the official files in `data/tessdata`
(git-ignored; found automatically, or set `NYAYASIM_TESSDATA`):

```powershell
curl.exe -sSL --fail -o data\tessdata\hin.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/hin.traineddata
curl.exe -sSL --fail -o data\tessdata\eng.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata
curl.exe -sSL --fail -o data\tessdata\osd.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/osd.traineddata
```

## Run (from `backend/`)

```powershell
.\.venv\Scripts\python.exe -m scripts.ingest_hrera --register
.\.venv\Scripts\python.exe -m scripts.ingest_hrera --fetch 200
.\.venv\Scripts\python.exe -m scripts.ingest_hrera --fetch 200 --years 2025
```

Re-running is safe: known listing rows and fetched orders are skipped.
