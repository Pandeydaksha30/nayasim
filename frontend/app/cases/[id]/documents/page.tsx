import { notFound } from "next/navigation";
import { getCase } from "@/lib/demo-case";
import { fmtDate } from "@/lib/format";

export const metadata = { title: "Documents" };

export default async function DocumentsPage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase((await params).id);
  if (!c) notFound();

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Documents</h2>
          <p>Everything the report is built from. Add a new builder letter or a hearing order at any time; only the parts it affects are re-run.</p>
        </div>
        <button className="btn" type="button">Add documents</button>
      </div>

      <div className="panel table-wrap">
        <table className="ledger">
          <thead>
            <tr><th>Document</th><th>Dated</th><th className="r">Pages</th><th>Language</th><th>Reading</th></tr>
          </thead>
          <tbody>
            {c.documents.map((d) => (
              <tr key={d.id}>
                <td>{d.title}<div className="small faint">{d.kind}</div></td>
                <td className="num">{fmtDate(d.date)}</td>
                <td className="r num">{d.pages}</td>
                <td>{d.language}</td>
                <td>
                  <span className={`tag ${d.ocr === "OCR, needs review" ? "tag-mid" : "tag-neutral"}`}>{d.ocr}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 style={{ margin: "32px 0 10px" }}>Case history</h3>
      <ol style={{ listStyle: "none", padding: 0, margin: 0, borderLeft: "1px solid var(--rule-strong)" }}>
        {c.history.map((h, i) => (
          <li key={i} style={{ padding: "4px 0 10px 16px", position: "relative" }}>
            <span className="num faint" style={{ marginRight: 12 }}>{fmtDate(h.date)}</span>
            {h.text}
          </li>
        ))}
      </ol>
    </>
  );
}
