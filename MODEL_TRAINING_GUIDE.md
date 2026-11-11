# Model training guide

## What in NyayaSim is trained, and what is not

| Component | Kind | Learns from our data? |
|---|---|---|
| Outcome / claim-type text classifiers (`app/ml/text_classifier.py`) | **Trained** (TF-IDF + logistic regression, scikit-learn) | Yes: fit on labelled orders |
| Claim × delay rule (`app/backtest/baselines.py`) | **Trained** in the simplest sense (counts) | Yes: most common outcome per bucket |
| Search embeddings (BAAI/bge-small-en-v1.5) | Pretrained, used as is (**retrieval**) | No fine-tuning |
| Order field extraction, buyer facts, hearing agents (Gemini) | **Prompting + inference** | No: the model is Google's; we only write prompts |
| Citation verifier, calculator, facts/findings cut | Rules | No |

Nothing is fine-tuned. Fine-tuning an LLM would need far more checked labels than exist, and the
free Gemini tier offers no fine-tuning.

## Data and splits

- Source: public HRERA Gurugram orders (`docs/ingestion.md`). Labels: `case_records`, extracted by
  Gemini with every value's quote verified against the stored page, **not yet checked by people**.
- Splits: `benchmark/split_v1.json`, by decision date (train < 2024 <= validation < 2025 <= test),
  frozen. Duplicates (same PDF or complaint number) never cross splits.
- Input text: only the parties' part of each order (`app/backtest/facts.py`), cut before the
  authority's reasoning. Orders without a safe cut are not used.
- Rules: choose settings on validation only; refit on train + validation; score test **once** per
  model configuration. Never train on test orders. Never evaluate on data used for training.

## Commands (from `backend/`)

```powershell
# 1. more orders (polite fetcher, logged; OCR for scans)
.\.venv\Scripts\python.exe -m scripts.ingest_hrera --fetch 1000 --years 2025 2026
# 2. labels for fetched orders (Gemini, quotes verified by code)
.\.venv\Scripts\python.exe -m scripts.extract_fields --limit 500
# 3. train + evaluate (validation for settings, test once)
.\.venv\Scripts\python.exe -m scripts.train_classifier
```

Models are saved to `data/models/<task>_tfidf_lr.joblib` (git-ignored); every report to
`data/benchmark/train_<task>_<time>.json`.

## Results so far (11 Nov 2026)

First training run: 180 labelled orders with a safe facts part (68 skipped).

| Task | Train / val / test | Validation macro-F1 (chosen) | **Test accuracy** | **Test macro-F1** | Test baseline |
|---|---|---|---|---|---|
| Outcome (allowed / partly / dismissed) | 58 / 24 / 59 | 0.259 | 55.9% | 0.377 | majority 57.6% / 0.244; claim × delay rule 72.9% / 0.581; LLM with facts 67.8% / 0.653 |
| Claim type (refund / delay / other) | 76 / 30 / 74 | 0.423 | 55.4% | 0.316 | majority 73.0% / 0.281 |

**Reading:** with 58-76 training examples the trained models do not beat simple baselines on
accuracy.

### Second run (11 Nov 2026, after labelling 500 more fetched orders)

358 labelled orders with a safe facts part (144 skipped). All the new labels fell in the training
period (orders decided before 2024); validation and test are the same cases as in the first run.

| Task | Train / val / test | Validation macro-F1 (chosen) | **Test accuracy** | **Test macro-F1** | First run | Test baseline |
|---|---|---|---|---|---|---|
| Outcome | 179 / 24 / 59 | 0.293 | 50.8% | 0.340 | 55.9% / 0.377 | majority 57.6% / 0.244; claim x delay rule 72.9% / 0.581; LLM with facts 67.8% / 0.653 |
| Claim type | 254 / 30 / 74 | 0.443 | 62.2% | 0.359 | 55.4% / 0.316 | majority 73.0% / 0.281 |

Confusion (rows = truth, columns = predicted, same label order):
- Outcome (allowed / partly / dismissed): 6/7/0, 10/24/0, 6/6/0. **"Dismissed" is never predicted.**
- Claim type (delay / refund / other): 40/14/0, 9/6/0, 2/3/0.

**Reading.**
- Three times the training data did **not** help the outcome model: 30 of 59 correct against 33
  before, a difference well inside chance on 59 cases. It is still below "always partly allowed"
  (57.6%), the rule (72.9%) and the LLM with facts (67.8%).
- Claim type improved (46 of 74 against 41) but is still below the majority baseline on accuracy.
  Only 6 of 15 refund cases are recognised from a text whose relief section normally says "refund".
  That points at the labels or at the facts cut dropping the relief section, not at too little data.
- So more machine-made labels of the same kind are not the way forward. The next useful steps are
  the human label check (`docs/annotation-guide.md`) and an error review of the claim-type misses
  on **validation** orders.
- Disclosure: the same 59 / 74 test cases have now been scored twice by this model family. Any
  further change must be chosen on validation and confirmed on a new test period.

## On the 95% target

- **Reachable, and measured:** citation verification (precision 100%, recall 98.3% on held-out
  orders).
- **Plausible with enough checked labels:** claim type, dates and amounts.
- **Not supported by any evidence so far (two training runs):** 95% on allowed / partly allowed / dismissed. The best
  method is 72.9% (90% range about 62–81%) on 59 cases; the labels are unchecked; and "allowed" vs
  "partly allowed" is a judgement call whose human agreement rate (to be measured with two
  annotators) caps any model. A number above that cap would mean leakage or overfitting, not skill.
