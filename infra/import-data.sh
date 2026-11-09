#!/usr/bin/env bash
# Load an order-data file made by export-data.sh into the RUNNING production stack.
# Run after the stack is up (migrations create the empty tables first).
#
# Usage (from the repo root):  bash infra/import-data.sh nyayasim-data.dump
# Refuses to run if the orders table already has rows, so it never mixes or duplicates data.
# To replace existing data: FORCE=1 bash infra/import-data.sh nyayasim-data.dump
set -euo pipefail

DUMP="${1:?usage: bash infra/import-data.sh <file.dump>}"
COMPOSE=(docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod)
# Fresh servers: the user may not be in the docker group until they log in again.
if ! docker info >/dev/null 2>&1 && command -v sudo >/dev/null && sudo docker info >/dev/null 2>&1; then
  COMPOSE=(sudo "${COMPOSE[@]}")
fi
TABLES="orders, order_pages, order_chunks, case_records, fetch_log"

[ -f "$DUMP" ] || { echo "error: $DUMP not found" >&2; exit 1; }
# Absolute path, taken before changing directory. (pwd -W gives C:/... on Git Bash for Windows,
# which docker cp needs; on Linux it fails and plain pwd is used.)
DUMP="$(cd "$(dirname "$DUMP")" && (pwd -W 2>/dev/null || pwd))/$(basename "$DUMP")"
cd "$(dirname "$0")/.."

psql_q() { "${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -v ON_ERROR_STOP=1 -tAc "$1"; }

existing="$(psql_q 'select count(*) from orders')"
if [ "$existing" != "0" ]; then
  if [ "${FORCE:-0}" != "1" ]; then
    echo "error: the database already has $existing orders. Re-run with FORCE=1 to replace them." >&2
    exit 1
  fi
  echo "FORCE=1: emptying $TABLES ..."
  psql_q "truncate $TABLES cascade"
fi

echo "Copying $DUMP into the database container ..."
"${COMPOSE[@]}" cp "$DUMP" postgres:/tmp/nyayasim-data.dump
echo "Restoring (a few minutes for the full set) ..."
"${COMPOSE[@]}" exec -T postgres pg_restore -U nyayasim -d nyayasim --data-only --disable-triggers \
  --no-owner --exit-on-error /tmp/nyayasim-data.dump
"${COMPOSE[@]}" exec -T postgres rm -f /tmp/nyayasim-data.dump
psql_q 'analyze' >/dev/null

echo "Loaded: $(psql_q 'select count(*) from orders') orders, $(psql_q 'select count(*) from order_chunks') search chunks, $(psql_q 'select count(*) from case_records') case records."
