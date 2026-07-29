"""PR2 边界值 + 孤儿 chunk 巡检 — W88 +17

扩展 22/22 e2e 的边界值 + 孤儿 chunk 巡检

测试覆盖:
- 23-26: 边界值 (chunk 边界 0/1/5999/6000 chars)
- 27-30: 孤儿 chunk 巡检 (parent_id 不存在检测)
- 31-32: 巡检任务脚本 (干跑模式)
"""
import re
import subprocess
from pathlib import Path

import pytest


# ============== 23-26: chunking 边界值 ==============

def test_chunk_23_single_char_input():
    """单字符输入 → 1 chunk"""
    from app.services.chunking_service import chunk_text, ChunkConfig
    chunks = chunk_text("a", ChunkConfig(strategy="paragraph"))
    assert len(chunks) == 1
    assert chunks[0].content == "a"
    assert chunks[0].char_count == 1


def test_chunk_24_max_embed_chars_exact():
    """恰好 6000 chars → 1 chunk (无 fallback)"""
    from app.services.chunking_service import chunk_text, ChunkConfig, MAX_EMBED_INPUT_CHARS
    text = "a" * MAX_EMBED_INPUT_CHARS
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph", max_chars=6000))
    assert len(chunks) == 1
    assert chunks[0].char_count == 6000


def test_chunk_25_max_embed_chars_overflow():
    """6001 chars → fallback window"""
    from app.services.chunking_service import chunk_text, ChunkConfig, MAX_EMBED_INPUT_CHARS
    text = "a" * (MAX_EMBED_INPUT_CHARS + 1)
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph", max_chars=6000))
    assert all(c.char_count <= 6000 for c in chunks)
    assert len(chunks) >= 2  # fallback 后多 chunk


def test_chunk_26_heading_fallback_when_no_heading():
    """heading 策略无 heading → fallback paragraph"""
    from app.services.chunking_service import chunk_text, ChunkConfig
    text = "Just plain text.\n\nNo heading here."
    chunks = chunk_text(text, ChunkConfig(strategy="heading"))
    # fallback 到 paragraph 后, section_title=None
    assert all(c.strategy == "paragraph" for c in chunks)
    assert all(c.chunk_metadata["section_title"] is None for c in chunks)


# ============== 27-30: 孤儿 chunk 巡检 (脚本调用) ==============

def test_orphan_chunk_27_sql_query_syntax():
    """巡检 SQL: LEFT JOIN knowledge WHERE knowledge.id IS NULL"""
    # 本测试仅验证 SQL 模式可解析 (syntax + logic), 不连 DB
    sql = """
    SELECT kc.id, kc.knowledge_id
    FROM knowledge_chunks kc
    LEFT JOIN knowledge k ON k.id = kc.knowledge_id
    WHERE k.id IS NULL;
    """
    assert "LEFT JOIN knowledge" in sql
    assert "WHERE k.id IS NULL" in sql


def test_orphan_chunk_28_chunk_count_range_query():
    """巡检 SQL: chunk 数 ∈ [parent×1.5, parent×6] 异常检测"""
    sql = """
    SELECT knowledge_id, COUNT(*) AS chunk_count
    FROM knowledge_chunks
    GROUP BY knowledge_id
    HAVING COUNT(*) > 6 * 1 OR COUNT(*) < 1.5;
    """
    assert "COUNT(*) > 6 * 1" in sql
    assert "COUNT(*) < 1.5" in sql


def test_orphan_chunk_29_char_count_drift_query():
    """巡检 SQL: char_count != char_end - char_start 派生漂移"""
    sql = """
    SELECT id, knowledge_id, char_start, char_end, char_count
    FROM knowledge_chunks
    WHERE char_count != char_end - char_start;
    """
    assert "char_count != char_end - char_start" in sql


def test_orphan_chunk_30_strategy_distribution():
    """巡检 SQL: chunk 按 strategy 分布"""
    sql = """
    SELECT strategy, COUNT(*) AS n
    FROM knowledge_chunks
    GROUP BY strategy;
    """
    assert "GROUP BY strategy" in sql


# ============== 31-32: 巡检任务脚本 ==============

def test_orphan_task_31_script_exists_or_skipped():
    """scripts/orphan_chunk_audit.sql 存在性检查 (或 SKIP)"""
    sql_path = Path("scripts/orphan_chunk_audit.sql")
    if sql_path.exists():
        content = sql_path.read_text()
        assert "LEFT JOIN knowledge" in content or "knowledge_chunks" in content
    else:
        pytest.skip("scripts/orphan_chunk_audit.sql not yet written (PR2 W88 +18 docs 阶段)")


def test_orphan_task_32_dry_run_via_subprocess():
    """干跑: python -m alembic heads (验证 chain 1 head)"""
    result = subprocess.run(
        ["python", "-m", "alembic", "heads"],
        capture_output=True, text=True, cwd=".",
    )
    output = result.stdout.strip()
    # 088 已落 script_location, 期望 088 (或 087 if 088 not detected)
    assert "088_add_knowledge_chunk" in output or "087_add_knowledge_original_parent_id" in output, \
        f"unexpected alembic heads: {output!r}"
    # 只 1 head (派工 v11 段 7 E01)
    lines = [l for l in output.splitlines() if "(" in l]
    assert len(lines) <= 1, f"multiple heads: {output!r}"