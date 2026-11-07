import Link from "next/link";
import { PlusIcon } from "@/components/icons";
import { demoCase } from "@/lib/demo-case";
import { fmtDate, fmtINRShort, pct } from "@/lib/format";

export default function CasesPage() {
  const cases = [demoCase];
  const paid = cases.reduce((s, c) => s + c.payments.reduce((t, p) => t + p.amount, 0), 0);
  const ready = cases.filter((c) => c.status === "Report ready").length;

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Cases</h1>
          <p>Each case keeps its documents, facts and reports. Add a new builder letter or hearing order and the report updates.</p>
        </div>
        <Link href="/cases/new" className="btn btn-primary"><PlusIcon /> New case</Link>
      </div>

      <div className="stats">
        <div className="panel stat">
          <div className="label">Open cases</div>
          <div className="stat-value">{cases.length}</div>
          <div className="stat-note">{ready} with a report ready</div>
        </div>
        <div className="panel stat">
          <div className="label">Amount paid to builders</div>
          <div className="stat-value">{fmtINRShort(paid)}</div>
          <div className="stat-note">Across all open cases</div>
        </div>
        <div className="panel stat">
          <div className="label">Past orders compared</div>
          <div className="stat-value">{cases.reduce((s, c) => s + c.report.similarCount, 0)}</div>
          <div className="stat-note">Similar final orders found</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2 style={{ fontSize: 16 }}>All cases</h2>
          <span className="small faint">{cases.length} case</span>
        </div>
        <div className="table-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Case</th>
                <th>Project</th>
                <th>Claim</th>
                <th className="r">Paid</th>
                <th className="r">Similar cases won</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/cases/${c.id}/report`} className="cell-title">{c.title}</Link>
                    <div className="cell-sub">{c.unit}</div>
                  </td>
                  <td>
                    {c.project}
                    <div className="cell-sub">{c.location}</div>
                  </td>
                  <td>{c.claimType}</td>
                  <td className="r num">{fmtINRShort(c.payments.reduce((t, p) => t + p.amount, 0))}</td>
                  <td className="r num">{pct(c.report.outcome.allowed + c.report.outcome.partly)}</td>
                  <td><span className="tag tag-pos">{c.status}</span></td>
                  <td className="num faint">{fmtDate(c.updated)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="small faint" style={{ marginTop: 14 }}>
        “Similar cases won” counts orders allowed in full or in part among similar past orders. It is not a prediction of your
        own hearing.
      </p>
    </main>
  );
}
