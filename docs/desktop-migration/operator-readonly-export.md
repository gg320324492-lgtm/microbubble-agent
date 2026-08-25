# Read-Only Web Snapshot Export Operator Guide

This guide describes how to run `scripts/desktop_migration/export_web_snapshot.py` to capture a snapshot of the web database and MinIO objects for desktop migration.

## Mandatory prerequisites

1. **Read-only PostgreSQL role.** The migration script must be given a DSN whose role has only `SELECT` privilege on every table listed in `snapshot_schema.ALLOWED_SOURCE_TYPES`. The application role must NOT be reused.
2. **Read-only MinIO credentials.** The MinIO access key must have `s3:GetObject` and `s3:ListBucket` only, on the bucket prefix used by the web app.
3. **First SQL is `BEGIN READ ONLY` / `SET TRANSACTION READ ONLY`.** The exporter enforces this and refuses any non-SELECT statement.
4. **Local output directory.** The script writes NDJSON files and `snapshot-manifest.json` into the directory passed via `--output-dir`.

## Running the exporter

```powershell
python -m scripts.desktop_migration.export_web_snapshot `
  --database-url 'postgres://readonly_ro:***@db.example.com:5432/microbubble' `
  --minio-endpoint 'https://minio.example.com' `
  --minio-access-key 'readonly-key' `
  --minio-secret-key '***' `
  --output-dir C:\snapshots\snap-2026-08-26 `
  --snapshot-id snap-2026-08-26-001
```

## Output layout

```
snap-2026-08-26/
├── members.ndjson
├── projects.ndjson
├── milestones.ndjson
├── tasks.ndjson
├── meetings.ndjson
├── knowledge.ndjson
├── drive.ndjson
├── chat.ndjson
├── audit.ndjson
├── objects/<sha256>          # raw attachments by content hash
└── snapshot-manifest.json    # counts, sha256, startedAt/endedAt
```

## Programmatic usage

The CLI is intentionally minimal (validates configuration). Real exports use the
Python entry point so callers can inject their own asyncpg connection and
object-storage client:

```python
from scripts.desktop_migration.export_web_snapshot import export_snapshot

manifest = export_snapshot(
    connection=readonly_asyncpg_conn,
    object_storage=readonly_minio_client,
    output_dir="/mnt/snapshots/snap-001",
    snapshot_id="snap-001",
)
```

## Security checklist before running

- [ ] Database role verified as read-only (`\du` in psql; only `SELECT` privileges)
- [ ] MinIO key verified as read-only (`mc admin policy info readonly-migration`)
- [ ] `--output-dir` is on an encrypted volume or wiped after handoff
- [ ] No write operations on the web app during the export window

## Failure modes

- `UnsafeSourceQueryError` — exporter tried to run a non-SELECT statement. **Stop** and report to the orchestrator.
- Missing role privileges — exporter will fail with a PostgreSQL permission error. **Stop** and request a properly scoped role from the DBA.
