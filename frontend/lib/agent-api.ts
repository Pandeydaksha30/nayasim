/**
 * Client for app/api/rag.py (questions over the case's own documents) and app/api/agent.py
 * (agentic analysis). Citations returned here have been checked by code on the server.
 */
import { ApiError, BASE } from "./api";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { cache: "no-store", credentials: "same-origin", ...init });
  } catch {
    throw new ApiError("The NyayaSim service is not reachable. Start the backend and try again.");
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

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface DocCitation {
  ref: string;
  source?: "document" | "order";
  filename?: string;
  complaint_no?: string;
  decided_on?: string;
  page_no: number;
  quote: string;
}

export interface Rejected {
  ref: string;
  quote: string;
  reason: string;
}

export interface AskResult {
  id?: number;
  question: string;
  answer: string;
  insufficient: boolean;
  reason: string | null;
  mode: string;
  model: string;
  citations: DocCitation[];
  rejected_citations: Rejected[];
  retrieved: { ref: string; filename: string; page_no: number }[];
}

export interface PassageHit {
  chunk_id: number;
  filename: string;
  page_no: number;
  text: string;
}

export const askCase = (caseId: string, question: string) =>
  call<AskResult>(`/api/v1/cases/${caseId}/ask`, json({ question }));
export const searchPassages = (caseId: string, q: string) =>
  call<{ mode: string; hits: PassageHit[] }>(`/api/v1/cases/${caseId}/passages?q=${encodeURIComponent(q)}`);
export const listQuestions = (caseId: string) => call<AskResult[]>(`/api/v1/cases/${caseId}/questions`);

export interface AgentStep {
  n: number;
  agent: string;
  action: string;
  args: Record<string, unknown>;
  thought: string;
  ok: boolean;
  observation: unknown;
  ms: number;
}

export interface AgentRun {
  id: number;
  objective: string;
  model: string;
  status: "running" | "completed" | "incomplete" | "failed";
  error: string | null;
  steps: AgentStep[];
  result: {
    answer?: string;
    insufficient?: boolean;
    grounded?: boolean;
    citations?: DocCitation[];
    rejected_citations?: Rejected[];
    stop_reason?: string;
    hearing_run_id?: number | null;
    judge?: { outcome: string; reasoning: string; weak_points: { title: string; fix: string }[] };
  };
  started_at: string;
}

export const startAgent = (caseId: string, objective: string) =>
  call<AgentRun>(`/api/v1/cases/${caseId}/agent`, json({ objective }));
export const getAgentRun = (caseId: string, runId: number) =>
  call<AgentRun>(`/api/v1/cases/${caseId}/agent/runs/${runId}`);
export const listAgentRuns = (caseId: string) => call<AgentRun[]>(`/api/v1/cases/${caseId}/agent/runs`);

export const citeLabel = (c: DocCitation) =>
  c.source === "order" ? `Order ${c.complaint_no} (${c.decided_on}), page ${c.page_no}` : `${c.filename}, page ${c.page_no}`;
