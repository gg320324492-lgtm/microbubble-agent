"""W74 第 1 批 B-1: 9 表 2 索引缺口修复 e2e 验证

锚点范式: W73 第 1 批 242 → W74 第 1 批 B-1 246 守恒 (+1)

测试目标 (7 case):
- 4 GIN 索引 case (meeting.cluster_id_history / speaker_mapping / speaker_stats
  GIN 存在 + 性能提示)
- 2 联合部分索引 case (member voice_confirmed anchor 查询走 partial)
- 1 alembic 串单链 verify (1 head 守恒)

注意: 测试需真 microbubble_test DB, SKIP_DB_SETUP=1 时整文件 skip.
0 production code 改动铁律守恒 (alembic + DDL 范畴, 例同 W72 第 2 批 B-3).
"""
import os
import pytest
from sqlalchemy import inspect, text

from app.core.database import engine
from alembic.config import Config
from alembic.script import ScriptDirectory


SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))
pytestmark = pytest.mark.skipif(
    SKIP_DB_SETUP,
    reason="SKIP_DB_SETUP=1: alembic 084 验证需真 DB, 整文件 skip",
)


# ==================== 1. alembic 串单链 (1 head 守恒) ====================

def test_alembic_084_head_singleton():
    """alembic 串单链 1 head 守恒: head = '084_meeting_cluster_jsonb_gin_index'

    W73 A-1 修复后单链 076→078→080→081→082→083, 084 严格接 083.
    W73 第 1 批 A-1 派工 v6 段 5 反馈 #3: alembic 链序按数字 commit 顺序派
    (不按 alphabetic).
    """
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["084_meeting_cluster_jsonb_gin_index"], (
        f"alembic 不是单 head, 实际 heads={heads}, 期望 ['084_meeting_cluster_jsonb_gin_index']"
    )


# ==================== 2. GIN 索引存在性 (3 case) ====================

def test_meeting_cluster_id_history_gin_index_exists():
    """meeting.cluster_id_history 字段应有 GIN 索引 (jsonb_path_ops)"""
    insp = inspect(engine.sync_engine)
    indexes = {ix["name"]: ix for ix in insp.get_indexes("meeting")}
    assert "ix_meeting_cluster_id_history_gin" in indexes, (
        "ix_meeting_cluster_id_history_gin GIN 索引不存在"
    )


def test_meeting_speaker_mapping_gin_index_exists():
    """meeting.speaker_mapping 字段应有 GIN 索引 (jsonb_path_ops)"""
    insp = inspect(engine.sync_engine)
    indexes = {ix["name"] for ix in insp.get_indexes("meeting")}
    assert "ix_meeting_speaker_mapping_gin" in indexes, (
        "ix_meeting_speaker_mapping_gin GIN 索引不存在"
    )


def test_meeting_speaker_stats_gin_index_exists():
    """meeting.speaker_stats 字段应有 GIN 索引 (jsonb_path_ops)"""
    insp = inspect(engine.sync_engine)
    indexes = {ix["name"] for ix in insp.get_indexes("meeting")}
    assert "ix_meeting_speaker_stats_gin" in indexes, (
        "ix_meeting_speaker_stats_gin GIN 索引不存在"
    )


# ==================== 3. 联合部分索引存在性 + 性能 (2 case) ====================

def test_member_voice_confirmed_partial_index_exists():
    """member voice_confirmed_* 联合部分索引存在 (WHERE voice_confirmed_at IS NOT NULL)

    voice_confirmed_at IS NOT NULL = anchor (2026-06-28 增量 Cross-Anchor 策略)
    """
    insp = inspect(engine.sync_engine)
    indexes = {ix["name"] for ix in insp.get_indexes("member")}
    assert "ix_member_voice_confirmed_partial" in indexes, (
        "ix_member_voice_confirmed_partial 部分索引不存在"
    )


def test_member_voice_confirmed_partial_index_used_in_query():
    """EXPLAIN 验证: anchor 查询走 ix_member_voice_confirmed_partial 部分索引

    必含查询: SELECT * FROM member WHERE voice_confirmed_at IS NOT NULL
    ORDER BY voice_confirmed_at DESC LIMIT 10
    期望 EXPLAIN 中包含 ix_member_voice_confirmed_partial
    """
    with engine.sync_engine.connect() as conn:
        result = conn.execute(
            text(
                "EXPLAIN SELECT * FROM member "
                "WHERE voice_confirmed_at IS NOT NULL "
                "ORDER BY voice_confirmed_at DESC LIMIT 10"
            )
        )
        plan = "\n".join(row[0] for row in result)
    assert "ix_member_voice_confirmed_partial" in plan, (
        f"anchor 查询未走 ix_member_voice_confirmed_partial 部分索引\n"
        f"EXPLAIN 计划:\n{plan}"
    )


# ==================== 4. GIN 索引性能验证 (1 case 覆盖 3 GIN) ====================

def test_meeting_gin_index_used_in_query():
    """EXPLAIN 验证: meeting JSON 字段查询走 GIN 索引

    必含查询: SELECT * FROM meeting WHERE cluster_id_history @> '[1,2,3]'::jsonb
    期望 EXPLAIN 中包含 ix_meeting_cluster_id_history_gin (或 Bitmapscan on GIN)
    """
    with engine.sync_engine.connect() as conn:
        result = conn.execute(
            text(
                "EXPLAIN SELECT id FROM meeting "
                "WHERE cluster_id_history @> '[1,2,3]'::jsonb"
            )
        )
        plan = "\n".join(row[0] for row in result)
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
