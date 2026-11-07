import LiveMoney from "../live/live-money";
import { loadCase } from "@/lib/case-source";
import InterestCalculator from "@/components/interest-calculator";

export const metadata = { title: "Money owed" };

export default async function MoneyPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "live") return <LiveMoney c={src.data} />;
  if (src.kind !== "example") return null; // the layout shows the error
  const c = src.data;
  return (
    <>
      <div className="section-title">
        <div>
          <h2>What you could be owed</h2>
          <p>
            Calculated by code from your receipts, not estimated by AI. Change the inputs to see how the figure moves. The
            agreement’s ₹5 per sq ft clause is ignored here because the statutory rate is usually applied instead.
          </p>
        </div>
      </div>
      <InterestCalculator
        payments={c.payments}
        possessionPromised={c.possessionPromised}
        extensionMonths={c.extensionMonths}
        extensionBasis={c.extensionBasis}
        ratePct={c.ratePct}
        rateBasis={c.rateBasis}
        asOf={c.asOf}
      />
    </>
  );
}
