"use client";
/**
 * Agent analysis: the user states an objective; the server's agent chooses tools step by step
 * (bounded), and this page shows each step as it happens, then the answer with verified citations.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Citations, type PassageItem, Passages } from "@/components/evidence";
import styles from "@/components/evidence.module.css";
import { Banner } from "@/components/icons";
import { type AgentRun, type AgentStep, getAgentRun, listAgentRuns, startAgent } from "@/lib/agent-api";
import { fmtDate, fmtINR } from "@/lib/format";

const POLL_MS = 2500;

const SUGGESTIONS = [
  "When was possession promised, how late is it, and what interest could the buyer claim at 10.80%?",
  "Find past orders on delayed possession similar to this case and summarise how they ended.",
  "Run a simulated hearing and explain the judge's assessment and the weak points.",
];

const ACTION: Record<string, string> = {
  search_documents: "Searched your documents",
  get_facts: "Read the case facts",
  search_orders: "Searched past orders",
  verify_quote: "Checked a quote against its source",
  calculate_interest: "Calculated interest",
  estimate_outcome: "Counted how similar orders ended",
  run_hearing: "Ran the simulated hearing",
  delegate: "Handed a task to a specialist",
  model_error: "The model did not answer",
};
const AGENT: Record<string, string> = {
  orchestrator: "Coordinator",
  document_analysis: "Document analysis",
  legal_research: "Legal research",
  claim_analysis: "Claim analysis",
};
const STATUS: Record<AgentRun["status"], [string, string]> = {
  running: ["Running", "tag-mid"],
  completed: ["Completed", "tag-pos"],
  incomplete: ["Stopped early", "tag-mid"],
  failed: ["Failed", "tag-neg"],
};
const OUTCOME: Record<string, string> = {
  allowed: "Allowed", partly_allowed: "Partly allowed", dismissed: "Dismissed", disposed_of: "Disposed of", withdrawn: "Withdrawn",
};

type Obs = Record<string, unknown>;
const isObj = (x: unknown): x is Obs => typeof x === "object" && x !== null && !Array.isArray(x);
const str = (x: unknown) => (x === null || x === undefined ? "" : String(x));
const money = (x: unknown) => (x === null || x === undefined || x === "" ? "not available" : fmtINR(Number(x)));

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (<><dt>{k}</dt><dd>{children}</dd></>);
}

/** A readable view of what a tool returned; the untouched result stays one click away. */
function Result({ step }: { step: AgentStep }) {
  const o = step.observation;
  if (!isObj(o)) return null;
  if (!step.ok && typeof o.error === "string") return <p className={styles.stepError}>{o.error}</p>;

  let body: React.ReactNode = null;
  if (Array.isArray(o.passages)) {
    const items: PassageItem[] = (o.passages as Obs[]).map((p, i) => ({
      key: i, source: `${str(p.ref)} · ${str(p.file)}`, where: `page ${str(p.page)}`, text: str(p.text),
    }));
    body = <Passages items={items} empty="No passage of the documents matched." />;
  } else if (Array.isArray(o.excerpts)) {
    const items: PassageItem[] = (o.excerpts as Obs[]).map((p, i) => ({
      key: i, source: `${str(p.ref)} · ${str(p.complaint_no)}`, mono: true,
      where: `decided ${fmtDate(str(p.decided_on))} · page ${str(p.page)}`, text: str(p.text),
    }));
    body = <Passages items={items} empty="No stored order matched." />;
  } else if (Array.isArray(o.facts)) {
    const facts = o.facts as Obs[];
    body = facts.length === 0 ? <p className="muted small">No usable facts in this case yet.</p> : (
      <dl className={styles.kv}>
        {facts.slice(0, 12).map((f, i) => (
          <Row key={i} k={`${str(f.ref)} · ${str(f.label)}`}>{str(f.value).replace(";", " · ₹")} <span className="faint">({str(f.file)}, p. {str(f.page)})</span></Row>
        ))}
        {facts.length > 12 && <Row k="">and {facts.length - 12} more</Row>}
      </dl>
    );
  } else if ("refund_interest" in o && "amount_paid" in o) {
    body = (
      <dl className={styles.kv}>
        <Row k="Rate">{str(o.rate_pct)}% a year, to {fmtDate(str(o.as_of))}</Row>
        <Row k="Amount paid">{money(o.amount_paid)}</Row>
        <Row k="Delay interest">{money(o.delay_interest)}{o.possession_due ? ` (possession was due ${fmtDate(str(o.possession_due))})` : ""}</Row>
        {"refund_total_with_interest" in o && (
          <Row k="Refund with interest">{money(o.refund_total_with_interest)} (interest {money(o.refund_interest)})</Row>
        )}
        <Row k="Method">{str(o.method)}</Row>
      </dl>
    );
  } else if ("verified" in o) {
    body = o.verified
      ? <Passages empty="" items={[{ key: 1, source: "Found word for word", where: `page ${str(o.page)}`, text: str(o.stored_quote) }]} />
      : <p className={styles.stepError}>Not verified: {str(o.reason)}</p>;
  } else if ("judge_outcome" in o) {
    body = (
      <dl className={styles.kv}>
        <Row k="Bench's view">{OUTCOME[str(o.judge_outcome)] ?? str(o.judge_outcome)}</Row>
        <Row k="Arguments kept">buyer {str(o.buyer_arguments_kept)}, builder {str(o.builder_arguments_kept)}</Row>
        <Row k="Removed by citation check">{str(o.arguments_removed_by_citation_check)}</Row>
        <Row k="Weak points">{(o.weak_points as string[] | undefined)?.join("; ") || "none listed"}</Row>
      </dl>
    );
  } else if ("predicted" in o || "available" in o) {
    body = o.available === false ? <p className="muted small">No estimate: {str(o.reason)}.</p> : (
      <dl className={styles.kv}>
        <Row k="Most common result">{OUTCOME[str(o.predicted)] ?? str(o.predicted)}</Row>
        <Row k="Counted from">{str(o.orders_used)} {str(o.basis)}</Row>
        <Row k="Counts">{isObj(o.counts) ? Object.entries(o.counts).map(([k, n]) => `${OUTCOME[k] ?? k} ${n}`).join(", ") : ""}</Row>
      </dl>
    );
  } else if ("answer" in o && "agent" in o) {
    body = (
      <dl className={styles.kv}>
        <Row k="Specialist">{AGENT[str(o.agent)] ?? str(o.agent)} ({str(o.steps_used)} steps)</Row>
        <Row k="Reported">{str(o.answer)}</Row>
      </dl>
    );
  }
  return (
    <div className={styles.stepResult}>
      {body}
      <details className={styles.raw}>
        <summary>Raw result</summary>
        <pre>{JSON.stringify(o, null, 2)}</pre>
      </details>
    </div>
  );
}

