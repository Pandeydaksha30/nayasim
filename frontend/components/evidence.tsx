/**
 * Evidence shown with an answer: citations the server verified word for word, and passages.
 * Used by "Ask your documents" and "Agent analysis", so both read the same way.
 */
import type { DocCitation, Rejected } from "@/lib/agent-api";
import { fmtDate } from "@/lib/format";
import styles from "./evidence.module.css";

export function Citations({ citations, rejected }: { citations: DocCitation[]; rejected?: Rejected[] }) {
  return (
    <>
      {citations.length > 0 && (
        <ul className={styles.cites}>
          {citations.map((c, i) => (
            <li key={i} className={styles.cite}>
              <div className={styles.citeSource}>
                {c.source === "order" ? (
                  <>
                    <b className="code">{c.complaint_no}</b>
                    Past order{c.decided_on ? `, decided ${fmtDate(c.decided_on)}` : ""} · page {c.page_no}
                  </>
                ) : (
                  <>
                    <b>{c.filename}</b>
                    Your document · page {c.page_no}
                  </>
                )}
                <span className={styles.kind}>Quote verified</span>
              </div>
              <blockquote className={styles.citeQuote}>“{c.quote.split(/\s+/).join(" ")}”</blockquote>
            </li>
          ))}
        </ul>
      )}
      {!!rejected?.length && (
        <p className={styles.removed}>
          {rejected.length} {rejected.length === 1 ? "quote" : "quotes"} proposed by the model {rejected.length === 1 ? "was" : "were"} removed:
          not found word for word in the source.
        </p>
      )}
    </>
  );
}

export interface PassageItem {
  key: string | number;
  source: string;
  where: string;
  text: string;
  mono?: boolean;
}

export function Passages({ items, empty }: { items: PassageItem[]; empty: string }) {
  if (items.length === 0) return <p className="muted small">{empty}</p>;
  return (
    <ul className={styles.passages}>
      {items.map((p) => (
        <li key={p.key} className={styles.passage}>
          <div className={styles.passageHead}>
            <b className={p.mono ? "code" : undefined}>{p.source}</b>
            <span>{p.where}</span>
          </div>
          <p className={styles.passageText}>{p.text.split(/\s+/).join(" ")}</p>
        </li>
      ))}
    </ul>
  );
}
