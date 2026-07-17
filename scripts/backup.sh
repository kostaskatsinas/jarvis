#!/usr/bin/env bash
# Jarvis backup: hot Postgres dumps daily, volume snapshots on Sundays
# (or FULL=1). Retention via PRUNE_DAYS. See docs/runbooks/backup.md.
set -euo pipefail
cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/jarvis-backups}"
PRUNE_DAYS="${PRUNE_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_DIR/$STAMP"
mkdir -p "$DEST"
chmod 700 "$BACKUP_DIR"

echo "== Postgres dumps (hot, consistent) =="
docker compose exec -T postgres pg_dump -U jarvis -Fc jarvis > "$DEST/jarvis.dump"
docker compose exec -T postgres pg_dump -U jarvis -Fc langfuse > "$DEST/langfuse.dump"

echo "== Secrets =="
cp .env "$DEST/env"
chmod 600 "$DEST/env"

if [ "$(date +%u)" = "7" ] || [ "${FULL:-0}" = "1" ]; then
    echo "== Volume snapshots (weekly/full) =="
    # caddy_data: TLS certs (restoring avoids Let's Encrypt rate limits).
    # clickhouse_data + minio_data: Langfuse traces — crash-consistent tar
    # is an accepted risk; traces are expendable relative to Postgres.
    for vol in caddy_data clickhouse_data minio_data; do
        docker run --rm \
            -v "jarvis_${vol}:/src:ro" \
            -v "$DEST:/dest" \
            alpine tar czf "/dest/${vol}.tar.gz" -C /src .
    done
fi

echo "== Pruning backups older than ${PRUNE_DAYS} days =="
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+${PRUNE_DAYS}" -exec rm -rf {} +

echo "backup complete: $DEST"
du -sh "$DEST"
