import LiveDocuments from "../live/live-documents";
import { loadCase } from "@/lib/case-source";
import { FileIcon, PlusIcon } from "@/components/icons";
import { fmtDate } from "@/lib/format";

export const metadata = { title: "Documents" };

export default async function DocumentsPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "live") return <LiveDocuments c={src.data} />;
  if (src.kind !== "example") return null; // the layout shows the error
  const c = src.data;

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Documents</h2>
          <p>Everything the report is built from. Add a new builder letter or a hearing order at any time; only the parts it affects are re-run.</p>
        </div>
        <button className="btn" type="button"><PlusIcon /> Add documents</button>
      </div>

      <div className="panel table-wrap">
        <table className="ledger stack">
          <thead>
            <tr><th>Document</th><th>Dated</th><th className="r">Pages</th><th>Language</th><th>Reading</th></tr>
          </thead>
          <tbody>
            {c.documents.map((d) => (
              <tr key={d.id}>
                <td data-label="Document">
                  <span style={{ display: "inline-flex", gap: 10, alignItems: "flex-start" }}>
                    <span style={{ color: "var(--primary)", marginTop: 2 }}><FileIcon /></span>
                    <span>
                      <span className="cell-title">{d.title}</span>
                      <span className="cell-sub" style={{ display: "block" }}>{d.kind}</span>
                    </span>
                  </span>
                </td>
                <td data-label="Dated" className="num">{fmtDate(d.date)}</td>
                <td data-label="Pages" className="r num">{d.pages}</td>
                <td data-label="Language">{d.language}</td>
                <td data-label="Reading">
                  <span className={`tag ${d.ocr === "OCR, needs review" ? "tag-mid" : "tag-neutral"}`}>{d.ocr}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel" style={{ marginTop: 24 }}>
        <div className="panel-head"><h3>Case history</h3></div>
        <ol style={{ listStyle: "none", padding: "8px 18px 12px", margin: 0 }}>
          {c.history.map((h, i) => (
            <li
              key={i}
              style={{ display: "grid", gridTemplateColumns: "110px 1fr", gap: 12, padding: "10px 0", borderBottom: i < c.history.length - 1 ? "1px solid var(--border)" : "none" }}
            >
              <span className="num faint">{fmtDate(h.date)}</span>
              <span>{h.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </>
  );
}
