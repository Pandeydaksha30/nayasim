# User accounts and security

## What a user can do

| Action | Page | API |
|---|---|---|
| Create an account (name, email, password, accept terms) | `/signup` | `POST /api/v1/auth/signup` |
| Confirm the email (link, 24 h, single use, needs one click) | `/verify-email?token=` | `POST /api/v1/auth/verify-email` |
| Sign in / out | `/login`, account menu | `POST /api/v1/auth/login`, `/logout` |
| Continue with Google | `/login`, `/signup` | `GET /api/v1/auth/google/start` → Google → `/google/callback` |
| Forgot password (link, 1 h, single use) | `/forgot-password`, `/reset-password` | `POST /forgot-password`, `/reset-password` |
| Change name, change or set password, sign out everywhere, delete account | `/account` | `PATCH /me`, `POST /change-password`, `POST /logout-all`, `DELETE /me` |

Every case belongs to the account that created it. Another user asking for it gets **404**
(not 403), so case ids cannot be probed. Demo cases created before accounts existed have no
owner: every signed-in user can read them, nobody can change them.

## Security design

| Threat | Defence | Tested in `tests/test_auth.py` |
|---|---|---|
| Stolen database → passwords | Argon2id hashes (argon2-cffi defaults, rehash on login if parameters change) | `test_password_rules` |
| Stolen database → sessions | Cookie holds 32 random bytes; DB stores only SHA-256 | `test_signup_verify_login_logout` |
| Session theft via page script | Cookie is `HttpOnly`, `SameSite=Lax`, `Secure` in production | same |
| Cross-site request forgery | SameSite cookie **and** Origin/Referer must be the site's own for POST/PUT/PATCH/DELETE (`app/middleware.py`) | `test_cross_site_requests_are_blocked` |
| Password guessing | 20 sign-ins / 5 min per IP, 10 per email; account locks 15 min after 8 wrong passwords | `test_lockout_…`, `test_login_rate_limited` |
| Finding out who has an account | Same answer and same timing for unknown email vs wrong password; sign-up and "forgot password" answer the same either way | `test_wrong_password_and_unknown_email_look_the_same`, `test_signup_does_not_reveal_existing_accounts`, `test_forgot_password_same_answer_for_unknown_email` |
| Email link reuse | Links are hashed, single use, expire; a new link cancels older ones | `test_verify_link_is_single_use` |
| Reset while someone else is signed in | A reset signs out every device; a change signs out other devices | `test_reset_password_signs_out_everywhere`, `test_change_password_needs_current` |
| Google login CSRF / code interception | `state` checked against an httpOnly cookie; PKCE (S256) | `test_google_sign_up_and_wrong_state` |
| Forged Google token | Code exchanged server-to-server over TLS; issuer, audience, expiry, `email_verified` checked | `test_google_claims_are_checked` |
| Pre-registering a victim's email, then waiting for them to use Google | When Google proves the inbox, an unconfirmed password on that email is removed and its sessions ended | `test_google_takes_over_unverified_squatter_account` |
| Open redirect after sign-in | `next` must be a same-site path | `test_next_redirect_only_allows_local_paths` |
| Reading another user's case | Owner check on every case route | `test_cases_are_private_to_their_owner` |
| Clickjacking, sniffing, mixed content | `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'`, `nosniff`, HSTS (Caddy + API in production) | header check in CSRF test |

Audit log: `auth_events` records sign-ups, sign-ins, failures, lockouts, resets, password changes,
Google linking and deletions with time, IP and user agent. A daily job removes expired sessions,
used/expired links, and events older than 365 days (`purge_expired`, stated in the Privacy Policy).

**Known limits (before a public launch):** rate limits are per API process (one process per server
is the deployed setup; several servers would need Redis); no two-factor authentication; email
address change is not built; the breached-password check is a short built-in list, not a lookup
service; Terms and Privacy pages are drafts awaiting a lawyer's review.

## Setting up Google sign-in

1. https://console.cloud.google.com → create a project → **APIs & Services → OAuth consent screen**:
   External, app name "NyayaSim", your support email, scopes `openid`, `email`, `profile`.
2. **Credentials → Create credentials → OAuth client ID → Web application.**
   Authorized redirect URIs (add each place the site runs):
   - `http://localhost:3100/api/v1/auth/google/callback` (local)
   - `https://your-domain/api/v1/auth/google/callback` (server)
3. Copy the client ID and secret:
   - local: `NYAYASIM_GOOGLE_CLIENT_ID=...` and `NYAYASIM_GOOGLE_CLIENT_SECRET=...` in `backend\.env`
   - server: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `infra/.env.prod`
4. Restart the API. The "Continue with Google" button appears only when both are set.

While the consent screen is in "Testing" mode, only Google accounts added as test users can sign in;
publish it for everyone.

## Setting up email

Any SMTP service works. Set in `backend\.env` (local) or `infra/.env.prod` (server, without the
`NYAYASIM_` prefix): `SMTP_HOST`, `SMTP_PORT` (587 STARTTLS or 465 TLS), `SMTP_USER`,
`SMTP_PASSWORD`, `SMTP_FROM`. Free options: Brevo (300 emails/day), or Gmail with an app password
(for testing only). Without SMTP, emails are written to `data/outbox/` and their links logged:
fine on your own PC, not for a public site.
