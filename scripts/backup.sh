#!/usr/bin/env bash
set -euo pipefail

# GSTSense — database backup script
# Backs up PostgreSQL to S3 with date-stamped filenames
# Usage: bash scripts/backup.sh [--local]

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILENAME="gstsense_backup_${TIMESTAMP}.sql.gz"
LOCAL_DIR="${REPO_ROOT}/backups"
LOCAL_MODE=false

if [[ "${1:-}" == "--local" ]]; then
    LOCAL_MODE=true
fi

# ── Load env ───────────────────────────────────────────────────────────────

if [ -f "$REPO_ROOT/backend/.env" ]; then
    set -a
    source "$REPO_ROOT/backend/.env"
    set +a
fi

# ── Defaults ──────────────────────────────────────────────────────────────

DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-gstsense}"
DB_USER="${POSTGRES_USER:-gstsense}"
export PGPASSWORD="${POSTGRES_PASSWORD:-gstsense_dev_pass}"

S3_BUCKET="${S3_BUCKET_NAME:-gstsense-dev}"
S3_BACKUP_PREFIX="backups/db"

# ── Dump ──────────────────────────────────────────────────────────────────

mkdir -p "$LOCAL_DIR"
TMPFILE="${LOCAL_DIR}/${BACKUP_FILENAME}"

echo "==> Dumping database ${DB_NAME}@${DB_HOST}:${DB_PORT}..."
pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --no-password \
    --format=plain \
    --clean \
    "$DB_NAME" | gzip > "$TMPFILE"

BACKUP_SIZE="$(du -sh "$TMPFILE" | cut -f1)"
echo "    Backup written: ${BACKUP_FILENAME} (${BACKUP_SIZE})"

# ── Upload or keep local ────────────────────────────────────────────────────

if $LOCAL_MODE; then
    echo "    --local flag set. Keeping backup at: ${TMPFILE}"
else
    echo "==> Uploading to s3://${S3_BUCKET}/${S3_BACKUP_PREFIX}/${BACKUP_FILENAME}..."
    aws s3 cp "$TMPFILE" "s3://${S3_BUCKET}/${S3_BACKUP_PREFIX}/${BACKUP_FILENAME}" \
        --storage-class STANDARD_IA
    echo "    Upload complete."

    # Remove local file after successful upload
    rm "$TMPFILE"
fi

# ── Prune old local backups (keep last 7) ─────────────────────────────────

if ls "$LOCAL_DIR"/gstsense_backup_*.sql.gz 2>/dev/null | wc -l | grep -qv "^0$"; then
    ls -t "$LOCAL_DIR"/gstsense_backup_*.sql.gz | tail -n +8 | xargs -r rm --
    echo "    Old local backups pruned (kept last 7)."
fi

echo "==> Backup complete: ${BACKUP_FILENAME}"
