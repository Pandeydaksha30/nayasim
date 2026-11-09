"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Banner, ChevronIcon, FileIcon, UploadIcon } from "@/components/icons";
import { createCase, DOC_KINDS, type DocKind, extractFacts, uploadDocument } from "@/lib/cases-api";
import styles from "./new.module.css";

interface Picked {
  key: string;
  file: File;
  kind: DocKind;
  status: "waiting" | "uploading" | "done" | "failed";
  message?: string;
}

function guessKind(name: string): DocKind {
  const n = name.toLowerCase();
  if (n.includes("agreement") || n.includes("bba")) return "agreement";
  if (n.includes("allot")) return "allotment_letter";
  if (n.includes("receipt") || n.includes("rcpt")) return "receipt";
  if (n.includes("order")) return "hearing_order";
  if (n.includes("letter")) return "builder_letter";
  return "other";
}

export default function NewCasePage() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [files, setFiles] = useState<Picked[]>([]);
  const [dragging, setDragging] = useState(false);
  const [consent, setConsent] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function add(list: FileList | null) {
    if (!list) return;
    const next = Array.from(list).map((f) => ({
      key: `${f.name}-${f.size}-${f.lastModified}`,
      file: f,
      kind: guessKind(f.name),
      status: "waiting" as const,
    }));
    setFiles((cur) => [...cur, ...next.filter((n) => !cur.some((c) => c.key === n.key))]);
  }

  const setFile = (key: string, patch: Partial<Picked>) =>
    setFiles((cur) => cur.map((c) => (c.key === key ? { ...c, ...patch } : c)));

  async function submit() {
    setError(null);
    try {
      setBusy("Creating the case…");
      const c = await createCase(title.trim() || "My case", isDemo);
      let uploaded = 0;
      for (const [i, f] of files.entries()) {
        setBusy(`Reading document ${i + 1} of ${files.length} (scans take longer)…`);
        setFile(f.key, { status: "uploading" });
        try {
          const doc = await uploadDocument(c.id, f.file, f.kind);
          uploaded += 1;
          setFile(f.key, { status: "done", message: doc.duplicate ? "Already uploaded" : `${doc.page_count} pages` });
        } catch (e) {
          setFile(f.key, { status: "failed", message: e instanceof Error ? e.message : "Upload failed" });
        }
      }
      if (uploaded === 0) {
        setError("No document could be read, so nothing was extracted. Check the files and try again.");
        setBusy(null);
        return;
      }
      if (isDemo) {
        setBusy("Finding facts in your documents…");
        await extractFacts(c.id);
      }
      router.push(`/cases/${c.id}/facts`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(null);
    }
  }

  const hasAgreement = files.some((f) => f.kind === "agreement");
  const canSubmit = files.length > 0 && consent && !busy;

  return (
    <main className="page page-narrow">
      <div className="crumb"><Link href="/dashboard">Cases</Link> <ChevronIcon size={12} /> <span>New case</span></div>
      <h1>Start a case</h1>
      <p className="muted" style={{ marginTop: 6 }}>
        Add the papers you have. Scans and phone photos are fine, in English or Hindi. Every fact we read is linked to the
        place it came from, so you can check it.
      </p>

      <section className={`panel ${styles.card}`}>
        <div className="panel-body">
          <label className="field">
            <span className="field-label">Case name</span>
            <input type="text" value={title} placeholder="e.g. Mehra v. Arvant Infra" maxLength={200}
                   onChange={(e) => setTitle(e.target.value)} style={{ width: "100%" }} />
            <span className="field-help">Only you see this name.</span>
          </label>
        </div>
      </section>

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
            <button type="button" className="btn" onClick={() => input.current?.click()} disabled={!!busy}>Browse files</button>
            <input ref={input} type="file" multiple accept=".pdf,image/png,image/jpeg" hidden
                   onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          </div>
        </div>

        {files.length > 0 && (
          <div className="table-wrap" style={{ borderTop: "1px solid var(--border)" }}>
            <table className="ledger">
              <thead>
                <tr><th>File</th><th>Document type</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.key}>
                    <td style={{ wordBreak: "break-all" }}>
                      <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}><FileIcon /> {f.file.name}</span>
                      <div className="cell-sub">{Math.max(1, Math.round(f.file.size / 1024))} KB</div>
                    </td>
                    <td>
                      <select value={f.kind} aria-label={`Document type for ${f.file.name}`} disabled={!!busy}
                              onChange={(e) => setFile(f.key, { kind: e.target.value as DocKind })}>
                        {DOC_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                      </select>
                    </td>
                    <td>
                      {f.status === "waiting" && <span className="tag tag-neutral">Ready</span>}
                      {f.status === "uploading" && <span className="tag tag-mid">Reading…</span>}
                      {f.status === "done" && <span className="tag tag-pos">{f.message}</span>}
                      {f.status === "failed" && <span className="small" style={{ color: "var(--neg)" }}>{f.message}</span>}
                    </td>
                    <td className="r">
                      {f.status === "waiting" && !busy && (
                        <button type="button" className="btn btn-quiet" onClick={() => setFiles((cur) => cur.filter((c) => c.key !== f.key))}>
                          Remove
                        </button>
                      )}
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
            <b>No builder-buyer agreement yet.</b> You can continue, but the promised possession date may be missing.
          </Banner>
        </div>
      )}

      <label className={styles.consent}>
        <input type="checkbox" checked={isDemo} onChange={(e) => setIsDemo(e.target.checked)} disabled={!!busy} />
        <span>
          <b>These are fictional demo documents.</b> Only demo documents are sent to the AI model for now. Real documents are
          stored and read on the NyayaSim server, but fact-finding stays off until a model that keeps no data is set up.
        </span>
      </label>
      <label className={styles.consent}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} disabled={!!busy} />
        <span>
          I agree that these documents are stored to prepare my case. <Link href="/method#data">How we handle documents</Link>
        </span>
      </label>

      {error && <div style={{ marginTop: 16 }}><Banner tone="error"><b>Could not finish.</b> {error}</Banner></div>}

      <div className={styles.actions}>
        <button type="button" className="btn btn-primary" disabled={!canSubmit} onClick={submit}>
          {busy ? "Working…" : "Create case"}
        </button>
        {busy && <span className="small muted" role="status">{busy}</span>}
        {!busy && <Link href="/cases/demo/facts" className="small">Or open the example case</Link>}
      </div>
    </main>
  );
}
