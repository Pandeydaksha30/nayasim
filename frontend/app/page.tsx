import Link from "next/link";
import { demoCase } from "@/lib/demo-case";
import { pct } from "@/lib/format";
import { getUser } from "@/lib/server-session";
import styles from "./home.module.css";

export const dynamic = "force-dynamic";

const STEPS = [
  ["Upload your papers", "Agreement, allotment letter, receipts and builder letters, including scans and Hindi text."],
  ["Check the facts", "Dates, payments and the promised possession date, each shown with the line on the page it came from."],
  ["Answer what is missing", "Only the questions your documents do not answer, such as whether possession was offered."],
  ["See the money", "Delay interest and refund worked out payment by payment at the prescribed rate, by ordinary code."],
  ["Read the hearing", "Arguments for both sides and a bench view, citing only past orders whose quotes are found in the record."],
] as const;

const LIMITS = [
  ["Not legal advice", "NyayaSim helps you prepare. It does not replace an advocate, and it does not file anything for you."],
  ["Predictions can be wrong", "Outcome shares describe how similar past orders ended. Your bench may decide differently."],
  ["One authority for now", "Past orders come from HRERA Gurugram. Other authorities are planned, not yet covered."],
  ["Early access", "Features are still being tested. Accuracy figures will be published only after they are checked."],
] as const;

export default async function HomePage() {
  const user = await getUser();
  const r = demoCase.report;
  return (
    <main>
      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div>
            <div className={styles.kicker}>For home buyers with a RERA claim</div>
            <h1 className={styles.title}>Prepare your complaint with the record in front of you.</h1>
            <p className={styles.lede}>
              NyayaSim reads your builder–buyer papers, works out what you are owed, and shows how the authority
              decided cases like yours, with every figure traceable to a page.
            </p>
            <div className={styles.ctas}>
              {user ? (
                <Link href="/dashboard" className="btn btn-primary">Go to your cases</Link>
              ) : (
                <Link href="/signup" className="btn btn-primary">Create a free account</Link>
              )}
              <Link href={`/cases/${demoCase.id}/report`} className="btn">See an example report</Link>
            </div>
            <div className={styles.fine}>Free during early access. Decision support, not legal advice.</div>
          </div>

          <div className={styles.sheet} aria-label="Excerpt from the example report">
            <div className={styles.sheetHead}>
              <span className="label" style={{ fontSize: 11 }}>Decision report · excerpt</span>
              <span className="tag tag-neutral">Fictional example</span>
            </div>
            <div className={styles.sheetBody}>
              <div className={styles.caseName}>{demoCase.title}</div>
              <div className={styles.caseSub}>{demoCase.claimType} · {demoCase.project}</div>
              <div className={styles.bars}>
                {[
                  ["Allowed", r.outcome.allowed, ""],
                  ["Partly allowed", r.outcome.partly, styles.fillMid],
                  ["Dismissed", r.outcome.dismissed, styles.fillLow],
                ].map(([label, v, cls]) => (
                  <div key={label as string} className={styles.bar}>
                    <span className="muted">{label}</span>
                    <span className={styles.track}><span className={`${styles.fill} ${cls}`} style={{ width: `${(v as number) * 100}%` }} /></span>
                    <span className={styles.pct}>{pct(v as number)}</span>
                  </div>
                ))}
              </div>
              <dl className={styles.sheetRows}>
                <div className={styles.sheetRow}><dt>Similar past orders</dt><dd className="num">{r.similarCount}</dd></div>
                <div className={styles.sheetRow}><dt>Weak points found</dt><dd className="num">{r.weakPoints.length}</dd></div>
                <div className={styles.sheetRow}><dt>Citations kept only if verified</dt><dd>Yes</dd></div>
              </dl>
            </div>
          </div>
        </div>
      </section>

      <div className={styles.figuresWrap}>
        <div className={styles.figures}>
          <div className={styles.figure}>
            <div className={styles.figureValue}>2,019</div>
            <div className={styles.figureLabel}>public HRERA Gurugram orders read and searched for cases like yours, of 13,992 published</div>
          </div>
          <div className={styles.figure}>
            <div className={styles.figureValue}>2018–2026</div>
            <div className={styles.figureLabel}>decisions covered, from April 2018 to October 2026</div>
          </div>
          <div className={styles.figure}>
            <div className={styles.figureValue}>65,974</div>
            <div className={styles.figureLabel}>passages indexed, so a cited quote can be checked word for word</div>
          </div>
        </div>
      </div>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2>How it works</h2>
          <p>Five steps from a folder of papers to a report you can take to your advocate.</p>
        </div>
        <ol className={styles.steps}>
          {STEPS.map(([title, text], i) => (
            <li key={title}>
              <span className={styles.stepNo}>{String(i + 1).padStart(2, "0")}</span>
              <span className={styles.stepTitle}>{title}</span>
              <span className={styles.stepText}>{text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2>What it is not</h2>
          <p>The limits matter as much as the features. <Link href="/method">Read the full method</Link>.</p>
        </div>
        <div className={styles.limits}>
          {LIMITS.map(([title, text]) => (
            <div key={title} className={styles.limit}>
              <b>{title}</b>
              <span>{text}</span>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.closing}>
        <div className={styles.closingBox}>
          <div>
            <h2>Start with the papers you already have.</h2>
            <p>Your documents stay in your account. Delete the account and they are deleted with it.</p>
          </div>
          {user ? (
            <Link href="/cases/new" className="btn btn-primary">Start a new case</Link>
          ) : (
            <Link href="/signup" className="btn btn-primary">Create a free account</Link>
          )}
        </div>
      </section>
    </main>
  );
}
