#!/usr/bin/env bash
# Back up the RUNNING production stack: the whole database and the uploaded files.
#
# Usage (from the repo root):   bash infra/backup.sh [folder]        (default: backups/)
# Writes two files named with the UTC time:
#   nyayasim-db-<time>.dump        every table (accounts, cases, facts, runs, public orders)
#   nyayasim-files-<time>.tar.gz   /srv/data of the API: uploads, email outbox, model files
#
# These files contain users' private documents and password hashes (never passwords). Keep them
# off the server, encrypted, and delete old ones. Restore with infra/restore.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-backups}"
COMPOSE=(docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.prod)
if ! docker info >/dev/null 2>&1 && command -v sudo >/dev/null && sudo docker info >/dev/null 2>&1; then
  COMPOSE=(sudo "${COMPOSE[@]}")
fi
[ -f infra/.env.prod ] || { echo "error: infra/.env.prod not found (is the stack set up here?)" >&2; exit 1; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
umask 077

echo "Database ..."
"${COMPOSE[@]}" exec -T postgres pg_dump -U nyayasim -d nyayasim --format=custom --compress=6 \
  > "$OUT/nyayasim-db-$stamp.dump"
echo "Uploaded files ..."
"${COMPOSE[@]}" exec -T api sh -c 'tar -czf - -C /srv data' > "$OUT/nyayasim-files-$stamp.tar.gz"

ls -l "$OUT/nyayasim-db-$stamp.dump" "$OUT/nyayasim-files-$stamp.tar.gz"
echo "Schema version: $("${COMPOSE[@]}" exec -T postgres psql -U nyayasim -d nyayasim -tAc 'select version_num from alembic_version')"
echo "Done. Copy both files off this server."
