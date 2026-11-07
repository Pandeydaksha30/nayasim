import Link from "next/link";
import { Banner } from "@/components/icons";

/** Hearing, report and draft need steps 6-8 (search, citation checks, agents). Say so plainly. */
export default function NotBuilt({ what, caseId }: { what: string; caseId: string }) {
  return (
    <>
      <div className="section-title"><div><h2>{what}</h2></div></div>
      <Banner tone="info">
        <b>Not built yet.</b> The {what.toLowerCase()} needs the search over past orders, citation checks and the hearing
        agents (build steps 6–8). Nothing is shown here until it can be based on real, checked orders.{" "}
        <Link href="/cases/demo/report">See how it will look in the example case</Link>.
      </Banner>
      <p className="small faint" style={{ marginTop: 12 }}>
        <Link href={`/cases/${caseId}/money`}>Back to money owed</Link>
      </p>
    </>
  );
}
