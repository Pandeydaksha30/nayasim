"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import styles from "./new.module.css";

const KINDS = ["Builder-buyer agreement", "Allotment letter", "Payment receipt", "Builder letter", "Hearing order", "Other"] as const;

interface Picked {
  key: string;
  name: string;
  sizeKb: number;
  kind: (typeof KINDS)[number];
}

function guessKind(name: string): Picked["kind"] {
  const n = name.toLowerCase();
  if (n.includes("agreement") || n.includes("bba")) return "Builder-buyer agreement";
  if (n.includes("allot")) return "Allotment letter";
  if (n.includes("receipt") || n.includes("rcpt")) return "Payment receipt";
  if (n.includes("order")) return "Hearing order";
  if (n.includes("letter")) return "Builder letter";
  return "Other";
}

export default function NewCasePage() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<Picked[]>([]);
  const [dragging, setDragging] = useState(false);
  const [consent, setConsent] = useState(false);

  function add(list: FileList | null) {
    if (!list) return;
    const next = Array.from(list).map((f) => ({
      key: `${f.name}-${f.size}-${f.lastModified}`,
      name: f.name,
      sizeKb: Math.max(1, Math.round(f.size / 1024)),
      kind: guessKind(f.name),
    }));
    setFiles((cur) => [...cur, ...next.filter((n) => !cur.some((c) => c.key === n.key))]);
  }

  const hasAgreement = files.some((f) => f.kind === "Builder-buyer agreement");

  return (
    <main className="page" style={{ maxWidth: 860 }}>
      <div className="crumb"><Link href="/">Cases</Link> / New case</div>
      <h1>Start a case</h1>
      <p className="muted" style={{ marginTop: 8, maxWidth: "62ch" }}>
        Add the papers you have. Scans and phone photos are fine, in English or Hindi. We read the facts from them and show you where
        each one came from, so you can check it.
      </p>

      <ol className={styles.checklist}>
        <li><b>Builder-buyer agreement.</b> Needed. It holds the promised date and the delay clause.</li>
        <li><b>Payment receipts</b> or bank statement lines for every payment.</li>
        <li><b>Allotment letter</b> and any <b>letters from the builder</b> about delays, revised dates or extra charges.</li>
      </ol>

      <div
        className={`${styles.drop} ${dragging ? styles.dropActive : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); add(e.dataTransfer.files); }}
      >
        <p style={{ margin: 0 }}>Drop PDF or image files here, or</p>
        <button type="button" className="btn" onClick={() => input.current?.click()}>Choose files</button>
        <input
          ref={input}
          type="file"
          multiple
          accept=".pdf,image/*"
          hidden
          onChange={(e) => { add(e.target.files); e.target.value = ""; }}
        />
        <p className="small faint" style={{ margin: 0 }}>PDF, JPG or PNG, up to 25 MB each.</p>
      </div>

      {files.length > 0 && (
        <div className="panel table-wrap" style={{ marginTop: 16 }}>
          <table className="ledger">
            <thead>
              <tr><th>File</th><th>What it is</th><th className="r">Size</th><th /></tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.key}>
                  <td style={{ wordBreak: "break-all" }}>{f.name}</td>
                  <td>
                    <select
                      className={styles.select}
                      value={f.kind}
                      aria-label={`Document type for ${f.name}`}
                      onChange={(e) =>
                        setFiles((cur) => cur.map((c) => (c.key === f.key ? { ...c, kind: e.target.value as Picked["kind"] } : c)))
                      }
                    >
                      {KINDS.map((k) => <option key={k}>{k}</option>)}
                    </select>
                  </td>
                  <td className="r num">{f.sizeKb} KB</td>
                  <td className="r">
                    <button type="button" className="btn btn-quiet" onClick={() => setFiles((cur) => cur.filter((c) => c.key !== f.key))}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {files.length > 0 && !hasAgreement && (
        <p className={styles.warn}>No builder-buyer agreement yet. You can continue, but the promised date will have to be entered by hand.</p>
      )}

      <label className={styles.consent}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          I agree that these documents are processed to prepare my report. They are stored encrypted on servers in India and deleted
          after 90 days unless I keep the case open. <Link href="/method#data">How we handle documents</Link>
        </span>
      </label>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 20 }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={files.length === 0 || !consent}
          onClick={() => router.push("/cases/demo/facts")}
        >
          Read my documents
        </button>
        <button type="button" className="btn" onClick={() => router.push("/cases/demo/facts")}>
          Use the demo case instead
        </button>
      </div>
      <p className="small faint" style={{ marginTop: 10 }}>Demo build: files are not uploaded; both buttons open the demo case.</p>
    </main>
  );
}
