# Security

What is in place, how it is checked, and what is not done yet.

## Controls

| Area | Control | Checked by |
|---|---|---|
| Sessions | Server-side sessions, random token, only its hash stored; cookie HttpOnly, SameSite=Lax, Secure in production | `tests/test_auth.py`, e2e `setup` |
| Passwords | Hashed (`app/auth/security.py`), lockout after repeated failures, rate limits on login and sign-up | `tests/test_auth.py` |
| CSRF | State-changing requests must carry an allowed `Origin` | e2e `setup` ("request from another origin is refused") |
| Case ownership | Every case route calls `case_for()`; another user's case answers **404** (ids cannot be probed) | `tests/test_case_rag.py`, `tests/test_agent.py`, e2e `isolation` (9 checks) |
| Document chunks | Separate table from public orders; `case_id` in every query; each returned row re-checked (`CaseLeak`); `search_case()` refuses a non-UUID case id | `tests/test_case_rag.py` |
| Agent runs, questions | Stored per case, deleted with the case (`ON DELETE CASCADE`); readable only through `case_for()` | `tests/test_agent.py` |
| External model | Case text goes to Gemini only for fictional demo cases (`is_demo`) unless `NYAYASIM_PRIVATE_LLM_OK=true`; otherwise 403 | tests + e2e (`ask`, `agent`, `facts`, `hearing` on a private case → 403) |
| Prompt injection | Passages are labelled as data in every prompt; the model has only read-only tools (except saving a hearing of the same case); its citations are checked by code, so injected text cannot add a false citation | design; `verify_cites` tests |
| Uploads | 100-page and size caps, type check, files stored outside the web root | `tests/test_buyer.py` |
| Secrets | `backend/.env` is git-ignored; on Render and Vercel secrets are set in the dashboards; only `.example` templates are committed; API keys stay on the server | `.gitignore`; ZIP check |
| Run limits | Agent: 6 steps, 7 minutes, model-call deadline, one running run per case (unique index) | `tests/test_agent.py` |

## Known gaps (not done)

- No external penetration test or dependency audit.
- No email provider: verification and reset links are written to `data/outbox/`.
- Gemini free tier may retain data; real (non-demo) cases are therefore blocked from the model.
  A zero-retention provider contract is needed before real use.
- A first request after login could previously race the session commit (401); fixed on 13 Nov by
  committing the session before the response. Other writes still commit after the response; no
  failure was observed in the e2e runs, but it is a known pattern to review.
- Backups of the production database are scripted (`infra/export-data.sh`) but not scheduled.

## Reporting

This is a student project; report problems to the project owner directly, not in public issues.
