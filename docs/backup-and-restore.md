# Backup and Restore Runbook

This document describes a simple backup/restore flow for the XTA PostgreSQL database.

## Prerequisites

- Docker/Compose environment running with the `db` service.
- `pg_dump` available in the runtime environment where you execute backup.
- Environment variables for scripts (defaults are embedded):
  - `POSTGRES_HOST`
  - `POSTGRES_PORT`
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`

## 1) Create a Backup

From repository root:

```bash
chmod +x scripts/export_db_backup.sh scripts/restore_db_backup.sh
./scripts/export_db_backup.sh
```

This creates a PostgreSQL custom-format dump under `backups/`, e.g.:

`backups/xta_xta_db_20260401_120000.dump`

## 2) Restore a Backup

Use the generated backup path:

```bash
export DB_USER=xta_user
export DB_NAME=xta_db
export DB_PASS=xta_password
./scripts/restore_db_backup.sh backups/xta_xta_db_20260401_120000.dump
```

The script:

- validates file exists
- restores using `pg_restore --clean --if-exists`
- runs restore inside the `db` container via `docker compose exec`

## Safety Recommendations

- Restore first in staging, then production.
- Keep rolling daily backups and at least one weekly retention point.
- Pin production image tags (`vX.Y.Z`) during restore windows.

