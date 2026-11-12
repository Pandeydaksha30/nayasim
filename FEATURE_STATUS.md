# Feature status (12 Nov 2026)

Classes: **Working and verified** (run and checked, date given), **Implemented but untested**
(code exists, not exercised in a recorded check), **Partially implemented**, **Broken**,
**Missing**. Nothing is running at the moment of this audit, so "verified" refers to the dated
check; everything will be re-verified in the end-to-end test (Phase 4).

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
| 12 | Run precedent search | Partially implemented | Runs inside the hearing; no standalone search page or endpoint |
| 13 | Start a hearing simulation | Working and verified (10 Nov, 1 completed run) | Demo cases only; depends on the Gemini free tier (slow, can fail) |
| 14 | Claim-type classification | Partially implemented | The buyer picks the claim type when creating a case. The trained classifier (74.3% on test) is offline only. |
| 15 | Outcome prediction | Partially implemented | The hearing report shows outcome shares from precedents and the judge's finding. Trained classifier and rule are offline only (best 72.9%). |
| 16 | Log out and log in again | Working and verified (10 Nov, tests) | |

## Other features

| Feature | Status | Evidence / note |
|---|---|---|
| Backend starts, `/health` | Working and verified (11 Nov) | Stopped now |
| Database connection, migrations to `0008` | Working and verified (12 Nov, queried) | |
| Frontend to backend through the `/api` rewrite | Working and verified (10 Nov) | |
| Email verification, password reset | Working and verified (tests) | Links go to `data/outbox/`; real sending untested (no SMTP) |
| Google sign-in | Implemented but untested | No Google client configured; covered by unit tests only |
| Rate limits, lockout, CSRF origin check, case ownership (404 for others) | Working and verified (tests) | No external security test yet |
| Account page (change password, delete account, sign out everywhere) | Working and verified (tests) | |
| Fact extraction from uploaded documents | Working and verified (10 Nov, demo case) | Demo cases only; blocked for real cases by the privacy rule |
| Fact confirmation, follow-up questions | Working and verified (10 Nov) | |
| Interest calculator (page and API) | Working and verified (tests) | Deterministic Python |
| Money, report and draft pages of a case | Implemented but untested | Pages exist; not re-checked since the accounts work |
| Citation verifier | Working and verified (benchmark) | Precision 100%, recall 98.3% on held-out orders |
| Order ingestion and OCR | Working and verified | 2,209 orders with text; latest download stopped at about 190 of 1,000 |
| Embedding of order chunks | Partially implemented | 65,974 of 72,970 chunks embedded |
| Classifier training and evaluation scripts | Working and verified (11 Nov) | Offline |
| Prediction API endpoints | **Missing** | |
| Production stack (Docker Compose + Caddy, `infra/deploy.sh`) | Implemented but untested on a real server | Images built locally on 9 Nov; never deployed to a public host |
| Public deployment | **Missing** | No server, no public URL |
| Invalid file, empty upload, unsupported format handling | Implemented but untested in this audit | Unit tests cover some cases; to be exercised in Phase 4 |

## Broken

Nothing was found broken by reading the code. This will be confirmed or corrected by actually
running the journey in Phase 4.
