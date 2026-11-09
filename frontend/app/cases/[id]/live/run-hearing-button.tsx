"use client";

/**
 * Starts a simulated hearing. The server runs it in the background; this polls the run every few
 * seconds and refreshes the page when it finishes. A reload while it runs picks the run back up.
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Banner } from "@/components/icons";
import { ApiError } from "@/lib/api";
import { getActiveRun, getRun, runHearing } from "@/lib/cases-api";

const POLL_MS = 3000;

export default function RunHearingButton({ caseId, again }: { caseId: string; again?: boolean }) {
  const router = useRouter();
  const [runId, setRunId] = useState<number | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    getActiveRun(caseId)
      .then((run) => {
        if (run && alive.current) {
          setRunId(run.id);
          setStartedAt(Date.parse(run.started_at));
        }
      })
      .catch(() => {});
    return () => {
      alive.current = false;
    };
  }, [caseId]);

  const poll = useCallback(async () => {
    if (runId === null) return;
    try {
      const run = await getRun(caseId, runId);
      if (!alive.current) return;
      if (run.status === "completed") {
        setRunId(null);
        router.refresh();
      } else if (run.status === "failed") {
        setRunId(null);
        setError(run.error ?? "The hearing failed.");
      }
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : "Lost track of the hearing. Reload the page.");
      setRunId(null);
    }
  }, [caseId, runId, router]);

  useEffect(() => {
    if (runId === null) return;
    const t = setInterval(() => {
      poll();
      if (startedAt) setElapsed(Math.round((Date.now() - startedAt) / 1000));
    }, POLL_MS);
    return () => clearInterval(t);
  }, [runId, startedAt, poll]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const run = await runHearing(caseId);
      setRunId(run.id);
      setStartedAt(Date.now());
      setElapsed(0);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const active = await getActiveRun(caseId).catch(() => null);
        if (active) {
          setRunId(active.id);
          setStartedAt(Date.parse(active.started_at));
        }
      } else {
        setError(e instanceof Error ? e.message : "The hearing could not be started.");
      }
    } finally {
      setStarting(false);
    }
  }

  const running = runId !== null;
  return (
    <div style={{ display: "grid", gap: 10, justifyItems: "start" }}>
      <button type="button" className={again ? "btn" : "btn btn-primary"} onClick={start} disabled={starting || running}>
        {starting ? "Starting…" : running ? "Hearing in progress…" : again ? "Run again" : "Run simulated hearing"}
      </button>
      {running && (
        <span className="small muted" role="status">
          The advocates and the bench are working through the precedents. This usually takes under a minute
          {elapsed > 0 ? ` (${elapsed} s so far)` : ""}. You can leave this page and come back.
        </span>
      )}
      {error && <Banner tone="error"><b>Not completed.</b> {error}</Banner>}
    </div>
  );
}
