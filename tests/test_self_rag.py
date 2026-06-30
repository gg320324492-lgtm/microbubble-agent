"""#009 Phase 8 - Self-RAG 单元测试 (2026-06-30)

覆盖:
- check_relevance model kwarg 透传
- check_relevance 失败时 default-on-fail (confidence=0.3, can_answer=True)
- refine_query 确定性改写 (含中文 + 停用词)
- ContextCompressor.deduplicate 标题 + 内容前 200 字符

不依赖真实 LLM (mock), 全部单元级。
"""
import pytest

from app.services.self_rag import (
    ContextCompressor,
    SelfRAGChecker,
)


# ============================================================================
# refine_query 确定性改写
# ============================================================================


class TestRefineQuery:
    """v1 改写是 deterministic 关键词拼接，零额外 LLM latency"""

    def test_basic_关键词拼接(self):
        """原始 query + intent.keywords + missing 关键词 → 拼接"""
        checker = SelfRAGChecker()
        result = checker.refine_query(
            original_query="什么是微纳米气泡",
            missing="缺少 zeta 电位实验数据",
            intent_keywords=["微纳米气泡", "zeta电位"],
        )
        # 原始 + 关键词 + missing 关键词
        assert "微纳米气泡" in result
        assert "zeta电位" in result
        assert "缺少" not in result  # 停用词被剥
        # 顺序: 原始 query 在前
        assert result.startswith("什么是微纳米气泡")

    def test_empty_input_兜底(self):
        """original 空 + keywords 空 + missing 空 → 仍返非空"""
        checker = SelfRAGChecker()
        result = checker.refine_query(original_query="", missing="", intent_keywords=None)
        # 不抛异常, 返空字符串或纯空格（取决于实现）
        assert isinstance(result, str)

    def test_missing_单字被剥(self):
        """单字 stop_word 被剥 (de的/了/在/是/和/与/或)"""
        checker = SelfRAGChecker()
        result = checker.refine_query(
            original_query="Q",
            missing="的 了 在 缺少 实验数据 zeta电位",  # 多个停用词
            intent_keywords=None,
        )
        # 停用词 (单字) 必须被剥
        assert "的" not in result.split()
        assert "了" not in result.split()
        assert "在" not in result.split()
        assert "缺少" not in result.split()  # 缺少 是停用词
        # 真实内容词保留
        assert "实验数据" in result
        assert "zeta电位" in result

    def test_intent_keywords_优先_前3(self):
        """intent.keywords 只取前 3 个"""
        checker = SelfRAGChecker()
        result = checker.refine_query(
            original_query="Q",
            missing="",
            intent_keywords=["k1", "k2", "k3", "k4", "k5"],  # 5 个, 只取前 3
        )
        assert "k1" in result
        assert "k2" in result
        assert "k3" in result
        assert "k4" not in result
        assert "k5" not in result

    def test_max_chars_截断(self):
        """max_chars=20 截断 (按空格分隔避免半字)"""
        checker = SelfRAGChecker()
        result = checker.refine_query(
            original_query="很长的原始查询很长的原始查询很长的原始查询很长的原始查询",  # > 20 chars
            missing="",
            intent_keywords=None,
            max_chars=20,
        )
        assert len(result) <= 20

    def test_去重_intent_keywords_与_missing_重叠(self):
        """去重: intent.kw + missing kw 重叠时只保留 1 次"""
        checker = SelfRAGChecker()
        result = checker.refine_query(
            original_query="Q",
            missing="实验 实验 实验 重复 重复",  # 重复词
            intent_keywords=["实验"],  # 与 missing 重叠
        )
        # "实验" 只出现 1 次
        assert result.count("实验") == 1


# ============================================================================
# check_relevance mock 测试
# ============================================================================


class TestCheckRelevance:
    """LLM-as-judge mock 测试"""

    @pytest.mark.asyncio
    async def test_正常返回_high_confidence(self, monkeypatch):
        """Mock LLM 返高 confidence → 透传"""
        import app.core.llm as llm_mod

        class MockResp:
            class Content:
                text = '{"can_answer": true, "reason": "ok", "missing": "", "confidence": 0.9}'
            content = [Content()]

        class MockClient:
            class messages:
                @staticmethod
                async def create(*args, **kwargs):
                    return MockResp()

        monkeypatch.setattr(llm_mod, "get_anthropic_client", lambda: MockClient())
        monkeypatch.setattr(llm_mod, "get_default_model", lambda: "claude-haiku-4-5-20251001")

        checker = SelfRAGChecker()
        result = await checker.check_relevance("Q", "ctx", model="claude-haiku-4-5-20251001")
        assert result["can_answer"] is True
        assert result["confidence"] == 0.9
        assert result["model_used"] == "claude-haiku-4-5-20251001"
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_异常_default_on_fail(self, monkeypatch):
        """LLM 抛异常 → default-on-fail (can_answer=True, confidence=0.3)"""
        import app.core.llm as llm_mod

        class MockClient:
            class messages:
                @staticmethod
                async def create(*args, **kwargs):
                    raise Exception("API down")

        monkeypatch.setattr(llm_mod, "get_anthropic_client", lambda: MockClient())
        monkeypatch.setattr(llm_mod, "get_default_model", lambda: "claude-haiku-4-5-20251001")

        checker = SelfRAGChecker()
        result = await checker.check_relevance("Q", "ctx", model="claude-haiku-4-5-20251001")
        assert result["can_answer"] is True  # default-on-fail
        assert result["confidence"] == 0.3
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_非JSON_返_默认(self, monkeypatch):
        """LLM 返非 JSON 文本 → can_answer=True, confidence=0.5"""
        import app.core.llm as llm_mod

        class MockResp:
            class Content:
                text = "我无法判断, 这是一个非 JSON 回答"
            content = [Content()]

        class MockClient:
            class messages:
                @staticmethod
                async def create(*args, **kwargs):
                    return MockResp()

        monkeypatch.setattr(llm_mod, "get_anthropic_client", lambda: MockClient())
        monkeypatch.setattr(llm_mod, "get_default_model", lambda: "claude-haiku-4-5-20251001")

        checker = SelfRAGChecker()
        result = await checker.check_relevance("Q", "ctx", model="claude-haiku-4-5-20251001")
        assert result["can_answer"] is True
        assert result["confidence"] == 0.5
        assert "无法判断" in result["reason"] or "默认" in result["reason"]


# ============================================================================
# ContextCompressor.deduplicate
# ============================================================================


class TestContextCompressor:
    def test_deduplicate_去重_标题(self):
        """相同标题 → 保留 1 个"""
        comp = ContextCompressor()
        results = [
            {"title": "A", "content": "aaa..."},
            {"title": "B", "content": "bbb..."},
            {"title": "A", "content": "aaa..."},  # dup
        ]
        unique = comp.deduplicate(results)
        assert len(unique) == 2
        assert {r["title"] for r in unique} == {"A", "B"}

    def test_deduplicate_去重_内容_hash(self):
        """不同标题但内容前 200 字符相同 → 视为同一篇"""
        comp = ContextCompressor()
        results = [
            {"title": "A", "content": "X" * 250},
            {"title": "B", "content": "X" * 250},  # content[:200] = "XXX..."
        ]
        unique = comp.deduplicate(results)
        assert len(unique) == 1  # 内容前 200 字符 hash 相同

    def test_deduplicate_空列表_兜底(self):
        comp = ContextCompressor()
        assert comp.deduplicate([]) == []
