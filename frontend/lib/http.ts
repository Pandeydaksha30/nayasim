/**
 * The one place every API request goes through.
 *
 * Real cases: a fetch to the ContractIQ API, errors thrown as ApiError with the server's message.
 *
 * The public example case ("demo"): answered from lib/example-snapshot.json, a recording of the
 * API's own answers for a real run on fictional documents (backend/scripts/export_example.py).
 * So the example pages are the same pages a real case uses, showing exactly what the system
 * produced, and they work without signing in. The example is read-only.
 */
import { ApiError, BASE } from "./api";

/** Server components pass the signed-in user's cookie (lib/server-session.ts); the browser sends
 * it by itself. */
export type Auth = { headers?: Record<string, string> };

export const EXAMPLE_ID = "demo";
const EXAMPLE_API = `/api/v1/cases/${EXAMPLE_ID}`;

export const isExample = (caseId: string) => caseId === EXAMPLE_ID;

async function exampleAnswer<T>(path: string, init?: RequestInit): Promise<T> {
  if ((init?.method ?? "GET").toUpperCase() !== "GET") {
    throw new ApiError("The example case is read-only. Create your own case to try this.", 403);
  }
  const snapshot = (await import("./example-snapshot.json")).default as { responses: Record<string, unknown> };
  if (path in snapshot.responses) return snapshot.responses[path] as T;
  if (path.startsWith(`${EXAMPLE_API}/passages`)) {
    throw new ApiError("Searching runs on the server, so it is switched off in the example. It works in your own cases.", 403);
  }
  throw new ApiError("This is not part of the recorded example.", 404);
}

export async function call<T>(path: string, init?: RequestInit, auth?: Auth): Promise<T> {
  if (path === EXAMPLE_API || path.startsWith(`${EXAMPLE_API}/`)) return exampleAnswer<T>(path, init);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      cache: "no-store",
      credentials: "same-origin",
      ...init,
      headers: { ...(init?.headers as Record<string, string> | undefined), ...auth?.headers },
    });
  } catch {
    throw new ApiError("The ContractIQ service is not reachable. Please try again in a moment.");
  }
  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

/** When the example was recorded, for the notice on its pages. */
export async function exampleRecordedAt(): Promise<string> {
  return ((await import("./example-snapshot.json")).default as { recorded_at: string }).recorded_at;
}
