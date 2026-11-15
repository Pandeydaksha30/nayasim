import Link from "next/link";
import { getCase, getHearing } from "@/lib/cases-api";
import { fmtINRShort } from "@/lib/format";
import { EXAMPLE_ID } from "@/lib/http";
import { getStats, type PublicStats } from "@/lib/insights-api";
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
  // Figures are counted from the database on each visit; if the API is down the band is left out.
  let stats: PublicStats | null = null;
  try {
    stats = await getStats();
  } catch {
    stats = null;
  }
  // The excerpt is read from the recorded example, so it shows what the system really produced.
  const [example, run] = await Promise.all([getCase(EXAMPLE_ID), getHearing(EXAMPLE_ID)]);
  const h = run?.result;
  const kept = h ? h.arguments.buyer.length + h.arguments.builder.length : 0;
  const quotes = h
    ? [...h.arguments.buyer, ...h.arguments.builder].reduce((n, a) => n + a.citations.length, 0) + h.judge.citations.length
    : 0;
  const num = (n: number) => n.toLocaleString("en-IN");
  const year = (iso: string | null) => (iso ? iso.slice(0, 4) : "");
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
              <Link href={`/cases/${EXAMPLE_ID}/report`} className="btn">See an example report</Link>
            </div>
            <div className={styles.fine}>Free during early access. Decision support, not legal advice.</div>
          </div>

          <div className={styles.sheet} aria-label="Excerpt from the example report">
            <div className={styles.sheetHead}>
              <span className={`label ${styles.sheetLabel}`}>Decision report · excerpt</span>
              <span className="tag tag-neutral">Fictional buyer, real orders</span>
            </div>
            <div className={styles.sheetBody}>
              <div className={styles.caseName}>{example.title.replace(/\s*\(DEMO\)$/, "")}</div>
              <div className={styles.caseSub}>
                Delayed possession · {example.documents.length} documents, {example.facts.length} facts checked
              </div>
              {h && (
                <dl className={styles.sheetRows}>
                  <div className={styles.sheetRow}><dt>Past orders the hearing drew on</dt><dd className="num">{h.precedents.length}</dd></div>
                  <div className={styles.sheetRow}><dt>Arguments that passed the citation check</dt><dd className="num">{kept}</dd></div>
                  <div className={styles.sheetRow}><dt>Quotes verified word for word</dt><dd className="num">{quotes}</dd></div>
                  {h.award.available && h.award.delay_interest && (
                    <div className={styles.sheetRow}>
                      <dt>Delay interest, worked out by code</dt>
                      <dd className="num">{fmtINRShort(Number(h.award.delay_interest))}</dd>
                    </div>
                  )}
                  <div className={styles.sheetRow}>
                    <dt>Share of similar orders won</dt>
                    <dd>
                      {h.outcome_shares.insufficient
                        ? "Not shown: too few verified"
                        : `${Math.round((h.outcome_shares.buyer_wins ?? 0) * 100)}%`}
                    </dd>
                  </div>
                </dl>
              )}
            </div>
          </div>
        </div>
      </section>

      {stats && stats.orders_read > 0 && (
        <div className={styles.figuresWrap}>
          <div className={styles.figures}>
            <div className={styles.figure}>
              <div className={styles.figureValue}>{num(stats.orders_read)}</div>
              <div className={styles.figureLabel}>
                public {stats.source} orders read and searchable, of {num(stats.orders_listed)} published
              </div>
            </div>
            <div className={styles.figure}>
              <div className={styles.figureValue}>{year(stats.first_decided)}–{year(stats.last_decided)}</div>
              <div className={styles.figureLabel}>years of decisions covered by those orders</div>
            </div>
            <div className={styles.figure}>
              <div className={styles.figureValue}>{num(stats.passages)}</div>
              <div className={styles.figureLabel}>passages indexed, so a cited quote can be checked word for word</div>
            </div>
          </div>
        </div>
      )}

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
