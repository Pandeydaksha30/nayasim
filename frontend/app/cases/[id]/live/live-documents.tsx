import Link from "next/link";
import { AddDocuments, DeleteDocumentButton } from "@/components/case-actions";
import { FileIcon } from "@/components/icons";
import { type CaseFull, kindLabel } from "@/lib/cases-api";
import styles from "./live-documents.module.css";

export default function LiveDocuments({ c }: { c: CaseFull }) {
  const canEdit = !c.shared;
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Documents</h2>
          <p>Everything this case is built from. Text is read from the file itself, or by OCR for scans and photos.</p>
        </div>
      </div>
      {canEdit && <div className={styles.add}><AddDocuments caseId={c.id} /></div>}
      <div className="panel table-wrap">
        <table className="ledger stack">
          <thead>
            <tr><th>Document</th><th>Type</th><th className="r">Pages</th><th>Reading</th>{canEdit && <th className="r">Remove</th>}</tr>
          </thead>
          <tbody>
            {c.documents.length === 0 && (
              <tr><td colSpan={canEdit ? 5 : 4} className="muted">No documents yet. Add your agreement and payment receipts to begin.</td></tr>
            )}
            {c.documents.map((d) => (
              <tr key={d.id}>
                <td data-label="Document" className={styles.docCell}>
                  <span className={styles.doc}>
                    <span className={styles.icon}><FileIcon /></span>
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
                {canEdit && (
                  <td data-label="Remove" className="r">
                    <DeleteDocumentButton caseId={c.id} docId={d.id} filename={d.filename} />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {c.documents.length > 0 && (
        <p className={`small muted ${styles.next}`}>
          Next: <Link href={`/cases/${c.id}/facts`}>check the facts read from these documents</Link>.
          {canEdit && c.is_demo && " After adding a document, use “Find facts again” there."}
        </p>
      )}
    </>
  );
}
