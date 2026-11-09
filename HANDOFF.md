# NyayaSim: handoff for a new chat

Written 2026-11-09. Paste this whole file into a new Claude Code chat (opened in
`C:\Users\pande\Downloads\CONTRACT_IQ\contractiq`) and say which pending task to do. Everything the
new chat needs is here; it should not have to re-discover anything.

---

## 1. What NyayaSim is

A grounded RERA dispute simulator for Indian home buyers. A buyer uploads their papers; the app reads
facts (each tied to a quote on a page), asks follow-up questions, works out delay interest with
deterministic Python, finds similar past regulator orders, runs a simulated hearing (buyer's advocate,
builder's advocate, bench) where every citation is checked against the stored order, and writes a
decision report. v1 data source: **HRERA Gurugram** public orders (UP RERA is behind a CAPTCHA, phase 2).

Original plan PDF: `C:\Users\pande\Downloads\Tab 1.pdf`.
Built on top of the user's older ContractIQ repo (kept under `legacy/`).

## 2. The user's rules (must follow)

1. Work incrementally, one feature at a time.
2. Never fabricate legal orders, citations, facts or case outcomes.
3. All money calculations in deterministic Python, never LLM arithmetic.
4. Every extracted fact keeps its document source and page reference.
5. Every legal citation must be verifiable against the stored order.
6. Write unit tests for critical components.
7. Explain the purpose of every file created or modified.
8. Give exact terminal commands to run and test each feature.
9. Never silently skip errors.
10. Do not claim a feature works until it has actually been tested.

Also:
- The website must look designer-built, not "vibe coded". Research real legal/enterprise sites before
  frontend work. Current style: light enterprise SaaS (slate / indigo / emerald, white cards), plain CSS
  tokens in `frontend/app/globals.css`, no Tailwind.
- **Privacy:** real buyers' documents must never go to the free Gemini tier. Only cases marked
  `is_demo` may. The switch `NYAYASIM_PRIVATE_LLM_OK` stays `false` until a zero-retention model is set up.
- **Secrets:** the Gemini key lives only in `backend\.env` (git-ignored). Never print it, never commit
  `.env` or `data/`. The key was pasted in chat twice: it should be rotated.
- Never accept terms/agreements for the user. Git identity: `pandeydaksha30` / `pandeydaksha30@gmail.com`.
- Commit messages end with a `Co-Authored-By: Claude ...` line.

## 3. Where everything is on this PC

| What | Exact location |
|---|---|
| Project (git repo) | `C:\Users\pande\Downloads\CONTRACT_IQ\contractiq` |
| Branch | `nyayasim/foundation` (other branches: `main`, `cleanup/remove-false-claims`). **Never pushed; no remote.** |
| Backend (FastAPI, Python 3.12, uv) | `contractiq\backend` (venv: `backend\.venv`, deps pinned in `uv.lock`) |
| Backend secrets | `contractiq\backend\.env` (`GEMINI_API_KEY`, database URL). Template: `backend\.env.example` |
| Frontend (Next.js 15.5.4, TypeScript) | `contractiq\frontend` (dev port 3100) |
| Local DB + Redis (Docker) | `contractiq\infra\docker-compose.yml` → containers `infra-postgres-1` (127.0.0.1:5432), `infra-redis-1` |
| Production deploy setup | `contractiq\infra\docker-compose.prod.yml`, `infra\Caddyfile`, `infra\.env.prod.example`, `backend\Dockerfile`, `frontend\Dockerfile`; guide `docs\deploy.md` |
| Docs per step | `contractiq\docs\` (data-gate, ingestion, extraction, buyer-documents, search, citations, hearing, backtest, deploy) |
| Architecture notes | `contractiq\architecture\ARCHITECTURE.md`, `CODE_MAP.md` |
| Downloaded order PDFs (3.9 GB, git-ignored) | `contractiq\data\orders\hrera_gurugram\<sha256>.pdf` |
| Hindi OCR data | `contractiq\data\tessdata` |
| Embedding model cache | `contractiq\data\models` (bge-small-en-v1.5 is the one in use) |
| Buyer uploads | `contractiq\data\uploads` |
| **200-record hand-check sheet** | `contractiq\data\review\review_2026-11-08.csv` (893 fields; fill `correct (Y/N)`, `correct_value`, `notes`) |
| Extraction review queue | `contractiq\data\extraction\needs_review.jsonl` |
| **Backtest result** | `contractiq\data\backtest\backtest_20261109_0103.json` |
| Embedding log | `contractiq\data\logs\embed_chunks.log` |
| Upload zip of the code | `contractiq\release\nyayasim-ebcf9c7.zip` (one commit behind HEAD; `release/` is locally git-excluded) |
| Tesseract 5.4 | installed system-wide (English + Hindi) |
| Docker Desktop | `C:\Program Files\Docker\Docker\Docker Desktop.exe` |

## 4. How to run it locally (PowerShell 5.1: no `&&`, one command per terminal tab)

1. Start Docker Desktop (it does not always start with Windows; it stopped overnight on 2026-11-08):
   `Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'`
2. Database (only if the containers are not running):
   `cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq; docker compose -f infra/docker-compose.yml up -d`
3. API: `cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
4. Website: `cd C:\Users\pande\Downloads\CONTRACT_IQ\contractiq\frontend; npm run dev`
5. Open http://localhost:3100 (health: http://127.0.0.1:8000/health).

Tests and checks:
- Backend: `cd backend; $env:NYAYASIM_REQUIRE_DB='1'; $env:NYAYASIM_REQUIRE_OCR='1'; .\.venv\Scripts\python.exe -m pytest -q` (173 pass as of ebcf9c7), then `.\.venv\Scripts\python.exe -m ruff check .`
- Frontend: `cd frontend; npx tsc --noEmit; npm run build:check` (`build:check` builds into `.next-check` so it is safe while `npm run dev` runs).

## 5. Windows / tooling gotchas (save time)

- Claude's own Bash/PowerShell runs sandboxed: installs into AppData are invisible to the user's shell.
  Install packages and run long jobs in the user's terminal (`run_in_terminal`).
- Use `127.0.0.1`, never `localhost`, for Postgres (IPv6 hang with Docker Desktop).
- Never run plain `npm run build` while `npm run dev` runs (corrupts `.next`); use `build:check`.
- Closing a terminal tab kills what it started. Start Docker Desktop with `Start-Process` (detached).
- Terminal tabs vanish when the desktop app restarts: long jobs stop with them. Check `list_terminal_tabs`.
- Max ~6 terminal tabs. `read_terminal` returns early on new output: measure durations inside scripts.
- Set `PYTHONIOENCODING=utf-8` for scripts that print Hindi/₹.
- Gemini free tier: `gemini-3.8-flash` daily quota is tiny; `gemini-3.5-flash-lite` hits per-minute 429s
  and a daily cap. Long LLM jobs (backtest, extraction) mostly wait on quota.
- The machine is CPU-bound when OCR (6 workers) runs; embeddings run ~30x slower alongside it.

## 6. What has been built (all committed on `nyayasim/foundation`)

| Commit | Step |
|---|---|
| 70f4905 … 68b3a4e | Imported ContractIQ, removed false marketing claims, made frontend build |
| 3a69002 | Step 0–1: backend foundation, deterministic Decimal interest calculator |
| c297da0 | Step 2: data gate → HRERA Gurugram (13,992 orders listed; UP behind CAPTCHA) |
| aa2dad5, 62cac96, d1c6dc4 | New NyayaSim case workflow frontend; light enterprise redesign |
| c81b935 | Step 3: database schema (migrations 0001…), DB-enforced provenance rules |
| 3b1ab46, 3da4fb5 | Step 4: ingestion (polite 2.5 s fetcher, every request in `fetch_log`), pdfium text + Tesseract OCR eng+hin, exact-offset chunker, keep-awake |
| be231e0, 4c59ec8, 745648c | Step 4b: outcome extraction. Gemini proposes fields with quote + page; **code** verifies the quote against stored text (exact, or fuzzy ≥90 with numbers re-parsed from the stored span). Key-page selection; pass 1 flash-lite, `--retry-review` pass with 3.8-flash |
| dfe5214, a7d7f53 | Step 5: buyer uploads + OCR, verified facts (DB trigger: quote must equal page substring), rule-based follow-up questions, privacy guard (HTTP 403 `PrivateDataBlocked`); website wired to real cases |
| 082e036 | Step 6: hybrid search. Postgres FTS + pgvector cosine, merged by RRF k=60, max 2 chunks/order, **mandatory decision-date cutoff** (`CutoffLeak` otherwise). Local fastembed `BAAI/bge-small-en-v1.5` (384 dims) |
| 8ee9487 | Step 7: citation checker, 7 rules; numbers must match exactly even on fuzzy quote matches |
| e06b85d | Step 8: LangGraph hearing (buyer → builder → citation gate → bench → report), outcome shares with Wilson 90% interval (min 5 records), award from the calculator at the median precedent rate, `hearing_runs` table, hard per-call deadline, no DB transaction open during model calls |
| dcea538 | Step 9: time-split backtest (train < 2025-01-01, test ≥ 2025, merits classes only); methods: majority, buckets, single LLM, debate; accuracy + Wilson CI, macro-F1, confusion, McNemar |
| ebcf9c7 | 10-pass review fixes (413 for >25 MB uploads, no open transactions during OCR/model calls everywhere, vector search fills its pool under strict cutoffs, hearing default flash-lite, removed inaccurate privacy/encryption text and fake user), phone-friendly stacked tables, **production Docker + Caddy deploy** (smoke-tested: all containers healthy, OCR eng+hin in container, non-root, Caddy single-origin routing + password verified) |
| 592cd13 | API allows the local website on both `localhost:3100` and `127.0.0.1:3100` |

API routes: `POST /api/v1/calculations/interest`; `GET/POST /api/v1/cases`; `GET /api/v1/cases/{id}`;
`POST /api/v1/cases/{id}/documents`; `GET .../documents/{doc}/pages/{n}`; `POST .../facts/extract`;
`POST .../facts/{fact}/confirm`; `POST/GET /api/v1/cases/{id}/hearing`; `GET /health`.

Backend scripts (`cd backend; .\.venv\Scripts\python.exe -m scripts.<name> ...`):
`ingest_hrera` (`--register`, `--fetch N`, `--years`, `--all-types`, `--delay`), `ingest_report`,
`extract_fields` (`--limit N`, `--model`, `--interval`, `--retry-review`, `--thinking`, `--check-key`, `--list-models`),
`export_review` (`--sample 200`), `embed_chunks` (`--limit`, `--batch`), `demo_buyer_case`, `run_hearing`,
`backtest` (`--cutoff`, `--limit`, `--model`, `--thinking`), `check_db`, `data_gate_haryana`.

## 7. Data state (measured 2026-11-09)

| Item | Count |
|---|---|
| Orders registered from the HRERA listing | 13,992 |
| Orders fetched (PDF + page text stored) | 2,019 (last fetch 2026-11-09 04:15 IST; the 2,000-order batch is done) |
| Order pages / search chunks | 37,816 / 65,974 |
| Chunks with embeddings | **65,974 / 65,974 (complete)** → hybrid search (BM25 + vector) is now fully available |
| Verified outcome records (`case_records`) | 248 (partly_allowed 88, disposed_of 73, allowed 47, dismissed 26, withdrawn 14); 0 hand-reviewed |
| Buyer cases / hearing runs | 1 (demo) / 1 |
| Database size | 481 MB |

## 8. Backtest result (first run) and a suspected bug

File: `data\backtest\backtest_20261109_0103.json`. Model flash-lite, cutoff 2025-01-01, 97 training
records, 64 test cases, 46 scored (merits classes), 25 hours (mostly quota waits). Search was
keyword-only for this run (embeddings were not finished).

| Method | Accuracy (90% CI) | Macro-F1 | Errors |
|---|---|---|---|
| Majority (always "partly allowed") | 54.3% (42–66) | 0.24 | 0 |
| **Buckets (claim type × delay band)** | **71.7% (60–81)** | **0.60** | 0 |
| Single LLM | 58.7% (47–70) | 0.36 | 15 |
| Debate (full hearing) | 56.5% (45–68) | 0.32 | 17 |

Debate vs single: McNemar p = 1.0 (no difference).

**Suspected bug, investigate first:** the LLM methods predicted "dismissed" for 8 of the 9 truly
"allowed" test orders, while buckets got all 9 right. That systematic flip suggests the LLM is
misreading the case summary or the label meaning (e.g. who the complainant is: HRERA also has promoter
complaints, or the summary built in `app/backtest/dataset.py` / prompt `SINGLE` in
`app/backtest/run.py` lacks the deciding facts). Do **not** publish these LLM scores in
`docs/backtest.md` until this is explained. LLM errors (15/17) were Gemini quota 429s, not failures of
the method, and are recorded as errors, not wrong answers.

## 9. Pending work, in the recommended order

1. **Investigate the allowed→dismissed flip** (section 8). Print the exact prompt + summary for 2–3 such
   cases (e.g. `RERA-GRG-3069-2020`, `RERA-GRG-6170-2022`), compare with the order text, fix, add a test.
2. **Rerun the backtest with hybrid search** (embeddings are now complete), after the quota resets or
   with a paid key. Better: add a `--resume FILE` / `--methods` option to `scripts/backtest.py` so only
   errored cases or only LLM methods re-run. Then write the scores into `docs/backtest.md` and commit.
3. **Extract outcomes for the newly fetched orders:** 2,019 fetched but only 248 `case_records`.
   `python -m scripts.extract_fields --limit N`, then `--retry-review --model gemini-3.8-flash --thinking low`.
   More training records = a fairer backtest (only 97 training records now).
4. **User's hand check** of `data\review\review_2026-11-08.csv` (the user does this; then load the
   verdicts and compute field accuracy; mark `reviewed_by/reviewed_at`).
5. **Fetch the remaining ~12,000 orders** in batches: `python -m scripts.ingest_hrera --fetch 2000`
   (≈12 s/order incl. OCR; run in the user's terminal; then `embed_chunks` for new chunks).
6. **Paid zero-retention LLM** (user to choose provider): add a provider behind the `LLM` interface in
   `app/extraction/gemini.py` / `app/hearing`, then allow real cases (`NYAYASIM_PRIVATE_LLM_OK`).
7. **Complaint draft for real cases** (frontend `app/cases/[id]/live/not-built.tsx` currently shows "not built yet"; demo-only draft exists). Must cite only verified facts + verified orders.
8. **Real authentication** (accounts, per-user case isolation) replacing the single site password.
9. **DPDP compliance:** consent notice, encryption at rest for uploads, user deletion/erasure, access logs, retention policy.
10. **Deployment:** recommended free host = Oracle Cloud Always Free (Ampere A1, Mumbai/Hyderabad) +
    DuckDNS name + `docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod --profile https up -d --build`
    (see `docs/deploy.md`). Quick demo alternative: Cloudflare quick tunnel from this PC.
    The user must create the Oracle account; Claude cannot.
11. **Push to GitHub** (user creates an empty private repo): `git remote add origin <url>` then
    `git push -u origin nyayasim/foundation`. Rotate the Gemini key first.
12. Small: "Download PDF" on the demo report is a placeholder button; legal review of report wording.

## 10. How to work efficiently in the new chat

- Read this file, `README.md` and the relevant `docs/<step>.md` first; don't re-explore the repo.
- Check services before assuming they run: `docker ps`, `curl http://127.0.0.1:8000/health`.
- Run long jobs (fetch, extraction, backtest, embeddings) in the user's terminal tabs, in the background,
  and don't run OCR and embeddings at the same time.
- Batch LLM work around the free-tier quota (daily reset) or get the paid key first.
- Keep each change small, tested (`pytest`, `ruff`, `tsc`, `build:check`), and committed with a clear message.
