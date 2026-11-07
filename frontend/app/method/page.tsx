export const metadata = { title: "How it works" };

export default function MethodPage() {
  return (
    <main className="page" style={{ maxWidth: 760 }}>
      <h1>How NyayaSim works</h1>
      <p className="muted" style={{ marginTop: 8 }}>What happens to your papers, where the numbers come from, and what the report can and cannot tell you.</p>

      <h2 style={{ marginTop: 32 }}>From documents to a report</h2>
      <ol>
        <li><b>Reading.</b> We read your agreement, receipts and letters, including scans in Hindi. Every fact is linked to the place it came from so you can check it.</li>
        <li><b>Questions.</b> We ask only about what the papers do not say, such as whether you received an offer of possession.</li>
        <li><b>Money.</b> Interest and refund amounts are calculated by ordinary code, payment by payment, at the prescribed rate. AI is never used for arithmetic.</li>
        <li><b>Past orders.</b> We find final orders of the authority with facts close to yours.</li>
        <li><b>Simulated hearing.</b> One agent argues for you, one for the builder, and a third weighs both. Any argument citing an order we cannot find is removed.</li>
        <li><b>Report.</b> You see how similar cases ended, a range for the award, and the weak points in your case first.</li>
      </ol>

      <h2 style={{ marginTop: 32 }}>How we test it</h2>
      <p>
        We build the system only on orders decided up to a cut-off date, then ask it to predict later orders and compare with what
        actually happened. We publish how often it is right, how far its award estimates are off, and how it compares with simpler
        methods.
      </p>

      <h2 id="data" style={{ marginTop: 32 }}>Your documents</h2>
      <p>
        Documents are stored encrypted on servers in India and deleted after 90 days unless you keep the case open. You can delete a
        case at any time. Your documents are not used to train models. We follow the Digital Personal Data Protection Act, 2023.
      </p>

      <h2 style={{ marginTop: 32 }}>What it is not</h2>
      <p>
        NyayaSim is not a law firm and does not give legal advice. Only an enrolled advocate can advise you or represent you. Use the
        report to prepare, and have an advocate review it before you file.
      </p>
    </main>
  );
}
