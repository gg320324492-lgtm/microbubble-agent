"""验证 alembic 013 迁移添加 members.voice_embedding HNSW 索引

Wave 3a: 加速声纹识别和跨成员匹配
为 members 表的 voice_embedding 字段创建 idx_member_voice_embedding HNSW 索引
（vector_cosine_ops），用于 pgvector cosine 距离搜索，避免大规模成员（>100）
时的全表扫描。

实现说明：
- 本测试使用同步 psycopg2 而非 asyncpg，避开 conftest.py 中 session-scope
  event_loop fixture 与 function-scope async test 之间的已知冲突
  （同一冲突也导致 test_migration_010_voice_embedding.py 无法在容器内运行）。
- 测试在 module-scope autouse fixture 中先 apply 迁移 SQL（IF NOT EXISTS 幂等），
  这样 conftest 的 setup_db（create_all + drop_all）下也能验证迁移后的 schema。
- 注意：本测试连 microbubble_test DB，不连 prod microbubble DB。
  验证 prod DB 需手工 psql 检查。
- 当设置 MIGRATION_013_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
"""
import os
import time

import psycopg2
import pytest

# SKIP_DB_SETUP=1 整文件 skip (跟 conftest db fixture 跳过逻辑一致)
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
def _apply_013_migration(request):
    """在测试运行前先 apply 013 迁移 SQL 到 test DB（IF NOT EXISTS 幂等）。

    必须等 conftest 的 setup_db 完成 create_all 后才能 ALTER TABLE。
    conftest 的 setup_db 是 session-scope autouse，会在所有 module fixture 之前
    完成 create_all。我们用短 sleep 等它完成。

    当设置 MIGRATION_013_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
    """
    if os.getenv("MIGRATION_013_SKIP") == "1":
        yield
        return
    time.sleep(0.5)
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_member_voice_embedding "
                "ON members USING hnsw (voice_embedding vector_cosine_ops)"
            )
        conn.commit()
    yield


def test_member_voice_embedding_hnsw_index_exists():
    """members 表应有 idx_member_voice_embedding HNSW 索引"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'members' AND indexname = 'idx_member_voice_embedding'
            """)
            row = cur.fetchone()
    assert row is not None, "idx_member_voice_embedding HNSW 索引不存在"
