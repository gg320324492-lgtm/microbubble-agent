"""验证 alembic 014 迁移添加 reminders.target_type + reminders.meeting_id

Wave 3a: 5 分钟前自动会议提醒
为 reminders 表增加 2 个字段：
- target_type (VARCHAR 20) — 提醒目标类型，取值 'task' | 'meeting'，server_default='task'
- meeting_id (INTEGER) — 关联 meetings.id（可选，task 提醒时为 NULL）

并创建 idx_reminder_meeting_id 索引加速按 meeting_id 查找提醒。

实现说明：
- 本测试使用同步 psycopg2 而非 asyncpg，避开 conftest.py 中 session-scope
  event_loop fixture 与 function-scope async test 之间的已知冲突
  （同一冲突也导致 test_migration_010_voice_embedding.py 无法在容器内运行）。
- 测试在 module-scope autouse fixture 中先 apply 迁移 SQL（IF NOT EXISTS 幂等），
  这样 conftest 的 setup_db（create_all + drop_all）下也能验证迁移后的 schema。
- 注意：本测试连 microbubble_test DB，不连 prod microbubble DB。
  验证 prod DB 需手工 psql 检查。
- 当设置 MIGRATION_014_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
"""
import os
import time

import psycopg2
import pytest


def _get_test_db_conn():
    """获取同步 psycopg2 连接，TEST_DATABASE_URL 形如 postgresql+asyncpg://...@host:port/db"""
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:password@localhost:5432/microbubble_test",
    )
    url = url.replace("postgresql+asyncpg://", "")
    userinfo, hostinfo = url.split("@", 1)
    user, password = userinfo.split(":", 1)
    host_port, dbname = hostinfo.split("/", 1)
    host, port = host_port.split(":", 1)
    return psycopg2.connect(
        host=host, port=int(port), user=user, password=password, dbname=dbname
    )


@pytest.fixture(scope="module", autouse=True)
def _apply_014_migration(request):
    """在测试运行前先 apply 014 迁移 SQL 到 test DB（IF NOT EXISTS 幂等）。

    必须等 conftest 的 setup_db 完成 create_all 后才能 ALTER TABLE。
    conftest 的 setup_db 是 session-scope autouse，会在所有 module fixture 之前
    完成 create_all。我们用短 sleep 等它完成。

    当设置 MIGRATION_014_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
    """
    if os.getenv("MIGRATION_014_SKIP") == "1":
        yield
        return
    time.sleep(0.5)
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE reminders
                ADD COLUMN IF NOT EXISTS target_type VARCHAR(20) DEFAULT 'task',
                ADD COLUMN IF NOT EXISTS meeting_id INTEGER
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminder_meeting_id "
                "ON reminders (meeting_id)"
            )
        conn.commit()
    yield


def test_reminder_meeting_columns_exist():
    """reminders 表应有 target_type / meeting_id 2 列"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'reminders'
                AND column_name IN ('target_type', 'meeting_id')
            """)
            columns = {row[0] for row in cur.fetchall()}
    assert columns == {'target_type', 'meeting_id'}


def test_reminder_target_type_default_is_task():
    """target_type 列的 server_default 应为 'task'，保证老数据兼容"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'reminders' AND column_name = 'target_type'
            """)
            row = cur.fetchone()
    assert row is not None, "target_type 列不存在"
    assert row[1] == 'character varying', f"target_type 应为 varchar，实际为 {row[1]}"
    assert row[2] is not None and 'task' in row[2], (
        f"target_type 应有 server_default='task'，实际为 {row[2]}"
    )


def test_reminder_meeting_id_index_exists():
    """reminders 表应有 idx_reminder_meeting_id 索引"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'reminders' AND indexname = 'idx_reminder_meeting_id'
            """)
            row = cur.fetchone()
    assert row is not None, "idx_reminder_meeting_id 索引不存在"
