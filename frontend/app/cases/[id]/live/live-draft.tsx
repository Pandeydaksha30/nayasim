import Link from "next/link";
import { Banner } from "@/components/icons";
import { sessionAuth } from "@/lib/server-session";
import type { CaseFull } from "@/lib/cases-api";
import { getDraft } from "@/lib/insights-api";
import DraftActions from "./draft-actions";
import styles from "../draft/draft.module.css";

export default async function LiveDraft({ c }: { c: CaseFull }) {
  let d;
  try {
    d = await getDraft(c.id, await sessionAuth());
  } catch (e) {
    return <Banner tone="error"><b>Could not build the draft.</b> {e instanceof Error ? e.message : ""}</Banner>;
  }

  return (
    <>
      <div className="section-title">
        <div>
          <h2>Complaint draft</h2>
          <p>
            Put together by code from your facts and from citations checked against the stored orders. Nothing is
            written by a model here; anything not known is left as a blank in square brackets.
          </p>
        </div>
        <DraftActions text={d.text} />
      </div>

      <div style={{ marginBottom: 16 }}><Banner tone="info">{d.disclaimer}</Banner></div>

      {d.missing.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Banner tone="warn">
            <b>Still needed before filing:</b>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
              {d.missing.map((m) => <li key={m}>{m}</li>)}
            </ul>
          </Banner>
        </div>
      )}

      <div className={styles.layout}>
        <div className={styles.paper}>
          <article className={styles.doc}>
            <p className={styles.center}><b>{d.header[0]}</b></p>
            <p className={styles.center}>{d.header[1]}</p>
            <p className={styles.parties}>{d.header[2]}</p>
            {d.sections.map((s) => (
              <section key={s.heading}>
                <h4>{s.heading}</h4>
                {s.paragraphs.map((p, i) => (
                  <p key={i} className={s.heading.startsWith("5.") ? styles.annex : undefined}>{p}</p>
                ))}
              </section>
            ))}
          </article>
        </div>

        <aside className={styles.notes}>
          <div className={styles.note}>
            <span className="label">Sources</span>
            {d.based_on_hearing
              ? `${d.verified_citations} checked citation(s) from your latest simulated hearing.`
              : <>No hearing yet. <Link href={`/cases/${c.id}/hearing`}>Run the hearing</Link> to add checked precedents and an amount.</>}
          </div>
          {d.notes.map((n) => (
            <div key={n.label} className={styles.note}>
              <span className="label">{n.label}</span>
              {n.text}
            </div>
          ))}
        </aside>
      </div>
    </>
  );
}
