# Financial claim calculator: audit

Audited 17 Nov 2026 against the code (`backend/app/calculator/interest.py`), every place that uses
it, and the public HRERA Gurugram orders stored in the project's database (2,209 orders with text).
Where a statement is supported by those orders, the number of orders containing it is given;
anything that could not be checked against an authoritative source is marked **Not verified**.

## 1. Who computes the money

| Figure | Computed by | Where |
|---|---|---|
| Delay interest, refund interest, refund total | **Deterministic Python** (Decimal arithmetic) | `app/calculator/interest.py` |
| Calculator page and "Money owed" step | Same code, through `POST /api/v1/calculations/interest` | `app/api/calculations.py`, `frontend/components/interest-calculator.tsx` |
| Award figure on the report | Same code; the rate is taken from a stored order | `app/hearing/stats.py` (`award`) |
| Agent tool `calculate_interest` | Same code; the model only passes the rate given by the user | `app/agent/tools.py` |
| Complaint draft amounts | Copied from the report's award, by code | `app/insights/draft.py` |

**No language model produces an amount.** The hearing's advocates and judge are told not to
calculate money (`app/hearing/agents.py`, `RULES`). The agent's tool description says the rate
must come from the objective or task; the model cannot change the arithmetic.

## 2. Formulas

All interest is **simple interest, worked out per payment, on a 365-day year**:

```
interest(payment) = amount × rate% × days ÷ (100 × 365)      rounded half-up to the paisa
total interest    = sum of the rounded rows
```

| Claim | Interest runs from | Interest runs to |
|---|---|---|
| **Delay interest** (buyer keeps the unit) | the later of the payment date and the possession due date | the earliest of: the calculation date; **offer of possession + 2 months**; actual handover |
| **Refund** (buyer withdraws) | each payment's own date | the calculation date (the date of refund); the principal is returned on top |

Possession due date = promised date + extension months (calendar months, clamped to month end).

## 3. Legal basis, and what supports each part

| Part of the method | Source | Checked how |
|---|---|---|
| Delay interest "for every month of delay, till the handing over of the possession, at such rate as may be prescribed" | RERA Act 2016, **s.18(1) proviso** | Quoted in stored orders, e.g. RERA-GRG-5929-2025 (13.10.2026) |
| Refund "with interest at such rate as may be prescribed" when the promoter fails to give possession | RERA Act 2016, **s.18(1)(a)** | Quoted in stored orders, e.g. RERA-GRG-127-2025 (25.08.2026) |
| Rate = "State Bank of India highest marginal cost of lending rate + 2%" | **Haryana RERA Rules 2017, Rule 15** | Reproduced word for word in **774** stored orders |
| Same rate for promoter and allottee in default | RERA Act s.2(za) | Discussed in **351** stored orders |
| Rate actually applied, Jul–Oct 2026: **10.80%** (MCLR 8.80% + 2%) | HRERA orders | e.g. RERA-GRG-919-2022 (08.10.2026), RERA-GRG-1150-2026 (18.09.2026) |
| Refund interest "from the date of each payment till the actual date of refund" | HRERA orders | e.g. RERA-GRG-919-2022 |
| Delay interest "till offer of possession plus two months or actual handing over of possession, whichever is earlier" | HRERA orders | Found in **64** stored orders, e.g. RERA-GRG-5139-2025 (29.09.2026) |
| The two months are the allottee's time to take possession after the occupation certificate | RERA Act s.19(10) | **Not verified** in this audit (not quoted in a stored order found by the search); stated from the Act |
| 6-month extension for COVID-19 | HRERA notification no. 9/3-2020 dated 26.05.2020 | Cited in **250** stored orders. Whether it applies is decided per project; it is an input |
| Interest computed per payment from the due date (payments before the due date earn from the due date) | HRERA orders compute DPC on the amount paid from the due date | Practice in orders; consistent with the code |
| Simple interest, 365-day year, rounding to the paisa | Not stated in the Act or Rule 15 | **Convention, not legally verified.** Orders state "% p.a." without compounding; simple interest matches the orders read, but no rule prescribes the day count |
| Pro rata by day, although the Act says "for every month of delay" | — | **Convention, not legally verified.** A month-by-month count gives slightly different figures |

