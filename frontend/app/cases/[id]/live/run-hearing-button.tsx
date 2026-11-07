"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Banner } from "@/components/icons";
import { runHearing } from "@/lib/cases-api";

export default function RunHearingButton({ caseId, again }: { caseId: string; again?: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await runHearing(caseId);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The hearing could not be run.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 10, justifyItems: "start" }}>
      <button type="button" className={again ? "btn" : "btn btn-primary"} onClick={run} disabled={busy}>
        {busy ? "Running the hearing… (a few minutes)" : again ? "Run again" : "Run simulated hearing"}
      </button>
      {error && <Banner tone="error"><b>Not completed.</b> {error}</Banner>}
    </div>
  );
}
