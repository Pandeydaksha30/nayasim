import Link from "next/link";
import { Banner, PlusIcon } from "@/components/icons";
import { type CaseSummary, listCases } from "@/lib/cases-api";
import { demoCase } from "@/lib/demo-case";
import { fmtDate } from "@/lib/format";
import { requireUser, sessionAuth } from "@/lib/server-session";

const CLAIM: Record<string, string> = { delayed_possession: "Delayed possession", refund: "Refund", other: "Other" };

export const dynamic = "force-dynamic";
export const metadata = { title: "Your cases" };

export default async function CasesPage() {
  const user = await requireUser("/dashboard");
  let cases: CaseSummary[] = [];
  let error: string | null = null;
  try {
    cases = await listCases(await sessionAuth());
  } catch (e) {
    error = e instanceof Error ? e.message : "Could not load cases.";
  }
  const own = cases.filter((c) => !c.shared);
  const docs = own.reduce((s, c) => s + c.documents, 0);
  const facts = own.reduce((s, c) => s + c.facts, 0);

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <div className="label" style={{ marginBottom: 6 }}>{user.name ? `Welcome back, ${user.name.split(" ")[0]}` : "Welcome back"}</div>
          <h1>Your cases</h1>
          <p>Each case keeps its documents and the facts read from them, each linked to the exact page it came from.</p>
        </div>
        <Link href="/cases/new" className="btn btn-primary"><PlusIcon /> New case</Link>
      </div>

      {error && <div style={{ marginBottom: 16 }}><Banner tone="error"><b>Your cases could not be loaded.</b> {error}</Banner></div>}

      <div className="stats">
        <div className="panel stat">
          <div className="label">Your cases</div>
          <div className="stat-value">{error ? "—" : own.length}</div>
          <div className="stat-note">{own.length === 0 ? "Start one with your agreement and receipts" : `${own.filter((c) => c.is_demo).length} with demo documents`}</div>
        </div>
        <div className="panel stat">
          <div className="label">Documents</div>
          <div className="stat-value">{error ? "—" : docs}</div>
          <div className="stat-note">Visible only to your account</div>
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
          <span className="small faint">{own.length} {own.length === 1 ? "case" : "cases"} + {cases.length - own.length + 1} shared {cases.length - own.length + 1 === 1 ? "example" : "examples"}</span>
        </div>
        <div className="table-wrap">
          <table className="ledger stack">
            <thead>
              <tr><th>Case</th><th>Claim</th><th className="r">Documents</th><th className="r">Facts</th><th>Status</th><th>Created</th></tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td data-label="Case">
                    <Link href={`/cases/${c.id}/facts`} className="cell-title">{c.title}</Link>
                    {c.shared ? <div className="cell-sub">Shared example (read-only)</div> : c.is_demo && <div className="cell-sub">Demo documents</div>}
                  </td>
                  <td data-label="Claim">{CLAIM[c.claim_type] ?? c.claim_type}</td>
                  <td data-label="Documents" className="r num">{c.documents}</td>
                  <td data-label="Facts" className="r num">{c.facts}</td>
                  <td data-label="Status">
                    <span className={`tag ${c.facts ? "tag-pos" : c.documents ? "tag-mid" : "tag-neutral"}`}>
                      {c.facts ? "Facts found" : c.documents ? "Documents uploaded" : "New"}
                    </span>
                  </td>
                  <td data-label="Created" className="num faint">{fmtDate(c.created_at.slice(0, 10))}</td>
                </tr>
              ))}
              <tr>
                <td data-label="Case">
                  <Link href={`/cases/${demoCase.id}/report`} className="cell-title">{demoCase.title}</Link>
                  <div className="cell-sub">Example with a full report (fictional)</div>
                </td>
                <td data-label="Claim">{demoCase.claimType}</td>
                <td data-label="Documents" className="r num">{demoCase.documents.length}</td>
                <td data-label="Facts" className="r num">{demoCase.facts.length}</td>
                <td data-label="Status"><span className="tag tag-neutral">Example</span></td>
                <td data-label="Created" className="num faint">{fmtDate(demoCase.updated)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
