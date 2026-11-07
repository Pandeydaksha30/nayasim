import LiveHearing from "../live/live-hearing";
import { loadCase } from "@/lib/case-source";
import { type Speaker } from "@/lib/demo-case";
import styles from "./hearing.module.css";

export const metadata = { title: "Simulated hearing" };

const WHO: Record<Speaker, string> = {
  buyer: "Buyer’s advocate",
  builder: "Builder’s advocate",
  judge: "Bench",
};

export default async function HearingPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "live") return <LiveHearing c={src.data} />;
  if (src.kind !== "example") return null; // the layout shows the error
  const c = src.data;
  const rounds = [...new Set(c.hearing.map((a) => a.round))];

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Simulated hearing</h2>
          <p>
            Three agents argue over your facts. Each may only rely on past orders that exist in our store; an argument whose citation
            cannot be found is removed before the bench sees it.
          </p>
        </div>
        <span className="small muted">
          {c.hearing.length} arguments · {c.blockedCount} citation removed
        </span>
      </div>

      <div className={styles.transcript}>
        {rounds.map((r) => (
          <section key={r} className={styles.round}>
            <div className={styles.roundHead}>
              <span className="label">Round {r}</span>
            </div>
            {c.hearing
              .filter((a) => a.round === r)
              .map((a) => (
                <article key={a.id} className={`${styles.arg} ${styles[a.speaker]}`}>
                  <header className={styles.who}>{WHO[a.speaker]}</header>
                  <h3>{a.heading}</h3>
                  <p>{a.body}</p>
                  <ul className={styles.cites}>
                    {a.citations.map((ct) => (
                      <li key={ct.orderId + ct.pinpoint} className={ct.status === "blocked" ? styles.blocked : undefined}>
                        <span><span className="code">{ct.orderId}</span>, {ct.pinpoint}</span>
                        {ct.status === "verified" ? (
                          <span className={styles.ok}>verified</span>
                        ) : (
                          <span className={styles.no}>not found in store, removed</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
          </section>
        ))}
      </div>
    </>
  );
}
