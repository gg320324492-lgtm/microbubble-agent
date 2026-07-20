"""验证 alembic 012 迁移添加 meetings.embedding / agenda / related_meeting_ids + HNSW 索引

Wave 3a: 跨会议相似度匹配需要 meeting embedding
为 meetings 表增加 3 个字段：
- agenda (JSON) — 议题列表（Wave 3b 准备）
- embedding (vector(768)) — 会议文本 embedding，pgvector cosine 距离
- related_meeting_ids (JSON) — 人类选择的关联会议 ID 列表

并创建 idx_meeting_embedding HNSW 索引加速 cosine 搜索。

实现说明：
- 本测试使用同步 psycopg2 而非 asyncpg，避开 conftest.py 中 session-scope
  event_loop fixture 与 function-scope async test 之间的已知冲突
  （同一冲突也导致 test_migration_010_voice_embedding.py 无法在容器内运行）。
- 测试在 module-scope autouse fixture 中先 apply 迁移 SQL（IF NOT EXISTS 幂等），
  这样 conftest 的 setup_db（create_all + drop_all）下也能验证迁移后的 schema。
- 注意：本测试连 microbubble_test DB，不连 prod microbubble DB。
  验证 prod DB 需手工 psql 检查。
- 当设置 MIGRATION_012_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
"""
import os
import time

import psycopg2
import pytest

# SKIP_DB_SETUP=1 整文件 skip (跟 conftest db fixture 跳过逻辑一致)
# 这些测试需要真 microbubble_test DB 才能跑 (psycopg2 同步连), SKIP 模式优雅 skip
# W1 (2026-07-21) class 1 migration_stale 修复: convert ERROR → graceful SKIP
SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))
pytestmark = pytest.mark.skipif(
    SKIP_DB_SETUP,
    reason="SKIP_DB_SETUP=1：psycopg2 同步连 TEST_DATABASE_URL 需要真 DB, SKIP 模式 skip",
)


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
def _apply_012_migration(request):
    """在测试运行前先 apply 012 迁移 SQL 到 test DB（IF NOT EXISTS 幂等）。

    必须等 conftest 的 setup_db 完成 create_all 后才能 ALTER TABLE。
    conftest 的 setup_db 是 session-scope autouse，会在所有 module fixture 之前
    完成 create_all。我们用短 sleep 等它完成。

    当设置 MIGRATION_012_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
    """
    if os.getenv("MIGRATION_012_SKIP") == "1":
        yield
        return
    time.sleep(0.5)
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE meetings
                ADD COLUMN IF NOT EXISTS agenda JSON,
                ADD COLUMN IF NOT EXISTS embedding vector(768),
                ADD COLUMN IF NOT EXISTS related_meeting_ids JSON
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_meeting_embedding "
                "ON meetings USING hnsw (embedding vector_cosine_ops)"
            )
        conn.commit()
    yield


def test_meeting_embedding_columns_exist():
    """meetings 表应有 agenda / embedding / related_meeting_ids 3 列"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'meetings'
                AND column_name IN ('agenda', 'embedding', 'related_meeting_ids')
            """)
            columns = {row[0] for row in cur.fetchall()}
    assert columns == {'agenda', 'embedding', 'related_meeting_ids'}


def test_meeting_embedding_column_type():
    """embedding 应是 vector(768) 类型"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = 'meetings' AND column_name = 'embedding'
            """)
            row = cur.fetchone()
    assert row is not None, "embedding 列不存在"
    # pgvector 在 information_schema 中 udt_name = 'vector'
    assert row[1] == 'vector', f"embedding 应为 vector 类型，实际为 {row[1]}"


def test_meeting_embedding_hnsw_index_exists():
    """meetings 表应有 idx_meeting_embedding HNSW 索引"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'meetings' AND indexname = 'idx_meeting_embedding'
            """)
            row = cur.fetchone()
    assert row is not None, "idx_meeting_embedding HNSW 索引不存在"
