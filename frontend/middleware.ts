/**
 * Sends signed-out visitors from private pages to the sign-in page (and back afterwards).
 * This only checks that a session cookie exists; the API checks that it is valid and that the
 * case belongs to the user on every request, so this is a convenience, not the security boundary.
 */
import { type NextRequest, NextResponse } from "next/server";

const PRIVATE = [/^\/dashboard(\/|$)/, /^\/account(\/|$)/, /^\/cases\/new(\/|$)/, /^\/cases\/(?!demo(\/|$))[^/]+/];

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  if (PRIVATE.some((r) => r.test(pathname)) && !req.cookies.has("nyayasim_session")) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/dashboard/:path*", "/account/:path*", "/cases/:path*"] };
