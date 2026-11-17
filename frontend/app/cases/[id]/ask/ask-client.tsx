"use client";
/**
 * Ask a question about this case's uploaded documents. The answer is shown only with citations
 * the server found word for word in the stored page text; otherwise "not enough evidence".
 * Private (non-demo) cases can be searched, but are not sent to the model.
 */
import { useEffect, useState } from "react";
import { Citations, Passages } from "@/components/evidence";
import styles from "@/components/evidence.module.css";
import { Banner } from "@/components/icons";
import { type AskResult, type PassageHit, askCase, listQuestions, searchPassages } from "@/lib/agent-api";
import ClauseAnalysis from "./clause-analysis";

const SUGGESTIONS = [
  "When was possession promised?",
  "What does the agreement say the builder pays for delay?",
  "How much has the buyer paid, and when?",
];

export default function AskClient({ caseId, isDemo, readOnly }: { caseId: string; isDemo: boolean; readOnly: boolean }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResult | null>(null);
  const [hits, setHits] = useState<PassageHit[] | null>(null);
  const [history, setHistory] = useState<AskResult[]>([]);

  useEffect(() => {
    listQuestions(caseId).then(setHistory).catch(() => {});
  }, [caseId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    setHits(null);
    try {
      if (isDemo) {
        const r = await askCase(caseId, q);
        setResult(r);
        setHistory((h) => [r, ...h]);
      } else {
        setHits((await searchPassages(caseId, q)).hits);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "The question could not be answered.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Ask your documents</h2>
          <p>
            Answers come only from the documents uploaded to this case. Every quoted passage is checked against the stored
            page text by code; an answer without a verified quote is not shown.
          </p>
        </div>
      </div>

      {readOnly ? (
        <Banner tone="info">
          <b>This example is a recording, so new questions cannot be asked here.</b> The questions below were asked when it
          was recorded; the answers and quotes are shown exactly as the system returned them.
        </Banner>
      ) : (
        <>
          {!isDemo && (
            <div className={styles.stack} style={{ marginTop: 0, marginBottom: 12 }}>
              <Banner tone="info">
                This is a private case, so its text is not sent to the AI model. You see the matching passages of your
                documents instead of a written answer.
              </Banner>
            </div>
          )}
          <form onSubmit={submit} className="panel">
            <div className="panel-body">
              <div className={styles.formRow}>
                <label className="field">
                  <span className="field-label">Your question</span>
                  <input className="input" value={q} onChange={(e) => setQ(e.target.value)}
                         placeholder="When was possession promised?" minLength={5} maxLength={500} required />
                </label>
                <button className="btn btn-primary" disabled={busy || q.trim().length < 5}>
                  {busy ? "Searching…" : isDemo ? "Ask" : "Search passages"}
                </button>
              </div>
              <div className={styles.suggest}>
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className={styles.chip} disabled={busy} onClick={() => setQ(s)}>{s}</button>
                ))}
              </div>
            </div>
          </form>
        </>
      )}

      <div className={styles.stack}>
        {error && <Banner tone="error">{error}</Banner>}

        {result && (
          <section className="panel">
            <div className="panel-head"><h3>Answer</h3></div>
            <div className="panel-body"><Answer r={result} /></div>
          </section>
        )}

        {hits && (
          <section className="panel">
            <div className="panel-head"><h3>Matching passages</h3><span className="small faint">{hits.length} found</span></div>
            <div className="panel-body">
              <Passages
                empty="No passage of your documents matched these words."
                items={hits.map((h) => ({ key: h.chunk_id, source: h.filename, where: `page ${h.page_no}`, text: h.text }))}
              />
            </div>
          </section>
        )}

        <ClauseAnalysis caseId={caseId} canRun={isDemo && !readOnly} />

        {history.length > 0 && (
          <section className="panel">
            <div className="panel-head"><h3>{readOnly ? "Recorded questions" : "Earlier questions"}</h3><span className="small faint">{history.length}</span></div>
            <ul className={styles.history}>
              {history.map((h, i) => (
                <li key={h.id ?? i}>
                  <details open={readOnly && i === 0}>
                    <summary>{h.question}</summary>
                    <div className={styles.historyBody}><Answer r={h} /></div>
                  </details>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  );
}

function Answer({ r }: { r: AskResult }) {
  return (
    <>
      {r.insufficient ? (
        <Banner tone="warn">
          <b>{r.answer}</b>
          {r.reason && <div className="small">Why: {r.reason}.</div>}
        </Banner>
      ) : (
        <p className={styles.answer}>{r.answer}</p>
      )}
      {r.citations.length > 0 && <div className={styles.subhead}>Where this comes from</div>}
      <Citations citations={r.citations} rejected={r.rejected_citations} />
      <div className={styles.answerMeta}>
        <span>Passages read: {r.retrieved.map((x) => `${x.filename} p. ${x.page_no}`).join(", ") || "none"}</span>
        <span>Search: {r.mode === "hybrid" ? "keywords and meaning" : "keywords"}</span>
        <span>Model: {r.model}</span>
      </div>
    </>
  );
}
