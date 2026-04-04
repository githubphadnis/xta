#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/export_db_backup.sh [output_dir]
#
# Env vars (optional):
#   POSTGRES_HOST (default: db)
#   POSTGRES_PORT (default: 5432)
#   POSTGRES_DB   (default: xta_db)
#   POSTGRES_USER (default: xta_user)
#   POSTGRES_PASSWORD (default: xta_password)

OUTPUT_DIR="${1:-./backups}"
mkdir -p "$OUTPUT_DIR"

POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-xta_db}"
POSTGRES_USER="${POSTGRES_USER:-xta_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-xta_password}"

TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${OUTPUT_DIR}/xta_${POSTGRES_DB}_${TS}.dump"

echo "Exporting PostgreSQL backup to ${OUT_FILE}"
export PGPASSWORD="${POSTGRES_PASSWORD}"
pg_dump \
  --format=custom \
  --host="${POSTGRES_HOST}" \
  --port="${POSTGRES_PORT}" \
  --username="${POSTGRES_USER}" \
  --dbname="${POSTGRES_DB}" \
  --file="${OUT_FILE}"
unset PGPASSWORD

echo "Backup complete: ${OUT_FILE}"
