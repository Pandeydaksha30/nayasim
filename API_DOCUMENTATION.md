# API documentation

Generated from the FastAPI app (`app.openapi()`), 17 Nov 2026. Interactive version with
request and response schemas: http://localhost:8000/docs while the backend runs locally (switched off under HTTPS).

Authentication: session cookie `nyayasim_session` set by `POST /api/v1/auth/login` (HttpOnly, SameSite=Lax; the
internal name is kept from the earlier build so existing sessions stay valid).
State-changing requests must come from an allowed Origin (CSRF check). Someone else's case answers 404.

## auth

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/auth/config` | What the sign-in page should offer. |
| POST | `/api/v1/auth/signup` | Signup |
| POST | `/api/v1/auth/verify-email` | Verify Email |
| POST | `/api/v1/auth/resend-verification` | Resend Verification |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/logout` | Logout |
| POST | `/api/v1/auth/logout-all` | Logout All |
| POST | `/api/v1/auth/forgot-password` | Forgot Password |
| POST | `/api/v1/auth/reset-password` | Reset Password |
| GET | `/api/v1/auth/me` | Me |
| PATCH | `/api/v1/auth/me` | Update Me |
| DELETE | `/api/v1/auth/me` | Delete Me |
| POST | `/api/v1/auth/change-password` | Change Password |
| GET | `/api/v1/auth/google/start` | Google Start |
| GET | `/api/v1/auth/google/callback` | Google Callback |

## calculations

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/calculations/interest` | Calculate Interest |

## cases

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/cases` | List Cases |
| POST | `/api/v1/cases` | Create Case |
| GET | `/api/v1/cases/{case_id}` | Get Case |
| DELETE | `/api/v1/cases/{case_id}` | Delete a case with everything derived from it: documents and their files, page text, search |
| POST | `/api/v1/cases/{case_id}/documents` | Upload Document |
| GET | `/api/v1/cases/{case_id}/documents/{document_id}/pages/{page_no}` | Get Page |
| POST | `/api/v1/cases/{case_id}/facts/extract` | Extract Facts |
| POST | `/api/v1/cases/{case_id}/facts/{fact_id}/confirm` | Confirm Fact |
| PUT | `/api/v1/cases/{case_id}/answers/{question_id}` | Answer Question |
| DELETE | `/api/v1/cases/{case_id}/documents/{document_id}` | Delete one document with its file, page text, search chunks and the facts read from it. |
| GET | `/api/v1/cases/{case_id}/documents/{document_id}/pages/{page_no}/image` | A picture (PNG) of the uploaded page, for comparing a fact with the real document. |
| GET | `/api/v1/cases/{case_id}/documents/{document_id}/pages/{page_no}/highlight` | Where the characters [start, end) of the stored page text sit on the page picture, as |

## hearing

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/cases/{case_id}/hearing` | Checks run now (privacy, facts, precedents) so problems are reported at once; the model calls |
| GET | `/api/v1/cases/{case_id}/hearing` | Latest Hearing |
| GET | `/api/v1/cases/{case_id}/hearing/runs/{run_id}` | Get Run |
| GET | `/api/v1/cases/{case_id}/hearing/active` | The hearing currently running for this case, if any (so a reloaded page keeps waiting). |

## insights

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/search/orders` | Hybrid (keyword + vector) search over the stored public HRERA Gurugram orders. |
| GET | `/api/v1/cases/{case_id}/estimate` | Rule-based outcome estimate from how past orders with the same claim type and delay ended. |
| GET | `/api/v1/cases/{case_id}/draft` | Complaint draft assembled by code from verified facts and checked citations. |
| POST | `/api/v1/predictions/order-text` | The trained classifiers applied to the parties' part of an order (facts, relief sought, reply). |
| GET | `/api/v1/stats` | What the order store holds right now, counted from the database (cached for ten minutes). |

## document questions

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/cases/{case_id}/passages` | Passages of this case's documents that match the words. No model is called. |
| POST | `/api/v1/cases/{case_id}/ask` | An answer grounded in this case's documents, with citations checked by code. |
| GET | `/api/v1/cases/{case_id}/questions` | Questions |
| POST | `/api/v1/cases/{case_id}/clauses` | Rights, obligations and penalties of each party, each quoted and checked against the document. |
| GET | `/api/v1/cases/{case_id}/clauses` | Latest Clauses |

## agent

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/cases/{case_id}/agent` | Start Agent |
| GET | `/api/v1/cases/{case_id}/agent/runs/{run_id}` | Get Agent Run |
| GET | `/api/v1/cases/{case_id}/agent/runs` | List Agent Runs |

## other

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health |
