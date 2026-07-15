"""#043 自动拓展 — service 层单测 (无 async fixture 依赖, 避免 conftest 不兼容)

跑法:
    docker exec microbubble-agent-app-1 bash -c "cd /app && python -m pytest tests/test_auto_expansion.py -v"

覆盖:
- 正常入库
- 幂等 (重复 qa_id 不创建新行)
- scope → category 映射
- 空 tool_calls / rich_blocks 优雅降级
- list source_type 过滤
- stats source_types 分布
"""
import asyncio
import pytest

from app.core.database import async_session
from app.services.knowledge_service import KnowledgeService
from app.models.knowledge import Knowledge
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_from_auto_expansion_inserts_row():
    """首次入库: 字段全填, RichBlock 模式 meta 正确"""
    async with async_session() as db:
        svc = KnowledgeService(db)
        k = await svc.create_from_auto_expansion(
            qa_id="TEST-INSERT-AE001",
            question="什么是 DLVO 理论?",
            content="DLVO 理论是解释胶体稳定性的经典理论..." * 5,
            scope="theory", score=5, intent="explain_concept",
            tool_calls=[{"name": "search_knowledge", "input": {"query": "DLVO"}}],
            rich_blocks=[{"type": "KnowledgeRefBlock", "data": {}}],
        )
        assert k.id is not None
        assert k.source_type == "auto_expansion"
        assert k.source == "qa-bench:TEST-INSERT-AE001"
        assert k.created_by is None
        assert k.analysis_status == "done"
        assert k.quality_score == 1.0
        assert "自动拓展" in k.tags
        assert k.meta.get("qa_id") == "TEST-INSERT-AE001"
        assert k.meta.get("tool_calls")[0]["name"] == "search_knowledge"
        assert k.category == "理论基础"
        # 清理
        await db.delete(k)
        await db.commit()


@pytest.mark.asyncio
async def test_create_from_auto_expansion_idempotent():
    """幂等: 同一 qa_id 第二次调用返同一 id, 不创建新行"""
    async with async_session() as db:
        svc = KnowledgeService(db)
        k1 = await svc.create_from_auto_expansion(
            qa_id="TEST-IDEMPOTENT-AE001",
            question="重复测试",
            content="重复测试内容 " * 50,
            scope="core", score=4, intent="explain_concept",
        )
        k2 = await svc.create_from_auto_expansion(
            qa_id="TEST-IDEMPOTENT-AE001",
            question="重复测试（不同内容）",
            content="完全不同内容 " * 50,
            scope="core", score=4, intent="explain_concept",
        )
        assert k1.id == k2.id, f"幂等失败: k1={k1.id}, k2={k2.id}"
        # 清理
        await db.delete(k1)
        await db.commit()


@pytest.mark.asyncio
async def test_scope_to_category_mapping():
    """8 种 scope 全部映射正确 + 默认 fallback"""
    async with async_session() as db:
        svc = KnowledgeService(db)
        cases = [
            ("core", "基础知识"),
            ("method", "实验方法"),
            ("industry", "行业应用"),
            ("application", "应用案例"),
            ("academic", "学术研究"),
            ("policy", "政策法规"),
            ("theory", "理论基础"),
            ("emerging", "新兴方向"),
            ("", "基础知识"),
            (None, "基础知识"),
        ]
        created_ids = []
        for i, (scope, expected_cat) in enumerate(cases):
            k = await svc.create_from_auto_expansion(
                qa_id=f"TEST-SCOPE-{scope or 'none'}-{i}",
                question=f"scope={scope}",
                content=f"内容 {scope} " * 30,
                scope=scope, score=4, intent="explain_concept",
            )
            assert k.category == expected_cat, f"scope={scope} → {k.category}, expected {expected_cat}"
            created_ids.append(k.id)
        # 清理
        for kid in created_ids:
            k = (await db.execute(select(Knowledge).where(Knowledge.id == kid))).scalar_one_or_none()
            if k:
                await db.delete(k)
        await db.commit()


@pytest.mark.asyncio
async def test_create_from_auto_expansion_empty_tool_calls():
    """空 tool_calls + 空 rich_blocks 仍入库, content 标 '_(无工具调用)_'"""
    async with async_session() as db:
        svc = KnowledgeService(db)
        k = await svc.create_from_auto_expansion(
            qa_id="TEST-EMPTY-TOOLS-AE001",
            question="无工具测试",
            content="无工具测试内容 " * 50,
            scope="theory", score=5, intent="explain_concept",
            tool_calls=[], rich_blocks=[],
        )
        assert k.id is not None
        assert "_(无工具调用)_" in k.content
        assert k.meta["tool_calls"] == []
        assert k.meta["rich_blocks"] == []
        await db.delete(k)
        await db.commit()


@pytest.mark.asyncio
async def test_create_from_auto_expansion_returns_existing_id():
    """幂等返回值: service 层返 existing row 时调用方能区分新旧"""
    async with async_session() as db:
        svc = KnowledgeService(db)
        qa_id = "TEST-RETURN-AE001"
        # 第一次创建
        k1 = await svc.create_from_auto_expansion(
            qa_id=qa_id, question="first", content="first " * 50,
            scope="core", score=4, intent="explain_concept",
        )
        # 第二次 (不同内容) - 应返 existing row id
        k2 = await svc.create_from_auto_expansion(
            qa_id=qa_id, question="second", content="second " * 50,
            scope="theory", score=5, intent="search_info",
        )
        assert k1.id == k2.id
        # title/content 应是第一次的 (existing row 内容)
        assert k1.title == k2.title
        assert k1.content == k2.content
        # 清理
        await db.delete(k1)
        await db.commit()


