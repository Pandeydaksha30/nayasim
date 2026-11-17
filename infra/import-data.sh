#!/usr/bin/env bash
# Load the public order data (made by export-data.sh) into a database whose tables already exist
# (the API runs the migrations when it starts, so start it once first).
#
# Local development database (infra/docker-compose.yml):
#   bash infra/import-data.sh release/nyayasim-public-orders.dump
#
# Render PostgreSQL: use the database's EXTERNAL connection URL from the Render dashboard.
#   TARGET_URL='postgresql://user:pass@host.render.com/contractiq' bash infra/import-data.sh release/nyayasim-public-orders.dump
#   Uses pg_restore/psql 17 if installed; otherwise runs them from the pgvector image with Docker
#   (a local tool only, not part of the deployment).
#
# Refuses to run if the orders table already has rows, so it never mixes or duplicates data.
# To replace existing data: FORCE=1 ...
set -euo pipefail

DUMP="${1:?usage: bash infra/import-data.sh <file.dump>}"
TABLES="orders, order_pages, order_chunks, case_records, fetch_log"
[ -f "$DUMP" ] || { echo "error: $DUMP not found" >&2; exit 1; }
# Absolute path, taken before changing directory. (pwd -W gives C:/... on Git Bash for Windows.)
DUMP_DIR="$(cd "$(dirname "$DUMP")" && (pwd -W 2>/dev/null || pwd))"
DUMP_NAME="$(basename "$DUMP")"
cd "$(dirname "$0")/.."

if [ -n "${TARGET_URL:-}" ]; then
  URL="$TARGET_URL"
  case "$URL" in *sslmode=*) ;; *\?*) URL="$URL&sslmode=require" ;; *) URL="$URL?sslmode=require" ;; esac
  if command -v pg_restore >/dev/null 2>&1 && command -v psql >/dev/null 2>&1; then
    psql_q() { psql "$URL" -v ON_ERROR_STOP=1 -tAc "$1"; }
    restore() { pg_restore -d "$URL" --data-only --disable-triggers --no-owner --exit-on-error "$DUMP_DIR/$DUMP_NAME"; }
  else
    IMG=pgvector/pgvector:0.8.0-pg17
    psql_q() { MSYS_NO_PATHCONV=1 docker run --rm "$IMG" psql "$URL" -v ON_ERROR_STOP=1 -tAc "$1"; }
    restore() {
      MSYS_NO_PATHCONV=1 docker run --rm -v "$DUMP_DIR:/dump:ro" "$IMG" \
        pg_restore -d "$URL" --data-only --disable-triggers --no-owner --exit-on-error "/dump/$DUMP_NAME"
    }
  fi
  where="the database at TARGET_URL"
else
  COMPOSE=(docker compose -f infra/docker-compose.yml)
  psql_q() { "${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -v ON_ERROR_STOP=1 -tAc "$1"; }
  restore() {
    "${COMPOSE[@]}" cp "$DUMP_DIR/$DUMP_NAME" postgres:/tmp/nyayasim-data.dump
    # Inside `sh -c` so Git Bash on Windows does not rewrite /tmp/... into a Windows path.
    "${COMPOSE[@]}" exec -T postgres sh -c 'pg_restore -U nyayasim -d nyayasim --data-only --disable-triggers --no-owner --exit-on-error /tmp/nyayasim-data.dump; rc=$?; rm -f /tmp/nyayasim-data.dump; exit $rc'
  }
  where="the local development database"
fi

existing="$(psql_q 'select count(*) from orders')"
if [ "$existing" != "0" ]; then
  if [ "${FORCE:-0}" != "1" ]; then
    echo "error: $where already has $existing orders. Re-run with FORCE=1 to replace them." >&2
    exit 1
  fi
  echo "FORCE=1: emptying $TABLES ..."
  psql_q "truncate $TABLES cascade"
fi

echo "Restoring $DUMP_NAME into $where (a few minutes for the full set) ..."
restore
psql_q 'analyze' >/dev/null
echo "Loaded: $(psql_q 'select count(*) from orders') orders, $(psql_q 'select count(*) from order_chunks') search chunks, $(psql_q 'select count(*) from case_records') case records."
