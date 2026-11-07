"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import type { CaseDocument, Fact } from "@/lib/demo-case";
import styles from "./facts.module.css";

const SPAN = /\{\{([\w-]+)\|([^}]+)\}\}/g;

/** Splits "text {{id|source}} more" into plain text and marked source spans. */
function renderParagraph(text: string, active: string | null, onPick: (id: string) => void) {
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(SPAN)) {
    const [whole, id, words] = m;
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    out.push(
      <mark
        key={at}
        id={`src-${id}`}
        className={`${styles.mark} ${active === id ? styles.markActive : ""}`}
        onClick={() => onPick(id)}
      >
        {words}
      </mark>,
    );
    last = at + whole.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function FactsView({ facts, documents }: { facts: Fact[]; documents: CaseDocument[] }) {
  const [active, setActive] = useState<string | null>(facts[0]?.id ?? null);
  const [docId, setDocId] = useState(facts[0]?.docId ?? documents[0].id);
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const viewer = useRef<HTMLDivElement>(null);

  const doc = documents.find((d) => d.id === docId) ?? documents[0];

  function pick(id: string) {
    const f = facts.find((x) => x.id === id);
    if (!f) return;
    setActive(id);
    setDocId(f.docId);
  }

  useEffect(() => {
    if (!active) return;
    const el = document.getElementById(`src-${active}`);
    const box = viewer.current;
    if (el && box) {
      const top = el.offsetTop - box.offsetTop - box.clientHeight / 3;
      box.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    }
  }, [active, docId]);

  const toReview = facts.filter((f) => f.confidence === "review" && !confirmed[f.id]).length;

  return (
    <div className={styles.split}>
      <div className="panel">
        <div className="panel-head">
          <span className="label">{facts.length} facts</span>
          <span className="small" style={{ color: toReview ? "var(--mid)" : "var(--pos)" }}>
            {toReview ? `${toReview} to check` : "All checked"}
          </span>
        </div>
        <ul className={styles.factList}>
          {facts.map((f) => {
            const needsCheck = f.confidence === "review" && !confirmed[f.id];
            return (
              <li key={f.id}>
                <button
                  type="button"
                  className={`${styles.fact} ${active === f.id ? styles.factActive : ""}`}
                  onClick={() => pick(f.id)}
                  aria-pressed={active === f.id}
                >
                  <span className={styles.factLabel}>{f.label}</span>
                  <span className={styles.factValue}>{f.value}</span>
                  <span className={styles.factWhere}>
                    {documents.find((d) => d.id === f.docId)?.title}, p. {f.page}
                    {needsCheck && <span className="tag tag-mid" style={{ marginLeft: 8 }}>Check</span>}
                  </span>
                </button>
                {active === f.id && (f.note || needsCheck) && (
                  <div className={styles.factNote}>
                    {f.note && <p>{f.note}</p>}
                    {needsCheck && (
                      <div style={{ display: "flex", gap: 8 }}>
                        <button type="button" className="btn" onClick={() => setConfirmed((c) => ({ ...c, [f.id]: true }))}>
                          This is correct
                        </button>
                        <button type="button" className="btn btn-quiet">Edit value</button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="panel" style={{ minWidth: 0 }}>
        <div className={styles.tabs} role="tablist" aria-label="Documents">
          {documents.map((d) => (
            <button
              key={d.id}
              role="tab"
              type="button"
              aria-selected={d.id === doc.id}
              className={styles.tab}
              onClick={() => setDocId(d.id)}
            >
              {d.title}
            </button>
          ))}
        </div>
        <div className={styles.viewer} ref={viewer}>
          {doc.excerpt.map((pg) => (
            <Fragment key={pg.number}>
              <div className={styles.pageNo}>Page {pg.number} of {doc.pages}</div>
              <article className={styles.sheet}>
                {pg.paragraphs.map((p, i) => (
                  <p key={i}>{renderParagraph(p, active, pick)}</p>
                ))}
              </article>
            </Fragment>
          ))}
          {doc.pages > doc.excerpt.length && (
            <p className="small faint" style={{ textAlign: "center" }}>
              Showing pages with extracted facts. {doc.pages - doc.excerpt.length} other pages hidden.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
