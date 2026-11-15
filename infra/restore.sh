#!/usr/bin/env bash
# Restore a backup made by infra/backup.sh into the RUNNING production stack.
# This REPLACES the current database and uploaded files.
#
# Usage (from the repo root):
#   CONFIRM=yes bash infra/restore.sh backups/nyayasim-db-<time>.dump backups/nyayasim-files-<time>.tar.gz
#
# The code must be the same version as, or newer than, the one that made the backup: after the
# restore the "migrate" service is run once to bring an older database up to date.
set -euo pipefail

DB="${1:?usage: CONFIRM=yes bash infra/restore.sh <db.dump> <files.tar.gz>}"
FILES="${2:?usage: CONFIRM=yes bash infra/restore.sh <db.dump> <files.tar.gz>}"
[ -f "$DB" ] && [ -f "$FILES" ] || { echo "error: backup file not found" >&2; exit 1; }
[ "${CONFIRM:-}" = "yes" ] || { echo "error: this replaces all current data. Run again with CONFIRM=yes" >&2; exit 1; }
DB="$(cd "$(dirname "$DB")" && pwd)/$(basename "$DB")"
FILES="$(cd "$(dirname "$FILES")" && pwd)/$(basename "$FILES")"
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod)
if ! docker info >/dev/null 2>&1 && command -v sudo >/dev/null && sudo docker info >/dev/null 2>&1; then
  COMPOSE=(sudo "${COMPOSE[@]}")
fi

echo "Stopping the API and website ..."
"${COMPOSE[@]}" stop api web >/dev/null

echo "Restoring the database ..."
"${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d postgres -v ON_ERROR_STOP=1 -q \
  -c "DROP DATABASE IF EXISTS nyayasim WITH (FORCE)" -c "CREATE DATABASE nyayasim OWNER nyayasim"
"${COMPOSE[@]}" exec -T postgres pg_restore -U nyayasim -d nyayasim --no-owner --exit-on-error < "$DB"

echo "Applying any newer migrations ..."
"${COMPOSE[@]}" run --rm migrate >/dev/null

echo "Restoring uploaded files ..."
"${COMPOSE[@]}" start api >/dev/null
"${COMPOSE[@]}" exec -T api sh -c 'find /srv/data -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf - -C /srv' < "$FILES"

"${COMPOSE[@]}" start web >/dev/null
echo "Restored. Users: $("${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -tAc 'select count(*) from users'), cases: $("${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -tAc 'select count(*) from cases'), orders: $("${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -tAc 'select count(*) from orders')"
