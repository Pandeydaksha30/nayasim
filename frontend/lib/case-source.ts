/**
 * Where a case page gets its data. Every case, including the public example, is read through the
 * same API client; the example ("demo") is answered from a recording of a real run (lib/http.ts).
 * Server-side only. API errors are returned, not hidden, so pages can show them.
 */
import { notFound, redirect } from "next/navigation";
import { ApiError } from "./api";
import { type CaseFull, getCase as fetchCase } from "./cases-api";
import { EXAMPLE_ID, isExample } from "./http";
import { sessionAuth } from "./server-session";

export { EXAMPLE_ID };

export type CaseSource = { kind: "live"; data: CaseFull } | { kind: "error"; message: string };

export async function loadCase(id: string): Promise<CaseSource> {
  if (!isExample(id) && !/^[0-9a-f-]{36}$/i.test(id)) notFound();
  try {
    return { kind: "live", data: await fetchCase(id, isExample(id) ? undefined : await sessionAuth()) };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    if (e instanceof ApiError && e.status === 401) redirect(`/login?next=${encodeURIComponent(`/cases/${id}`)}`);
    return { kind: "error", message: e instanceof Error ? e.message : "Could not load the case." };
  }
}
