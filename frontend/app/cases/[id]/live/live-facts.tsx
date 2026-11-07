"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Banner } from "@/components/icons";
import {
  type CaseFact,
  type CaseFull,
  confirmFact,
  extractFacts,
  getPage,
  groupFacts,
  kindLabel,
  type PageText,
} from "@/lib/cases-api";
import { fmtDate, fmtINR } from "@/lib/format";
import styles from "../facts/facts.module.css";

function display(key: string, value: string) {
  if (key === "payment") {
    const [d, a] = value.split(";");
    return `${fmtINR(Number(a))} on ${fmtDate(d)}`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return fmtDate(value);
  if (/^\d+\.\d{2}$/.test(value)) return fmtINR(Number(value));
  return value;
}

export default function LiveFacts({ c }: { c: CaseFull }) {
  const router = useRouter();
  const groups = useMemo(() => groupFacts(c.facts), [c.facts]);
  const [active, setActive] = useState<CaseFact | null>(groups[0]?.sources[0] ?? null);
  const [page, setPage] = useState<PageText | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const markRef = useRef<HTMLElement>(null);
  const docName = (id: string) => c.documents.find((d) => d.id === id)?.filename ?? "document";

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setPageError(null);
    getPage(c.id, active.document_id, active.page_no)
      .then((p) => !cancelled && setPage(p))
      .catch((e) => !cancelled && setPageError(e instanceof Error ? e.message : "Could not load the page."));
    return () => {
      cancelled = true;
    };
  }, [c.id, active]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [page]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const header = (
    <div className="section-title">
      <div>
        <h2>Facts from your documents</h2>
        <p>Select a fact to see the exact words it was read from. Every fact is checked against the stored page before it is shown.</p>
      </div>
      {c.is_demo && c.documents.length > 0 && (
        <button type="button" className="btn" disabled={busy} onClick={() => run(() => extractFacts(c.id))}>
          {busy ? "Finding facts…" : c.facts.length ? "Find facts again" : "Find facts"}
        </button>
      )}
    </div>
  );

  if (c.facts.length === 0) {
    return (
      <>
        {header}
        {error && <Banner tone="error"><b>Could not find facts.</b> {error}</Banner>}
        {!c.is_demo ? (
          <Banner tone="info">
            <b>Your documents are stored and readable, but facts are not extracted yet.</b> Real documents are not sent to the
            current AI model because it may keep data. This switches on once a model that keeps no data is configured.
          </Banner>
        ) : c.documents.length === 0 ? (
          <Banner tone="warn">Upload documents first.</Banner>
        ) : (
          <Banner tone="info">No facts yet. Use “Find facts” to read your documents.</Banner>
        )}
      </>
    );
  }

  const review = c.facts.filter((f) => f.confidence === "review" && !f.confirmed).length;

  return (
    <>
      {header}
      {error && <div style={{ marginBottom: 12 }}><Banner tone="error"><b>Could not finish.</b> {error}</Banner></div>}
      <div className={styles.split}>
        <div className="panel">
          <div className="panel-head">
            <span className="label">{groups.length} facts</span>
            <span className="small" style={{ color: review ? "var(--mid)" : "var(--pos)" }}>
              {review ? `${review} to check` : "All checked"}
            </span>
          </div>
          <ul className={styles.factList}>
            {groups.map((g) => {
              const isActive = !!active && g.sources.some((s) => s.id === active.id);
              const needsCheck = g.sources.some((s) => s.confidence === "review" && !s.confirmed);
              return (
                <li key={`${g.key}:${g.value}`}>
                  <button type="button" className={`${styles.fact} ${isActive ? styles.factActive : ""}`}
                          aria-pressed={isActive} onClick={() => setActive(g.sources[0])}>
                    <span className={styles.factLabel}>{g.label}</span>
                    <span className={styles.factValue}>{display(g.key, g.value)}</span>
                    <span className={styles.factWhere}>
                      {docName(g.sources[0].document_id)}, p. {g.sources[0].page_no}
                      {g.sources.length > 1 && ` · also in ${g.sources.length - 1} more`}
                      {needsCheck && <span className="tag tag-mid">Check</span>}
                    </span>
                  </button>
                  {isActive && (g.sources.length > 1 || needsCheck) && (
                    <div className={styles.factNote}>
                      {g.sources.length > 1 && (
                        <p style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {g.sources.map((s) => (
                            <button key={s.id} type="button" className="btn btn-quiet" onClick={() => setActive(s)}>
                              {docName(s.document_id)} p. {s.page_no}
                            </button>
                          ))}
                        </p>
                      )}
                      {needsCheck && (
                        <>
                          <p>Read from a scan or matched approximately. Compare it with the page before relying on it.</p>
                          <button type="button" className="btn" disabled={busy}
                                  onClick={() => run(() => Promise.all(g.sources.map((s) => confirmFact(c.id, s.id))))}>
                            This is correct
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        <div className="panel" style={{ minWidth: 0 }}>
          <div className="panel-head">
            <span className="small">
              {active ? <><b>{docName(active.document_id)}</b> · {kindLabel(c.documents.find((d) => d.id === active.document_id)?.kind ?? "")}</> : "—"}
            </span>
            {page?.text_source === "ocr" && <span className="tag tag-mid">OCR {page.ocr_confidence ? `${Math.round(Number(page.ocr_confidence))}%` : ""}</span>}
          </div>
          <div className={styles.viewer}>
            {pageError && <Banner tone="error">{pageError}</Banner>}
            {page && active && (
              <>
                <div className={styles.pageNo}>Page {page.page_no} of {page.page_count}</div>
                <article className={styles.sheet} style={{ whiteSpace: "pre-wrap" }}>
                  {page.text.slice(0, active.char_start)}
                  <mark ref={markRef} className={`${styles.mark} ${styles.markActive}`}>
                    {page.text.slice(active.char_start, active.char_end)}
                  </mark>
                  {page.text.slice(active.char_end)}
                </article>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
