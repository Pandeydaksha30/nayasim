import Link from "next/link";
import { DeleteCaseButton } from "@/components/case-actions";
import { Banner, PlusIcon } from "@/components/icons";
import { type CaseFull, type CaseSummary, getCase, listCases } from "@/lib/cases-api";
import { fmtDate } from "@/lib/format";
import { EXAMPLE_ID, exampleRecordedAt } from "@/lib/http";
import { requireUser, sessionAuth } from "@/lib/server-session";
import styles from "./dashboard.module.css";

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
  const shared = cases.filter((c) => c.shared);
  let example: CaseFull | null = null;
  let recorded = "";
  try {
    example = await getCase(EXAMPLE_ID);
    recorded = (await exampleRecordedAt()).slice(0, 10);
  } catch {
    example = null;
  }

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <div className={`label ${styles.welcome}`}>{user.name ? `Welcome back, ${user.name.split(" ")[0]}` : "Welcome back"}</div>
          <h1>Your cases</h1>
          <p>Each case keeps its documents and the facts read from them, each linked to the exact page it came from.</p>
        </div>
        <Link href="/cases/new" className="btn btn-primary"><PlusIcon /> New case</Link>
      </div>

      {error && <div className={styles.gap}><Banner tone="error"><b>Your cases could not be loaded.</b> {error}</Banner></div>}

      {!error && own.length === 0 && (
        <section className={`panel ${styles.empty}`}>
          <h2>Start with your agreement and receipts</h2>
          <p className="muted">
            Upload the builder-buyer agreement and your payment receipts. ContractIQ reads them, shows each fact on the page it
            came from, and works out the delay interest payment by payment.
          </p>
          <div className={styles.emptyActions}>
            <Link href="/cases/new" className="btn btn-primary"><PlusIcon /> Start a case</Link>
            <Link href={`/cases/${EXAMPLE_ID}/report`} className="btn">Look at the example first</Link>
          </div>
        </section>
      )}

      {own.length > 0 && (
        <div className="panel">
          <div className="panel-head">
            <h2 className={styles.h}>Your cases</h2>
            <span className="small faint">{own.length} {own.length === 1 ? "case" : "cases"} · visible only to your account</span>
          </div>
          <div className="table-wrap">
            <table className="ledger stack">
              <thead>
                <tr><th>Case</th><th>Claim</th><th className="r">Documents</th><th className="r">Facts</th><th>Status</th><th>Created</th><th className="r">Remove</th></tr>
              </thead>
              <tbody>
                {own.map((c) => (
                  <tr key={c.id}>
                    <td data-label="Case">
                      <Link href={`/cases/${c.id}/${c.documents ? "facts" : "documents"}`} className="cell-title">{c.title}</Link>
                      {c.is_demo && <div className="cell-sub">Demo documents</div>}
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
                    <td data-label="Remove" className="r"><DeleteCaseButton caseId={c.id} title={c.title} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(example || shared.length > 0) && (
        <div className={`panel ${styles.examples}`}>
          <div className="panel-head">
            <h2 className={styles.h}>Examples</h2>
            <span className="small faint">Fictional buyer and documents · read-only</span>
          </div>
          <div className="table-wrap">
            <table className="ledger stack">
              <thead>
                <tr><th>Case</th><th>Claim</th><th className="r">Documents</th><th className="r">Facts</th><th>What it shows</th><th>Recorded</th></tr>
              </thead>
              <tbody>
                {example && (
                  <tr>
                    <td data-label="Case">
                      <Link href={`/cases/${EXAMPLE_ID}/report`} className="cell-title">{example.title}</Link>
                      <div className="cell-sub">Recorded from a real run</div>
                    </td>
                    <td data-label="Claim">{CLAIM[example.claim_type] ?? example.claim_type}</td>
                    <td data-label="Documents" className="r num">{example.documents.length}</td>
                    <td data-label="Facts" className="r num">{example.facts.length}</td>
                    <td data-label="What it shows">Every step, from documents to the complaint draft</td>
                    <td data-label="Recorded" className="num faint">{recorded ? fmtDate(recorded) : ""}</td>
                  </tr>
                )}
                {shared.map((c) => (
                  <tr key={c.id}>
                    <td data-label="Case">
                      <Link href={`/cases/${c.id}/facts`} className="cell-title">{c.title}</Link>
                      <div className="cell-sub">Shared on this server</div>
                    </td>
                    <td data-label="Claim">{CLAIM[c.claim_type] ?? c.claim_type}</td>
                    <td data-label="Documents" className="r num">{c.documents}</td>
                    <td data-label="Facts" className="r num">{c.facts}</td>
                    <td data-label="What it shows">Live on this server</td>
                    <td data-label="Recorded" className="num faint">{fmtDate(c.created_at.slice(0, 10))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}
