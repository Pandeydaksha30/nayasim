/** Layout for Terms and Privacy: a single readable column, serif headings, a draft notice. */
import { Banner } from "./icons";

export default function LegalDoc({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <main className="page" style={{ maxWidth: 760 }}>
      <article className="legal">
        <div className="label">Last updated {updated}</div>
        <h1>{title}</h1>
        <div style={{ margin: "18px 0 28px" }}>
          <Banner tone="warn">
            <b>Draft for early access.</b> This text has not yet been reviewed by a lawyer and will be revised before
            NyayaSim opens to the public.
          </Banner>
        </div>
        {children}
      </article>
    </main>
  );
}