# ─────────────────────────────────────────────────────────────────
# 2026-07-15 修复: content_hash 兜底 + search dedup 单测
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_from_auto_expansion_content_hash_fallback():
    """★ 2026-07-15: content_hash 兜底 — qa_id 不同但 content 相同时仍能 dedup

    根因: 历史脏数据中 3 条记录 (id=38/86/135) source 列全 NULL + title 完全一致,
    旧逻辑按 source='qa-bench:qa_id' 查重失效导致重复入库。
    修复: 计算 sha256(question|content[:500]) 写 meta.content_hash, 查重双重兜底。
    """
    async with async_session() as db:
        svc = KnowledgeService(db)
        same_q = "膜污染测试问题"
        same_c = "膜污染控制内容 " * 50
        # 第 1 次: 真实 qa_id 入库
        k1 = await svc.create_from_auto_expansion(
            qa_id="TEST-HASH-AE001", question=same_q, content=same_c,
            scope="core", score=4, intent="explain_concept",
        )
        assert k1.id is not None
        assert k1.meta.get("content_hash") is not None
        assert len(k1.meta["content_hash"]) == 32

        # 第 2 次: 不同 qa_id 但同 question+content → 应被 content_hash 兜底命中
        k2 = await svc.create_from_auto_expansion(
            qa_id="TEST-HASH-AE002", question=same_q, content=same_c,
            scope="core", score=4, intent="explain_concept",
        )
        assert k1.id == k2.id, (
            f"content_hash 兜底失败: k1={k1.id}, k2={k2.id}"
        )
        # 清理
        await db.delete(k1)
        await db.commit()


@pytest.mark.asyncio
async def test_create_from_auto_expansion_content_hash_distinguishes_diff_content():
    """content_hash 必须区分不同内容 (sha256 严格)"""
    async with async_session() as db:
        svc = KnowledgeService(db)
        # 完全不同 question+content → 应创建 2 行
        k1 = await svc.create_from_auto_expansion(
            qa_id="TEST-HASH-DIFF-AE001", question="Q1", content="content 1",
            scope="core", score=4, intent="explain_concept",
        )
        k2 = await svc.create_from_auto_expansion(
            qa_id="TEST-HASH-DIFF-AE002", question="Q2", content="content 2",
            scope="core", score=4, intent="explain_concept",
        )
        assert k1.id != k2.id
        assert k1.meta["content_hash"] != k2.meta["content_hash"]
        # 清理
        await db.delete(k1)
        await db.delete(k2)
        await db.commit()


# ─────────────────────────────────────────────────────────────────
# 2026-07-15 修复: search 层 _dedup_search_results_by_title 单测
# ─────────────────────────────────────────────────────────────────


class TestDedupSearchResultsByTitle:
    """★ 2026-07-15: search 层防御性去重, 防止历史脏数据渲染重复卡片

    5 cases 覆盖核心场景:
      1. 同 title 3 条 → 保留 score 最高
      2. 平局 score → id 最大优先
      3. 不同 title → 全保留
      4. 空 title → 跳过不入 dedup map
      5. 空列表 → 原样返回
    """

    def test_keeps_highest_score_for_duplicate_title(self):
        from app.services.knowledge_service import KnowledgeService
        results = [
            {"id": 1, "title": "Same", "score": 0.7},
            {"id": 2, "title": "Same", "score": 0.9},  # 最高
            {"id": 3, "title": "Same", "score": 0.8},
        ]
        out = KnowledgeService._dedup_search_results_by_title(results)
        assert len(out) == 1
        assert out[0]["id"] == 2
        assert out[0]["score"] == 0.9

    def test_tie_score_keeps_largest_id(self):
        from app.services.knowledge_service import KnowledgeService
        results = [
            {"id": 10, "title": "Tie", "score": 0.5},
            {"id": 30, "title": "Tie", "score": 0.5},
            {"id": 20, "title": "Tie", "score": 0.5},
        ]
        out = KnowledgeService._dedup_search_results_by_title(results)
        assert len(out) == 1
        assert out[0]["id"] == 30

    def test_different_titles_all_kept(self):
        from app.services.knowledge_service import KnowledgeService
        results = [
            {"id": 1, "title": "A", "score": 0.9},
            {"id": 2, "title": "B", "score": 0.8},
            {"id": 3, "title": "C", "score": 0.7},
        ]
        out = KnowledgeService._dedup_search_results_by_title(results)
        assert [r["id"] for r in out] == [1, 2, 3]

    def test_empty_title_skipped(self):
        from app.services.knowledge_service import KnowledgeService
        results = [
            {"id": 1, "title": "", "score": 0.9},
            {"id": 2, "title": "Real", "score": 0.8},
        ]
        out = KnowledgeService._dedup_search_results_by_title(results)
        # 空 title 不入 dedup map, 但会原样输出 (入参顺序)
        # 实际上 dedup 逻辑: 空 title 直接 continue (既不进 map 也不进 output)
        assert all(r.get("title") for r in out)
        assert [r["id"] for r in out] == [2]

    def test_empty_list_returns_empty(self):
        from app.services.knowledge_service import KnowledgeService
        assert KnowledgeService._dedup_search_results_by_title([]) == []

    def test_preserves_original_order(self):
        """★ 入参已按 score 降序, 输出也按原始顺序 (不重新排序)"""
        from app.services.knowledge_service import KnowledgeService
        results = [
            {"id": 1, "title": "Z-title", "score": 0.9},
            {"id": 2, "title": "A-title", "score": 0.8},
            {"id": 3, "title": "Z-title", "score": 0.7},  # dup of #1
        ]
        out = KnowledgeService._dedup_search_results_by_title(results)
        assert [r["id"] for r in out] == [1, 2]  # 保持入参顺序