# Post-Deploy Checklist (Synology + Portainer + Cloudflare)

Use this checklist after merging a PR that changes application code, schema, or dependencies.

## 1) Merge and release tag

1. Merge PR into `main`.
2. Create and push the next version tag:

```bash
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

## 2) Confirm image build in GitHub Actions

1. Open GitHub -> **Actions** -> **Build and Publish**.
2. Confirm workflow is green for the new tag.
3. Confirm image exists in GHCR (`ghcr.io/githubphadnis/xta`), including `latest` and the new version tag.

## 3) Deploy in Portainer

If webhook deploy is configured:

```bash
curl -X POST "YOUR_PORTAINER_WEBHOOK_URL"
```

If webhook fails, redeploy manually from Portainer stack UI and pull latest image.

## 4) Run database migrations (no SSH required)

In Portainer:
1. Containers -> `ctrl-xta-prod-web` -> **Exec Console**.
2. Run:

```bash
cd /code
python3 -m alembic upgrade head
python3 -m alembic current
```

Expected output includes:

```text
... (head)
```

## 5) Quick smoke tests

1. Health endpoint:
   - `GET https://xta.pphadnis.com/health`
   - Expect: HTTP `200`, JSON shows `"status":"online"` and `"database":"connected"`.
2. Upload tests:
   - Upload one receipt image (`.png/.jpg/.jpeg`) and one statement (`.csv/.xls/.xlsx`).
3. UI checks:
   - `/expenses` loads.
   - Charts render.
   - Delete action works for a test entry.
4. Guardrail check:
   - Upload a file > `MAX_UPLOAD_SIZE_MB` to confirm rejection.

## 6) Alembic edge case recovery (already-existing tables)

If `alembic upgrade head` fails with `DuplicateTable` because tables were created before Alembic tracking:

```bash
cd /code
python3 -m alembic stamp 30eb4843fa0b
python3 -m alembic upgrade head
python3 -m alembic current
```

## 7) Rollback (if needed)

1. In Portainer, redeploy using last known-good image tag (not `latest`).
2. Restart web container.
3. Re-run smoke tests.

## 8) Operational notes

- Keep `.env` secrets only in deployment environment (never commit).
- Prefer immutable version tags (`vX.Y.Z`) for controlled rollback.
- Run migrations on every deploy that includes schema changes.
