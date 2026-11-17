# End-to-end test report (12 Nov 2026)

Run against the local app (website http://localhost:3100, API on 8000 started with `-AllowDemo`,
PostgreSQL 17 + pgvector 0.8 in Docker). All requests went through the website address, so the
`/api` forwarding and the session cookie were exercised. Only fictional documents were used
(`demo/sample-documents/`, the invented "Mehra v. Arvant Infra" case).

Tool: `backend/scripts/e2e_check.py` (commands in RUN_LOCAL.md). Results below are the actual
output of this run; nothing is marked passed without having been run.

**Totals: 49 checks, 49 passed, 0 failed.** Plus 18 pages loaded without error.

## How it was tested, and what was not

- Tested through HTTP exactly as the browser sends it (same routes, cookies, origin header), and
  by loading every page's server-rendered HTML as the logged-in user.
- **Not tested: clicking through the pages in a real browser window in this run** (the screenshot
  tool was unavailable because the app window was hidden). The pages were last clicked through by
  hand on 10 Nov. Do one manual pass before the demo (DEMO_GUIDE.md).
- Not tested: Google sign-in (no Google client configured), real email delivery (no SMTP), any
  public deployment (none exists).

## Results

### Start-up and connectivity

| Check | Result |
|---|---|
| Database up, `vector` extension 0.8.0, migrations at `0008` | PASS |
| Backend `/health` returns `{"status":"ok"}` | PASS |
| Backend `/docs` and `/openapi.json` | PASS (HTTP 200) |
| Website opens | PASS |
| `/health` and `/api/v1/auth/config` through the website (frontend to backend) | PASS |

### Accounts and session

| Check | Result |
|---|---|
| Dashboard without login redirects to `/login` | PASS (307) |
| API without login refused | PASS (401) |
| Sign-up accepted | PASS (202) |
| Login before email verification refused | PASS (403) |
| Verification link written to `data/outbox/` | PASS |
| Email verified with that link | PASS |
| Login | PASS |
| Session cookie is HttpOnly and SameSite=Lax | PASS |
| `GET /auth/me` returns the user | PASS |
| Wrong password refused | PASS (401) |
| Request from another origin refused (CSRF check) | PASS (403) |
| Dashboard with login | PASS |
| Logout | PASS |
| Session refused after logout | PASS (401) |
| Login again, session works, demo case still there | PASS |

### Case, upload and text extraction

| Check | Result |
|---|---|
| Create demo case; appears in the list | PASS |
| Upload `agreement.pdf` (2 pages) | PASS, 0.3 s, text layer, 114 words on page 1 |
| Upload `receipts.pdf` (2 pages) | PASS, 0.1 s, text layer |
| Upload `builder_letter.pdf` (1 page) | PASS, 0.1 s, text layer |
| Upload `receipt_scan.png` (image) | PASS, 1.3 s, read by OCR, confidence 90.9, amount "10,80,000" read correctly |

### Invalid input and unauthorized access

| Check | Result |
|---|---|
| Empty file | PASS: 422 "The file is empty." |
| Unsupported format (.txt) | PASS: 422 "Only PDF, PNG and JPG files can be read." |
| Damaged PDF | PASS: 422 "Could not read the file ...", not a server error |
| Unknown document type | PASS (422) |
| Upload without login | PASS (401) |
| Unknown case id | PASS (404) |

### Privacy rule

| Check | Result |
|---|---|
| Non-demo case: fact extraction by the external model is blocked | PASS: 403 "Real buyer documents are not sent to the configured model because it may retain data ..." |
| Non-demo case: hearing is blocked | PASS: 403 |

Only the fictional demo case was sent to Gemini in this run.

### Fact extraction (Gemini, live)

| Check | Result |
|---|---|
| Extraction on the demo case | PASS, 15 s, 4 documents, 19 facts, no errors |
| Every fact has source document, page and quote | PASS |
| Facts confirmed | PASS (19) |

Examples: agreement date 2018-05-02 (p. 1), promised possession 2021-06-30 (p. 2), total price
Rs. 72,00,000 (p. 1), three payments with dates and amounts, builder's revised date 2025-12-31,
extra charge Rs. 1,44,000. One proposed value was rejected by the quote check, as designed.

### Hearing simulation (Gemini, live)

