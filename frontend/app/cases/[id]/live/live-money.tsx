import { Banner } from "@/components/icons";
import InterestCalculator from "@/components/interest-calculator";
import { type CaseFull, paymentsFromFacts } from "@/lib/cases-api";

// No legal rate is asserted here: the starting value is illustrative and labelled as such.
const RATE_BASIS =
  "10.85% is an illustrative starting value, not the rate for your case. Enter the rate the authority applies " +
  "under its state rules (tied to SBI's MCLR), checked against the current circular.";

export default function LiveMoney({ c }: { c: CaseFull }) {
  const payments = paymentsFromFacts(c.facts);
  const promised = c.facts.find((f) => f.key === "possession_promised")?.value;
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
            ratePct={10.85}
            rateBasis={RATE_BASIS}
            asOf={today}
          />
        </>
      )}
    </>
  );
}
