# ruff: noqa: E501  (long legal sentences are kept on one line each)
"""Complaint draft assembled by code from what is already verified.

Sources, and nothing else:
- the buyer's facts (each tied to a document page), and their answers;
- the deterministic calculator's figures stored with the latest completed hearing;
- citations from that hearing whose quote was verified against the stored order.

No model is called here. Anything not known is left as a bracketed blank and listed under
"missing", never guessed. The draft is a starting point to be checked by the complainant or
their advocate before filing; it follows the Haryana authority (Gurugram), the only one covered.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Case, CaseAnswer, CaseDocument, Fact, HearingRun

KIND_LABEL = {
    "agreement": "Builder-buyer agreement",
    "allotment_letter": "Allotment letter",
    "receipt": "Payment receipts",
    "builder_letter": "Letter from the respondent",
    "hearing_order": "Order of the authority",
    "other": "Other document",
}


def _d(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def _rs(amount: str | Decimal) -> str:
    """Indian digit grouping: 3240000 -> Rs. 32,40,000/-"""
    n = int(Decimal(str(amount)).quantize(Decimal(1)))
    s = str(abs(n))
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"Rs. {','.join([*groups, tail])}/-"


def build_draft(s: Session, case: Case) -> dict:
    docs = {
        d.id: d
        for d in s.scalars(
            select(CaseDocument)
            .where(CaseDocument.case_id == case.id)
            .order_by(CaseDocument.uploaded_at, CaseDocument.filename)
        )
    }
    annex = {doc_id: f"P-{i}" for i, doc_id in enumerate(docs, start=1)}
    facts = list(s.scalars(select(Fact).where(Fact.case_id == case.id).order_by(Fact.id)))
    answers = {
        a.question_id: a.answer for a in s.scalars(select(CaseAnswer).where(CaseAnswer.case_id == case.id))
    }
    run = s.scalar(
        select(HearingRun)
        .where(HearingRun.case_id == case.id, HearingRun.status == "completed")
        .order_by(HearingRun.started_at.desc())
    )
    result = run.result if run else {}
    missing: list[str] = []
    unconfirmed = sum(1 for f in facts if not f.confirmed)

    def first(key: str) -> Fact | None:
        return next((f for f in facts if f.key == key), None)

    def src(f: Fact) -> str:
        d = docs.get(f.document_id)
        return (
            f"(Annexure {annex.get(f.document_id, '?')}: {d.filename if d else 'document'}, page {f.page_no})"
        )

    def val(key: str, label: str) -> str:
        f = first(key)
        if f is None:
            missing.append(label)
            return f"[{label}: not found in the uploaded documents]"
        return f.value

    builder, unit = first("builder_name"), first("unit")
    reg, agreement, price = first("rera_registration"), first("agreement_date"), first("total_price")
    promised, clause = first("possession_promised"), first("delay_compensation_clause")
    revised, escalation = first("revised_completion_date"), first("escalation_demand")
    offer = first("offer_of_possession_date")
    payments = sorted((f for f in facts if f.key == "payment"), key=lambda f: f.value)
    total_paid = sum((Decimal(f.value.split(";")[1]) for f in payments), Decimal(0))
    refund = case.claim_type == "refund"
    missing.append("Complainant's full name, address and contact details")

    sections: list[dict] = []
    sections.append(
        {
            "heading": "1. Particulars of the project and the unit",
            "paragraphs": [
                f"1.1 The Respondent, {val('builder_name', 'Name of the promoter')}, is the promoter of the project "
                f"{val('project_name', 'Name of the project')}"
                + (f", registered under number {reg.value} {src(reg)}" if reg else "")
                + ".",
                f"1.2 The unit allotted to the Complainant is {val('unit', 'Unit number')}"
                + (f" {src(unit)}" if unit else "")
                + ".",
            ],
        }
    )

    f_paras = []
    n = 1
    if agreement or price:
        f_paras.append(
            f"2.{n} "
            + (
                f"The parties executed an agreement for sale on {_d(agreement.value)} {src(agreement)}"
                if agreement
                else "The parties executed an agreement for sale [date not found in the uploaded documents]"
            )
            + (f", for a total price of {_rs(price.value)} {src(price)}." if price else ".")
        )
        n += 1
    if not agreement:
        missing.append("Date of the agreement for sale")
    if promised:
        f_paras.append(
            f"2.{n} Under the agreement the Respondent was to hand over possession on or before "
            f"{_d(promised.value)} {src(promised)}."
        )
    else:
        missing.append("Promised date of possession")
        f_paras.append(f"2.{n} [Promised date of possession: not found in the uploaded documents]")
    n += 1
    if payments:
        lines = "; ".join(
            f"{_rs(f.value.split(';')[1])} on {_d(f.value.split(';')[0])} {src(f)}" for f in payments
        )
        f_paras.append(
            f"2.{n} The Complainant has paid the Respondent {_rs(total_paid)} in {len(payments)} "
            f"payment(s): {lines}."
        )
    else:
        missing.append("Payments made to the promoter, with receipts")
        f_paras.append(f"2.{n} [Payments made: no receipt was read from the uploaded documents]")
    n += 1
    if clause:
        f_paras.append(
            f"2.{n} The agreement provides for compensation for delay as follows: {clause.value} {src(clause)}."
        )
        n += 1
    if revised or escalation:
        parts = []
        if revised:
            parts.append(f"stated a revised completion date of {_d(revised.value)} {src(revised)}")
        if escalation:
            parts.append(f"demanded a further sum of {_rs(escalation.value)} {src(escalation)}")
        f_paras.append(f"2.{n} The Respondent has since " + " and ".join(parts) + ".")
        n += 1
    answer = answers.get("offer_of_possession")
    if offer:
        f_paras.append(f"2.{n} An offer of possession was made on {_d(offer.value)} {src(offer)}.")
    elif answer == "No":
        f_paras.append(f"2.{n} No offer of possession has been made to the Complainant to date.")
    elif answer:
        f_paras.append(f"2.{n} As to an offer of possession, the Complainant states: {answer}.")
    else:
        missing.append("Whether a written offer of possession was received (answer the question in step 3)")
        f_paras.append(f"2.{n} [Offer of possession: not yet answered]")
    sections.append({"heading": "2. Facts of the case", "paragraphs": f_paras})

    grounds = [
        "3.1 Section 18(1) of the Real Estate (Regulation and Development) Act, 2016 provides that where the "
        "promoter fails to give possession in accordance with the agreement for sale, an allottee who wishes "
        "to withdraw from the project is entitled to return of the amount paid with interest, and an allottee "
        "who does not intend to withdraw shall be paid interest for every month of delay till the handing "
        "over of possession, at the prescribed rate."
    ]
    cited: list[dict] = []
    seen: set[tuple] = set()
    pool = [c for a in result.get("arguments", {}).get("buyer", []) for c in a.get("citations", [])]
    for c in pool:
        key = (c.get("order_id"), c.get("page_no"), c.get("quote"))
        if c.get("status") != "verified" or key in seen:
            continue
        seen.add(key)
        cited.append(c)
    for i, c in enumerate(cited, start=2):
        quote = " ".join(str(c.get("stored_quote") or c["quote"]).split())
        grounds.append(
            f"3.{i} In Complaint No. {c['complaint_no']}, decided on {_d(c['decided_on'])}, the Haryana Real "
            f"Estate Regulatory Authority, Gurugram recorded (page {c['page_no']} of the order): “{quote}”"
        )
    if not run:
        missing.append("Checked precedents (run the simulated hearing to add them)")
    elif not cited:
        missing.append("Checked precedents (the last hearing produced no verified citation for the buyer)")
    sections.append({"heading": "3. Grounds", "paragraphs": grounds})

    award = result.get("award") or {}
    relief = []
    if refund:
        text = (
            "(a) Refund of the entire amount paid"
            + (f", being {_rs(total_paid)}," if payments else "")
            + " with interest at the rate prescribed under Rule 15 of the Haryana Real Estate (Regulation and "
            "Development) Rules, 2017 from the date of each payment until refund"
        )
        if award.get("available"):
            text += (
                f"; calculated at {award['rate_pct']}% a year this comes to {_rs(award['refund_total'])} "
                f"in all as on {_d(award['as_of'])}"
            )
        relief.append(text + ";")
    else:
        text = (
            "(a) Interest under the proviso to Section 18(1) on each payment, at the rate prescribed under "
            "Rule 15 of the Haryana Real Estate (Regulation and Development) Rules, 2017, "
            + (f"from {_d(promised.value)} " if promised else "from the promised date of possession ")
            + "until possession is handed over"
        )
        if award.get("available") and award.get("delay_interest"):
            text += (
                f"; calculated at {award['rate_pct']}% a year this comes to {_rs(award['delay_interest'])} "
                f"as on {_d(award['as_of'])}"
            )
        relief.append(text + ";")
        relief.append("(b) a direction to the Respondent to hand over possession within a fixed time;")
    if escalation:
        relief.append(
            f"({'b' if refund else 'c'}) a declaration that the further sum of {_rs(escalation.value)} "
            "demanded by the Respondent is not payable;"
        )
    relief.append(f"({'abcd'[len(relief)]}) any other relief the Authority considers fit.")
    if not award.get("available"):
        missing.append("Amount claimed (run the simulated hearing, or use the Money owed step)")
    sections.append({"heading": "4. Relief sought", "paragraphs": relief})

    ann = [f"{annex[i]}: {KIND_LABEL.get(d.kind, d.kind)} ({d.filename})" for i, d in docs.items()]
    ann.append(f"P-{len(docs) + 1}: Interest calculation")
    sections.append({"heading": "5. Annexures", "paragraphs": ann})
    sections.append(
        {
            "heading": "6. Verification",
            "paragraphs": [
                "I, [Complainant's full name], the Complainant, verify that the contents of this complaint are "
                "true to my knowledge and belief and that nothing material has been concealed. "
                "[Place, date and signature]"
            ],
        }
    )

    notes = []
    if award.get("available"):
        notes.append(
            {
                "label": "Interest rate",
                "text": f"The figure uses {award['rate_pct']}% ({award['rate_basis']}). The Authority applies "
                "the rate prescribed on the date of its order; check the current rate before filing.",
            }
        )
    for w in (result.get("judge") or {}).get("weak_points", [])[:4]:
        notes.append(
            {"label": f"Weak point: {w.get('title', '')}", "text": w.get("fix") or w.get("detail", "")}
        )
    if unconfirmed:
        notes.append(
            {
                "label": "Unconfirmed facts",
                "text": f"{unconfirmed} fact(s) used here have not been confirmed by you. Confirm them in step 2.",
            }
        )

    header = [
        "BEFORE THE HARYANA REAL ESTATE REGULATORY AUTHORITY, GURUGRAM",
        "Complaint under Section 31 of the Real Estate (Regulation and Development) Act, 2016",
        f"[Complainant's full name] ... Complainant  versus  {builder.value if builder else '[Promoter]'} ... Respondent",
    ]
    text = "\n\n".join([*header, *(sec["heading"] + "\n" + "\n".join(sec["paragraphs"]) for sec in sections)])
    return {
        "case_id": str(case.id),
        "claim_type": case.claim_type,
        "header": header,
        "sections": sections,
        "notes": notes,
        "missing": missing,
        "based_on_hearing": run.id if run else None,
        "verified_citations": len(cited),
        "disclaimer": "Assembled by code from your verified facts and checked citations. It is a draft to be "
        "reviewed by you or your advocate before filing, not legal advice. It follows the Haryana authority "
        "at Gurugram; check which authority has jurisdiction over your project.",
        "text": text,
    }
