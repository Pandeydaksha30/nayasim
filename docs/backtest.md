# Time-split backtest (step 9)

`python -m scripts.backtest --limit 64` (from `backend/`). Every prediction is saved to
`data/backtest/backtest_<time>.json` (git-ignored); scores are printed.

## Design

* **Split:** training = verified case records decided **before 1 Jan 2025**; test = records
  decided on or after it. Only outcomes decided on the merits are used (allowed, partly
  allowed, dismissed); "disposed of" and "withdrawn" are excluded from both sides.
* **No leaks:** a test case's input is only its own structured facts — claim type, amount
  paid, promised possession date, hearing date (`app/backtest/dataset.case_input`). The order's
  text, which contains the decision, is never used. Precedents come from search with the
  2025-01-01 cutoff, so no test-year order can be retrieved (tested).
* **Methods**
  1. *Majority* — the most common training outcome.
  2. *Claim type × delay* — most common outcome among training records with the same claim
     type and delay band (<2 y, 2–4 y, >4 y, unknown), with fallbacks. Stands in for the plan's
     "simple model on structured facts": with ~100 training records a fitted classifier would
     not be more reliable.
  3. *Single model* — one call: case summary + precedents -> outcome.
  4. *Debate* — the full hearing (two advocates, citation gate, judge).
  3 and 4 get **the same precedents** per case, so the difference is the debate alone.
* **Scores** (on cases where every method produced a prediction): accuracy with a 90% Wilson
  range, macro-F1 over the three outcomes, confusion tables, debate-vs-single discordant pairs
  with an exact McNemar test, and citation verification counts from the debates.

## Limits of this sample run

* Small: ~64 test cases, so accuracy ranges are wide (about ±10 points).
* Model: `gemini-3.5-flash-lite` (free tier); the stronger model's daily quota was used up.
* Search is keyword-only here (embeddings are not complete yet).
* Ground truth is the extracted case records, which have **not yet been hand-checked**
  (the 200-record review). Errors in them count against every method equally.
* Award error is not measured yet: test cases have only a total amount paid, not dated
  payments, so the calculator cannot reproduce the order's figure.
