/**
 * Client for the NyayaSim API. Money always comes from the Python calculator;
 * the frontend only formats it. Errors are thrown, never replaced with a fallback figure.
 */
import type { Payment } from "./types";

// The browser always calls the API on the website's own address (/api/...): next.config.ts
// forwards it to the API locally, and Caddy does in production. Same origin means the session
// cookie is first-party and no cross-origin request is ever needed.
// Server-side calls go straight to the API. 127.0.0.1: on Windows "localhost" may try IPv6 first
// while the API listens on IPv4 only.
export const BASE = typeof window === "undefined" ? process.env.API_URL ?? "http://127.0.0.1:8000" : "";

export interface InterestInput {
  payments: Payment[];
  possessionPromised: string;
  extensionMonths: number;
  annualRatePct: number;
  asOf: string;
  rateSource: string;
}

export interface InterestRowOut {
  paid_on: string;
  amount: string;
  reference: string;
  interest_from: string;
  days: number;
  interest: string;
}

export interface InterestResultOut {
  rows: InterestRowOut[];
  principal: string;
  interest: string;
  total: string;
}

export interface InterestOutput {
  possession_due: string;
  annual_rate_pct: string;
  rate_source: string;
  method: string;
  delay: InterestResultOut;
  refund: InterestResultOut;
}

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export async function computeInterest(input: InterestInput, signal?: AbortSignal): Promise<InterestOutput> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1/calculations/interest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      signal,
      body: JSON.stringify({
        payments: input.payments.map((p) => ({ paid_on: p.date, amount: String(p.amount), reference: p.reference })),
        possession_promised: input.possessionPromised,
        extension_months: input.extensionMonths,
        annual_rate_pct: String(input.annualRatePct),
        as_of: input.asOf,
        rate_source: input.rateSource,
      }),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("The calculation service is not reachable. Start the backend and try again.");
  }
  if (!res.ok) {
    let detail = `Calculation failed (HTTP ${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}
