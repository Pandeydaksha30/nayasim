# Buyer documents, facts and follow-up questions (step 5)

## Flow

1. `POST /api/v1/cases` creates a case (`is_demo: true` only for fictional documents).
2. `POST /api/v1/cases/{id}/documents` (multipart: `file`, `kind`) stores the file under
   `data/uploads/<case id>/` (git-ignored) and the text of every page: PDF text layer, or
   Tesseract OCR (English + Hindi) for scans and photos. File type is checked by content.
   Re-uploading the same file is reported as a duplicate, not stored twice.
3. `POST /api/v1/cases/{id}/facts/extract` asks the model for facts, each with a verbatim
   quote and page, then keeps only facts whose quote is on that stored page and whose
   date/amount is readable from the stored text (names must appear in it). The stored
   quote is the page text itself; a database trigger rejects any fact whose quote differs
   from the page at its offsets.
4. `GET /api/v1/cases/{id}` returns documents, facts (with page and offsets), follow-up
   questions with answers, and the total of verified payments.
5. `GET .../documents/{doc}/pages/{n}` returns a page's text for the highlighted-source view;
   `PUT .../answers/{question_id}` stores an answer (must be one of the options);
   `POST .../facts/{fact_id}/confirm` marks a fact as checked by the buyer.

## Privacy rule

Buyers' documents are private. Extraction is **refused (HTTP 403)** unless the case is a
fictional demo or `NYAYASIM_PRIVATE_LLM_OK=true` is set for a model that does not retain
data. The free Gemini tier may retain data, so leave it `false` until a paid no-retention
option is in place. Upload and OCR run locally and are not affected.

## Follow-up questions

Plain rules in `app/buyer/questions.py`, no model: e.g. ask about an offer of possession only
if none was found, about the extra charge only if a demand was found, for the agreement only
if no promised date was found.

## Demo run (7 Nov 2026, fictional "Mehra v. Arvant Infra")

`python -m scripts.demo_buyer_case`: 3 generated documents (agreement, two receipts, builder
letter) -> 16 facts in 27 s, 0 rejected, all quotes exact: agreement date, price Rs 72,00,000,
promised possession 30 Jun 2021, delay clause, both payments, revised date 31 Dec 2025,
extra charge Rs 1,44,000. Questions asked: offer of possession, payments complete, late
instalments, relief, extra charge paid.

Known gap: a fact present in several documents (builder name in all three) is returned once
per document; the case screen should group them as one fact with several sources.
