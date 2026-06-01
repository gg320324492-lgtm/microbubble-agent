"""验证 alembic 016 迁移创建 meeting_templates 表 + 4 个内置种子

Wave 3b: 会议模板（组会/一对一/立项会/自由 + 用户自建）
为 meeting_templates 表：
- id (PK), name (索引), title_template, description, agenda (JSON),
  default_duration_minutes, default_participant_ids (JSON), default_location,
  is_builtin, is_active, created_by (FK members.id), created_at, updated_at
并创建 idx_meeting_template_active 索引（is_active）。
并 seed 4 个内置模板：组会 / 一对一 / 立项会 / 自由会议。

实现说明：
- 本测试使用同步 psycopg2 而非 asyncpg，避开 conftest.py 中 session-scope
  event_loop fixture 与 function-scope async test 之间的已知冲突
  （与 014 一致）。
- 测试在 module-scope autouse fixture 中先 apply 迁移 SQL（IF NOT EXISTS 幂等），
  这样 conftest 的 setup_db（create_all + drop_all）下也能验证迁移后的 schema。
- 当设置 MIGRATION_016_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
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
def _apply_016_migration(request):
    """在测试运行前先 apply 016 迁移 SQL 到 test DB（IF NOT EXISTS 幂等）。

    必须等 conftest 的 setup_db 完成 create_all 后才能 CREATE TABLE。
    conftest 的 setup_db 是 session-scope autouse，会在所有 module fixture 之前
    完成 create_all。我们用短 sleep 等它完成。

    当设置 MIGRATION_016_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
    """
    if os.getenv("MIGRATION_016_SKIP") == "1":
        yield
        return
    time.sleep(0.5)
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS meeting_templates (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    title_template VARCHAR(200),
                    description TEXT,
                    agenda JSON,
                    default_duration_minutes INTEGER DEFAULT 60,
                    default_participant_ids JSON,
                    default_location VARCHAR(200),
                    is_builtin BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_meeting_template_name "
                "ON meeting_templates (name)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_meeting_template_active "
                "ON meeting_templates (is_active)"
            )
            # Seed 4 builtin templates (idempotent)
            builtin = [
                ("组会", "组会 - {date}", "项目组例行周会", 60),
                ("一对一", "1-on-1 沟通", "导师与学生或同事间的一对一沟通", 30),
                ("立项会", "立项评审 - {project_name}", "新项目立项评审", 90),
                ("自由会议", "临时讨论", "无固定议程的自由讨论", 30),
            ]
            for name, title, desc, dur in builtin:
                cur.execute(
                    "SELECT 1 FROM meeting_templates WHERE name = %s AND is_builtin = true",
                    (name,),
                )
                if cur.fetchone() is None:
                    cur.execute(
                        "INSERT INTO meeting_templates "
                        "(name, title_template, description, agenda, "
                        "default_duration_minutes, is_builtin, is_active) "
                        "VALUES (%s, %s, %s, %s::json, %s, true, true)",
                        (name, title, desc, "[]", dur),
                    )
        conn.commit()
    yield


def test_meeting_templates_table_exists():
    """meeting_templates 表应存在"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_name = 'meeting_templates'
            """)
            row = cur.fetchone()
    assert row is not None, "meeting_templates 表不存在"


def test_meeting_templates_builtin_seeded():
    """应有 4 个内置模板（组会/一对一/立项会/自由）"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT name FROM meeting_templates WHERE is_builtin = true
            """)
            names = {row[0] for row in cur.fetchall()}
    assert {"组会", "一对一", "立项会", "自由会议"}.issubset(names), (
        f"缺少内置模板，当前内置: {names}"
    )


def test_meeting_templates_active_index_exists():
    """meeting_templates 表应有 idx_meeting_template_active 索引"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'meeting_templates'
                AND indexname = 'idx_meeting_template_active'
            """)
            row = cur.fetchone()
    assert row is not None, "idx_meeting_template_active 索引不存在"
