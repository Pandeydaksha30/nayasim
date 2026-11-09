/**
 * Cases API client (backend app/api/cases.py). Every function throws ApiError with the
 * server's message on failure; callers show it. Nothing is ever filled in locally.
 */
import { ApiError, BASE } from "./api";

export type DocKind = "agreement" | "allotment_letter" | "receipt" | "builder_letter" | "hearing_order" | "other";

export const DOC_KINDS: { value: DocKind; label: string }[] = [
  { value: "agreement", label: "Builder-buyer agreement" },
  { value: "allotment_letter", label: "Allotment letter" },
  { value: "receipt", label: "Payment receipt" },
  { value: "builder_letter", label: "Builder letter" },
  { value: "hearing_order", label: "Hearing order" },
  { value: "other", label: "Other" },
];

export const kindLabel = (k: string) => DOC_KINDS.find((d) => d.value === k)?.label ?? k;

export interface CaseSummary {
  id: string;
  title: string;
  claim_type: string;
  status: string;
  is_demo: boolean;
  shared: boolean;
  created_at: string;
  documents: number;
  facts: number;
}

export interface CaseDocument {
  id: string;
  filename: string;
  kind: DocKind;
  page_count: number;
  ocr_pages: number;
  duplicate?: boolean;
}

export interface CaseFact {
  id: number;
  document_id: string;
  key: string;
  label: string;
  value: string;
  page_no: number;
  char_start: number;
  char_end: number;
  quote: string;
  confidence: "high" | "review";
  confirmed: boolean;
}

export interface CaseQuestion {
  id: string;
  question: string;
  why: string;
  options: string[];
  answer: string | null;
}

export interface CaseFull {
  id: string;
  title: string;
  claim_type: string;
  status: string;
  is_demo: boolean;
  created_at: string;
  documents: CaseDocument[];
  facts: CaseFact[];
  questions: CaseQuestion[];
  payments_total: string;
}

export interface PageText {
  page_no: number;
  page_count: number;
  text: string;
  text_source: "text_layer" | "ocr";
  ocr_confidence: string | null;
}

export interface ExtractSummary {
  documents: number;
  facts: number;
  rejected: { document: string; field: string; reason: string }[];
  errors: { document: string; error: string }[];
}

/** Server components pass the signed-in user's cookie (lib/server-session.ts); the browser sends
 * it by itself. */
export type Auth = { headers?: Record<string, string> };

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
      /* keep generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const listCases = (auth?: Auth) => call<CaseSummary[]>("/api/v1/cases", undefined, auth);
export const getCase = (id: string, auth?: Auth) => call<CaseFull>(`/api/v1/cases/${id}`, undefined, auth);
export const createCase = (title: string, isDemo: boolean) =>
  call<CaseFull>("/api/v1/cases", { method: "POST", ...json({ title, is_demo: isDemo }) });

export function uploadDocument(caseId: string, file: File, kind: DocKind) {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  return call<CaseDocument>(`/api/v1/cases/${caseId}/documents`, { method: "POST", body: form });
}

export const extractFacts = (caseId: string) =>
  call<ExtractSummary>(`/api/v1/cases/${caseId}/facts/extract`, { method: "POST" });
export const getPage = (caseId: string, docId: string, page: number) =>
  call<PageText>(`/api/v1/cases/${caseId}/documents/${docId}/pages/${page}`);
export const confirmFact = (caseId: string, factId: number) =>
  call<CaseFact>(`/api/v1/cases/${caseId}/facts/${factId}/confirm`, { method: "POST" });
export const answerQuestion = (caseId: string, questionId: string, answer: string) =>
  call<CaseFull>(`/api/v1/cases/${caseId}/answers/${questionId}`, { method: "PUT", ...json({ answer }) });

/** Verified payment facts as calculator payments ("2018-03-12;720000.00"). */
export function paymentsFromFacts(facts: CaseFact[]) {
  return facts
    .filter((f) => f.key === "payment")
    .map((f) => {
      const [date, amount] = f.value.split(";");
      return { id: `f${f.id}`, date, amount: Number(amount), reference: `Receipt, p. ${f.page_no}` };
    })
    .sort((a, b) => a.date.localeCompare(b.date));
}

/** One entry per fact key; the same value found in several documents becomes several sources. */
export function groupFacts(facts: CaseFact[]) {
  const groups = new Map<string, { key: string; label: string; value: string; sources: CaseFact[] }>();
  for (const f of facts) {
    const id = f.key === "payment" ? `payment:${f.value}` : `${f.key}:${f.value.toLowerCase()}`;
    const g = groups.get(id);
    if (g) g.sources.push(f);
    else groups.set(id, { key: f.key, label: f.label, value: f.value, sources: [f] });
  }
  return [...groups.values()];
}

// ── Hearing (backend app/api/hearing.py) ──

export interface HearingCitation {
  precedent: string;
  order_id?: number;
  complaint_no?: string;
  decided_on?: string;
  page_no: number;
  quote: string;
  status: "verified" | "rejected";
  reasons: string[];
  stored_quote?: string | null;
}

export interface HearingArgument {
  heading: string;
  body: string;
  side: "buyer" | "builder";
  citations: HearingCitation[];
  removed_because?: string;
}

export interface HearingResult {
  summary: string;
  precedents: {
    ref: string;
    order_id: number;
    complaint_no: string;
    decided_on: string;
    outcome: string | null;
    interest_rate_pct: string | null;
    pages: number[];
  }[];
  outcome_shares: {
    precedents: number;
    with_record: number;
    counts: Record<string, number>;
    insufficient: boolean;
    note?: string;
    buyer_wins?: number;
    interval_90?: [number, number];
  };
  award: {
    available: boolean;
    reason?: string;
    rate_pct?: string;
    rate_basis?: string;
    principal?: string;
    as_of?: string;
    refund_total?: string;
    delay_interest?: string | null;
    delay_note?: string;
    possession_due?: string;
  };
  arguments: { buyer: HearingArgument[]; builder: HearingArgument[]; removed: HearingArgument[] };
  judge: {
    outcome: string;
    reasoning: string;
    weak_points: { title: string; detail: string; fix: string }[];
    citations: HearingCitation[];
    citations_removed: HearingCitation[];
  };
}

export interface HearingRun {
  id: number;
  status: "completed" | "failed";
  error: string | null;
  cutoff: string;
  models: string;
  started_at: string;
  finished_at: string | null;
  result: HearingResult;
}

/** Latest completed hearing, or null if none has been run yet. */
export async function getHearing(caseId: string, auth?: Auth): Promise<HearingRun | null> {
  try {
    return await call<HearingRun>(`/api/v1/cases/${caseId}/hearing`, undefined, auth);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export const runHearing = (caseId: string) =>
  call<HearingRun>(`/api/v1/cases/${caseId}/hearing`, { method: "POST" });
