import { Banner } from "@/components/icons";
import { type CaseFull, getHearing, type HearingArgument } from "@/lib/cases-api";
import { fmtDate } from "@/lib/format";
import styles from "../hearing/hearing.module.css";
import RunHearingButton from "./run-hearing-button";

const WHO = { buyer: "Buyer’s advocate", builder: "Builder’s advocate" } as const;

function ArgumentCard({ a }: { a: HearingArgument }) {
  return (
    <article className={`${styles.arg} ${styles[a.side]}`}>
      <header className={styles.who}>{WHO[a.side]}</header>
      <h3>{a.heading}</h3>
      <p>{a.body}</p>
      <ul className={styles.cites}>
        {a.citations.map((c, i) => (
          <li key={i}>
            <span><span className="code">{c.complaint_no ?? c.precedent}</span>, p. {c.page_no}</span>
            <span className={styles.ok}>verified</span>
            {c.stored_quote && <span className="small muted" style={{ flexBasis: "100%" }}>“{c.stored_quote.split(/\s+/).join(" ")}”</span>}
          </li>
        ))}
      </ul>
    </article>
  );
}

export default async function LiveHearing({ c }: { c: CaseFull }) {
  let run;
  try {
    run = await getHearing(c.id);
  } catch (e) {
    return <Banner tone="error"><b>Could not load the hearing.</b> {e instanceof Error ? e.message : ""}</Banner>;
  }

  const header = (
    <div className="section-title">
      <div>
        <h2>Simulated hearing</h2>
        <p>
          Advocates for both sides argue from past orders decided before the hearing date. Every citation is checked against
          the stored order; an argument with any failed citation is removed before the bench sees it.
        </p>
      </div>
      {run && c.is_demo && <RunHearingButton caseId={c.id} again />}
    </div>
  );

  if (!run) {
    return (
      <>
        {header}
        {c.is_demo ? (
          c.facts.length ? <RunHearingButton caseId={c.id} /> : <Banner tone="warn">Find facts in your documents first.</Banner>
        ) : (
          <Banner tone="info">
            <b>Not available for real documents yet.</b> The hearing sends your case facts to the AI model, which may keep
            data. It switches on once a model that keeps no data is configured.
          </Banner>
        )}
      </>
    );
  }

  const r = run.result;
  const removed = r.arguments.removed;
  return (
    <>
      {header}
      <p className="small faint" style={{ marginTop: -8, marginBottom: 16 }}>
        Run on {fmtDate(run.started_at.slice(0, 10))} · precedents decided before {fmtDate(run.cutoff)} · {r.precedents.length} similar orders · {run.models}
      </p>
      <div className={styles.transcript}>
        <section className={styles.round}>
          <div className={styles.roundHead}><span className="label">Arguments that passed the citation check</span></div>
          {[...r.arguments.buyer, ...r.arguments.builder].map((a, i) => <ArgumentCard key={i} a={a} />)}
          {r.arguments.buyer.length + r.arguments.builder.length === 0 && (
            <Banner tone="warn">No argument survived the citation check.</Banner>
          )}
        </section>

        <section className={styles.round}>
          <div className={styles.roundHead}><span className="label">Bench</span></div>
          <article className={`${styles.arg} ${styles.judge}`}>
            <header className={styles.who}>Bench · likely outcome: {r.judge.outcome.replace("_", " ")}</header>
            <p>{r.judge.reasoning}</p>
            {r.judge.citations.length > 0 && (
              <ul className={styles.cites}>
                {r.judge.citations.map((ct, i) => (
                  <li key={i}><span><span className="code">{ct.complaint_no}</span>, p. {ct.page_no}</span><span className={styles.ok}>verified</span></li>
                ))}
              </ul>
            )}
          </article>
        </section>

        {(removed.length > 0 || r.judge.citations_removed.length > 0) && (
          <section className={styles.round}>
            <div className={styles.roundHead}><span className="label">Removed by the citation check</span></div>
            <div className="panel table-wrap">
              <table className="ledger stack">
                <thead><tr><th>Side</th><th>Argument</th><th>Why removed</th></tr></thead>
                <tbody>
                  {removed.map((a, i) => (
                    <tr key={i}>
                      <td data-label="Side">{WHO[a.side]}</td>
                      <td data-label="Argument" className="cell-title">{a.heading}</td>
                      <td data-label="Why removed" className="small muted">
                        {a.removed_because}
                        {a.citations.filter((x) => x.status !== "verified").flatMap((x) => x.reasons).slice(0, 2).map((reason, j) => <div key={j}>· {reason}</div>)}
                      </td>
                    </tr>
                  ))}
                  {r.judge.citations_removed.map((ct, i) => (
                    <tr key={`j${i}`}>
                      <td data-label="Side">Bench</td>
                      <td data-label="Argument">Citation of {ct.complaint_no ?? ct.precedent}, p. {ct.page_no}</td>
                      <td data-label="Why removed" className="small muted">{ct.reasons.join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
