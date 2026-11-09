import Link from "next/link";
import { Banner } from "@/components/icons";
import { sessionAuth } from "@/lib/server-session";
import { type CaseFull, getHearing } from "@/lib/cases-api";
import { fmtDate, fmtINRShort, pct } from "@/lib/format";
import styles from "../report/report.module.css";

const OUTCOME_LABEL: Record<string, string> = {
  allowed: "Allowed",
  partly_allowed: "Partly allowed",
  dismissed: "Dismissed",
  disposed_of: "Disposed of",
  withdrawn: "Withdrawn",
  other: "Other",
};
const OUTCOME_CLASS: Record<string, string> = { allowed: styles.segPos, partly_allowed: styles.segMid, dismissed: styles.segNeg };

export default async function LiveReport({ c }: { c: CaseFull }) {
  let run;
  try {
    run = await getHearing(c.id, await sessionAuth());
  } catch (e) {
    return <Banner tone="error"><b>Could not load the report.</b> {e instanceof Error ? e.message : ""}</Banner>;
  }
  if (!run) {
    return (
      <>
        <div className="section-title"><div><h2>Decision report</h2></div></div>
        <Banner tone="info">
          The report is built from a simulated hearing. <Link href={`/cases/${c.id}/hearing`}>Run the hearing first</Link>.
        </Banner>
      </>
    );
  }

  const r = run.result;
  const s = r.outcome_shares;
  const order = ["allowed", "partly_allowed", "dismissed", "disposed_of", "withdrawn", "other"];
  const bars = order.filter((k) => s.counts[k]).map((k) => ({ k, n: s.counts[k], v: s.counts[k] / s.with_record }));

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Decision report</h2>
          <p>
            Based on {r.precedents.length} similar orders decided before {fmtDate(run.cutoff)}, and the simulated hearing.
            Numbers are counted and calculated by code; the bench’s view is the model’s reasoning on checked arguments.
          </p>
        </div>
        <Link className="btn" href={`/cases/${c.id}/hearing`}>See the hearing</Link>
      </div>

      <div className={styles.summary}>
        <section className="panel panel-body">
          <div className="label">How similar cases ended</div>
          {s.insufficient ? (
            <div style={{ marginTop: 12 }}><Banner tone="warn"><b>Insufficient precedent.</b> {s.note}</Banner></div>
          ) : (
            <>
              <div className={styles.stack} role="img" aria-label={bars.map((b) => `${OUTCOME_LABEL[b.k]} ${b.n}`).join(", ")}>
                {bars.map((b) => (
                  <div key={b.k} className={`${styles.seg} ${OUTCOME_CLASS[b.k] ?? ""}`}
                       style={{ width: `${b.v * 100}%`, background: OUTCOME_CLASS[b.k] ? undefined : "var(--border-strong)" }} />
                ))}
              </div>
              <ul className={styles.legend}>
                {bars.map((b) => (
                  <li key={b.k}>
                    <span className={`${styles.swatch} ${OUTCOME_CLASS[b.k] ?? ""}`}
                          style={{ background: OUTCOME_CLASS[b.k] ? undefined : "var(--border-strong)" }} />
                    {OUTCOME_LABEL[b.k] ?? b.k} <span className="num">{b.n}</span>
                  </li>
                ))}
              </ul>
              <p className={styles.read}>
                The buyer won (allowed or partly allowed) in <b>{pct(s.buyer_wins ?? 0)}</b> of the {s.with_record} similar
                orders with a verified outcome (90% range {pct(s.interval_90?.[0] ?? 0)}–{pct(s.interval_90?.[1] ?? 1)}).
                The bench’s view on your facts: <b>{OUTCOME_LABEL[r.judge.outcome] ?? r.judge.outcome}</b>.
              </p>
            </>
          )}
        </section>

        <section className="panel panel-body">
          <div className="label">Estimated amount to date</div>
          {r.award.available ? (
            <>
              <div className={styles.award}>
                {r.award.delay_interest ? (
                  <span className="num">{fmtINRShort(Number(r.award.delay_interest))}</span>
                ) : (
                  <span className="num">{fmtINRShort(Number(r.award.refund_total))}</span>
                )}
              </div>
              <p className="small muted" style={{ margin: "8px 0 0" }}>
                {r.award.delay_interest
                  ? `Delay interest on ${fmtINRShort(Number(r.award.principal))} paid, from ${fmtDate(r.award.possession_due!)} to ${fmtDate(r.award.as_of!)}.`
                  : `Refund of ${fmtINRShort(Number(r.award.principal))} with interest to ${fmtDate(r.award.as_of!)}.`}{" "}
                Rate {r.award.rate_pct}%: {r.award.rate_basis}. Withdrawing instead: {fmtINRShort(Number(r.award.refund_total))}.{" "}
                <Link href={`/cases/${c.id}/money`}>Change the inputs</Link>
              </p>
            </>
          ) : (
            <div style={{ marginTop: 12 }}><Banner tone="warn"><b>No figure.</b> Not calculated: {r.award.reason}.</Banner></div>
          )}
        </section>
      </div>

      <h3 className={styles.h}>Where your case is weak (bench’s view)</h3>
      {r.judge.weak_points.length === 0 && <p className="muted">The bench listed no weak points.</p>}
      <ol className={styles.weak}>
        {r.judge.weak_points.map((w, i) => (
          <li key={i} className="panel">
            <span className={styles.idx}>{i + 1}</span>
            <div>
              <h3>{w.title}</h3>
              <p className="muted">{w.detail}</p>
              <p className={styles.fix}><b>What to do:</b> {w.fix}</p>
            </div>
          </li>
        ))}
      </ol>

      <h3 className={styles.h}>What the builder is likely to argue</h3>
      {r.arguments.builder.length === 0 ? (
        <p className="muted">No builder defence survived the citation check.</p>
      ) : (
        <div className="panel table-wrap">
          <table className="ledger stack">
            <thead><tr><th>Defence</th><th>Based on</th></tr></thead>
            <tbody>
              {r.arguments.builder.map((a, i) => (
                <tr key={i}>
                  <td data-label="Defence"><span className="cell-title">{a.heading}</span><div className="cell-sub">{a.body}</div></td>
                  <td data-label="Based on" className="small">{a.citations.map((ct) => `${ct.complaint_no} p.${ct.page_no}`).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 className={styles.h}>Similar past orders used</h3>
      <div className={styles.orders}>
        {r.precedents.map((p) => (
          <article key={p.ref} className="panel panel-body">
            <div className={styles.orderTop}>
              <span className="code">{p.complaint_no}</span>
              {p.outcome ? <span className="tag tag-neutral">{OUTCOME_LABEL[p.outcome] ?? p.outcome}</span> : <span className="tag tag-mid">Outcome not verified</span>}
            </div>
            <div className="small faint">
              Decided {fmtDate(p.decided_on)} · pages {p.pages.join(", ")}
              {p.interest_rate_pct && ` · rate ${Number(p.interest_rate_pct)}%`}
            </div>
          </article>
        ))}
      </div>

      <div className={styles.caveat}>
        <Banner tone="info">
          <b>Not legal advice.</b> This report shows patterns in past orders and a simulated view; it does not say how your
          bench will decide. Have an advocate who appears before the authority review it before filing.
        </Banner>
      </div>
    </>
  );
}
