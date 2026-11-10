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
| 10 Nov, control | original 9 Nov wording, rerun today (`--summary legacy`) | 64 | 54.7% | 71.9% | **56.2%** (macro-F1 0.400) | not run |

Confusion tables on the same 64 cases (rows = truth: allowed / partly / dismissed; columns =
predicted allowed / partly / dismissed):

| Run | allowed (14) | partly allowed (35) | dismissed (15) | Correct |
|---|---|---|---|---|
| Control, original wording | 0 / 2 / 12 | 0 / 26 / 9 | 0 / 5 / 10 | 36 |
| Fix A | 0 / 9 / 5 | 0 / 27 / 8 | 0 / 12 / 3 | 30 |
| Fix B | 0 / 2 / 12 | 0 / 28 / 7 | 0 / 11 / 4 | 32 |

**Conclusion: the "none verified" hypothesis was wrong.** With the wording fixed (fix B), allowed
cases are still called "dismissed" exactly as often (12 of 14); control vs fix B is within chance
(10 vs 6 discordant cases, McNemar p = 0.45). Neither wording change is kept: both were reverted.
In every run the model **never predicted "allowed"**.

**Actual root cause (measured):** the error follows the claim type. 13 of the 16 refund test cases
were allowed, and the model called almost all of them "dismissed", whatever facts were given. The
precedent search query was mostly about delay ("delay in handing over possession; interest for
every month of delay; force majeure; refund ..."), so a refund case was shown delay-interest orders:
only **17%** of the excerpts shown for refund cases (32 of 192) mentioned a refund. The model was
asked to decide a refund claim from precedents that were not about refunds.

**Claim-matched search (tested on validation, not on test):** the query now follows the relief
claimed (refund cases search for refund / withdrawal / section 18(1) orders). On the **validation
year** (cutoff 2024-01-01, test = 2024, 68 training / 29 test cases):

| Validation, 29 cases (12 allowed, 12 partly, 5 dismissed) | Correct | Accuracy | macro-F1 |
|---|---|---|---|
| Always "partly allowed" | 12 | 41.4% | 0.195 |
| Claim × delay rule | 18 | 62.1% | 0.569 |
| Single LLM call, old query | 5 | 17.2% | 0.146 |
| Single LLM call, claim-matched query | 3 | 10.3% | 0.091 |

Refund-relevant excerpts for refund cases rose from 20/120 to 80/120, but predictions did not
improve (2 vs 0 discordant cases, McNemar p = 0.5). The 2025+ test set was **not** run, because
validation showed no gain. The query change is kept for live hearings because it puts refund
orders in front of the advocates for refund claims; whether it improves search relevance will be
decided by the human relevance judgements (section 3), not assumed.

**What this establishes.** Across 5 runs and 2 time periods, the single-call LLM predictor never
predicts "allowed", mostly answers "dismissed" when facts are thin, and is at or below the
always-"partly allowed" baseline on validation. Neither the summary wording nor precedent
relevance fixes it. The input is the limiting factor: claim type, sometimes a date and an amount.
Tuning prompts further against 29–64 noisy, machine-extracted labels would be fitting noise.

### Facts-before-findings input (`--input facts`, 10 Nov 2026)

The model also gets the parties' part of the order: unit details, the complainant's facts and
relief sought, the builder's reply, cut before the authority's own reasoning
(`app/backtest/facts.py`). Orders without a safe cut are skipped (5 of 29 validation, 5 of 64 test).

**Leakage check.** A first heading-only cut leaked the authority's reasoning in 42 of 135 orders
(OCR-damaged headings), including decisions ("the authority is of the view that complainant cannot
be refunded"). The final cut stops at the earliest heading or authority phrase; an independent
phrase audit then finds only the parties' own words (10 hits, e.g. a reply asking "the Authority
is requested to consider ..."). A 30-order hand check (`data/annotation/facts_split_check.csv`)
is **pending**; until it is done, a residual leak cannot be ruled out.

| Validation 2024, 24 usable cases (10 allowed, 11 partly, 5→3 dismissed) | Correct | Accuracy | macro-F1 |
|---|---|---|---|
| Always "partly allowed" | 11 | 45.8% | 0.210 |
| Single LLM, summary only | 3 | 12.5% | 0.105 |
| Claim × delay rule | 15 | 62.5% | 0.557 |
| **Single LLM, facts input** | **16** | **66.7%** | **0.613** |

Facts vs summary: 13 vs 0 discordant cases, McNemar p = 0.0002. Facts vs rule: 5 vs 4, p = 1.

**Test 2025+ (run once, after validation; 59 usable cases: 13 allowed, 34 partly, 12 dismissed):**

| Method | Correct | Accuracy (90% Wilson) | macro-F1 | Confusion (rows allowed / partly / dismissed → predicted allowed, partly, dismissed) |
|---|---|---|---|---|
| Always "partly allowed" | 34 | 57.6% | 0.244 | 0/13/0, 0/34/0, 0/12/0 |
| Single LLM, summary only (original wording) | 32 | 54.2% | 0.372 | 0/2/11, 0/25/9, 0/5/7 |
| **Single LLM, facts input** | **40** | **67.8% (57.2–76.8)** | **0.653** | 6/3/4, 0/25/8, 0/2/9 |
| **Claim × delay rule** | **43** | **72.9%** | 0.581 | 11/2/0, 2/31/1, 2/9/1 |

Facts vs summary: 12 vs 4 discordant cases, p = 0.077. Facts vs rule: 8 vs 11, p = 0.65.

**What this establishes.**
- Giving the model the parties' filings is the first change that clearly helps (decisive on
  validation, same direction but not significant on test).
- It does **not** beat the simple rule on accuracy. It has the best macro-F1, because the two make
  different errors: the model finds dismissals (9/12 vs the rule's 1/12) and the rule finds
  allowed cases (11/13 vs the model's 6/13).
- 95% accuracy is not in sight for outcome prediction: the best method is 73% with a 90% range of
  roughly 62–81% on 59 cases, against labels that are still machine-extracted.
- The test set has now been used for this configuration. A combination of the rule and the model
  (an obvious next idea) must be developed on validation and confirmed on a **new** test period
  (orders decided after 13 Oct 2026 once fetched), not tuned on this test set.

## 3. Not measured yet (tools ready, waiting on human labels)

| Component | Metric | Tool | Material ready |
|---|---|---|---|
| Order field extraction | accuracy per field vs gold, coverage, outcome confusion | `annotate-export/agree/score` | `data/annotation/blind_A.csv`, `blind_B.csv`: 100 test orders |
| Annotator agreement | Cohen's kappa (outcome, claim), raw agreement | `annotate-agree` | as above |
| Precedent search | MRR, nDCG@10, P@5, recall@10 in pool; keyword vs hybrid | `retrieval-export/score` | `data/annotation/retrieval_judgements.csv`: 30 queries, 476 pooled results |
| OCR | CER, WER vs hand transcription | `ocr-export/score` | `data/annotation/ocr/`: 30 scanned test pages |
