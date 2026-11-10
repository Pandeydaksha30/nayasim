# Model evaluation

Every number here comes from a saved run (`data/benchmark/*.json`, `data/backtest/*.json`) and can
be reproduced with the command shown. Nothing is reported from the test split unless it is the
final number for a component; development uses the validation split.

## Benchmark v1 (frozen 10 Nov 2026)

`benchmark/split_v1.json`, made by `python -m scripts.benchmark split`, never overwritten.

| Split | Rule | Orders with text | With extracted labels |
|---|---|---|---|
| train | decided before 2024-01-01 | 929 | 107 |
| validation | 2024 | 321 | 45 |
| test | from 2025-01-01 | 769 | 96 |

104 groups of duplicate orders (same PDF, or same complaint number) were found; none span two
splits, so no evaluated order has a twin in training. Labels are still **machine-extracted and not
yet checked by a person**; the blind two-annotator process (`docs/annotation-guide.md`) will
replace them with gold labels.

## 1. Citation verifier (rule-based, not trained)

`python -m scripts.benchmark citations --split validation|test`. Genuine citations are real
spans of stored test/validation pages; fabricated ones are made from them by one known change
each (see `app/benchmark/citations.py`). 150 pages sampled per run.

| Run | Split | Precision | Recall | F1 | Fabrications caught |
|---|---|---|---|---|---|
| Before fix | test | 0.870 | 1.000 | 0.930 | 95.6% (meaning flips: 2 of 47 caught) |
| **After fix (final)** | **test** | **1.000** | **0.983** | **0.992** | **100%** (1,015 of 1,015) |
| After fix | validation, seed 20261110 | 1.000 | 0.970 | 0.985 | 100% |
| After fix | validation, seed 7 | 1.000 | 0.983 | 0.992 | 100% |

Catch rate per fabrication type after the fix (test): altered number, wrong page, nonexistent
order, quote from another order, order decided after the cutoff, shuffled words, too-short quote,
reversed meaning: **all 100%**. Genuine quotes: exact 100% accepted, with simulated OCR noise
96.7% (the rest are rejected because the noise hit a meaning word: the verifier errs towards
rejecting).

**What the fix was:** the verifier tolerated ≥90%-similar quotes (for OCR noise) and checked only
numbers exactly, so "the respondent is liable" quoted as "is not liable" passed. Now words that
decide meaning (not, no, never, allowed, dismissed, entitled, liable, shall, may, …) must match the
stored text exactly. Two test-generation errors were found and fixed along the way (boilerplate
repeated on several pages; a "flip" that recreated the real wording); neither was a verifier error.

**Disclosure:** the meaning-flip weakness was first seen on the test split, then confirmed on
validation with a fresh seed. The rule is general (a fixed word list), not fitted to examples.

**Not covered yet:** whether a genuine quote actually *supports* the argument that cites it. That
needs human judgement on a sample.

## 2. Outcome prediction (backtest; Gemini prompting, not trained)

Time split: train before 2025-01-01 (97 records), test from 2025 (64 records). Truth = extracted
labels (not yet hand-checked). Keyword search for precedents in all runs below, so runs differ only
in the case summary.

| Run | Summary given to the model | Cases scored | Majority | Claim × delay rule | Single LLM call | Debate |
|---|---|---|---|---|---|---|
| 9 Nov (original) | "Payments: none verified" when unknown | 46 | 54.3% | 71.7% | 58.7% | 56.5% |
| 10 Nov, fix A | payments "not stated (does not mean nothing paid)" + "not stated: possession date" | 64 | 54.7% | 71.9% | **46.9%** | not run |
| 10 Nov, fix B (ablation) | payments wording only | 64 | 54.7% | 71.9% | **50.0%** | not run |
| 10 Nov, control | original 9 Nov wording, rerun today (`--summary legacy`) | 64 | — | — | *running* | not run |

On the 49 cases scored in both 9 Nov and fix A: single call 59.2% → 42.9%. Allowed cases called
"dismissed" fell from 8 to 3, but partly-allowed cases called "dismissed" rose from 1 to 8: the
"not stated: possession date" line reads to the model as a weak case. Fix B removes that line and
scores 50.0%, still below the 9 Nov figure. The first control cases show the original wording
also calling allowed refund cases "dismissed" today, so part of the difference may be the hosted
model changing between runs rather than the wording. The control run (same wording as 9 Nov, today)
decides this; until it finishes, the summary change is **not committed** and no improvement is
claimed.

**Why outcome prediction is hard here:** a test case gives the model only claim type, sometimes a
possession date and an amount, and the hearing date: the order's own text cannot be used (it
contains the answer). With that little information, the claim type alone decides most outcomes
(refund claims are mostly allowed), which is why the simple claim × delay rule wins. The model has
far more to work with in real use (a buyer's full documents), but that cannot be backtested until
there are labelled buyer cases.

## 3. Not measured yet (tools ready, waiting on human labels)

| Component | Metric | Tool | Material ready |
|---|---|---|---|
| Order field extraction | accuracy per field vs gold, coverage, outcome confusion | `annotate-export/agree/score` | `data/annotation/blind_A.csv`, `blind_B.csv`: 100 test orders |
| Annotator agreement | Cohen's kappa (outcome, claim), raw agreement | `annotate-agree` | as above |
| Precedent search | MRR, nDCG@10, P@5, recall@10 in pool; keyword vs hybrid | `retrieval-export/score` | `data/annotation/retrieval_judgements.csv`: 30 queries, 476 pooled results |
| OCR | CER, WER vs hand transcription | `ocr-export/score` | `data/annotation/ocr/`: 30 scanned test pages |
