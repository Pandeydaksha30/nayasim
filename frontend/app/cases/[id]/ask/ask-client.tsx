"use client";

/**
 * Ask a question about this case's uploaded documents. The answer is shown only with citations
 * the server found word for word in the stored page text; otherwise "not enough evidence".
 * Private (non-demo) cases can be searched, but are not sent to the model.
 */
import { useEffect, useState } from "react";
import { Banner } from "@/components/icons";
import { type AskResult, type PassageHit, askCase, citeLabel, listQuestions, searchPassages } from "@/lib/agent-api";

export default function AskClient({ caseId, isDemo }: { caseId: string; isDemo: boolean }) {
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
      {!isDemo && (
        <div style={{ marginBottom: 12 }}>
          <Banner tone="info">
            This is a private case, so its text is not sent to the AI model. You see the matching passages of your
            documents instead of a written answer.
          </Banner>
        </div>
      )}
      <form onSubmit={submit} className="panel">
        <div className="panel-body">
          <label className="field">
            <span className="field-label">Your question</span>
            <input
              className="input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="When was possession promised?"
              minLength={5}
              maxLength={500}
              required
            />
          </label>
          <div className="section-actions" style={{ marginTop: 12 }}>
            <button className="btn btn-primary" disabled={busy || q.trim().length < 5}>
              {busy ? "Searching…" : isDemo ? "Ask" : "Search passages"}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div style={{ marginTop: 12 }}>
          <Banner tone="error">{error}</Banner>
        </div>
      )}
      {result && <Answer r={result} />}
      {hits && (
        <div className="panel" style={{ marginTop: 16 }}>
          <div className="panel-head">Matching passages ({hits.length})</div>
          <div className="panel-body">
            {hits.length === 0 && <p className="muted">No passage of your documents matched.</p>}
            {hits.map((h) => (
              <blockquote key={h.chunk_id} style={{ margin: "0 0 12px" }}>
                <div className="small faint">
                  {h.filename}, page {h.page_no}
                </div>
                {h.text}
              </blockquote>
            ))}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="panel" style={{ marginTop: 16 }}>
          <div className="panel-head">Earlier questions</div>
          <div className="panel-body">
            {history.map((h, i) => (
              <details key={h.id ?? i} style={{ marginBottom: 8 }}>
                <summary>{h.question}</summary>
                <Answer r={h} compact />
              </details>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function Answer({ r, compact }: { r: AskResult; compact?: boolean }) {
  return (
    <div className={compact ? "" : "panel"} style={{ marginTop: compact ? 8 : 16 }}>
      {!compact && <div className="panel-head">Answer</div>}
      <div className={compact ? "" : "panel-body"}>
        {r.insufficient ? (
          <Banner tone="warn">
            <b>{r.answer}</b>
            {r.reason && <div className="small">Why: {r.reason}.</div>}
          </Banner>
        ) : (
          <p>{r.answer}</p>
        )}
        {r.citations.map((c, i) => (
          <blockquote key={i} style={{ margin: "6px 0" }}>
            <span className="tag tag-pos">verified</span> {citeLabel(c)}: “{c.quote}”
          </blockquote>
        ))}
        {r.rejected_citations.length > 0 && (
          <p className="small faint" style={{ marginTop: 8 }}>
            {r.rejected_citations.length} quote(s) proposed by the model were removed: not found in your documents.
          </p>
        )}
        <p className="small faint">
          Passages searched: {r.retrieved.map((x) => `${x.filename} p.${x.page_no}`).join(", ") || "none"} · search:{" "}
          {r.mode} · model: {r.model}
        </p>
      </div>
    </div>
  );
}
