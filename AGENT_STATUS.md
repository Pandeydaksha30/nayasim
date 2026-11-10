# NyayaSim — Agent and model status (Phase 1 audit)

Audited 10 Nov 2026 at commit `9d1a709`, from the code, the database and the stored backtest
(`data/backtest/backtest_20261109_0103.json`). Every number below was read from those sources;
"not measured" means no evaluation exists, not that the result is bad.

## Summary

- **No model in NyayaSim is trained or fine-tuned.** The "AI" parts are: one pretrained embedding
  model used as-is (BAAI/bge-small-en-v1.5), Google Gemini called with prompts
  (`gemini-3.5-flash-lite` on the free tier), Tesseract OCR, and rule-based / statistical code.
  There is no Groq integration in this codebase.
- **Data actually usable:** 13,992 HRERA Gurugram orders are *listed*; **2,019 are downloaded,
  read (833 needed OCR) and searchable** (65,974 passages, all with embeddings), decided
  26 Apr 2018 – 13 Oct 2026. **248** have structured outcome labels, extracted by Gemini and checked
  by code against the order text. **0** labels have been checked by a person.
- **Labels by outcome:** partly allowed 88, disposed of 73, allowed 47, dismissed 26, withdrawn 14.
  By claim: delayed possession 135, refund 63, other 50. Before 2025: 152; from 2025: 96.
- **Only one end-to-end accuracy figure exists:** the time-split backtest (train before 1 Jan 2025,
  97 usable training records; 46 test cases scored by all methods). A simple rule beats the agents.
- **Correction found in the audit:** the website and README said "13,992 orders searched"; only
  2,019 are. Fixed in the same commit as this file.

## Agents and components

