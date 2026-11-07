"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Banner, ChevronIcon, FileIcon, UploadIcon } from "@/components/icons";
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
    <main className="page page-narrow">
      <div className="crumb"><Link href="/">Cases</Link> <ChevronIcon size={12} /> <span>New case</span></div>
      <h1>Start a case</h1>
      <p className="muted" style={{ marginTop: 6 }}>
        Add the papers you have. Scans and phone photos are fine, in English or Hindi. Every fact we read is linked to the
        place it came from, so you can check it.
      </p>

      <section className={`panel ${styles.card}`}>
        <div className="panel-head"><h2 style={{ fontSize: 16 }}>Documents</h2><span className="small faint">PDF, JPG or PNG · up to 25 MB each</span></div>
        <div className="panel-body">
          <ul className={styles.checklist}>
            <li><span className={styles.req}>1</span><span><b>Builder-buyer agreement</b> (required): holds the promised date and the delay clause.</span></li>
            <li><span className={styles.req}>2</span><span><b>Payment receipts</b> or bank statement lines for every payment.</span></li>
            <li><span className={styles.req}>3</span><span><b>Allotment letter</b> and any <b>builder letters</b> about delays, revised dates or extra charges.</span></li>
          </ul>

          <div
            className={`${styles.drop} ${dragging ? styles.dropActive : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); add(e.dataTransfer.files); }}
          >
            <span className={styles.dropIcon}><UploadIcon size={20} /></span>
            <p className={styles.dropTitle}>Drag files here</p>
            <p className="small faint" style={{ margin: 0 }}>or</p>
            <button type="button" className="btn" onClick={() => input.current?.click()}>Browse files</button>
            <input
              ref={input}
              type="file"
              multiple
              accept=".pdf,image/*"
              hidden
              onChange={(e) => { add(e.target.files); e.target.value = ""; }}
            />
          </div>
        </div>

        {files.length > 0 && (
          <div className="table-wrap" style={{ borderTop: "1px solid var(--border)" }}>
            <table className="ledger">
              <thead>
                <tr><th>File</th><th>Document type</th><th className="r">Size</th><th /></tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.key}>
                    <td style={{ wordBreak: "break-all" }}>
                      <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}><FileIcon /> {f.name}</span>
                    </td>
                    <td>
                      <select
                        value={f.kind}
                        aria-label={`Document type for ${f.name}`}
                        onChange={(e) =>
                          setFiles((cur) => cur.map((c) => (c.key === f.key ? { ...c, kind: e.target.value as Picked["kind"] } : c)))
                        }
                      >
                        {KINDS.map((k) => <option key={k}>{k}</option>)}
                      </select>
                    </td>
                    <td className="r num faint">{f.sizeKb} KB</td>
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
      </section>

      {files.length > 0 && !hasAgreement && (
        <div style={{ marginTop: 16 }}>
          <Banner tone="warn">
            <b>No builder-buyer agreement yet.</b> You can continue, but the promised possession date will have to be entered by hand.
          </Banner>
        </div>
      )}

      <label className={styles.consent}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          I agree that these documents are processed to prepare my report. They are stored encrypted on servers in India and deleted
          after 90 days unless I keep the case open. <Link href="/method#data">How we handle documents</Link>
        </span>
      </label>

      <div className={styles.actions}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={files.length === 0 || !consent}
          onClick={() => router.push("/cases/demo/facts")}
        >
          Read my documents
        </button>
        <button type="button" className="btn" onClick={() => router.push("/cases/demo/facts")}>
          Open the demo case
        </button>
        <span className="small faint">Demo build: files are not uploaded yet.</span>
      </div>
    </main>
  );
}
