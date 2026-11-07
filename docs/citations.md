# Citation checker (step 7)

`app/verifier/citations.py` — `verify_citation(session, Citation(...), before=<cutoff>, allowed_orders=...)`.

The gate between the hearing agents (step 8) and the judge: a citation that fails any rule is
rejected with its reasons, and the argument relying on it is removed, so an invented or
misquoted precedent never reaches the buyer. All checks are code; no model is involved.

| # | Rule | Example rejection |
|---|---|---|
| 1 | The order exists in the store | `complaint RERA-GRG-99999-2020 is not in the store` |
| 2 | Order id and complaint number are the same order | `order id 12 is RERA-GRG-101-2022, not RERA-GRG-202-2024` |
| — | A complaint with several decisions must be cited by order id | `complaint … has 2 decisions; cite the order id` |
| 3 | The order's text is stored | `the order's text is not stored, so the quote cannot be checked` |
| 4 | Decided strictly before the case's cutoff | `decided on 2025-03-01, not before the cutoff 2025-01-01` |
| 5 | Among the orders retrieved for this case (if given) | `not among the orders retrieved for this case` |
| 6 | Quote on the cited page: ≥ 20 characters; exact, or ≥ 90% similar for OCR noise in letters, but **every number identical** | `quote not found on page 3`, `numbers in the quote (107, 2022) differ from the stored text (101, 2022)` |
| 7 | A claimed outcome matches the verified record (if one exists) | `says the outcome was dismissed, but the record says allowed` |

A verified citation returns the **stored** text and its offsets; downstream code shows that,
never the agent's own quote.

## Real-data check (7 Nov 2026)

12 citations built from real search results (cutoff 1 Jan 2025): all 12 genuine ones verified
(exact matches); tampered versions rejected — wrong page 12/12, invented complaint 12/12,
cutoff before the decision 12/12, wrong outcome 4/4 (where a record exists), one digit changed
10/10. The digit check was added after the first run let all 12 number-changed quotes through
on the ≥ 90% similarity rule.

What this does **not** check: whether the quoted passage actually supports the argument made
with it. That needs judgement; the plan measures it by hand on a sample (target 95%).
