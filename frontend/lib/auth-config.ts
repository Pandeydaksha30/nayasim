/** Server-only: whether Google sign-in is configured on the API (hides the button if not). */
import { BASE } from "./api";

export async function googleEnabled(): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}/api/v1/auth/config`, { cache: "no-store" });
    return r.ok ? Boolean((await r.json()).google) : false;
  } catch {
    return false;
  }
}
