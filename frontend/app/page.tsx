import Link from "next/link";
import { Banner, PlusIcon } from "@/components/icons";
import { type CaseSummary, listCases } from "@/lib/cases-api";
import { demoCase } from "@/lib/demo-case";
import { fmtDate } from "@/lib/format";

const CLAIM: Record<string, string> = { delayed_possession: "Delayed possession", refund: "Refund", other: "Other" };

export const dynamic = "force-dynamic";

export default async function CasesPage() {
  let cases: CaseSummary[] = [];
  let error: string | null = null;
  try {
    cases = await listCases();
  } catch (e) {
    error = e instanceof Error ? e.message : "Could not load cases.";
  }
  const docs = cases.reduce((s, c) => s + c.documents, 0);
  const facts = cases.reduce((s, c) => s + c.facts, 0);

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Cases</h1>
          <p>Each case keeps its documents and the facts read from them, each linked to the exact page it came from.</p>
        </div>
        <Link href="/cases/new" className="btn btn-primary"><PlusIcon /> New case</Link>
      </div>

      {error && <div style={{ marginBottom: 16 }}><Banner tone="error"><b>Your cases could not be loaded.</b> {error}</Banner></div>}

      <div className="stats">
        <div className="panel stat">
          <div className="label">Your cases</div>
          <div className="stat-value">{error ? "—" : cases.length}</div>
          <div className="stat-note">{cases.filter((c) => c.is_demo).length} with demo documents</div>
        </div>
        <div className="panel stat">
          <div className="label">Documents</div>
          <div className="stat-value">{error ? "—" : docs}</div>
          <div className="stat-note">Stored privately on this computer</div>
        </div>
        <div className="panel stat">
          <div className="label">Verified facts</div>
          <div className="stat-value">{error ? "—" : facts}</div>
          <div className="stat-note">Each quoting its source page</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2 style={{ fontSize: 16 }}>All cases</h2>
          <span className="small faint">{cases.length} {cases.length === 1 ? "case" : "cases"} + 1 example</span>
        </div>
        <div className="table-wrap">
          <table className="ledger">
            <thead>
              <tr><th>Case</th><th>Claim</th><th className="r">Documents</th><th className="r">Facts</th><th>Status</th><th>Created</th></tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/cases/${c.id}/facts`} className="cell-title">{c.title}</Link>
                    {c.is_demo && <div className="cell-sub">Demo documents</div>}
                  </td>
                  <td>{CLAIM[c.claim_type] ?? c.claim_type}</td>
                  <td className="r num">{c.documents}</td>
                  <td className="r num">{c.facts}</td>
                  <td>
                    <span className={`tag ${c.facts ? "tag-pos" : c.documents ? "tag-mid" : "tag-neutral"}`}>
                      {c.facts ? "Facts found" : c.documents ? "Documents uploaded" : "New"}
                    </span>
                  </td>
                  <td className="num faint">{fmtDate(c.created_at.slice(0, 10))}</td>
                </tr>
              ))}
              <tr>
                <td>
                  <Link href={`/cases/${demoCase.id}/report`} className="cell-title">{demoCase.title}</Link>
                  <div className="cell-sub">Example with a full report (fictional)</div>
                </td>
                <td>{demoCase.claimType}</td>
                <td className="r num">{demoCase.documents.length}</td>
                <td className="r num">{demoCase.facts.length}</td>
                <td><span className="tag tag-neutral">Example</span></td>
                <td className="num faint">{fmtDate(demoCase.updated)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
