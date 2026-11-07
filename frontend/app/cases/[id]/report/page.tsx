import Link from "next/link";
import { notFound } from "next/navigation";
import { getCase } from "@/lib/demo-case";
import { fmtDate, fmtINRShort, pct } from "@/lib/format";
import { computeInterest } from "@/lib/api";
import { Banner, DownloadIcon } from "@/components/icons";
import styles from "./report.module.css";

export const metadata = { title: "Report" };

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase((await params).id);
  if (!c) notFound();
  const { outcome, band, weakPoints, defences, similarCount } = c.report;
  // Award range comes from the Python calculator, never from the model: the top is the full claim;
  // the bottom assumes the bench also excludes a further 9 months for NGT bans and the second COVID wave.
  let award: { low: number; high: number } | null = null;
  let calcError: string | null = null;
  try {
    const base = { payments: c.payments, possessionPromised: c.possessionPromised, annualRatePct: c.ratePct, asOf: c.asOf, rateSource: c.rateBasis };
    const [full, reduced] = await Promise.all([
      computeInterest({ ...base, extensionMonths: c.extensionMonths }),
      computeInterest({ ...base, extensionMonths: c.extensionMonths + 9 }),
    ]);
    award = { low: Number(reduced.delay.interest), high: Number(full.delay.interest) };
  } catch (e) {
    calcError = e instanceof Error ? e.message : "Calculation failed.";
  }

  const bars = [
    { key: "allowed", label: "Allowed", v: outcome.allowed, cls: styles.segPos },
    { key: "partly", label: "Partly allowed", v: outcome.partly, cls: styles.segMid },
    { key: "dismissed", label: "Dismissed", v: outcome.dismissed, cls: styles.segNeg },
  ];

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Decision report</h2>
          <p>Based on {similarCount} past orders with facts close to yours, and the simulated hearing. Read the weak points before deciding to file.</p>
        </div>
        <div className="section-actions">
          <button type="button" className="btn"><DownloadIcon /> Download PDF</button>
          <Link href={`/cases/${c.id}/draft`} className="btn btn-primary">Open complaint draft</Link>
        </div>
      </div>

      <div className={styles.summary}>
        <section className="panel panel-body">
          <div className="label">How similar cases ended</div>
          <div className={styles.stack} role="img" aria-label={bars.map((b) => `${b.label} ${pct(b.v)}`).join(", ")}>
            {bars.map((b) => (
              <div key={b.key} className={`${styles.seg} ${b.cls}`} style={{ width: `${b.v * 100}%` }} />
            ))}
          </div>
          <ul className={styles.legend}>
            {bars.map((b) => (
              <li key={b.key}>
                <span className={`${styles.swatch} ${b.cls}`} />
                {b.label} <span className="num">{pct(b.v)}</span>
                <span className="faint num"> ({Math.round(b.v * similarCount)})</span>
              </li>
            ))}
          </ul>
          <p className={styles.read}>
            Likely outcome: <b>allowed in full</b>, with a confidence band of <span className="num">{pct(band[0])}–{pct(band[1])}</span>.
            In about one case in ten like yours, the complaint was dismissed.
          </p>
        </section>

        <section className="panel panel-body">
          <div className="label">Estimated award to date</div>
          {award ? (
            <div className={styles.award}>
              <span className="num">{fmtINRShort(award.low)}</span> <span className="faint" style={{ fontWeight: 400 }}>to</span>{" "}
              <span className="num">{fmtINRShort(award.high)}</span>
            </div>
          ) : (
            <div className={styles.calcError}>
              <Banner tone="error"><b>Could not calculate.</b> {calcError}</Banner>
            </div>
          )}
          <p className="small muted" style={{ margin: "10px 0 0" }}>
            Delay interest up to {fmtDate(c.asOf)}. The higher figure is the full claim. The lower one is what you get if the bench
            also excludes about nine months for construction bans and the second COVID wave, as some similar orders did.{" "}
            <Link href={`/cases/${c.id}/money`}>See the working</Link>
          </p>
        </section>
      </div>

      <h3 className={styles.h}>Where your case is weak</h3>
      <ol className={styles.weak}>
        {weakPoints.map((w, i) => (
          <li key={w.title} className="panel">
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
      <div className="panel table-wrap">
        <table className="ledger">
          <thead>
            <tr><th>Defence</th><th className="r">Raised in similar orders</th><th>Your answer</th></tr>
          </thead>
          <tbody>
            {defences.map((d) => (
              <tr key={d.title}>
                <td style={{ fontWeight: 500 }}>{d.title}</td>
                <td className="r num">{pct(d.seenIn)}</td>
                <td className="muted">{d.answer}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className={styles.h}>Most similar past orders</h3>
      <div className={styles.orders}>
        {c.similar.map((o) => (
          <article key={o.id} className="panel panel-body panel-hover">
            <div className={styles.orderTop}>
              <span className="code">{o.id}</span>
              <span className={`tag ${o.outcome === "Allowed" ? "tag-pos" : o.outcome === "Dismissed" ? "tag-neg" : "tag-mid"}`}>
                {o.outcome}
              </span>
            </div>
            <div className="small faint">{o.bench} · decided {fmtDate(o.decided)} · {pct(o.similarity)} similar</div>
            <p className={styles.holding}>{o.holding}</p>
            <div className="small muted">{o.claim}. Award: {o.award}.</div>
          </article>
        ))}
      </div>

      <div className={styles.caveat}>
        <Banner tone="info">
          <b>Not legal advice.</b> This report shows patterns in past orders and does not say how your bench will decide. Before
          filing, have an advocate who appears before the authority review it.
        </Banner>
      </div>
    </>
  );
}
