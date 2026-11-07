import Link from "next/link";
import { demoCase } from "@/lib/demo-case";
import { fmtDate, fmtINRShort, pct } from "@/lib/format";

export default function CasesPage() {
  const c = demoCase;
  const paid = c.payments.reduce((s, p) => s + p.amount, 0);

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Your cases</h1>
          <p>Each case keeps its documents, facts and reports. Upload a new builder letter or hearing order and the report updates.</p>
        </div>
        <Link href="/cases/new" className="btn btn-primary">New case</Link>
      </div>

      <div className="panel table-wrap">
        <table className="ledger">
          <thead>
            <tr>
              <th>Case</th>
              <th>Project</th>
              <th>Claim</th>
              <th className="r">Paid</th>
              <th className="r">Buyer wins (similar cases)</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <Link href={`/cases/${c.id}/report`}>{c.title}</Link>
                <div className="small faint">{c.unit}</div>
              </td>
              <td>
                {c.project}
                <div className="small faint">{c.location}</div>
              </td>
              <td>{c.claimType}</td>
              <td className="r num">{fmtINRShort(paid)}</td>
              <td className="r num">{pct(c.report.outcome.allowed + c.report.outcome.partly)}</td>
              <td><span className="tag tag-pos">{c.status}</span></td>
              <td className="num">{fmtDate(c.updated)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="small faint" style={{ marginTop: 14 }}>
        “Buyer wins” counts orders allowed in full or in part among {c.report.similarCount} similar past orders. It is not a prediction of your
        hearing on its own.
      </p>
    </main>
  );
}