| Check | Result |
|---|---|
| Hearing accepted as a background job | PASS (202, status "running") |
| Second start while one is running refused | PASS (409) |
| Background job completed | PASS, 9.6 s on the server |
| Result stored and returned by `GET /hearing` | PASS (run id 2) |
| Buyer advocate | 3 arguments, 3 citations, all verified |
| Builder advocate | 2 arguments, 2 citations, all verified |
| Citation gate | 0 arguments removed; 0 judge citations removed |
| Judge | outcome "partly allowed", 3 verified citations, 3 weak points with fixes |
| Precedents retrieved | 12 real HRERA orders (for example RERA-GRG-595-2024, p. 16) |
| Award figure | delay interest Rs. 18,97,388 on Rs. 32,40,000 paid, at 10.9% (median of 3 rates in similar orders) |
| Outcome shares | Reported as "insufficient": only 4 of 12 similar orders have a recorded outcome, 5 needed. Shown as such, not as a prediction. |

Two completed hearing runs are now stored (ids 1 and 2).

### Pages (loaded as the logged-in demo user)

All returned without an error page: `/`, `/dashboard`, `/account`, `/calculator`, `/method`,
`/terms`, `/privacy`, `/cases/new`, and for the demo case `documents`, `facts`, `questions`,
`money`, `hearing`, `report`, `draft`. `/login` and `/signup` redirect to the dashboard when
already logged in; `/cases/<id>` redirects to its first step.

| Page | Content check |
|---|---|
| Facts | Shows extracted values with page references |
| Hearing | Shows the outcome, "verified" marks and complaint numbers |
| Report | Shows amount (Rs. 18.97 lakh), rate basis, weak points |
| Money | Shows the three payments; figures are computed in the browser |
| Draft | 12 Nov: placeholder. 13 Nov: built, see the update below. |

## Not present by design (not failures, not claimed)

- Question-answering over an uploaded document.
- Chunks or embeddings of uploaded documents (only public orders are embedded).
- API endpoints for the trained classifiers (they are command-line scripts).
- A standalone precedent search page (search runs inside the hearing).

## Known weak points seen in this run

- The Gemini free tier answered quickly today; on other days it has returned 429 / 503 and a
  hearing took minutes or failed. A stored hearing is available as a fallback.
- 6,996 of 72,970 order chunks have no embedding yet, so the most recently downloaded orders are
  found by keyword search only.
- The demo documents name an invented Uttar Pradesh project while the precedents are Haryana
  (Gurugram) orders; this is a property of the fictional sample, not of the system.

## Update 13 Nov 2026

Added after the audit, each tested live (`scripts.e2e_check insights`, 16 of 16 checks) and by unit
tests (`backend/tests/test_insights.py`):

| Addition | Where | Notes |
|---|---|---|
| Complaint draft | `GET /api/v1/cases/{id}/draft`, step 7 of a case | Assembled by code from the buyer's facts and from citations verified in the latest hearing. No model call; unknown items are left as bracketed blanks and listed. Download as .txt. |
| Rule-based outcome estimate | `GET /api/v1/cases/{id}/estimate`, shown on the report | Counts how past orders with the same claim type and delay ended; states its measured accuracy (72.9%). |
| Search over past orders | `GET /api/v1/search/orders`, page `/search` | Hybrid keyword + vector search over the public orders, with order, page and passage. |
| Classifier demo | `POST /api/v1/predictions/order-text`, on `/search` | The trained claim-type and outcome models on pasted order text, each answer shown with its measured test accuracy. |
| Google sign-in | configured locally | A real Google sign-in completed on 13 Nov (seen in the API log). |
| Embeddings | `scripts.embed_chunks` | The 6,996 chunks without an embedding are being embedded. |

Still not present: question-answering over an uploaded document, embeddings of uploaded
documents, a public deployment. Accuracy figures are unchanged.

Results of 13 Nov: `insights` stage 16 of 16 passed (estimate: "partly allowed" from 63 past orders
with the same claim type and a delay over 4 years; draft with 3 verified citations from hearing
run 2; search 10 passages in about 5 s, hybrid mode; classifier demo; pages; login required).
`session` stage 6 of 6 passed. Unit tests: all 228 pass. Frontend type-check clean.
One fault found and fixed: the first classifier request after a restart failed while the model
libraries loaded; the models are now preloaded at start-up, and the stage passes right after a
restart. Again not clicked through in a real browser window by the tester.