Other states have their own rules (for example a different margin over MCLR). The project's data
covers HRERA Gurugram only, so the calculator is presented for Haryana. **The figure for another
state is not verified.**

## 4. Inputs

| Input | Required | Source in the app |
|---|---|---|
| Payments (date, amount) | Yes | Verified payment facts from receipts, or typed in |
| Promised possession date | Yes (delay interest) | Verified fact from the agreement, or typed in |
| Extension months | No (default 0) | Typed in; for COVID-19 usually 6, if the order allows it |
| Annual rate | Yes | Typed in; starting value 10.80% with its source shown |
| Calculate up to | Yes | Today by default |
| Offer of possession date | No | Verified fact from a builder letter, or typed in |
| Actual handover date | No (API only) | `possession_handed_over` |

## 5. Sample cases (all computed separately by hand and checked by tests)

Rate 10.80%, due date 30.06.2021, Rs 10,00,000 paid 01.01.2020, calculation date 17.11.2026.

| Case | Days | Interest |
|---|---|---|
| Delay interest, no offer yet (to 17.11.2026) | 1,966 | Rs 5,81,720.55 |
| Offer of possession 01.03.2025, so to 01.05.2025 | 1,401 | Rs 4,14,542.47 |
| Handed over 15.03.2025 (earlier than offer + 2 months) | 1,354 | Rs 4,00,635.62 |
| Rs 5,00,000 paid **after** the due date (10.01.2022), to 01.05.2025 | 1,207 | Rs 1,78,569.86 (from the payment date) |
| Refund of Rs 10,00,000 paid 01.01.2020, to 17.11.2026 | 2,512 | Rs 7,43,276.71 interest; Rs 17,43,276.71 total |

Tests: `backend/tests/test_interest.py` (sample cases, end-date rule) and
`backend/tests/test_api_calculations.py` (API, including the offer of possession).

## 6. Problems found and fixed in this audit

| # | Problem | Effect | Fix |
|---|---|---|---|
| 1 | Delay interest always ran to "today", ignoring an offer of possession | Overstated delay interest for every buyer who had received an offer | `delay_end()`: offer + 2 months or handover, whichever is earlier; used by the calculator, the report and the agent |
| 2 | The calculator page cited "UP RERA Rules r.15: SBI highest MCLR + 1%" | An unverified legal statement, and the wrong state for the data used | Replaced by Haryana Rule 15 (MCLR + 2%), verified from 774 orders |
| 3 | Starting rate 10.85% | Out of date: orders from Jul–Oct 2026 apply 10.80% | 10.80%, with the orders named; still an input |
| 4 | The report's award used the **median** rate of similar orders | Mixed rates from different years (e.g. 9.30% from 2021) although Rule 15 uses MCLR "as on date" | Uses the rate of the most recently decided similar order, and names it |
| 5 | A test compared money as floating-point numbers | Failed on some dates | Compares Decimal values exactly |

## 7. Limitations that remain (not computed; shown or documented)

- **Compensation already credited by the builder** is deducted in orders (e.g. RERA-GRG-5139-2025);
  the calculator does not deduct it. Subtract it by hand.
- The agreement's own delay clause (e.g. Rs 5 per sq ft per month) is not applied; orders apply the
  prescribed rate instead. The example case's money page says so; a real case's page does not yet.
- Taxes, maintenance, holding charges, escalation demands and any amount the buyer owes the
  builder (s.2(za) works both ways) are not netted off.
- Compensation for loss, harassment or litigation cost (adjudged separately) is not estimated.
- Whether a COVID-19 or other extension applies is a legal question for the authority; the app
  takes it as an input.
- The rate must be the SBI MCLR on the date of the order; the app cannot fetch it.
- Simple interest by day and the 365-day year are conventions (section 3).

The calculator is decision support for preparing a complaint. The figure in an actual order is
the authority's.
