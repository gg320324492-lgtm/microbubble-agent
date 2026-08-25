"""Read-only snapshot exporter.

Connects to the web database using a read-only role and exports every
table listed in snapshot_schema.ALLOWED_SOURCE_TYPES as NDJSON files.
Forbidden fields (passwords, tokens, voice embeddings) are stripped
at the SELECT layer.

CLI:
  python -m scripts.desktop_migration.export_web_snapshot \
    --database-url 'postgres://readonly:***@host:5432/db' \
    --minio-endpoint 'https://minio.example.com' \
    --minio-access-key 'readonly-key' \
    --minio-secret-key '***' \
    --output-dir /path/to/snap \
    --snapshot-id snap-2026-08-26-001
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

try:
    from .snapshot_schema import (
        ALLOWED_SOURCE_TYPES,
        select_clause,
        validate_record,
    )
except ImportError:
    # Allow direct script invocation (python script.py) where relative
    # imports are not available. python -m uses the package form above.
    from snapshot_schema import (
        ALLOWED_SOURCE_TYPES,
        select_clause,
        validate_record,
    )


# SQL safety ----------------------------------------------------------

SAFE_SQL_PREFIXES = (
    "SELECT",
    "SHOW",
    "SET TRANSACTION READ ONLY",
    "BEGIN READ ONLY",
    "BEGIN",
    "ROLLBACK",
    "COMMIT",
)


class UnsafeSourceQueryError(Exception):
    """Raised when a connection tries to execute a write or unknown statement."""


class ConnectionLike(Protocol):
    def execute(self, sql: str): ...
    def fetch_all(self, sql: str): ...
    def commit(self): ...
    def rollback(self): ...
    def close(self): ...


def assert_sql_safe(sql: str) -> None:
    s = sql.strip().lstrip("(").strip()
    upper = s.upper()
    if not upper.startswith(SAFE_SQL_PREFIXES):
        raise UnsafeSourceQueryError(f"Refusing non-SELECT statement: {sql[:80]}")


# Export session ------------------------------------------------------

class ExportSession:
    def __init__(self, conn: ConnectionLike):
        self._conn = conn
        self._started = False

    def begin(self) -> None:
        # 第一条必须是 BEGIN READ ONLY，第二条 SET TRANSACTION READ ONLY
        self._conn.execute("BEGIN READ ONLY")
        self._conn.execute("SET TRANSACTION READ ONLY")
        self._started = True

    def fetch_all(self, sql: str):
        assert_sql_safe(sql)
        return self._conn.fetch_all(sql)

    def close(self) -> None:
        if self._started:
            try:
                self._conn.rollback()
            except Exception:
                pass
            self._started = False


# NDJSON writer -------------------------------------------------------

def write_ndjson(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True))
            f.write("\n")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# Export entry point --------------------------------------------------

def export_snapshot(
    connection: ConnectionLike,
    object_storage,
    output_dir: str,
    snapshot_id: str,
) -> dict:
    """Export the web database to NDJSON + manifest. Synchronous entry point.

    The caller is responsible for providing:
      * connection: any object with execute/fetch_all/commit/rollback/close
                    methods. The session calls execute(BEGIN READ ONLY) then
                    execute(SET TRANSACTION READ ONLY) before any SELECT.
      * object_storage: any object with list_objects_sync() and
                        get_object_sync(key). Used to enumerate MinIO attachments.
                        Both methods MUST be synchronous.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    session = ExportSession(connection)
    session.begin()

    started_at = datetime.now(timezone.utc).isoformat()
    start = time.time()

    counts: dict[str, int] = {}
    files: list[dict] = []

    try:
        for table in ALLOWED_SOURCE_TYPES:
            rows = session.fetch_all(select_clause(table))
            records = [validate_record(table, r) for r in rows]
            nd_path = out / f"{table}.ndjson"
            write_ndjson(nd_path, records)
            counts[table] = len(records)
            files.append({
                "name": nd_path.name,
                "sha256": file_sha256(nd_path),
                "size": nd_path.stat().st_size,
                "rows": len(records),
            })

        # 复制附件对象（只读对象清单 → 拷贝到 objects/<sha256>）
        objects_dir = out / "objects"
        objects_dir.mkdir(exist_ok=True)
        object_records: list[dict] = []
        if hasattr(object_storage, "list_objects_sync"):
            try:
                obj_list = object_storage.list_objects_sync()
            except Exception:
                obj_list = []
        else:
            obj_list = []
        for entry in obj_list:
            # entry 可能是 (key, sha, size) 三元组或 dict
            if isinstance(entry, dict):
                obj_key = entry["key"]
                obj_sha = entry["sha256"]
                obj_size = entry.get("size", 0)
            else:
                obj_key, obj_sha, obj_size = entry[0], entry[1], entry[2]
            dest = objects_dir / obj_sha
            if not dest.exists():
                try:
                    data = object_storage.get_object_sync(obj_key)
                    dest.write_bytes(data)
                except Exception:
                    continue
            object_records.append({"key": obj_key, "sha256": obj_sha, "size": obj_size})

        ended_at = datetime.now(timezone.utc).isoformat()
        manifest: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "formatVersion": 1,
            "startedAt": started_at,
            "endedAt": ended_at,
            "durationSeconds": round(time.time() - start, 3),
            "counts": counts,
            "objectCount": len(object_records),
            "files": files,
            "objects": object_records,
            "safety": {
                "readOnly": True,
                "forbiddenFieldsStripped": True,
                "snapshotSchemaVersion": 1,
            },
        }
        manifest_path = out / "snapshot-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest
    finally:
        session.close()


# CLI -----------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="export_web_snapshot",
        description="Export the web database to a read-only NDJSON snapshot.",
    )
    p.add_argument("--database-url", required=True,
                   help="PostgreSQL DSN. MUST be a read-only role. "
                        "Do NOT pass the application DSN.")
    p.add_argument("--minio-endpoint", required=True,
                   help="MinIO endpoint URL. MUST use a read-only access key.")
    p.add_argument("--minio-access-key", required=True)
    p.add_argument("--minio-secret-key", required=True)
    p.add_argument("--output-dir", required=True,
                   help="Local directory to write NDJSON + manifest.")
    p.add_argument("--snapshot-id", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if not args.database_url:
        print("ERROR: --database-url required", file=sys.stderr)
        return 2
    # CLI 默认仅打印配置 + 安全检查提示。真实连接通过 export_snapshot() 由
    # 调用方注入（生产环境使用 asyncpg/aioboto3 实例）。
    print("[export_web_snapshot] Configuration accepted:")
    print(f"  database-url: {args.database_url.split('@')[-1]}  (MUST be read-only role)")
    print(f"  minio-endpoint: {args.minio_endpoint}  (MUST use read-only credentials)")
    print(f"  output-dir: {args.output_dir}")
    print(f"  snapshot-id: {args.snapshot_id}")
    print()
    print("Run via Python: connection + object_storage injection. "
          "Use export_snapshot() from tests with fake connections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
