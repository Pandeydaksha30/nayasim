/**
 * Client for app/api/insights.py: order search, outcome estimate, complaint draft, classifier demo.
 * All of these are computed on the server from stored data; none calls an external model.
 */
import { ApiError, BASE } from "./api";
import type { Auth } from "./cases-api";

async function call<T>(path: string, init?: RequestInit, auth?: Auth): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      cache: "no-store",
      credentials: "same-origin",
      ...init,
      headers: { ...(init?.headers as Record<string, string> | undefined), ...auth?.headers },
    });
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

export interface Measured {
  accuracy_pct: number;
  macro_f1?: number;
  test_orders?: number;
  test_cases?: number;
  majority_baseline_pct?: number;
  note?: string;
}

export interface Estimate {
  available: boolean;
  reason?: string;
  predicted?: string;
  basis?: string;
  counts?: Record<string, number>;
  orders_used?: number;
  delay_months?: number | null;
  delay_band?: string;
  as_of?: string;
  method?: string;
  measured?: Measured;
}

export interface Draft {
  case_id: string;
  claim_type: string;
  header: string[];
  sections: { heading: string; paragraphs: string[] }[];
  notes: { label: string; text: string }[];
  missing: string[];
  based_on_hearing: number | null;
  verified_citations: number;
  disclaimer: string;
  text: string;
}

export interface SearchHit {
  order_id: number;
  complaint_no: string;
  decided_on: string;
  page_no: number;
  text: string;
  outcome: string | null;
  claim_type: string | null;
}

export interface SearchResponse {
  query: string;
  mode: "hybrid" | "keyword";
  before: string;
  notes: string[];
  hits: SearchHit[];
}

export interface Classification {
  claim_type: { label: string; decided_by: string; model_scores: Record<string, number>; measured: Measured };
  outcome: { label: string; decided_by: string; scores: Record<string, number>; measured: Measured; note: string };
  caveat: string;
}

export const getEstimate = (caseId: string, auth?: Auth) =>
  call<Estimate>(`/api/v1/cases/${caseId}/estimate`, undefined, auth);
export const getDraft = (caseId: string, auth?: Auth) =>
  call<Draft>(`/api/v1/cases/${caseId}/draft`, undefined, auth);
export const searchOrders = (q: string, k = 10) =>
  call<SearchResponse>(`/api/v1/search/orders?q=${encodeURIComponent(q)}&k=${k}`);
export const classifyOrderText = (text: string) =>
  call<Classification>("/api/v1/predictions/order-text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
