import { Banner } from "@/components/icons";
import InterestCalculator from "@/components/interest-calculator";
import { type CaseFull, isUsable, paymentsFromFacts } from "@/lib/cases-api";

// The rule is verified (774 stored HRERA orders reproduce Rule 15); the figure changes with SBI's MCLR.
const RATE_BASIS =
  "Haryana RERA Rules 2017, Rule 15: SBI highest MCLR + 2%. HRERA Gurugram orders of Jul–Oct 2026 apply " +
  "10.80% (MCLR 8.80% + 2%). Check SBI's MCLR on the date of your order (sbi.co.in).";

export default function LiveMoney({ c }: { c: CaseFull }) {
  const payments = paymentsFromFacts(c.facts);
  const promised = c.facts.find((f) => f.key === "possession_promised")?.value;
  const offer = c.facts.find((f) => f.key === "offer_of_possession_date" && isUsable(f))?.value;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <>
      <div className="section-title">
        <div>
          <h2>What you could be owed</h2>
          <p>Calculated by code from the payments verified in your documents. Change the inputs to see how the figure moves.</p>
        </div>
      </div>
      {payments.length === 0 ? (
        <Banner tone="warn">
          <b>No verified payments yet.</b> Upload payment receipts (and, for demo documents, use “Find facts”) to calculate
          interest. Nothing is estimated without them.
        </Banner>
      ) : (
        <>
          {!promised && (
            <div style={{ marginBottom: 12 }}>
              <Banner tone="warn">The promised possession date was not found in your documents; enter it below.</Banner>
            </div>
          )}
          <InterestCalculator
            payments={payments}
            possessionPromised={promised ?? ""}
            extensionMonths={0}
            extensionBasis="Add months only if an extension order applies to your project."
            ratePct={10.8}
            offerOfPossession={offer}
            rateBasis={RATE_BASIS}
            asOf={today}
          />
        </>
      )}
    </>
  );
}
