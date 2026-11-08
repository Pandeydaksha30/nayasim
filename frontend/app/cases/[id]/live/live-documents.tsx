import Link from "next/link";
import { FileIcon, PlusIcon } from "@/components/icons";
import { type CaseFull, kindLabel } from "@/lib/cases-api";

export default function LiveDocuments({ c }: { c: CaseFull }) {
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Documents</h2>
          <p>Everything this case is built from. Text is read from the file itself, or by OCR for scans and photos.</p>
        </div>
        <Link className="btn" href="/cases/new"><PlusIcon /> New case</Link>
      </div>
      <div className="panel table-wrap">
        <table className="ledger stack">
          <thead>
            <tr><th>Document</th><th>Type</th><th className="r">Pages</th><th>Reading</th></tr>
          </thead>
          <tbody>
            {c.documents.length === 0 && (
              <tr><td colSpan={4} className="muted">No documents uploaded yet.</td></tr>
            )}
            {c.documents.map((d) => (
              <tr key={d.id}>
                <td data-label="Document" style={{ maxWidth: 360 }}>
                  <span style={{ display: "inline-flex", gap: 10, alignItems: "center", minWidth: 0 }}>
                    <span style={{ color: "var(--primary)" }}><FileIcon /></span>
                    <span className="cell-title cell-wrap">{d.filename}</span>
                  </span>
                </td>
                <td data-label="Type">{kindLabel(d.kind)}</td>
                <td data-label="Pages" className="r num">{d.page_count}</td>
                <td data-label="Reading">
                  {d.ocr_pages === 0 && <span className="tag tag-neutral">Text layer</span>}
                  {d.ocr_pages > 0 && d.ocr_pages < d.page_count && <span className="tag tag-mid">{d.ocr_pages} pages by OCR</span>}
                  {d.ocr_pages > 0 && d.ocr_pages === d.page_count && <span className="tag tag-mid">OCR</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
