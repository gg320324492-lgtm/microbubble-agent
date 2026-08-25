"""Read-only snapshot exporter tests (R2).

These tests verify:
1. ExportSession starts with BEGIN READ ONLY + SET TRANSACTION READ ONLY.
2. Unsafe SQL (DELETE/UPDATE/INSERT/TRUNCATE/DROP) is rejected.
3. Safe SELECT queries are allowed.
4. Session rolls back (not commits) on close.
5. export_snapshot() writes NDJSON files + snapshot-manifest.json with SHA-256.

Tests use a synchronous ConnectionLike stub matching the implementation
in scripts.desktop_migration.export_web_snapshot.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts.desktop_migration.export_web_snapshot import (
    ExportSession,
    UnsafeSourceQueryError,
    export_snapshot,
)


class FakeConnection:
    """Synchronous connection stub matching the ConnectionLike protocol."""

    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.executed: list[str] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, sql: str):
        self.executed.append(sql)
        # execute() for BEGIN / SET / ROLLBACK does not return rows.
        return None

    def fetch_all(self, sql: str):
        self.executed.append(sql)
        if not self.replies:
            raise AssertionError(f"No reply for SQL: {sql}")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_export_session_starts_with_read_only_tx():
    conn = FakeConnection([])
    session = ExportSession(conn)
    session.begin()
    sqls = conn.executed
    # 第一条必须是 BEGIN READ ONLY
    assert sqls[0].strip().upper().startswith("BEGIN READ ONLY"), sqls
    # 第二条必须是 SET TRANSACTION READ ONLY
    assert sqls[1].strip().upper() == "SET TRANSACTION READ ONLY", sqls
    session.close()


def test_export_session_rejects_unsafe_queries():
    conn = FakeConnection([])
    session = ExportSession(conn)
    session.begin()
    with pytest.raises(UnsafeSourceQueryError):
        session.fetch_all("DELETE FROM members")
    with pytest.raises(UnsafeSourceQueryError):
        session.fetch_all("UPDATE members SET name='x'")
    with pytest.raises(UnsafeSourceQueryError):
        session.fetch_all("INSERT INTO members VALUES (1)")
    with pytest.raises(UnsafeSourceQueryError):
        session.fetch_all("TRUNCATE members")
    with pytest.raises(UnsafeSourceQueryError):
        session.fetch_all("DROP TABLE members")


def test_export_session_allows_safe_queries():
    conn = FakeConnection([[]])
    session = ExportSession(conn)
    session.begin()
    rows = session.fetch_all("SELECT id FROM members")
    assert rows == []
    conn.replies = [[]]
    rows = session.fetch_all("SHOW TABLES")
    assert rows == []
    session.close()


def test_export_session_rolls_back_on_close():
    conn = FakeConnection([])
    session = ExportSession(conn)
    session.begin()
    session.close()
    assert conn.rolled_back is True
    assert conn.committed is False


def test_export_snapshot_writes_ndjson_and_manifest(tmp_path):
    """验证导出器写入 NDJSON 文件 + snapshot-manifest.json，含 SHA-256。"""
    out_dir = tmp_path / "snap"
    out_dir.mkdir()

    # 准备 fake 数据库响应（按调用顺序返回 rows）
    # export_snapshot 会按 source_type 顺序查询 9 张表
    fake_rows_per_table = {
        "members": [{"id": 1, "name": "Alice", "email": "a@x.com", "updated_at": "2026-08-26T00:00:00Z"}],
        "projects": [{"id": 1, "name": "P1", "updated_at": "2026-08-26T00:00:00Z"}],
        "milestones": [],
        "tasks": [{"id": 1, "title": "T1", "status": "in_progress", "updated_at": "2026-08-26T00:00:00Z"}],
        "meetings": [],
        "knowledge": [{"id": 1, "title": "K1", "updated_at": "2026-08-26T00:00:00Z"}],
        "drive": [],
        "chat": [],
        "audit": [],
    }

    fake_conn = FakeConn(fake_rows_per_table)
    fake_obj = FakeObject()

    manifest = export_snapshot(
        connection=fake_conn,
        object_storage=fake_obj,
        output_dir=str(out_dir),
        snapshot_id="snap-001",
    )

    # 检查 NDJSON 文件
    members_ndjson = (out_dir / "members.ndjson").read_text(encoding="utf-8")
    assert "Alice" in members_ndjson
    assert '"source_type": "members"' in members_ndjson
    projects_ndjson = (out_dir / "projects.ndjson").read_text(encoding="utf-8")
    assert "P1" in projects_ndjson

    # 检查 snapshot-manifest.json
    loaded = json.loads((out_dir / "snapshot-manifest.json").read_text(encoding="utf-8"))
    assert loaded["snapshot_id"] == "snap-001"
    assert loaded["counts"]["members"] == 1
    assert loaded["counts"]["projects"] == 1
    assert loaded["counts"]["tasks"] == 1
    assert loaded["counts"]["knowledge"] == 1
    # 每个 NDJSON 都应有 SHA-256
    assert len(loaded["files"]) >= 9  # 9 个 NDJSON
    for f in loaded["files"]:
        assert "sha256" in f and "size" in f
        assert len(f["sha256"]) == 64

    # 返回的 manifest 与磁盘一致
    assert manifest["snapshot_id"] == "snap-001"


def test_export_snapshot_strips_forbidden_fields():
    """验证 select_clause 白名单排除了密码/声纹/secret 字段。"""
    from scripts.desktop_migration.snapshot_schema import (
        FORBIDDEN_FIELDS,
        TABLE_FIELDS,
        select_clause,
        validate_record,
    )

    # 检查关键表的白名单不含 FORBIDDEN_FIELDS
    for table, fields in TABLE_FIELDS.items():
        overlap = FORBIDDEN_FIELDS.intersection(fields)
        assert not overlap, f"{table} 白名单包含禁止字段: {overlap}"

    # select_clause 生成的 SQL 不含禁止列
    for table in TABLE_FIELDS:
        sql = select_clause(table).upper().replace("\n", " ")
        for forbidden in FORBIDDEN_FIELDS:
            assert forbidden.upper() not in sql, f"{table} select 含禁止字段 {forbidden}"

    # validate_record 注入 source_* 字段
    rec = validate_record("members", {"id": 1, "name": "x", "updated_at": "2026-01-01T00:00:00Z"})
    assert rec["source_type"] == "members"
    assert rec["source_id"] == 1
    assert rec["source_updated_at"] == "2026-01-01T00:00:00Z"


def test_assert_sql_safe_blocks_dml_and_ddl():
    from scripts.desktop_migration.export_web_snapshot import assert_sql_safe

    # 必须放行的
    for safe in [
        "SELECT id FROM members",
        "select id from members",
        "SHOW TABLES",
        "SET TRANSACTION READ ONLY",
        "BEGIN READ ONLY",
        "ROLLBACK",
        "COMMIT",
    ]:
        assert_sql_safe(safe)  # 不抛

    # 必须拦截的
    for unsafe in [
        "DELETE FROM members",
        "UPDATE members SET name='x'",
        "INSERT INTO members VALUES (1)",
        "TRUNCATE members",
        "DROP TABLE members",
        "ALTER TABLE members ADD COLUMN",
        "CREATE TABLE x (id INT)",
        "GRANT SELECT ON x TO y",
    ]:
        with pytest.raises(UnsafeSourceQueryError):
            assert_sql_safe(unsafe)


# ---- 辅助 ----


class FakeConn:
    """比 FakeConnection 更智能：按 SQL 内容识别表名并返回对应 rows。"""

    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.executed: list[str] = []
        self.committed = False
        self.rolled_back = False

    def execute(self, sql: str):
        self.executed.append(sql)
        return None

    def fetch_all(self, sql: str):
        self.executed.append(sql)
        sql_upper = sql.upper().replace("\n", " ").strip()
        for table, rows in self.rows_by_table.items():
            if f"FROM {table.upper()}" in sql_upper:
                return list(rows)
        return []

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class FakeObject:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def list_objects_sync(self):
        """返回 [(key, sha256, size), ...]"""
        return [(k, _sha256_hex(v), len(v)) for k, v in self.objects.items()]

    def get_object_sync(self, key: str) -> bytes:
        return self.objects[key]

    def close(self):
        pass


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
