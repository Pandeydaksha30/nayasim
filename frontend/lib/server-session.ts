/**
 * Server-only: the signed-in user for server components, read by forwarding the browser's
 * session cookie to the API. Never import this from a "use client" file.
 */
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { BASE } from "./api";
import type { User } from "./auth-api";
import type { Auth } from "./cases-api";

export const SESSION_COOKIE = "nyayasim_session";

export async function sessionAuth(): Promise<Auth> {
  const c = (await cookies()).get(SESSION_COOKIE);
  return c ? { headers: { cookie: `${SESSION_COOKIE}=${c.value}` } } : {};
}

/** The user, or null when signed out (or the session expired). Throws only if the API is down. */
export async function getUser(): Promise<User | null> {
  const auth = await sessionAuth();
  if (!auth.headers) return null;
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/v1/auth/me`, { cache: "no-store", headers: auth.headers });
  } catch {
    return null; // pages that need data report the outage themselves
  }
  return res.ok ? ((await res.json()) as User) : null;
}

export async function requireUser(next: string): Promise<User> {
  const user = await getUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(next)}`);
  return user;
}
