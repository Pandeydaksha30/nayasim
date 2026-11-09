/**
 * Layout for the sign-in, sign-up and email-link pages: a statement panel with what NyayaSim
 * does (facts only, no marketing claims) beside the form.
 */
import styles from "./auth.module.css";

const POINTS = [
  { title: "Every fact points to a page", body: "Dates and payments are read from your papers and shown with the exact line they came from." },
  { title: "Citations are checked", body: "An argument that quotes a past order is kept only if the quote is found in the stored order." },
  { title: "Your documents stay private", body: "Uploads are visible only to your account, and real documents are never sent to an AI service that keeps data." },
];

export default function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.shell}>
      <aside className={styles.aside} aria-label="About NyayaSim">
        <div className={styles.kicker}>RERA dispute preparation</div>
        <p className={styles.statement}>Know how your hearing is likely to go before you file.</p>
        <ol className={styles.points}>
          {POINTS.map((p, i) => (
            <li key={p.title}>
              <span className={styles.pointNo}>{String(i + 1).padStart(2, "0")}</span>
              <div>
                <b>{p.title}</b>
                <span>{p.body}</span>
              </div>
            </li>
          ))}
        </ol>
        <div className={styles.asideFoot}>
          Built on <strong>13,992</strong> public HRERA Gurugram orders. Decision support, not legal advice.
        </div>
      </aside>
      <main className={styles.main}>
        <div className={styles.form}>{children}</div>
      </main>
    </div>
  );
}
