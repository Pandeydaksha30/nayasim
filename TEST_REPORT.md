# Test report (13 Nov 2026)

Everything below was run on this machine on 13 Nov 2026. Earlier results: END_TO_END_TEST_REPORT.md
(12 Nov). Nothing here was tuned on the held-out evaluation questions or the frozen ML test set.

## Unit and integration tests (backend)

`NYAYASIM_REQUIRE_DB=1 python -m pytest` against a throwaway database migrated from scratch to 0010:
**244 passed, 0 failed** (was 228; +9 document RAG, +7 agent).

| New test file | What it proves |
|---|---|
| `tests/test_case_rag.py` (9) | Upload creates chunks with document, page, embedding; search returns only this case's chunks; another user gets 404 on passages/ask/questions and 401 when signed out; a non-UUID case id is refused; answer shown only with a citation found in the document; invented quote, unknown label and altered number rejected; insufficient answers replaced; private case not sent to the model (403); model failure → 503; chunks deleted with the case |
| `tests/test_agent.py` (7) | Model's tool choices are executed in its order; final citations checked (altered year and never-retrieved label removed); 6-step limit, identical-call refusal, tool errors become observations; delegation runs a specialist loop restricted to its tools; two model failures stop the run without an answer; interest tool uses the calculator on verified facts; API saves runs, 403 for private case, 404 for another user; interrupted runs marked failed |

Frontend: `npx tsc --noEmit` clean. Production build succeeds inside Docker (`nyayasim-web`).

## Live end-to-end checks (running app, real Gemini, fictional documents)

`python -m scripts.e2e_check <stage>` through the website address (cookie + `/api` forwarding).

| Stage | Result | Notes |
|---|---|---|
| setup (register/login, case, upload, OCR, negatives) | 29 / 29 | |
| facts (Gemini) | 5 / 5 | 19 facts with page and quote, 10 s |
| rag | 9 / 9 | 6 passages, mode hybrid; answer "on or before 30th June 2021" with 1 verified citation; unanswerable question refused; history saved; private case 403 |
| isolation | 9 / 9 | Second user: 404 on case, passages, questions, agent runs, hearing, estimate, ask; case not in their list |
| agent (objective: dates, precedents, outcome) | completed | Model chose `search_documents` → `verify_quote` → finish; 2 verified citations |
| agent (objective: hearing + judge + interest) | 6 / 6 | Model chose `get_facts` → `calculate_interest(10.85)` → `run_hearing` → finish, 20 s; judge outcome "partly allowed"; **3 citations verified, 0 removed** |
| session | 6 / 6 | logout, refused, login again, case still there |
| insights | 16 / 16 | estimate, draft, order search, classifier |
| pages `/cases/{id}/ask`, `/agent`, `/hearing` | 200 | rendered with login |

Two problems found and fixed during these runs:

1. The first request right after login sometimes got 401: the session row was committed only after
   the response was sent. Fixed in `app/auth/service.py` (commit before setting the cookie).
2. The agent's answer cited hearing precedents with labels the final check did not know, so all 11
   were removed (shown as unsupported, not hidden). Fixed: verified hearing citations are now
   registered as evidence H1, H2… and re-checked against the stored order page.

## Document Q&A evaluation (`backend/eval/doc_qa.jsonl`, `scripts/eval_rag.py`)

40 questions over the fictional demo documents (agreement 2 pages, receipts 2 pages, builder
letter 1 page): 30 answerable with gold document, page and evidence passage; 10 unanswerable.
Split 20 development / 20 held-out. Model `gemini-3.5-flash-lite`, embeddings `bge-small-en-v1.5`.

| Metric | Development (20) | Held-out (20, run once) |
|---|---|---|
| Retrieval hit@1 | 0.933 | 1.000 |
| Retrieval recall@5 | 1.000 | 1.000 |
| Retrieval MRR | 0.967 | 1.000 |
| Answer accuracy (expected value in answer) | 15/15 | 15/15 |
| Citation accuracy (verified citation on gold page) | 15/15 | 15/15 |
| Abstention on unanswerable | 5/5 | 5/5 |
| Citations removed by the code check | 0 | 0 |

**Limit:** five short invented pages make this an easy test of the pipeline. It says nothing about
long, scanned or real agreements; that needs real documents and a person checking answers.
Raw results: `backend/eval/results_*_answers.json`.

## Not tested

- Production stack running on a server, HTTPS, real email sending.
- The specialist sub-agents chosen by Gemini in a live run (tested with a scripted model only).
- Long or scanned uploaded documents in the RAG evaluation.
- Load, concurrency beyond two background jobs, external security testing.
