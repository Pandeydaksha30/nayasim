"use client";

import { type FormEvent, useState } from "react";
import { Banner } from "@/components/icons";
import { type Classification, classifyOrderText, searchOrders, type SearchResponse } from "@/lib/insights-api";
import { fmtDate } from "@/lib/format";
import styles from "./search.module.css";

const OUTCOME: Record<string, string> = {
  allowed: "Allowed",
  partly_allowed: "Partly allowed",
  dismissed: "Dismissed",
  disposed_of: "Disposed of",
  withdrawn: "Withdrawn",
  other: "Other",
};
const CLAIM: Record<string, string> = { delayed_possession: "Delayed possession", refund: "Refund", other: "Other" };
const EXAMPLES = [
  "refund with interest after delay in possession",
  "force majeure Covid-19 extension of six months",
  "delay possession charges prescribed rate of interest",
];

export default function SearchClient() {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [res, setRes] = useState<SearchResponse | null>(null);

  const [text, setText] = useState("");
  const [cBusy, setCBusy] = useState(false);
  const [cError, setCError] = useState("");
  const [cls, setCls] = useState<Classification | null>(null);

  async function run(query: string) {
    setBusy(true);
    setError("");
    try {
      setRes(await searchOrders(query.trim()));
    } catch (e) {
      setRes(null);
      setError(e instanceof Error ? e.message : "Search failed.");
    } finally {
      setBusy(false);
    }
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    if (q.trim().length >= 3) void run(q);
  }

  async function onClassify(e: FormEvent) {
    e.preventDefault();
    setCBusy(true);
    setCError("");
    try {
      setCls(await classifyOrderText(text));
    } catch (err) {
      setCls(null);
      setCError(err instanceof Error ? err.message : "Classification failed.");
    } finally {
      setCBusy(false);
    }
  }

  return (
    <>
      <section className="panel">
        <form className={`panel-body ${styles.form}`} onSubmit={onSearch} role="search">
          <label className="field" style={{ flex: 1 }}>
            <span className="field-label">Search the stored orders</span>
            <input
              className="input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="For example: refund with interest after delay in possession"
              maxLength={400}
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy || q.trim().length < 3}>
            {busy ? "Searching…" : "Search"}
          </button>
        </form>
        <div className={`panel-body ${styles.examples}`}>
          <span className="small faint">Try:</span>
          {EXAMPLES.map((x) => (
            <button key={x} type="button" className="btn btn-quiet" onClick={() => { setQ(x); void run(x); }} disabled={busy}>
              {x}
            </button>
          ))}
        </div>
      </section>

      {error && <div style={{ marginTop: 16 }}><Banner tone="error"><b>Search failed.</b> {error}</Banner></div>}

      {res && (
        <>
          <p className="small muted" style={{ margin: "16px 0 10px" }}>
            {res.hits.length} passage(s) from orders decided before {fmtDate(res.before)}.{" "}
            {res.mode === "hybrid" ? "Keyword and meaning-based search combined." : "Keyword search only."}{" "}
            {res.notes.join(" ")}
          </p>
          {res.hits.length === 0 && <Banner tone="info">No stored order matches these words. Try other terms.</Banner>}
          <div className={styles.hits}>
            {res.hits.map((h, i) => (
              <article key={`${h.order_id}-${h.page_no}-${i}`} className="panel panel-body">
                <div className={styles.hitTop}>
                  <span className="code">{h.complaint_no}</span>
                  <span className="small muted">decided {fmtDate(h.decided_on)} · page {h.page_no}</span>
                  {h.outcome
                    ? <span className="tag tag-neutral">{OUTCOME[h.outcome] ?? h.outcome}</span>
                    : <span className="tag tag-mid">Outcome not recorded</span>}
                </div>
                <p className={styles.hitText}>{h.text}</p>
              </article>
            ))}
          </div>
        </>
      )}

      <h2 className={styles.h}>Try the trained classifier</h2>
      <p className="muted" style={{ maxWidth: "72ch", margin: "0 0 12px" }}>
        Paste the parties’ part of an order (facts, relief sought, reply). A rule reads the relief section; a
        TF-IDF and logistic regression model decides the rest. The measured accuracy is shown with every answer.
      </p>
      <section className="panel">
        <form className="panel-body" onSubmit={onClassify}>
          <label className="field">
            <span className="field-label">Order text (at least 200 characters)</span>
            <textarea
              className={`input ${styles.area}`}
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={7}
              maxLength={60000}
            />
          </label>
          <button type="submit" className="btn" disabled={cBusy || text.trim().length < 200} style={{ marginTop: 12 }}>
            {cBusy ? "Classifying…" : "Classify"}
          </button>
        </form>
      </section>
      {cError && <div style={{ marginTop: 16 }}><Banner tone="error"><b>Could not classify.</b> {cError}</Banner></div>}
      {cls && (
        <div className={styles.cls}>
          <section className="panel panel-body">
            <div className="label">Claim type</div>
            <div className={styles.big}>{CLAIM[cls.claim_type.label] ?? cls.claim_type.label}</div>
            <p className="small muted">
              Decided by: {cls.claim_type.decided_by}. Measured on {cls.claim_type.measured.test_orders} held-out orders:{" "}
              {cls.claim_type.measured.accuracy_pct}% accuracy (always guessing the most common type scores{" "}
              {cls.claim_type.measured.majority_baseline_pct}%).
            </p>
          </section>
          <section className="panel panel-body">
            <div className="label">Outcome (model)</div>
            <div className={styles.big}>{OUTCOME[cls.outcome.label] ?? cls.outcome.label}</div>
            <p className="small muted">
              Measured on {cls.outcome.measured.test_orders} held-out orders: {cls.outcome.measured.accuracy_pct}% accuracy,
              against {cls.outcome.measured.majority_baseline_pct}% for the simple baseline. {cls.outcome.note}
            </p>
          </section>
          <div style={{ gridColumn: "1 / -1" }}><Banner tone="warn">{cls.caveat}</Banner></div>
        </div>
      )}
    </>
  );
}
