# Annotation guide (benchmark v1)

For the two annotators (A and B) and the adjudicator. **The definitions below are proposals:
the adjudicator (a lawyer who knows RERA practice) should confirm or correct them before anyone
starts**, because unclear labels make both people and models disagree.

## Rules for everyone

- Work alone. Do not discuss orders with the other annotator, and do not look at NyayaSim's own
  answers (the review sheet in `data/review/` shows them; don't open it while annotating).
- Read the order's final directions (usually the last 2–4 pages) first, then search back for dates
  and amounts.
- If the order does not state something, leave it blank. Blank is a valid answer; a guess is not.
- Use `notes` for anything you were unsure about. Unsure items are what the adjudicator checks.
- Time: about 5–8 minutes per order. 100 orders ≈ 10–12 hours each.

## Files

| Task | File | What to fill |
|---|---|---|
| Order fields | `data/annotation/blind_A.csv` (or `_B`) | outcome, claim_type, possession_due, amount_paid, interest_rate_pct |
| Adjudication | `data/annotation/adjudication.csv` (made by `annotate-agree`) | `final` (or `blank`), `reason` |
| Search relevance | `data/annotation/retrieval_judgements.csv` | relevance 0/1/2 per row |
| OCR | `data/annotation/ocr/*.txt` | type exactly what the matching .png shows |

## Fields

**claim_type**: what the complainant mainly asked for.
- `refund`: wants to leave the project and get money back.
- `delayed_possession`: keeps the unit; wants possession and/or interest for the delay.
- `other`: anything else (e.g. only conveyance deed, only maintenance charges, only a fee dispute).
If both are asked "in the alternative", use the one the authority actually decided on.

**outcome** (proposed): the authority's decision **on that main relief**, ignoring side claims
such as compensation (which goes to the adjudicating officer) and litigation costs.
- `allowed`: the main relief is granted. A lower interest rate than asked (e.g. the prescribed
  rate instead of 18%) still counts as allowed.
- `partly_allowed`: the main relief is granted only in part or replaced by a smaller one. Examples:
  refund asked but only delay interest granted; delay interest granted for a shorter period than
  claimed; only some of several units or amounts allowed.
- `dismissed`: the main relief is refused (on merits, limitation, maintainability, or default).
- `disposed_of`: closed without granting or refusing it: settled, possession already handed over
  with no further relief, sent to another forum, or closed with general directions only.
- `withdrawn`: the complainant withdrew.

**possession_due**: the due date of possession *as the authority determined it* (after any grace
period it allowed), YYYY-MM-DD. Not the date the builder claims, unless the authority accepted it.

**amount_paid**: total paid by the complainant as stated in the order, rupees, digits only.

**interest_rate_pct**: the rate the authority ordered (e.g. 10.85). Blank if none was ordered.

## Search relevance (0 / 1 / 2)

Compare the query summary with the candidate order:
- **2, on point**: same kind of claim (refund vs delay interest) and similar facts (delay,
  payments, defences); a lawyer would cite it.
- **1, related**: same kind of claim, but different facts or a different issue decided.
- **0, not relevant**: different claim, or not a decision on such a complaint.

## OCR transcription

Type exactly what the page shows: same words, numbers and punctuation; Hindi in Devanagari. Line
breaks don't matter. Skip stamps, signatures and page headers you cannot read; write `[illegible]`
for unreadable words in the body.
