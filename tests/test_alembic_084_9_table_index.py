"""W74 第 1 批 B-1: 9 表 2 索引缺口修复 e2e 验证

锚点范式: W73 第 1 批 242 → W74 第 1 批 B-1 246 守恒 (+1)

测试目标 (7 case):
- 4 GIN 索引 case (meeting.cluster_id_history / speaker_mapping / speaker_stats
  GIN 存在 + 性能提示)
- 2 联合部分索引 case (member voice_confirmed anchor 查询走 partial)
- 1 alembic 串单链 verify (1 head 守恒)

2026-09-12 生产库测试迁移:
- engine 改 tests.conftest.get_test_engine (原 app.core.database.engine 直连生产库)
- DB 检查从 sync inspect 改 async run_sync (sync 路径对 async engine 必抛
  MissingGreenlet — 旧版在真库上也是坏的, 实测 app.engine 同样报错)
- 索引存在性 / EXPLAIN 4 case 加 ALEMBIC_VERIFY=1 门禁: 这些索引由 alembic
  迁移创建 (模型未声明), conftest 的 create_all 测试库没有; 只有指向
  alembic-migrated 库 (TEST_DATABASE_URL) 显式开启时才有意义。
- head_singleton 不依赖 DB, 保持常开。

SKIP_DB_SETUP=1 时整文件 skip.
"""
import os
import pytest
from sqlalchemy import inspect, text

from tests.conftest import get_test_engine  # 2026-09-12 生产库测试迁移
from alembic.config import Config
from alembic.script import ScriptDirectory


SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))
ALEMBIC_VERIFY = bool(os.getenv("ALEMBIC_VERIFY"))
NEED_MIGRATED_DB = pytest.mark.skipif(
    not ALEMBIC_VERIFY,
    reason=(
        "迁移专属索引 (alembic 084 建, 模型未声明) 在 create_all 测试库不存在; "
        "ALEMBIC_VERIFY=1 且 TEST_DATABASE_URL 指向 alembic-migrated 库时开启"
    ),
)
pytestmark = pytest.mark.skipif(
    SKIP_DB_SETUP,
    reason="SKIP_DB_SETUP=1: alembic 084 验证需真 DB, 整文件 skip",
)


async def _get_indexes(table: str) -> set:
    """async 反射表索引名集合 (run_sync 走 greenlet, 不踩 MissingGreenlet)"""
    engine = get_test_engine()
    async with engine.connect() as conn:
        rows = await conn.run_sync(
            lambda c: [ix["name"] for ix in inspect(c).get_indexes(table)]
        )
    return set(rows)


async def _explain(sql: str) -> str:
    """async EXPLAIN, 返回多行计划文本"""
    engine = get_test_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        return "\n".join(row[0] for row in result)


# ==================== 1. alembic 串单链 (1 head 守恒) ====================

def test_alembic_084_head_singleton():
    """alembic 串单链不变量: 恒为 1 个 head

    W73 A-1 修复后单链 076→078→080→081→082→083, 084 严格接 083.
    W73 第 1 批 A-1 派工 v6 段 5 反馈 #3: alembic 链序按数字 commit 顺序派
    (不按 alphabetic).
    2026-09-12: 断言从写死 '084_...' head 号改为"单 head"不变量 — head 号
    随每次迁移演进 (当前 139), 写死必然随时间失效; 单链约束才是本测试本意。
    """
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, (
        f"alembic 不是单 head (分叉!), 实际 heads={heads}"
    )


# ==================== 2. GIN 索引存在性 (3 case) ====================

@NEED_MIGRATED_DB
async def test_meeting_cluster_id_history_gin_index_exists():
    """meeting.cluster_id_history 字段应有 GIN 索引 (jsonb_path_ops)"""
    indexes = await _get_indexes("meetings")
    assert "ix_meeting_cluster_id_history_gin" in indexes, (
        "ix_meeting_cluster_id_history_gin GIN 索引不存在"
    )


@NEED_MIGRATED_DB
async def test_meeting_speaker_mapping_gin_index_exists():
    """meeting.speaker_mapping 字段应有 GIN 索引 (jsonb_path_ops)"""
    indexes = await _get_indexes("meetings")
    assert "ix_meeting_speaker_mapping_gin" in indexes, (
        "ix_meeting_speaker_mapping_gin GIN 索引不存在"
    )


@NEED_MIGRATED_DB
async def test_meeting_speaker_stats_gin_index_exists():
    """meeting.speaker_stats 字段应有 GIN 索引 (jsonb_path_ops)"""
    indexes = await _get_indexes("meetings")
    assert "ix_meeting_speaker_stats_gin" in indexes, (
        "ix_meeting_speaker_stats_gin GIN 索引不存在"
    )


# ==================== 3. 联合部分索引存在性 + 性能 (2 case) ====================

@NEED_MIGRATED_DB
async def test_member_voice_confirmed_partial_index_exists():
    """member voice_confirmed_* 联合部分索引存在 (WHERE voice_confirmed_at IS NOT NULL)

    voice_confirmed_at IS NOT NULL = anchor (2026-06-28 增量 Cross-Anchor 策略)
    """
    indexes = await _get_indexes("members")
    assert "ix_member_voice_confirmed_partial" in indexes, (
        "ix_member_voice_confirmed_partial 部分索引不存在"
    )


@NEED_MIGRATED_DB
async def test_member_voice_confirmed_partial_index_used_in_query():
    """EXPLAIN 验证: anchor 查询走 ix_member_voice_confirmed_partial 部分索引

    必含查询: SELECT * FROM members WHERE voice_confirmed_at IS NOT NULL
    ORDER BY voice_confirmed_at DESC LIMIT 10
    期望 EXPLAIN 中包含 ix_member_voice_confirmed_partial
    """
    plan = await _explain(
        "EXPLAIN SELECT * FROM members "
        "WHERE voice_confirmed_at IS NOT NULL "
        "ORDER BY voice_confirmed_at DESC LIMIT 10"
    )
    assert "ix_member_voice_confirmed_partial" in plan, (
        f"anchor 查询未走 ix_member_voice_confirmed_partial 部分索引\n"
        f"EXPLAIN 计划:\n{plan}"
    )


# ==================== 4. GIN 索引性能验证 (1 case 覆盖 3 GIN) ====================

@NEED_MIGRATED_DB
async def test_meeting_gin_index_used_in_query():
    """EXPLAIN 验证: meeting JSON 字段查询走 GIN 索引

    必含查询: SELECT * FROM meetings WHERE cluster_id_history @> '[1,2,3]'::jsonb
    期望 EXPLAIN 中包含 ix_meeting_cluster_id_history_gin (或 Bitmap scan on GIN)
    """
    plan = await _explain(
        "EXPLAIN SELECT id FROM meetings "
        "WHERE cluster_id_history @> '[1,2,3]'::jsonb"
    )
    # 接受 3 种 GIN 索引任一被使用 (测试数据可能空, 验证索引名出现)
    gin_indexes = {
        "ix_meeting_cluster_id_history_gin",
        "ix_meeting_speaker_mapping_gin",
        "ix_meeting_speaker_stats_gin",
    }
    used = gin_indexes & set(plan.split())
    assert used, (
        f"meeting JSON @> 查询未走任何 GIN 索引\n"
        f"EXPLAIN 计划:\n{plan}"
    )
