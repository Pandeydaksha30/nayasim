"use client";
/**
 * Deleting a case or a document, and adding documents to an existing case.
 * Deleting asks twice in place (no browser dialog) and says exactly what goes.
 */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { PlusIcon } from "@/components/icons";
import { deleteCase, deleteDocument, DOC_KINDS, type DocKind, guessKind, uploadDocument } from "@/lib/cases-api";
import styles from "./case-actions.module.css";

function ConfirmDelete({ what, detail, action, after }: { what: string; detail: string; action: () => Promise<unknown>; after?: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (after) router.push(after);
      router.refresh();
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return <button type="button" className={`btn btn-quiet ${styles.danger}`} onClick={() => setOpen(true)}>Delete</button>;
  }
  return (
    <span className={styles.confirm} role="group" aria-label={`Delete ${what}`}>
      <span className={styles.confirmText}>{error ?? detail}</span>
      <button type="button" className={`btn ${styles.dangerSolid}`} onClick={go} disabled={busy}>
        {busy ? "Deleting…" : "Delete for good"}
      </button>
      <button type="button" className="btn btn-quiet" onClick={() => { setOpen(false); setError(null); }} disabled={busy}>Keep</button>
    </span>
  );
}

export function DeleteCaseButton({ caseId, title }: { caseId: string; title: string }) {
  return (
    <ConfirmDelete
      what={title}
      detail="Deletes the case, its documents, facts, hearings and drafts. This cannot be undone."
      action={() => deleteCase(caseId)}
      after="/dashboard"
    />
  );
}

export function DeleteDocumentButton({ caseId, docId, filename }: { caseId: string; docId: string; filename: string }) {
  return (
    <ConfirmDelete
      what={filename}
      detail="Deletes the file, its text and the facts read from it. This cannot be undone."
      action={() => deleteDocument(caseId, docId)}
    />
  );
}

interface Picked {
  key: string;
  file: File;
  kind: DocKind;
  status: "waiting" | "uploading" | "done" | "failed";
  message?: string;
}

export function AddDocuments({ caseId }: { caseId: string }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<Picked[]>([]);
  const [busy, setBusy] = useState(false);

  const patch = (key: string, p: Partial<Picked>) => setFiles((cur) => cur.map((f) => (f.key === key ? { ...f, ...p } : f)));

  function add(list: FileList | null) {
    if (!list) return;
    const next = Array.from(list).map((f) => ({
      key: `${f.name}-${f.size}-${f.lastModified}`, file: f, kind: guessKind(f.name), status: "waiting" as const,
    }));
    setFiles((cur) => [...cur.filter((c) => c.status !== "done"), ...next.filter((n) => !cur.some((c) => c.key === n.key))]);
  }

  async function upload() {
    setBusy(true);
    for (const f of files.filter((x) => x.status !== "done")) {
      patch(f.key, { status: "uploading", message: undefined });
      try {
        const doc = await uploadDocument(caseId, f.file, f.kind);
        patch(f.key, { status: "done", message: doc.duplicate ? "Already in this case" : `${doc.page_count} ${doc.page_count === 1 ? "page" : "pages"} read` });
      } catch (e) {
        patch(f.key, { status: "failed", message: e instanceof Error ? e.message : "Upload failed" });
      }
    }
    setBusy(false);
    router.refresh();
  }

  const pending = files.filter((f) => f.status !== "done").length;
  return (
    <div className={styles.add}>
      <button type="button" className="btn" onClick={() => input.current?.click()} disabled={busy}><PlusIcon /> Add documents</button>
      <input ref={input} type="file" multiple accept=".pdf,image/png,image/jpeg" hidden
             onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      {files.length > 0 && (
        <div className={`panel ${styles.queue}`}>
          <ul>
            {files.map((f) => (
              <li key={f.key}>
                <span className={styles.name}>{f.file.name}</span>
                {f.status === "waiting" || f.status === "failed" ? (
                  <select value={f.kind} aria-label={`Document type for ${f.file.name}`} disabled={busy}
                          onChange={(e) => patch(f.key, { kind: e.target.value as DocKind })}>
                    {DOC_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                  </select>
                ) : <span />}
                <span className={styles.state}>
                  {f.status === "waiting" && <span className="tag tag-neutral">Ready</span>}
                  {f.status === "uploading" && <span className="tag tag-mid">Reading…</span>}
                  {f.status === "done" && <span className="tag tag-pos">{f.message}</span>}
                  {f.status === "failed" && <span className={styles.failed}>{f.message}</span>}
                </span>
              </li>
            ))}
          </ul>
          {pending > 0 && (
            <div className={styles.queueFoot}>
              <span className="small muted">PDF, JPG or PNG, up to 25 MB and 100 pages each. Scans take longer to read.</span>
              <button type="button" className="btn btn-primary" onClick={upload} disabled={busy}>
                {busy ? "Reading…" : `Upload ${pending} ${pending === 1 ? "file" : "files"}`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
