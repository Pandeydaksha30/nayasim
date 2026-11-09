# Simulated hearing and decision report (step 8)

`POST /api/v1/cases/{id}/hearing` runs a hearing; `GET` returns the latest completed run.
Every run (completed or failed) is stored in `hearing_runs` with its full result.

## Flow (LangGraph: `app/hearing/graph.py`)

1. **Inputs (code).** The case summary is built from verified facts and answers
   (`inputs.summary_text`). A search query is built from the case's issues and run with the
   cutoff (step 6). Each retrieved order becomes a numbered precedent `[P1]…` with its
   decision date, verified outcome and rate (if extracted) and the matching passages.
2. **Buyer's advocate** and **builder's advocate** (model): up to 3 arguments each, every one
   citing precedents by label, page and verbatim quote. Prompts forbid outside cases/law and
   any money calculation.
3. **Citation gate (code).** Each citation is mapped to its order and checked by the step 7
   checker against the cutoff and the retrieved set. An argument is kept only if it has at
   least one citation and **all** are verified; otherwise it is removed with the reason.
4. **Judge** (model): sees only kept arguments; gives an outcome, reasons and up to 3 weak
   points with fixes. Its citations are checked too; failed ones are removed and recorded.
5. **Report (code).**
   * *How similar cases ended*: counts of verified outcomes among the precedents, buyer-win
     share (allowed + partly allowed) with a 90% Wilson interval; fewer than 5 records ->
     "insufficient precedent", no percentage.
   * *Award*: the deterministic calculator on the buyer's verified payments and promised date,
     at the **median rate applied in the precedents that record one** (stated as such); no
     rate in any precedent -> no figure.

## Privacy

The hearing sends the case facts to the model, so it runs only for demo cases until a
no-retention model is configured (`NYAYASIM_PRIVATE_LLM_OK=true`); otherwise HTTP 403.

## Models

`settings.hearing_model` (default `gemini-3.8-flash`, thinking low). The model proposes;
the gate and the code decide what reaches the report.

## First real run (7 Nov 2026, fictional demo case)

* First attempt with `gemini-3.8-flash` **hung for ~2 hours** inside a model call despite the
  SDK timeout, holding a database transaction open. Fixed: every call now has a hard deadline
  (`call_with_deadline`, daemon thread, 330 s) and the hearing closes its transaction before
  each model call (tested). `scripts/run_hearing.py` prints each call and dumps stacks if
  stuck for 15 minutes.
* Second attempt: `gemini-3.8-flash` free-tier daily quota exhausted (HTTP 429, used up by
  extraction). Run with `NYAYASIM_HEARING_MODEL=gemini-3.5-flash-lite`: completed in 12 s.
* Result: 10 precedents (7 with verified outcomes: 4 allowed, 3 partly allowed -> 7/7, 90%
  range 72-100%); award: delay interest Rs 11,74,886 on Rs 21,60,000 paid at 10.15% (median
  of 4 precedent rates), matching a hand calculation; 3 arguments kept, 0 removed; bench:
  partly allowed (COVID extension); **5/5 citations exact against the stored page text,
  verified and decided before the cutoff.**

## Background runs (added 10 Nov 2026)

`POST /api/v1/cases/{id}/hearing` checks privacy, facts and precedents at once (403/422 straight
away), stores a run with status `running`, returns **202**, and runs the model calls on a 2-thread
pool (`app/hearing/jobs.py`). The page polls `GET .../hearing/runs/{run_id}` every 3 s and reloads
when it is `completed`, or shows the stored error when `failed`. `GET .../hearing/active` lets a
reloaded page keep waiting. A unique index allows one running hearing per case (a second start gets
409). Runs left `running` by a restart are marked failed at the next start (migration 0008).
