#!/usr/bin/env sh
set -eu

# Ensure database schema is up-to-date before serving traffic.
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
