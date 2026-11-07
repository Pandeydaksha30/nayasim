# Outcome extraction (step 4b)

Fills `case_records` (claim type, outcome, possession due date, amount paid, award, interest
rate, builder's defences) from fetched orders. The model **proposes**; code **decides**.

## How a field is accepted

1. Gemini (temperature 0, JSON schema) returns each field with a verbatim `quote` and the
   `page_no` it came from (`app/extraction/order_fields.py`).
2. `app/extraction/quotes.py` must find the quote on that page of the stored text, ignoring
   only whitespace and letter case. Paraphrases, "…", or corrected OCR text do not match.
3. Dates, amounts and rates must be readable from the quote by `app/extraction/parsing.py`
   (Indian formats: `Rs. 72,00,000/-`, `57.6 lakh`, `30.06.2021` day-first, `10.85%`).
   A number the model computed or rounded is rejected.
4. Categories must be one of the fixed labels.

Accepted fields are stored with `{page_no, char_start, char_end}` in `field_sources`;
rejected ones are kept under `field_sources._rejected` with the reason. If outcome or claim
type cannot be verified, no record is stored and the order goes to
`data/extraction/needs_review.jsonl` (not retried automatically, to save quota).

## Speed: key pages, two passes

Only key pages are sent (`app/extraction/page_select.py`): the first 3 and last 3 pages, plus
middle pages that mention due date, amounts paid, the prescribed rate, directions or the
decision, within 24,000 characters. Pages keep their real numbers; quotes are verified
against the whole stored order. In the trial, 118 of 164 pages were sent.

Measured on 15 orders from 2018 (free tier, 7 Nov 2026):

| Pass | Model | Time per order | Stored |
|---|---|---|---|
| 1 | `gemini-3.5-flash-lite` (default) | ~5 s | 10 of 15 |
| 2 (`--retry-review`) | `gemini-3.8-flash`, thinking low | ~90 s (+ 503 "high demand" retries) | 2 of the 5 |
| — | left for a human | — | 3 (no decision stated / quote across a page break) |

`gemini-3.8-flash` alone took 110–207 s per order even with fewer pages and low thinking:
the time is the model, not the input. `gemini-2.5-flash` is listed but returns 404 for new
accounts.

The outcome vocabulary includes **`disposed_of`** (migration 0002): many orders close
"the complaint is disposed of" with directions or a referral (e.g. NCLT moratorium),
without allowing or dismissing it.

## Setup

`backend/.env` (git-ignored) must contain `GEMINI_API_KEY=...`. Then, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.extract_fields --check-key
.\.venv\Scripts\python.exe -m scripts.extract_fields --limit 500
.\.venv\Scripts\python.exe -m scripts.extract_fields --retry-review --limit 100 --model gemini-3.8-flash --thinking low
.\.venv\Scripts\python.exe -m scripts.export_review --sample 200
```

The review sheet (`data/review/review_<date>.csv`) lists every stored field with the exact
quoted text and the PDF path; fill `correct (Y/N)` to measure accuracy.

Public orders only: the free Gemini tier may use submitted data, which is acceptable for
public regulator orders but **not** for buyers' private documents (step 5 needs a paid,
no-retention option).
