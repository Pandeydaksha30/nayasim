"use client";
/**
 * Contract clause analysis (the mid-viva eContractIQ "benefits and obligations" feature): rights,
 * obligations and penalties of each party. Every clause shown quotes the document, and the quote
 * was found on the page by code; clauses whose quote was not found are counted, not shown.
 */
import { useEffect, useState } from "react";
import styles from "@/components/evidence.module.css";
import { Banner } from "@/components/icons";
import { type ClauseAnalysis as Result, analyseClauses, latestClauses } from "@/lib/agent-api";

const KIND: Record<string, { label: string; tag: string }> = {
  obligation: { label: "Obligation", tag: "tag-neutral" },
  right: { label: "Right", tag: "tag-pos" },
  penalty: { label: "Penalty", tag: "tag-mid" },
  one_sided: { label: "One-sided", tag: "tag-neg" },
};

export default function ClauseAnalysis({ caseId, canRun }: { caseId: string; canRun: boolean }) {
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    latestClauses(caseId).then(setResult).catch(() => {});
  }, [caseId]);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await analyseClauses(caseId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The contract could not be analysed.");
    } finally {
      setBusy(false);
    }
  }

  const parties = result ? [...new Set(result.items.map((i) => i.party))] : [];
  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Contract analysis: who must do what</h3>
        {canRun && (
          <button className="btn" onClick={run} disabled={busy}>
            {busy ? "Reading the contract…" : result ? "Analyse again" : "Analyse the contract"}
          </button>
        )}
      </div>
      <div className="panel-body">
        <p className="small muted" style={{ marginTop: 0 }}>
          Rights, obligations and penalties of each party, and terms that clearly favour one side. Each clause quotes your
          document and the quote was found on that page by code. A plain-English reading, not legal advice.
        </p>
        {!canRun && !result && <p className="small faint">Runs for demo cases only: it sends passages to the AI model.</p>}
        {error && <Banner tone="error">{error}</Banner>}
        {result && result.items.length === 0 && (
          <Banner tone="warn">No clause could be verified against the documents{result.reason ? ` (${result.reason})` : ""}.</Banner>
        )}
        {parties.map((party) => (
          <div key={party} style={{ marginTop: 14 }}>
            <div className={styles.subhead}>{party}</div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {result!.items
                .filter((i) => i.party === party)
                .map((i, n) => (
                  <li key={n} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                    <span className={`tag ${KIND[i.kind]?.tag ?? "tag-neutral"}`}>{KIND[i.kind]?.label ?? i.kind}</span>{" "}
                    {i.summary}
                    <div className="small faint" style={{ marginTop: 4 }}>
                      {i.filename}, page {i.page_no}: “{i.quote}”
                    </div>
                  </li>
                ))}
            </ul>
          </div>
        ))}
        {result && (
          <div className={styles.answerMeta}>
            <span>{result.items.length} clauses verified</span>
            {result.removed.length > 0 && <span>{result.removed.length} removed: quote not found in the document</span>}
            <span>Passages read: {result.passages_read}</span>
            <span>Model: {result.model}</span>
          </div>
        )}
      </div>
    </section>
  );
}
