"use client";

import { useState } from "react";
import { DownloadIcon } from "@/components/icons";

/** Copy the draft, or save it as a plain text file. Both happen in the browser only. */
export default function DraftActions({ text }: { text: string }) {
  const [copied, setCopied] = useState<"" | "done" | "failed">("");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
    setTimeout(() => setCopied(""), 2500);
  }

  function download() {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "complaint-draft.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="section-actions">
      <button type="button" className="btn" onClick={copy} aria-live="polite">
        {copied === "done" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy text"}
      </button>
      <button type="button" className="btn btn-primary" onClick={download}>
        <DownloadIcon /> Download .txt
      </button>
    </div>
  );
}
