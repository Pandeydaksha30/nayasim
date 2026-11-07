import Link from "next/link";
import InterestCalculator from "@/components/interest-calculator";

export const metadata = { title: "Delay interest calculator" };

export default function CalculatorPage() {
  return (
    <main className="page" style={{ maxWidth: 1080 }}>
      <h1>Delay interest calculator</h1>
      <p className="muted" style={{ margin: "8px 0 20px", maxWidth: "64ch" }}>
        Enter what you paid and when. The calculator works out interest on each payment separately, the way RERA orders do.
        For a full case report with past orders and a complaint draft, <Link href="/cases/new">start a case</Link>.
      </p>
      <InterestCalculator
        editablePayments
        payments={[
          { id: "p1", date: "2019-04-01", amount: 1000000, reference: "" },
          { id: "p2", date: "2020-01-15", amount: 1500000, reference: "" },
          { id: "p3", date: "2021-02-10", amount: 1000000, reference: "" },
        ]}
        possessionPromised="2021-12-31"
        extensionMonths={0}
        extensionBasis="Add months only if an extension order applies to your project."
        ratePct={10.85}
        rateBasis="UP RERA Rules r.15: SBI highest MCLR + 1%. Illustrative figure; check SBI's current MCLR."
        asOf="2026-11-07"
      />
    </main>
  );
}
