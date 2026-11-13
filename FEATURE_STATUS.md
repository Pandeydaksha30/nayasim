# Feature status (12 Nov 2026)

Classes: **Working and verified** (run and checked, date given), **Implemented but untested**
(code exists, not exercised in a recorded check), **Partially implemented**, **Broken**,
**Missing**. Nothing is running at the moment of this audit, so "verified" refers to the dated
check. Update 12 Nov: the journey was re-run end to end and 49 of 49 checks passed
(END_TO_END_TEST_REPORT.md).

## The requested demo journey

| # | Step | Status | Evidence / note |
|---|---|---|---|
| 1 | Open application | Working and verified (10 Nov, browser) | Servers are currently stopped |
| 2 | Register a new user | Working and verified (10 Nov, browser + tests) | No email provider: the verification link is read from `data/outbox/` |
| 3 | Log in | Working and verified (10 Nov, browser + tests) | Session cookie, not JWT |
| 4 | Upload a sample legal document | Working and verified (10 Nov) | PDF and images; limit 100 pages |
| 5 | Document is parsed | Working and verified (10 Nov) | Text layer or Tesseract OCR, per page |
| 6 | Chunks generated for the uploaded document | **Missing** | Only public orders are chunked |
| 7 | Embeddings generated for the uploaded document | **Missing** | Only public order chunks are embedded |
| 8 | Uploaded document stored in a vector database | **Missing** | Pages are stored in Postgres as text; vectors exist for orders only |
| 9 | Ask a question about the uploaded document | **Missing** | No endpoint and no page |
| 10 | RAG retrieves relevant information | Partially implemented | Hybrid retrieval over public orders works (tests + backtests); it is not applied to the user's document. Relevance not yet judged by people. |
| 11 | Source citations displayed | Working and verified (10 Nov) | Facts show document + page; hearing citations are checked against stored text |
| 12 | Run precedent search | Working and verified (13 Nov) | Page `/search` and `GET /api/v1/search/orders`; also runs inside the hearing |
| 13 | Start a hearing simulation | Working and verified (10 Nov, 1 completed run) | Demo cases only; depends on the Gemini free tier (slow, can fail) |
| 14 | Claim-type classification | Working and verified (13 Nov) for pasted order text | `POST /api/v1/predictions/order-text` and the `/search` page (74.3% on test). For a buyer's own case the buyer still picks the claim type. |
| 15 | Outcome prediction | Working and verified (13 Nov) | The report shows a rule-based estimate (`GET /api/v1/cases/{id}/estimate`, 72.9% on test) next to the precedent shares and the judge's finding |
| 16 | Log out and log in again | Working and verified (10 Nov, tests) | |

## Other features

| Feature | Status | Evidence / note |
|---|---|---|
| Backend starts, `/health` | Working and verified (11 Nov) | Stopped now |
| Database connection, migrations to `0008` | Working and verified (12 Nov, queried) | |
| Frontend to backend through the `/api` rewrite | Working and verified (10 Nov) | |
| Email verification, password reset | Working and verified (tests) | Links go to `data/outbox/`; real sending untested (no SMTP) |
| Google sign-in | Working and verified locally (13 Nov) | A real Google account signed in; test-user mode on Google's side |
| Rate limits, lockout, CSRF origin check, case ownership (404 for others) | Working and verified (tests) | No external security test yet |
| Account page (change password, delete account, sign out everywhere) | Working and verified (tests) | |
| Fact extraction from uploaded documents | Working and verified (10 Nov, demo case) | Demo cases only; blocked for real cases by the privacy rule |
| Fact confirmation, follow-up questions | Working and verified (10 Nov) | |
| Interest calculator (page and API) | Working and verified (tests) | Deterministic Python |
| Money and report pages of a case | Working and verified (12 Nov) | END_TO_END_TEST_REPORT.md |
| Complaint draft page | Working and verified (13 Nov) | Built by code from verified facts and verified citations; blanks where something is unknown |
| Citation verifier | Working and verified (benchmark) | Precision 100%, recall 98.3% on held-out orders |
| Order ingestion and OCR | Working and verified | 2,209 orders with text; latest download stopped at about 190 of 1,000 |
| Embedding of order chunks | Partially implemented | 65,974 of 72,970 chunks embedded |
| Classifier training and evaluation scripts | Working and verified (11 Nov) | Offline |
| Prediction API endpoints | Working and verified (13 Nov) | Estimate and classifier demo |
| Production stack (Docker Compose + Caddy, `infra/deploy.sh`) | Implemented but untested on a real server | Images built locally on 9 Nov; never deployed to a public host |
| Public deployment | **Missing** | No server, no public URL |
| Invalid file, empty upload, unsupported format handling | Implemented but untested in this audit | Unit tests cover some cases; to be exercised in Phase 4 |

## Broken

Nothing was found broken by reading the code. This will be confirmed or corrected by actually
running the journey in Phase 4.
