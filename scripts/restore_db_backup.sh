#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "Usage: scripts/restore_db_backup.sh <backup_file.dump>"
  exit 1
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

if [[ -z "${DB_USER:-}" || -z "${DB_NAME:-}" || -z "${DB_PASS:-}" ]]; then
  echo "DB_USER, DB_NAME, and DB_PASS must be set in environment."
  exit 1
fi

echo "Restoring backup into '${DB_NAME}' from '${BACKUP_FILE}'..."
docker compose exec -T \
  -e PGPASSWORD="${DB_PASS}" \
  db pg_restore --clean --if-exists --no-owner --no-privileges \
  -U "${DB_USER}" -d "${DB_NAME}" < "${BACKUP_FILE}"

echo "Restore completed."
