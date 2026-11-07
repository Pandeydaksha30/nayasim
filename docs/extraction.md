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

## Setup

`backend/.env` (git-ignored) must contain `GEMINI_API_KEY=...`. Then, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m scripts.extract_fields --check-key
.\.venv\Scripts\python.exe -m scripts.extract_fields --limit 10
.\.venv\Scripts\python.exe -m scripts.export_review --sample 200
```

The review sheet (`data/review/review_<date>.csv`) lists every stored field with the exact
quoted text and the PDF path; fill `correct (Y/N)` to measure accuracy.

Public orders only: the free Gemini tier may use submitted data, which is acceptable for
public regulator orders but **not** for buyers' private documents (step 5 needs a paid,
no-retention option).
