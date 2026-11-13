"use client";

/**
 * Agentic analysis: the user states an objective; the server's agent chooses tools step by step
 * (bounded), and this page shows each step as it happens, then the answer with verified citations.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Banner } from "@/components/icons";
import { type AgentRun, citeLabel, getAgentRun, listAgentRuns, startAgent } from "@/lib/agent-api";

const POLL_MS = 2500;
const SUGGESTIONS = [
  "When was possession promised, how late is it, and what interest could the buyer claim at 10.85%?",
  "Find past orders on delayed possession similar to this case and summarise how they ended.",
  "Run a simulated hearing and explain the judge's assessment and the weak points.",
];

export default function AgentClient({ caseId, isDemo }: { caseId: string; isDemo: boolean }) {
  const [objective, setObjective] = useState(SUGGESTIONS[0]);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [past, setPast] = useState<AgentRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    listAgentRuns(caseId)
      .then((runs) => {
        if (!alive.current) return;
        setPast(runs);
        if (runs[0]) setRun(runs[0]);
      })
      .catch(() => {});
    return () => {
      alive.current = false;
    };
  }, [caseId]);

  const poll = useCallback(async () => {
    if (!run || run.status !== "running") return;
    try {
      const r = await getAgentRun(caseId, run.id);
      if (alive.current) setRun(r);
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : "Lost track of the run.");
    }
  }, [caseId, run]);

  useEffect(() => {
    if (run?.status !== "running") return;
    const t = setInterval(poll, POLL_MS);
    return () => clearInterval(t);
  }, [run?.status, poll]);

  async function start(e: React.FormEvent) {
    e.preventDefault();
    setStarting(true);
    setError(null);
    try {
      const r = await startAgent(caseId, objective);
      setRun(r);
      setPast((p) => [r, ...p]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The analysis could not be started.");
    } finally {
      setStarting(false);
    }
  }

  const res = run?.result ?? {};
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Agent analysis</h2>
          <p>
            The agent decides which tool to use next: your documents, past orders, the interest calculator, the outcome
            estimate, specialist sub-agents or the simulated hearing. It is limited to 6 steps and 7 minutes. Every step is
            shown, and every citation in the answer is checked by code.
          </p>
        </div>
      </div>
      {!isDemo && (
        <div style={{ marginBottom: 12 }}>
          <Banner tone="info">Agent analysis sends document passages to the AI model, so it runs only for demo cases.</Banner>
        </div>
      )}
      <form onSubmit={start} className="panel">
        <div className="panel-body">
          <label className="field">
            <span className="field-label">Objective</span>
            <textarea
              className="input"
              rows={3}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              minLength={10}
              maxLength={600}
            />
          </label>
          <div className="small faint" style={{ margin: "6px 0" }}>
            Examples:{" "}
            {SUGGESTIONS.map((s, i) => (
              <button key={i} type="button" className="btn btn-quiet" onClick={() => setObjective(s)}>
                {i + 1}
              </button>
            ))}
          </div>
          <button className="btn btn-primary" disabled={!isDemo || starting || run?.status === "running"}>
            {run?.status === "running" ? "Running…" : starting ? "Starting…" : "Run analysis"}
          </button>
        </div>
      </form>
      {error && (
        <div style={{ marginTop: 12 }}>
          <Banner tone="error">{error}</Banner>
        </div>
      )}

      {run && (
        <div className="panel" style={{ marginTop: 16 }}>
          <div className="panel-head">
            Run #{run.id}: <span className="tag">{run.status}</span> {res.stop_reason && `· ${res.stop_reason}`}
          </div>
          <div className="panel-body">
            <p className="small muted">Objective: {run.objective}</p>
            <ol style={{ paddingLeft: 20 }}>
              {run.steps.map((st) => (
                <li key={st.n} style={{ marginBottom: 8 }}>
                  <b>{st.action}</b> <span className="small faint">by {st.agent}</span>{" "}
                  <span className={`tag ${st.ok ? "tag-pos" : "tag-neg"}`}>{st.ok ? "ok" : "error"}</span>{" "}
                  <span className="small faint">{(st.ms / 1000).toFixed(1)} s</span>
                  {Object.keys(st.args).length > 0 && <div className="small code">{JSON.stringify(st.args)}</div>}
                  {st.thought && <div className="small muted">Why: {st.thought}</div>}
                  <details>
                    <summary className="small">What came back</summary>
                    <pre className="small" style={{ whiteSpace: "pre-wrap", maxHeight: 240, overflow: "auto" }}>
                      {JSON.stringify(st.observation, null, 2)}
                    </pre>
                  </details>
                </li>
              ))}
              {run.status === "running" && <li className="muted">Working…</li>}
            </ol>
            {run.error && <Banner tone="error">{run.error}</Banner>}
            {res.answer && (
              <>
                <div className="label">Answer</div>
                {res.insufficient || !res.grounded ? (
                  <Banner tone="warn">
                    {res.answer}
                    <div className="small">
                      {res.insufficient ? "The agent found the evidence insufficient." : "No citation could be verified: treat this as unsupported."}
                    </div>
                  </Banner>
                ) : (
                  <p>{res.answer}</p>
                )}
                {(res.citations ?? []).map((c, i) => (
                  <blockquote key={i} style={{ margin: "6px 0" }}>
                    <span className="tag tag-pos">verified</span> {citeLabel(c)}: “{c.quote}”
                  </blockquote>
                ))}
                {(res.rejected_citations ?? []).length > 0 && (
                  <p className="small faint">{res.rejected_citations!.length} citation(s) removed by the code check.</p>
                )}
              </>
            )}
            {res.judge && (
              <div style={{ marginTop: 12 }}>
                <div className="label">Judge assessment (simulated hearing #{res.hearing_run_id})</div>
                <p>
                  <b>{res.judge.outcome.replace(/_/g, " ")}</b>: {res.judge.reasoning}
                </p>
                <ul>
                  {res.judge.weak_points.map((w, i) => (
                    <li key={i}>
                      {w.title}: <span className="muted">{w.fix}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
      {past.length > 1 && (
        <p className="small faint" style={{ marginTop: 12 }}>
          Earlier runs:{" "}
          {past.slice(1).map((p) => (
            <button key={p.id} className="btn btn-quiet" onClick={() => setRun(p)}>
              #{p.id} {p.status}
            </button>
          ))}
        </p>
      )}
    </>
  );
}
