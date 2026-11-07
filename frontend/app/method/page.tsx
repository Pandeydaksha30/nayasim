import { Banner } from "@/components/icons";

export const metadata = { title: "How it works" };

const STEPS = [
  ["Reading", "We read your agreement, receipts and letters, including scans in Hindi. Every fact is linked to the place it came from so you can check it."],
  ["Questions", "We ask only about what the papers do not say, such as whether you received an offer of possession."],
  ["Money", "Interest and refund amounts are calculated by ordinary code, payment by payment, at the prescribed rate. AI is never used for arithmetic."],
  ["Past orders", "We find final orders of the authority with facts close to yours."],
  ["Simulated hearing", "One agent argues for you, one for the builder, and a third weighs both. Any argument citing an order we cannot find is removed."],
  ["Report", "You see how similar cases ended, a range for the award, and the weak points in your case first."],
] as const;

export default function MethodPage() {
  return (
    <main className="page page-narrow">
      <h1>How NyayaSim works</h1>
      <p className="muted" style={{ marginTop: 6 }}>
        What happens to your papers, where the numbers come from, and what the report can and cannot tell you.
      </p>

      <section className="panel" style={{ marginTop: 24 }}>
        <div className="panel-head"><h2 style={{ fontSize: 16 }}>From documents to a report</h2></div>
        <ol style={{ listStyle: "none", margin: 0, padding: "4px 18px 8px" }}>
          {STEPS.map(([title, text], i) => (
            <li
              key={title}
              style={{ display: "grid", gridTemplateColumns: "30px 1fr", gap: 12, padding: "14px 0", borderBottom: i < STEPS.length - 1 ? "1px solid var(--border)" : "none" }}
            >
              <span
                style={{ width: 26, height: 26, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 12.5, fontWeight: 700, background: "var(--primary-soft)", color: "var(--primary)" }}
              >
                {i + 1}
              </span>
              <span>
                <b style={{ fontWeight: 600 }}>{title}.</b> <span className="muted">{text}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel panel-body" style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>How we test it</h2>
        <p className="muted" style={{ margin: 0 }}>
          We build the system only on orders decided up to a cut-off date, then ask it to predict later orders and compare with what
          actually happened. We publish how often it is right, how far its award estimates are off, and how it compares with simpler
          methods.
        </p>
      </section>

      <section id="data" className="panel panel-body" style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 16, marginBottom: 8 }}>Your documents</h2>
        <p className="muted" style={{ margin: 0 }}>
          Documents are stored encrypted on servers in India and deleted after 90 days unless you keep the case open. You can delete a
          case at any time. Your documents are not used to train models. We follow the Digital Personal Data Protection Act, 2023.
        </p>
      </section>

      <div style={{ marginTop: 16 }}>
        <Banner tone="info">
          <b>What it is not.</b> NyayaSim is not a law firm and does not give legal advice. Only an enrolled advocate can advise or
          represent you. Use the report to prepare, and have an advocate review it before you file.
        </Banner>
      </div>
    </main>
  );
}
