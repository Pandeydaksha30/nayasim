"""HTTP security layers for every API response.

- CSRF: a browser request that changes something (POST/PUT/PATCH/DELETE) must carry an Origin
  (or, failing that, Referer) from the site's own address. Together with the SameSite=Lax session
  cookie this blocks other sites from acting as a signed-in user. Requests with neither header
  (curl, server-to-server) carry no browser cookie risk and pass.
- Security headers on API responses (the website sets its own in next.config.ts).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

API_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _origin_of(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ""


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in UNSAFE:
            origin = request.headers.get("origin") or _origin_of(request.headers.get("referer", ""))
            if origin and origin.rstrip("/") not in settings.allowed_origins:
                return JSONResponse({"detail": "Request blocked: it did not come from this site."}, 403)
        response = await call_next(request)
        for k, v in API_HEADERS.items():
            response.headers.setdefault(k, v)
        if settings.cookie_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/api/v1/auth") or request.url.path.startswith("/api/v1/cases"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
