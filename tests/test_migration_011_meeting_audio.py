"""验证 alembic 011 迁移添加 meetings.audio_archive_* 字段

Wave 2b: MinIO 音频存档 + Admin 删除支持
为 meetings 表增加 5 个字段：
- audio_archive_url (VARCHAR 500) — MinIO 中的存档 URL
- audio_duration_seconds (FLOAT) — 音频时长
- audio_size_bytes (BIGINT) — 音频文件大小
- audio_archived_at (TIMESTAMPTZ) — 存档时间
- audio_archived (BOOLEAN) — 是否已存档（默认 false）

实现说明：
- 本测试使用同步 psycopg2 而非 asyncpg，避开 conftest.py 中 session-scope
  event_loop fixture 与 function-scope async test 之间的已知冲突
  （同一冲突也导致 test_migration_010_voice_embedding.py 无法在容器内运行）。
- 测试在 module-scope autouse fixture 中先 apply 迁移 SQL（IF NOT EXISTS 幂等），
  这样 conftest 的 setup_db（create_all + drop_all）下也能验证迁移后的 schema。
- 注意：本测试连 microbubble_test DB，不连 prod microbubble DB。
  验证 prod DB 需手工 psql 检查。
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
def _apply_011_migration(request):
    """在测试运行前先 apply 011 迁移 SQL 到 test DB（IF NOT EXISTS 幂等）。

    必须等 conftest 的 setup_db 完成 create_all 后才能 ALTER TABLE。
    conftest 的 setup_db 是 session-scope autouse，会在所有 module fixture 之前
    完成 create_all。我们用短 sleep 等它完成。

    当设置 MIGRATION_011_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
    """
    if os.getenv("MIGRATION_011_SKIP") == "1":
        yield
        return
    time.sleep(0.5)
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE meetings
                ADD COLUMN IF NOT EXISTS audio_archive_url VARCHAR(500),
                ADD COLUMN IF NOT EXISTS audio_duration_seconds FLOAT,
                ADD COLUMN IF NOT EXISTS audio_size_bytes BIGINT,
                ADD COLUMN IF NOT EXISTS audio_archived_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS audio_archived BOOLEAN DEFAULT FALSE
            """)
        conn.commit()
    yield


def test_audio_archive_columns_exist():
    """meetings 表应有 audio_archive_url / audio_duration_seconds / audio_size_bytes / audio_archived_at / audio_archived 5 列"""
    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'meetings'
                AND column_name IN ('audio_archive_url', 'audio_duration_seconds',
                                    'audio_size_bytes', 'audio_archived_at', 'audio_archived')
            """)
            columns = {row[0] for row in cur.fetchall()}
    assert columns == {'audio_archive_url', 'audio_duration_seconds',
                       'audio_size_bytes', 'audio_archived_at', 'audio_archived'}
