import { notFound } from "next/navigation";
import { getCase } from "@/lib/demo-case";
import { computeInterest } from "@/lib/api";
import { fmtDate, fmtINR } from "@/lib/format";
import styles from "./draft.module.css";

export const metadata = { title: "Complaint draft" };

export default async function DraftPage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase((await params).id);
  if (!c) notFound();
  let result;
  try {
    result = await computeInterest({
      payments: c.payments,
      possessionPromised: c.possessionPromised,
      extensionMonths: c.extensionMonths,
      annualRatePct: c.ratePct,
      asOf: c.asOf,
      rateSource: c.rateBasis,
    });
  } catch (e) {
    return (
      <div role="alert" style={{ borderLeft: "3px solid var(--neg)", background: "var(--neg-soft)", padding: "12px 16px" }}>
        <b>The draft needs the interest calculation, which failed.</b> {e instanceof Error ? e.message : ""}
      </div>
    );
  }
  const due = result.possession_due;
  const calc = { principal: Number(result.delay.principal), interest: Number(result.delay.interest) };

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Complaint draft</h2>
          <p>Follows the UP RERA complaint format. Notes in the margin show where the draft answers a weak point from your report.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn">Copy text</button>
          <button type="button" className="btn btn-primary">Download .docx</button>
        </div>
      </div>

      <div className={styles.layout}>
        <article className={styles.doc}>
          <p className={styles.center}><b>BEFORE THE UTTAR PRADESH REAL ESTATE REGULATORY AUTHORITY</b></p>
          <p className={styles.center}>Complaint under Section 31 of the Real Estate (Regulation and Development) Act, 2016</p>
          <p className={styles.parties}>
            {c.buyer} … Complainant
            <br />versus<br />
            {c.builder} … Respondent
          </p>

          <h4>1. Particulars of the project</h4>
          <p>
            {c.project}, {c.location}, registered under number {c.reraNo}. Apartment {c.unit}.
          </p>

          <h4>2. Facts of the case</h4>
          <p>
            2.1 The Complainant booked the apartment on 12 March 2018 and executed an agreement for sale on 2 May 2018 for a total
            price of {fmtINR(c.price)}.
          </p>
          <p>
            2.2 Under clause 7.1 the Respondent was to hand over possession on or before {fmtDate(c.possessionPromised)}. Allowing
            the extension of {c.extensionMonths} months granted for COVID-19, possession fell due on {fmtDate(due)}.
          </p>
          <p id="para-payments">
            2.3 The Complainant has paid {fmtINR(calc.principal)} in {c.payments.length} instalments as demanded, the details of
            which, with bank statement entries, are at Annexure P-3. The instalment of 20 November 2021 was paid only to avoid
            cancellation and forfeiture, and not in acceptance of any delay.
          </p>
          <p>
            2.4 By letter dated 10 February 2024 the Respondent stated a revised completion date of 31 December 2025 and demanded a
            cost escalation of 2% of the price, for which the agreement makes no provision. No offer of possession has been made.
          </p>

          <h4>3. Relief sought</h4>
          <p>
            (a) Interest under the proviso to Section 18(1) at the rate prescribed by Rule 15 on each payment from {fmtDate(due)}{" "}
            until a valid offer of possession with an occupancy certificate, amounting to {fmtINR(calc.interest)} as on{" "}
            {fmtDate(c.asOf)} (calculation at Annexure P-5);
            <br />(b) a direction to hand over possession within a fixed time;
            <br />(c) a declaration that the escalation demand is not payable.
          </p>

          <h4>4. Annexures</h4>
          <p className={styles.annex}>
            P-1 Agreement for sale · P-2 Allotment letter · P-3 Payment receipts and bank statement entries · P-4 Respondent’s
            letter of 10 Feb 2024 · P-5 Interest calculation · P-6 Notice to the Respondent and proof of dispatch
          </p>
        </article>

        <aside className={styles.notes}>
          <div className={styles.note} style={{ marginTop: 300 }}>
            <span className="label">Answers weak point 1</span>
            Explains the November 2021 payment so it cannot be read as acceptance of delay.
          </div>
          <div className={styles.note}>
            <span className="label">Answers weak point 2</span>
            Bank statement entries added as proof for the two unclear receipts.
          </div>
          <div className={styles.note}>
            <span className="label">Answers weak point 3</span>
            Annexure P-6 needs the notice you send before filing.
          </div>
        </aside>
      </div>
    </>
  );
}
