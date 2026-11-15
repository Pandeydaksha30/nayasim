"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Banner } from "@/components/icons";
import {
  type CaseFact,
  type CaseFull,
  confirmFact,
  extractFacts,
  getHighlight,
  getPage,
  groupFacts,
  isUsable,
  kindLabel,
  type PageHighlight,
  pageImageUrl,
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

type View = "page" | "text";

export default function LiveFacts({ c }: { c: CaseFull }) {
  const router = useRouter();
  const groups = useMemo(() => groupFacts(c.facts), [c.facts]);
  // Open on a fact from a page with a text layer where there is one: it can be marked on the picture.
  const [active, setActive] = useState<CaseFact | null>(() => {
    const textDocs = new Set(c.documents.filter((d) => d.ocr_pages === 0).map((d) => d.id));
    const first = groups.find((g) => textDocs.has(g.sources[0].document_id)) ?? groups[0];
    return first?.sources[0] ?? null;
  });
  const [view, setView] = useState<View>("page");
  const [page, setPage] = useState<PageText | null>(null);
  const [highlight, setHighlight] = useState<PageHighlight | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const markRef = useRef<HTMLElement>(null);
  const rectRef = useRef<HTMLSpanElement>(null);
  const readOnly = c.shared;

  const docName = (id: string) => c.documents.find((d) => d.id === id)?.filename ?? "document";

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setPageError(null);
    setHighlight(null);
    setImageFailed(false);
    getPage(c.id, active.document_id, active.page_no)
      .then((p) => !cancelled && setPage(p))
      .catch((e) => !cancelled && setPageError(e instanceof Error ? e.message : "Could not load the page."));
    getHighlight(c.id, active.document_id, active.page_no, active.char_start, active.char_end)
      .then((h) => !cancelled && setHighlight(h))
      .catch(() => !cancelled && setHighlight({ rects: null, text_source: "text_layer" }));
    return () => {
      cancelled = true;
    };
  }, [c.id, active]);

  useEffect(() => {
    const el = view === "page" ? rectRef.current : markRef.current;
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [page, highlight, view]);

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
        <p>
          Select a fact to see it on the page it was read from. Every fact is checked against the stored page before it is
          shown.
        </p>
      </div>
      {c.is_demo && !readOnly && c.documents.length > 0 && (
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

  const rects = highlight?.rects ?? null;
  const activeDoc = active ? c.documents.find((d) => d.id === active.document_id) : undefined;

  return (
    <>
      {header}
      {error && <div className={styles.gap}><Banner tone="error"><b>Could not finish.</b> {error}</Banner></div>}
      {c.facts_to_check > 0 && (
        <div className={styles.gap}>
          <Banner tone="warn">
            <b>{c.facts_to_check} {c.facts_to_check === 1 ? "fact needs" : "facts need"} your check.</b> They were read from a
            weak scan or matched approximately. Until you confirm them they are left out of the money calculation, the
            hearing and the complaint draft.
          </Banner>
        </div>
      )}
      <div className={styles.split}>
        <div className="panel">
          <div className="panel-head">
            <span className="label">{groups.length} facts</span>
            <span className={`small ${c.facts_to_check ? styles.toCheck : styles.allChecked}`}>
              {c.facts_to_check ? `${c.facts_to_check} to check` : "All usable"}
            </span>
          </div>
          <ul className={styles.factList}>
            {groups.map((g) => {
              const isActive = !!active && g.sources.some((s) => s.id === active.id);
              const needsCheck = g.sources.some((s) => !isUsable(s));
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
                        <p className={styles.sources}>
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
                          {!readOnly && (
                            <button type="button" className="btn" disabled={busy}
                                    onClick={() => run(() => Promise.all(g.sources.filter((s) => !isUsable(s)).map((s) => confirmFact(c.id, s.id))))}>
                              This is correct
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        <div className={`panel ${styles.viewerPanel}`}>
          <div className={styles.viewerHead}>
            <div className={styles.viewerDoc}>
              {active ? <span><b>{docName(active.document_id)}</b><span className="faint"> · {kindLabel(activeDoc?.kind ?? "")}</span></span> : "—"}
              {page && <span className={styles.pageNoInline}>Page {page.page_no} of {page.page_count}</span>}
              {page?.text_source === "ocr" && (
                <span className="tag tag-mid">OCR{page.ocr_confidence ? ` ${Math.round(Number(page.ocr_confidence))}%` : ""}</span>
              )}
            </div>
            <div className={styles.tabs} role="tablist" aria-label="How to view the page">
              <button type="button" role="tab" aria-selected={view === "page"} className={styles.tab} onClick={() => setView("page")}>
                Page as filed
              </button>
              <button type="button" role="tab" aria-selected={view === "text"} className={styles.tab} onClick={() => setView("text")}>
                Text we read
              </button>
            </div>
          </div>
          <div className={styles.viewer}>
            {pageError && <Banner tone="error">{pageError}</Banner>}
            {active && view === "page" && (
              <>
                {highlight && rects === null && !imageFailed && (
                  <p className={styles.viewerNote}>
                    {highlight.text_source === "ocr"
                      ? "This page is a scan read by OCR, so the passage cannot be marked on the picture for certain. It is marked under “Text we read”."
                      : "The passage could not be placed on the picture for certain. It is marked under “Text we read”."}
                  </p>
                )}
                {imageFailed ? (
                  <Banner tone="warn">The page picture could not be loaded. The text we read is still available.</Banner>
                ) : (
                  <figure className={styles.pageImage}>
                    {/* eslint-disable-next-line @next/next/no-img-element -- a private, per-user page picture */}
                    <img
                      src={pageImageUrl(c.id, active.document_id, active.page_no)}
                      alt={`Page ${active.page_no} of ${docName(active.document_id)}`}
                      onError={() => setImageFailed(true)}
                    />
                    {rects?.map((r, i) => (
                      <span
                        key={`${active.id}-${i}`}
                        ref={i === 0 ? rectRef : undefined}
                        className={styles.rect}
                        style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: `${r.w * 100}%`, height: `${r.h * 100}%` }}
                      />
                    ))}
                  </figure>
                )}
              </>
            )}
            {page && active && view === "text" && (
              <article className={`${styles.sheet} ${styles.sheetText}`}>
                {page.text.slice(0, active.char_start)}
                <mark ref={markRef} className={`${styles.mark} ${styles.markActive}`}>
                  {page.text.slice(active.char_start, active.char_end)}
                </mark>
                {page.text.slice(active.char_end)}
              </article>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
