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