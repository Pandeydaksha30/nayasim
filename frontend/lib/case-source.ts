/**
 * Where a case page gets its data: the static example ("demo") or the API (real cases).
 * Server-side only. API errors are returned, not hidden, so pages can show them.
 */
import { notFound, redirect } from "next/navigation";
import { ApiError } from "./api";
import { type CaseFull, getCase as fetchCase } from "./cases-api";
import { demoCase, getCase as getDemo } from "./demo-case";
import { sessionAuth } from "./server-session";

export const EXAMPLE_ID = demoCase.id;

export type CaseSource =
  | { kind: "example"; data: typeof demoCase }
  | { kind: "live"; data: CaseFull }
  | { kind: "error"; message: string };

export async function loadCase(id: string): Promise<CaseSource> {
  const example = getDemo(id);
  if (example) return { kind: "example", data: example };
  if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
  try {
    return { kind: "live", data: await fetchCase(id, await sessionAuth()) };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    if (e instanceof ApiError && e.status === 401) redirect(`/login?next=${encodeURIComponent(`/cases/${id}`)}`);
    return { kind: "error", message: e instanceof Error ? e.message : "Could not load the case." };
  }
}
