#!/usr/bin/env bash
# Export the public order data (HRERA orders, page text, search chunks with embeddings, extracted
# case records) from the LOCAL dev database into one file a server can import.
#
# Buyer tables (cases, case_documents, facts, answers, hearing runs) are deliberately left out:
# the file contains public regulator orders only.
#
# Usage (from the repo root, Git Bash or Linux):
#   bash infra/export-data.sh                      # -> release/nyayasim-data.dump
#   bash infra/export-data.sh path/to/out.dump
set -euo pipefail

CONTAINER="${PG_CONTAINER:-infra-postgres-1}"
OUT="${1:-release/nyayasim-data.dump}"
TABLES=(orders order_pages order_chunks case_records fetch_log)

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "error: container '$CONTAINER' not found. Start the local DB (docker compose -f infra/docker-compose.yml up -d)" >&2
  echo "       or set PG_CONTAINER to the right name (see: docker ps)." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"
args=()
for t in "${TABLES[@]}"; do args+=(-t "public.$t"); done

echo "Exporting ${TABLES[*]} from $CONTAINER ..."
# shellcheck disable=SC2016
docker exec "$CONTAINER" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only --format=custom --compress=9 '"${args[*]}"' -f /tmp/nyayasim-data.dump'
docker cp "$CONTAINER:/tmp/nyayasim-data.dump" "$OUT"
docker exec "$CONTAINER" rm -f /tmp/nyayasim-data.dump

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo "Schema version of this data: $(docker exec "$CONTAINER" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select version_num from alembic_version"')"
