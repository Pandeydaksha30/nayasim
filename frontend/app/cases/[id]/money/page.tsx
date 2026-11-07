import { notFound } from "next/navigation";
import InterestCalculator from "@/components/interest-calculator";
import { getCase } from "@/lib/demo-case";

export const metadata = { title: "Money owed" };

export default async function MoneyPage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase((await params).id);
  if (!c) notFound();
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
