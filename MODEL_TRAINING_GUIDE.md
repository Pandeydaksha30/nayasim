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

**Reading:** with 58–76 training examples the trained models do not beat simple baselines on
accuracy. Claim type should be easy (the relief sought says "refund" or not), so this also hints at
label noise. More labels are being produced (extraction of fetched, unlabelled orders) and 1,000
unseen 2025–2026 orders are being downloaded; the models will be retrained and re-reported then.

## On the 95% target

- **Reachable, and measured:** citation verification (precision 100%, recall 98.3% on held-out
  orders).
- **Plausible with enough checked labels:** claim type, dates and amounts.
- **Not supported by any evidence so far:** 95% on allowed / partly allowed / dismissed. The best
  method is 72.9% (90% range about 62–81%) on 59 cases; the labels are unchecked; and "allowed" vs
  "partly allowed" is a judgement call whose human agreement rate (to be measured with two
  annotators) caps any model. A number above that cap would mean leakage or overfitting, not skill.
