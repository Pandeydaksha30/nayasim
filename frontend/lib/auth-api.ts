/**
 * Accounts API client (backend app/api/auth.py), used from the browser. Requests go to the
 * site's own /api path, so the httpOnly session cookie is sent and set automatically.
 */
import { ApiError } from "./api";

export interface User {
  id: string;
  email: string;
  name: string;
  email_verified: boolean;
  has_password: boolean;
  google_linked: boolean;
  created_at: string;
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/v1/auth${path}`, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("We couldn't reach NyayaSim. Check your connection and try again.");
  }
  if (!res.ok) {
    let detail = `Something went wrong (HTTP ${res.status}). Please try again.`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail)) {
        const first = j.detail[0];
        const field = first?.loc?.[first.loc.length - 1];
        detail = field === "email" ? "Enter a valid email address." : first?.msg ?? detail;
      }
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

type Msg = { message: string };

export const authConfig = () => send<{ google: boolean; email_delivery: "smtp" | "outbox" }>("/config", "GET");
export const signup = (name: string, email: string, password: string, acceptTerms: boolean) =>
  send<Msg>("/signup", "POST", { name, email, password, accept_terms: acceptTerms });
export const login = (email: string, password: string) => send<User>("/login", "POST", { email, password });
export const logout = () => send<Msg>("/logout", "POST");
export const logoutAll = () => send<Msg>("/logout-all", "POST");
export const verifyEmail = (token: string) => send<User>("/verify-email", "POST", { token });
export const resendVerification = (email: string) => send<Msg>("/resend-verification", "POST", { email });
export const forgotPassword = (email: string) => send<Msg>("/forgot-password", "POST", { email });
export const resetPassword = (token: string, password: string) =>
  send<Msg>("/reset-password", "POST", { token, password });
export const updateProfile = (name: string) => send<User>("/me", "PATCH", { name });
export const changePassword = (currentPassword: string | null, newPassword: string) =>
  send<Msg>("/change-password", "POST", { current_password: currentPassword, new_password: newPassword });
export const deleteAccount = (password: string | null, confirm: string) =>
  send<Msg>("/me", "DELETE", { password, confirm });

export const googleStartUrl = (next?: string) =>
  `/api/v1/auth/google/start${next ? `?next=${encodeURIComponent(next)}` : ""}`;

/** Same rules as the server (app/auth/security.py), checked as the user types. */
export function passwordProblem(pw: string, email = ""): string | null {
  if (pw.length < 10) return "Use at least 10 characters.";
  if (pw.length > 128) return "Use at most 128 characters.";
  if (new Set(pw).size < 4) return "This password is too easy to guess.";
  const local = email.split("@")[0].toLowerCase();
  if (local.length >= 4 && pw.toLowerCase().includes(local)) return "Don't include your email address.";
  return null;
}

/** Only same-site paths, mirroring the server's check, so ?next= cannot send people elsewhere. */
export function safeNext(path: string | null | undefined, fallback = "/dashboard"): string {
  if (!path || !path.startsWith("/") || path.startsWith("//") || path.includes("\\")) return fallback;
  return path;
}
