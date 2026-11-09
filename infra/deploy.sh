#!/usr/bin/env bash
# One-command deploy of NyayaSim on a fresh Ubuntu/Debian server.
#
# Run from the repo root on the server:
#   bash infra/deploy.sh                                     # asks for anything missing
#   DOMAIN=nyayasim.duckdns.org DATA=nyayasim-data.dump bash infra/deploy.sh
#
# Optional settings (environment variables, or edit infra/.env.prod afterwards and run again):
#   GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET  "Continue with Google" (see docs/deploy.md)
#   SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM   verification + reset emails
#   GEMINI_API_KEY                            AI hearings
#   SITE_PASSWORD                             also lock the whole site behind one shared password
#
# What it does:
#   1. Installs Docker if missing (official convenience script from get.docker.com).
#   2. Creates infra/.env.prod on first run (random database password, your domain, the options
#      above). An existing .env.prod is kept as it is.
#   3. Builds and starts database, API, website and Caddy (HTTPS with automatic certificates).
#   4. Loads the order data file if DATA is given and the database is still empty.
#   5. Checks https://DOMAIN/health.
# DOMAIN=none starts on http://SERVER_IP:3000 without HTTPS: only for a server behind a firewall.
set -euo pipefail
trap 'echo "error: deploy stopped at line $LINENO" >&2' ERR
cd "$(dirname "$0")/.."

ENV_FILE=infra/.env.prod
COMPOSE=(docker compose -f infra/docker-compose.prod.yml --env-file "$ENV_FILE")

say() { printf '\n== %s\n' "$*"; }
die() { echo "error: $*" >&2; exit 1; }
env_get() { grep -E "^$1=" "$ENV_FILE" | cut -d= -f2- || true; }

# 1. Docker -----------------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  say "Installing Docker"
  [ "$(id -u)" = 0 ] || command -v sudo >/dev/null || die "need root or sudo to install Docker"
  curl -fsSL https://get.docker.com | sh
  [ "$(id -u)" = 0 ] || sudo usermod -aG docker "$USER" || true
fi
if ! docker info >/dev/null 2>&1; then
  if [ "$(id -u)" != 0 ] && sudo docker info >/dev/null 2>&1; then
    say "Using sudo for Docker (log out and back in to use it without sudo)"
    COMPOSE=(sudo "${COMPOSE[@]}")
    docker() { sudo docker "$@"; }
  else
    die "Docker is installed but not running (try: sudo systemctl start docker)"
  fi
fi
docker compose version >/dev/null 2>&1 || die "the Docker Compose plugin is missing (apt install docker-compose-plugin)"

# 2. Settings ---------------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
  say "Creating $ENV_FILE"
  if [ -z "${DOMAIN:-}" ]; then
    read -rp "Domain pointing at this server (e.g. nyayasim.duckdns.org), or 'none': " DOMAIN
  fi
  [ -n "$DOMAIN" ] || die "DOMAIN is required ('none' for no HTTPS)"
  db_pw="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')"; db_pw="${db_pw:0:32}"

  caddyfile=Caddyfile; hash=""
  if [ "$DOMAIN" = "none" ]; then
    ip="$( (hostname -I 2>/dev/null || true) | awk '{print $1}')"; ip="${ip:-localhost}"
    web_url="http://$ip:${WEB_PORT:-3000}"; bind=0.0.0.0; domain_line=""; secure=false
  else
    web_url="https://$DOMAIN"; bind=127.0.0.1; domain_line="$DOMAIN"; secure=true
    if [ -n "${SITE_PASSWORD:-}" ]; then
      [ "${#SITE_PASSWORD}" -ge 10 ] || die "SITE_PASSWORD must be at least 10 characters"
      hash="$(docker run --rm caddy:2.10-alpine caddy hash-password --plaintext "$SITE_PASSWORD")"
      hash="${hash//\$/\$\$}"   # Compose reads $ as a variable: write each one as $$
      caddyfile=Caddyfile.locked
    fi
  fi

  umask 077
  cat > "$ENV_FILE" <<EOF
# Written by infra/deploy.sh on $(date -u +%F). Never commit this file.
POSTGRES_PASSWORD=$db_pw
PUBLIC_WEB_URL=$web_url
COOKIE_SECURE=$secure
GEMINI_API_KEY=${GEMINI_API_KEY:-}
NYAYASIM_PRIVATE_LLM_OK=false
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID:-}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET:-}
SMTP_HOST=${SMTP_HOST:-}
SMTP_PORT=${SMTP_PORT:-587}
SMTP_USER=${SMTP_USER:-}
SMTP_PASSWORD=${SMTP_PASSWORD:-}
SMTP_FROM=${SMTP_FROM:-NyayaSim <no-reply@${DOMAIN}>}
API_BIND=127.0.0.1
WEB_BIND=$bind
API_PORT=${API_PORT:-8000}
WEB_PORT=${WEB_PORT:-3000}
DOMAIN=$domain_line
CADDYFILE=$caddyfile
BASIC_AUTH_USER=${SITE_USER:-nyayasim}
BASIC_AUTH_HASH=$hash
EOF
  echo "Saved."
else
  say "Using existing $ENV_FILE"
fi

domain="$(env_get DOMAIN)"
profile=()
[ -n "$domain" ] && profile=(--profile https)
[ -n "$(env_get SMTP_HOST)" ] || echo "warning: SMTP_HOST is empty, so verification and password-reset emails are only saved
         inside the server (docker compose ... exec api ls /srv/data/outbox). New users cannot confirm
         their email by themselves until SMTP is set in $ENV_FILE (see docs/deploy.md)."
[ -n "$(env_get GOOGLE_CLIENT_ID)" ] || echo "note: GOOGLE_CLIENT_ID is empty, so the 'Continue with Google' button is hidden."

# 3. Build and start --------------------------------------------------------------------------
say "Building and starting (first build takes 5-15 minutes)"
"${COMPOSE[@]}" "${profile[@]}" up -d --build

say "Waiting for the API"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T api curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 5
done
[ "${ok:-0}" = 1 ] || { "${COMPOSE[@]}" logs --tail 50 api migrate; die "API did not become healthy"; }

# 4. Data -------------------------------------------------------------------------------------
if [ -n "${DATA:-}" ]; then
  orders="$("${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -tAc 'select count(*) from orders')"
  if [ "$orders" = "0" ]; then
    say "Loading order data from $DATA"
    bash infra/import-data.sh "$DATA"
  else
    say "Database already has $orders orders; not loading $DATA"
  fi
fi

# 5. Check ------------------------------------------------------------------------------------
if [ -n "$domain" ]; then
  say "Checking https://$domain (the certificate can take a minute on first start)"
  auth=()
  [ -n "${SITE_PASSWORD:-}" ] && auth=(-u "${SITE_USER:-nyayasim}:$SITE_PASSWORD")
  code=000
  for _ in $(seq 1 24); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "${auth[@]}" "https://$domain/health" || true)"
    [ "$code" = 200 ] && break; sleep 5
  done
  if [ "$code" = 200 ]; then echo "OK: https://$domain is live. Create the first account at https://$domain/signup"
  else echo "Not reachable yet (HTTP $code). Check that DNS points here and ports 80/443 are open, then: ${COMPOSE[*]} logs caddy"
  fi
else
  echo "Running on $(env_get PUBLIC_WEB_URL) without HTTPS. Keep this server behind a firewall."
fi
