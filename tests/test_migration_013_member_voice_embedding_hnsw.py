"""验证 alembic 013 迁移添加 members.voice_embedding HNSW 索引

Wave 3a: 加速声纹识别和跨成员匹配
为 members 表的 voice_embedding 字段创建 idx_member_voice_embedding HNSW 索引
（vector_cosine_ops），用于 pgvector cosine 距离搜索，避免大规模成员（>100）
时的全表扫描。

实现说明：
- 本测试使用同步 psycopg2 而非 asyncpg，避开 conftest.py 中 session-scope
  event_loop fixture 与 function-scope async test 之间的已知冲突
  （同一冲突也导致 test_migration_010_voice_embedding.py 无法在容器内运行）。
- ⚠️ **apply 迁移 SQL 的代码在测试函数体内，不在 module-scope fixture**（2026-10-13 修正）。
  conftest 的 `setup_db` 现在是 `scope="function"`（`conftest.py:207`，W6 为修
  ScopeMismatch 从 session 改来），在每个测试函数前 drop_all → create_all；
  而 pytest fixture 执行顺序是 session > module > function
  ⇒ 放在 module-scope fixture 里必然**先于**建表执行 ⇒ `UndefinedTable`。
  这一点此前连续两轮都修错方向（第一轮归因成"CI 负载高、sleep 0.5 秒不够"，
  改成轮询等待后 CI 仍红并给出"等 60 秒表仍未出现"才暴露真因 —— **不是竞态，是必现**）。
- 注意：本测试连 microbubble_test DB，不连 prod microbubble DB。
  验证 prod DB 需手工 psql 检查。
- 当设置 MIGRATION_013_SKIP=1 时跳过 apply（用于在迁移前手动验证测试会 fail）。
"""
import os

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


def test_member_voice_embedding_hnsw_index_exists():
    """members 表应有 idx_member_voice_embedding HNSW 索引

    ⚠️ **建索引必须写在测试函数体内，不能放在 module-scope fixture**。
    根因（2026-10-13 定位，之前连续两轮都修错方向）:
      conftest 的 `setup_db` 现在是 **`scope="function"`**（`tests/conftest.py:207`，
      W6 为修 `ScopeMismatch` 从 session 改过来的），它在**每个测试函数前**执行
      drop_all → create_all。
      而本文件原来的 `_apply_013_migration` 是 `scope="module"` ——
      pytest 的 fixture 执行顺序是 **session > module > function**，
      ⇒ module-scope 的 fixture **必然先于** `setup_db` 运行，
      ⇒ 建索引时 `members` 表还不存在 ⇒ `UndefinedTable`。
      **这不是 flaky，是必现。**
    所以把 CREATE INDEX 移进函数体：此时 autouse function fixture `setup_db` 已跑完。

    ⚠️ **上面只解决了第一层，表建出来后还有第二层**（2026-10-13 第三次才撞到）：
    `DatatypeMismatch: operator class "vector_cosine_ops" does not accept data type halfvec`。
    根因是**测试照抄了 013 迁移的 SQL，而 013 本身没错** —— 它写 `vector_cosine_ops`
    时列确实还是 `vector(256)`；此后 `017_voice_embedding_192dim` 改 192 维、
    `102_voiceprint_halfvec` 再改成 `halfvec(192)` 并用 `halfvec_cosine_ops` 重建了索引，
    **生产库实测确实如此**，唯独这份拷贝停在 013 那个时刻。
    ⇒ 修法是按列的真实 `udt_name` 选 opclass（见下方代码），不是再抄一次迁移。

    当设置 `MIGRATION_013_SKIP=1` 时跳过 apply（用于在迁移前手动验证测试会 fail）。
    """
    if os.getenv("MIGRATION_013_SKIP") != "1":
        with _get_test_db_conn() as conn:
            with conn.cursor() as cur:
                # ⚠️ **opclass 必须跟着列的实际类型走**（类 20.162）。
                # 本测试早年是照抄 013 迁移里的 `vector_cosine_ops`，但那之后
                # `017_voice_embedding_192dim` 把列改成 192 维、
                # `102_voiceprint_halfvec` 再改成 `halfvec(192)` 并用
                # `halfvec_cosine_ops` 重建索引 —— 测试没跟着改 ⇒
                # `DatatypeMismatch: operator class "vector_cosine_ops"
                # does not accept data type halfvec`。
                # 013 迁移**本身没错**（当时列确实是 vector），过时的只有这份拷贝。
                # ⇒ 按列的真实 `udt_name` 选 opclass，类型再变也不会再漂。
                cur.execute(
                    "SELECT udt_name FROM information_schema.columns "
                    "WHERE table_name = 'members' "
                    "AND column_name = 'voice_embedding'"
                )
                udt = cur.fetchone()[0]
                assert udt in ("halfvec", "vector"), (
                    f"members.voice_embedding 类型异常：{udt!r}；"
                    f"迁移链 010 → 017 → 102 只应产出 halfvec / vector"
                )
                ops = "halfvec_cosine_ops" if udt == "halfvec" else "vector_cosine_ops"
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_member_voice_embedding "
                    f"ON members USING hnsw (voice_embedding {ops})"
                )
            conn.commit()

    with _get_test_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'members' AND indexname = 'idx_member_voice_embedding'
            """)
            row = cur.fetchone()
    assert row is not None, "idx_member_voice_embedding HNSW 索引不存在"