| # | Name (code) | Purpose | Status | Model / method | Training data | Train / val / test | Accuracy | Precision | Recall | F1 | Known limitations | Required improvements |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Order ingestion** (`app/ingestion/`) | Fetch HRERA orders, read text, OCR scans (eng+hin), chunk with exact offsets | Implemented, tested (18 tests) | Rule-based; pdfium text layer; Tesseract 5 OCR | — (no learning) | — | OCR error rate **not measured** (only Tesseract's own confidence) | — | — | — | 11,973 listed orders not fetched yet; OCR quality on poor scans unknown | Fetch remaining orders; measure OCR CER/WER on a hand-typed sample |
| 2 | **Order outcome extractor** (`app/extraction/`) | Read an order → outcome, claim type, amounts, interest rate, dates, each with a quote | Implemented; run on 248 of 2,019 orders | Gemini prompting + **code verifies every quote** against the stored page (exact or ≥90% fuzzy, numbers must match) | — (zero-shot prompting) | — | **Not measured.** Trial: 10 of 15 orders passed verification on the first pass; 160 orders in the needs-review queue | not measured | not measured | not measured | Verification proves the quote exists, not that the label is right; free-tier quota limits throughput | 200-record hand check (sheet ready: `data/review/review_2026-11-08.csv`, 893 fields); then a second annotator on a subset; extract the remaining 1,771 fetched orders |
| 3 | **Buyer document reader** (`app/buyer/documents.py`) | Store uploads, read text/OCR, 100-page cap | Implemented, tested | Rule-based + Tesseract | — | — | OCR not measured | — | — | — | Uploads not encrypted at rest | Encryption at rest; OCR evaluation |
| 4 | **Buyer fact extractor** (`app/buyer/facts.py`) | Promoter, project, unit, price, possession date, payments, each with page + quote | Implemented; **runs only on demo cases** (privacy rule) | Gemini prompting + code quote verification (DB trigger: quote must be a substring of the page) | — | — | **Not measured** (one fictional demo case: 16 facts found) | not measured | not measured | not measured | Unusable for real cases until a no-retention model is configured | Paid zero-retention LLM; labelled set of real (consented) or realistic agreements |
| 5 | **Follow-up questions** (`app/buyer/questions.py`) | Ask only what the documents don't answer | Implemented | Rule-based | — | — | n/a (deterministic) | — | — | — | Fixed question list | — |
| 6 | **Interest / refund calculator** (`app/calculator/`) | Delay interest and refund per payment | Implemented, 15 tests | Deterministic Decimal arithmetic | — | — | Exact by construction for the stated rule; **award error vs real orders not measured** (test cases lack dated payments) | — | — | — | Rate basis must be confirmed by the user | Compare with awards in orders that list payments |
| 7 | **Precedent search** (`app/retrieval/`) | Find similar past orders before a cutoff date | Implemented, 11 tests; leak-proof cutoff | Hybrid: Postgres full-text (BM25-like) + pretrained bge-small embeddings (384-d, not fine-tuned), merged with RRF k=60 | — | — | **Recall@K / MRR / nDCG not measured** | — | — | — | No relevance judgements exist; HRERA Gurugram only | Build a judged query set; measure; then test a reranker / legal-domain embeddings against it |
| 8 | **Citation verifier** (`app/verifier/citations.py`) | Reject citations whose order, date, page or quote is not in the store | Implemented, 14 tests | Rule-based, 7 checks | — | — | In the backtest, 334 of 362 cited quotes passed (92.3%); 17 of 230 arguments removed. **Precision/recall of the verifier itself not measured** on a labelled set | not measured | not measured | — | Checks that the quote exists, not that it supports the argument | Labelled set of real vs. altered citations; "supports the claim" judgement by hand on a sample |
| 9 | **Buyer's advocate** (`app/hearing/agents.py`, graph node) | Arguments for the buyer from retrieved precedents | Implemented | Gemini prompting | — | — | Evaluated only as part of #12 | — | — | — | Free-tier model | — |
| 10 | **Builder's advocate** (same) | Arguments for the builder | Implemented | Gemini prompting | — | — | as #9 | — | — | — | — | — |
| 11 | **Bench / judge** (same) | Weigh arguments, outcome, weak points | Implemented | Gemini prompting | — | — | as #12 | — | — | — | — | — |
| 12 | **Hearing orchestration** (`app/hearing/graph.py`, `jobs.py`) | buyer → builder → citation gate → bench → report; background runs | Implemented (LangGraph); background jobs since 9d1a709 | — | — | **Backtest:** 97 train / 0 val / 46 test (64 sampled, 18 errored on quota) | **Debate 56.5%** (90% CI 44.5–67.8); single-call LLM 58.7%; **claim×delay rule 71.7%**; always-"partly allowed" 54.3% | per class: allowed 0/9 found | allowed recall **0.0** | macro-F1 **0.32** | Predicted "dismissed" for 4 of 9 allowed (single call: 8 of 9) — suspected bug; small test set; free model; keyword-only search during that run | Investigated 10 Nov (MODEL_EVALUATION.md §2): not the summary wording, not precedent relevance; the input (claim type ± a date/amount) is too thin. Next: leakage-free 'facts and submissions' input + gold labels |
| 13 | **Outcome statistics + award** (`app/hearing/stats.py`) | Share of similar orders by outcome (Wilson 90% interval); award at the median precedent rate | Implemented | Statistics on retrieved records | the 248 labels | — | not measured separately | — | — | — | Needs ≥5 labelled precedents; most retrieved orders have no label yet | More labels |
| 14 | **Baselines** (`app/backtest/baselines.py`) | Majority class; claim type × delay band | Implemented | Counting rules | 97 pre-2025 records | as #12 | 54.3% / **71.7%** | — | — | macro-F1 0.235 / **0.602** | — | Keep as the bar every model must beat |
| 15 | **Report** (`frontend` + hearing result) | Present outcome shares, award, arguments, weak points | Implemented for demo cases | Assembly of #12/#13 output | — | — | — | — | — | — | Complaint draft not built for real cases; "Download PDF" placeholder | Build draft from verified facts + verified citations |

Confusion tables (rows = truth, columns = predicted: allowed / partly / dismissed), 46 cases:

| Method | allowed row | partly row | dismissed row |
|---|---|---|---|
| Claim × delay rule | 9 / 0 / 0 | 1 / 23 / 1 | 2 / 9 / 1 |
| Single LLM call | 0 / 1 / 8 | 0 / 24 / 1 | 0 / 9 / 3 |
| Full debate | 0 / 5 / 4 | 0 / 24 / 1 | 0 / 10 / 2 |

Debate vs single call: 26 both right, 1 only single right, 0 only debate right, 19 both wrong
(McNemar p = 1.0): the debate adds nothing measurable yet.

## What does not exist yet

- Any trained or fine-tuned model; any validation split.
- Any human-annotated label (so no inter-annotator agreement either).
- Retrieval relevance judgements; OCR ground truth; a labelled citation set.
- Statute / legislation store (RERA Act, Haryana Rules) for statute retrieval.
- Higher-court judgments (Supreme Court, High Courts) relevant to RERA.
- Evaluation of LLM output quality (faithfulness, hallucination rate) beyond the citation check.