function StepArgs({ args }: { args: Record<string, unknown> }) {
  const parts: [string, string][] = [];
  if (args.query) parts.push(["Query", str(args.query)]);
  if (args.agent) parts.push(["To", AGENT[str(args.agent)] ?? str(args.agent)]);
  if (args.task) parts.push(["Task", str(args.task)]);
  if (args.ref) parts.push(["Source", str(args.ref)]);
  if (args.quote) parts.push(["Quote", `“${str(args.quote)}”`]);
  if (args.rate_pct !== undefined) parts.push(["Rate", `${str(args.rate_pct)}%`]);
  return (<>{parts.map(([k, v]) => <p key={k} className={styles.stepArg}><span>{k}: </span>{v}</p>)}</>);
}

export default function AgentClient({ caseId, isDemo, readOnly }: { caseId: string; isDemo: boolean; readOnly: boolean }) {
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
  const canRun = isDemo && !readOnly;
  const seconds = run ? run.steps.reduce((s, st) => s + st.ms, 0) / 1000 : 0;

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Agent analysis</h2>
          <p>
            The agent decides which tool to use next: your documents, past orders, the interest calculator, the outcome
            count, a specialist or the simulated hearing. It is limited to 6 steps and 7 minutes. Every step is shown, and
            every citation in the answer is checked by code.
          </p>
        </div>
      </div>

      {readOnly ? (
        <Banner tone="info">
          <b>This example is a recording, so a new analysis cannot be started here.</b> The runs below are shown exactly as
          they happened, including the steps that failed.
        </Banner>
      ) : (
        <>
          {!isDemo && (
            <div style={{ marginBottom: 12 }}>
              <Banner tone="info">
                Agent analysis sends passages of your documents to the AI model, which may keep data. It stays switched off
                for your case until a model that keeps no data is configured.
              </Banner>
            </div>
          )}
          <form onSubmit={start} className="panel">
            <div className="panel-body">
              <label className="field">
                <span className="field-label">What should the agent work out?</span>
                <textarea className="input" rows={3} value={objective} onChange={(e) => setObjective(e.target.value)}
                          minLength={10} maxLength={600} disabled={!canRun} />
              </label>
              <div className={styles.suggest}>
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className={styles.chip} disabled={!canRun} onClick={() => setObjective(s)}>{s}</button>
                ))}
              </div>
              <div className="section-actions" style={{ marginTop: 14 }}>
                <button className="btn btn-primary" disabled={!canRun || starting || run?.status === "running" || objective.trim().length < 10}>
                  {run?.status === "running" ? "Running…" : starting ? "Starting…" : "Run analysis"}
                </button>
              </div>
            </div>
          </form>
        </>
      )}

      <div className={styles.stack}>
        {error && <Banner tone="error">{error}</Banner>}

        {run && (
          <section className="panel">
            <div className={`panel-head ${styles.runHead}`}>
              <span className={styles.runTitle}>
                Run {run.id} <span className={`tag ${STATUS[run.status][1]}`}>{STATUS[run.status][0]}</span>
              </span>
              <span className={styles.runMeta}>
                {run.steps.length} {run.steps.length === 1 ? "step" : "steps"} · {seconds.toFixed(0)} s · {fmtDate(run.started_at.slice(0, 10))}
                {res.stop_reason ? ` · ${res.stop_reason}` : ""}
              </span>
            </div>
            <div className="panel-body">
              <p className={styles.objective}><span className="faint">Objective: </span>{run.objective}</p>

              <div className={styles.subhead}>Steps taken</div>
              <ol className={styles.timeline}>
                {run.steps.map((st) => (
                  <li key={st.n} className={`${styles.step} ${st.ok ? "" : styles.stepFail}`}>
                    <span className={styles.stepNo}>{st.n}</span>
                    <div>
                      <div className={styles.stepTop}>
                        <span className={styles.stepName}>{ACTION[st.action] ?? st.action}</span>
                        <span className={styles.stepBy}>{AGENT[st.agent] ?? st.agent}</span>
                        {!st.ok && <span className="tag tag-neg">Did not work</span>}
                        <span className={styles.stepTime}>{(st.ms / 1000).toFixed(1)} s</span>
                      </div>
                      <StepArgs args={st.args} />
                      {st.thought && <p className={styles.stepWhy}>Why: {st.thought}</p>}
                      <Result step={st} />
                    </div>
                  </li>
                ))}
              </ol>
              {run.status === "running" && (
                <div className={styles.working} role="status"><span className={styles.dot} /> Choosing the next step…</div>
              )}
              {run.error && <div style={{ marginTop: 14 }}><Banner tone="error">{run.error}</Banner></div>}

              {res.answer && (
                <>
                  <div className={styles.subhead}>Answer</div>
                  {res.insufficient || !res.grounded ? (
                    <Banner tone="warn">
                      {res.answer}
                      <div className="small">
                        {res.insufficient ? "The agent found the evidence insufficient." : "No citation could be verified: treat this as unsupported."}
                      </div>
                    </Banner>
                  ) : (
                    <p className={styles.answer}>{res.answer}</p>
                  )}
                  {!!res.citations?.length && <div className={styles.subhead}>Where this comes from</div>}
                  <Citations citations={res.citations ?? []} rejected={res.rejected_citations} />
                </>
              )}

              {res.judge && (
                <div className={styles.judge}>
                  <div className="label">Bench’s view in the simulated hearing</div>
                  <p><b>{OUTCOME[res.judge.outcome] ?? res.judge.outcome}.</b> {res.judge.reasoning}</p>
                  {res.judge.weak_points.length > 0 && (
                    <ul className={styles.weak}>
                      {res.judge.weak_points.map((w, i) => <li key={i}><b>{w.title}.</b> {w.fix}</li>)}
                    </ul>
                  )}
                </div>
              )}

              {past.length > 1 && (
                <div className={styles.earlier}>
                  Other runs:
                  {past.filter((p) => p.id !== run.id).map((p) => (
                    <button key={p.id} type="button" className="btn btn-quiet" onClick={() => setRun(p)}>
                      Run {p.id} · {STATUS[p.status][0].toLowerCase()}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}

        {!run && readOnly && <p className="muted">No agent run was recorded for this example.</p>}
      </div>
    </>
  );
}
