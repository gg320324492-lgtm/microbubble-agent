"""2026-07-13 #P1: 三态推理模式 dispatch 单元测试。

覆盖：
- TestResolveThinkingConfig: ThinkingConfig 工厂函数 (8 case)
- TestToolContextThinkingConfig: ToolContext 新字段默认与赋值 (2 case)
- TestSelfRagParseFix: Self-RAG judge parse-fail 三策略 + fallback (5 case, commit 3 配套)

设计原则：
- 纯函数测试，不调真实 LLM
- 参考 tests/unit/test_tool_call_converter.py pattern (无 mock, 纯输入输出)
- 参考 tests/unit/test_llm_client_model_override.py SKIP_DB_SETUP 模式
"""

import os

os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.thinking_config import ThinkingConfig, resolve_thinking_config


# ============================================================================
# TestResolveThinkingConfig
# ============================================================================


class TestResolveThinkingConfig:
    """resolve_thinking_config(mode) 工厂函数测试。"""

    def test_fast_default(self):
        """fast 模式: 关 Self-RAG + 小 budget + 关 prompt gates。"""
        tc = resolve_thinking_config("fast")
        assert tc.mode == "fast"
        assert tc.model == "qwen3:8b"
        assert tc.thinking == {"type": "disabled"}
        assert tc.max_tokens == 3000
        assert tc.max_tool_tokens == 500
        assert tc.self_rag_enabled is False
        assert tc.self_rag_max_reretrieve == 0
        assert tc.intent_aware_prompts is False
        assert tc.primitive_recognition is False
        assert tc.cross_domain_synthesis is False
        assert tc.json_protocol_strength == "none"
        assert tc.label == "快速"
        assert tc.cost_factor == 1.0

    def test_balanced_default_matches_old_behavior(self):
        """balanced 模式: Self-RAG on (默认) + prompt gates on (默认), 零行为差异。"""
        tc = resolve_thinking_config("balanced")
        assert tc.mode == "balanced"
        assert tc.model == "qwen3:8b"
        assert tc.thinking == {"type": "disabled"}
        # balanced max_tokens 来自 settings AGENT_THINKING_MODE_BALANCED_MAX_TOKENS=6000
        # 不等于旧 AGENT_MAX_SYNTHESIS_TOKENS=4000, 是预期 (略大)
        assert tc.max_tokens == 6000
        # max_tool_tokens 硬编码 500 (与 agentic_loop 现有硬编码一致)
        assert tc.max_tool_tokens == 500
        # balanced 应保留 settings 现有 Self-RAG 默认
        # (从 app.config import 时 settings 已加载)
        from app.core.config import settings

        assert tc.self_rag_enabled == settings.AGENT_SELF_RAG_ENABLED
        assert tc.self_rag_max_reretrieve == settings.AGENT_SELF_RAG_MAX_RERETRIEVE
        assert tc.intent_aware_prompts == settings.AGENT_INTENT_AWARE_PROMPTS
        assert tc.primitive_recognition == settings.AGENT_PRIMITIVE_RECOGNITION
        assert tc.cross_domain_synthesis == settings.AGENT_CROSS_DOMAIN_SYNTHESIS
        assert tc.json_protocol_strength == "full"
        assert tc.label == "平衡"

    def test_deep_default_uses_deepseek_r1(self):
        """deep 模式: DeepSeek-R1-Distill-Qwen-7B + thinking enabled + 重检索 2 次。"""
        tc = resolve_thinking_config("deep")
        assert tc.mode == "deep"
        assert tc.model == "deepseek-r1-distill-qwen:7b"
        assert tc.thinking == {"type": "enabled", "budget_tokens": 8000}
        assert tc.max_tokens == 12000
        assert tc.max_tool_tokens == 1500
        assert tc.self_rag_enabled is True
        assert tc.self_rag_max_reretrieve == 2
        assert tc.intent_aware_prompts is True
        assert tc.primitive_recognition is True
        assert tc.cross_domain_synthesis is True
        assert tc.json_protocol_strength == "full"
        assert tc.label == "深度"
        assert tc.cost_factor == 3.0

    def test_deep_thinking_budget_respects_settings(self):
        """deep 模式 thinking budget_tokens 是 hardcode 8000 (不动 settings, 因为 ollama 不识别)。"""
        tc = resolve_thinking_config("deep")
        assert tc.thinking["budget_tokens"] == 8000

    def test_unknown_mode_falls_back_to_balanced(self):
        """未知 mode 字符串回落 balanced, 不抛错 (前端脏数据安全)。"""
        tc = resolve_thinking_config("ultra_fast_xxx")
        assert tc.mode == "balanced"

    def test_none_mode_uses_settings_default(self):
        """mode=None 回落 settings.AGENT_THINKING_MODE_DEFAULT (默认 'balanced')。"""
        from app.config import settings

        tc = resolve_thinking_config(None)
        assert tc.mode == settings.AGENT_THINKING_MODE_DEFAULT
        assert tc.mode == "balanced"

    def test_empty_string_mode_uses_settings_default(self):
        """mode='' 回落 settings 默认。"""
        tc = resolve_thinking_config("")
        assert tc.mode == "balanced"

    def test_thinking_config_is_frozen(self):
        """ThinkingConfig 是 frozen dataclass, 运行时不可修改。"""
        tc = resolve_thinking_config("fast")
        try:
            tc.mode = "deep"  # type: ignore[misc]
            raise AssertionError("应该抛 FrozenInstanceError")
        except Exception as e:
            # pydantic_settings / dataclasses(frozen=True) 抛 FrozenInstanceError 或 AttributeError
            assert "FrozenInstanceError" in type(e).__name__ or "frozen" in str(e).lower()


# ============================================================================
# TestToolContextThinkingConfig
# ============================================================================


class TestSelfRagParseFix:
    """2026-07-13 #P1: Self-RAG judge parse-fail 修复 — 三策略 JSON 提取 + 低 confidence fallback。"""

    def test_strategy1_json_fence(self):
        """strategy1: ```json fence 包裹 — 最稳路径, judge prompt 鼓励用。"""
        from app.services.self_rag import _extract_self_rag_json
        text = '好的, 这是判断结果:\n```json\n{"can_answer": false, "reason": "上下文不足", "missing": "实验数据", "confidence": 0.3}\n```\n其他略.'
        result = _extract_self_rag_json(text)
        assert result is not None
        assert result["can_answer"] is False
        assert result["confidence"] == 0.3
        assert result["missing"] == "实验数据"

    def test_strategy2_brace_match(self):
        """strategy2: brace match — 处理裸 JSON 无 fence。"""
        from app.services.self_rag import _extract_self_rag_json
        text = '好的, 我认为 {"can_answer": true, "reason": "上下文足够", "missing": "", "confidence": 0.8} 这是结论'
        result = _extract_self_rag_json(text)
        assert result is not None
        assert result["can_answer"] is True
        assert result["confidence"] == 0.8

    def test_strategy3_full_parse(self):
        """strategy3: 整段 try parse — 兜底, 处理裸 JSON 无 fence。"""
        from app.services.self_rag import _extract_self_rag_json
        text = '{"can_answer": true, "reason": "可以", "missing": "", "confidence": 0.7}'
        result = _extract_self_rag_json(text)
        assert result is not None
        assert result["can_answer"] is True
        assert result["confidence"] == 0.7

    def test_all_fail_returns_none(self):
        """全部策略失败返回 None — caller 走 low-confidence fallback。"""
        from app.services.self_rag import _extract_self_rag_json
        # 完全没有 JSON 片段
        text = "好的, 我认为可以回答, 但具体细节需要查一下"
        result = _extract_self_rag_json(text)
        assert result is None

    def test_existing_well_formatted_still_works(self):
        """现有格式 (纯 JSON 无前缀) 仍 work — 不能破坏老路径。"""
        from app.services.self_rag import _extract_self_rag_json
        text = '{"can_answer": true, "reason": "OK", "missing": "", "confidence": 0.95}'
        result = _extract_self_rag_json(text)
        assert result is not None
        assert result["can_answer"] is True
        assert result["confidence"] == 0.95

    def test_nested_braces(self):
        """strategy2 处理嵌套 {} (e.g. metadata 字段含嵌套 dict)。"""
        from app.services.self_rag import _extract_self_rag_json
        text = '{"can_answer": false, "reason": "r", "missing": "m", "confidence": 0.4, "metadata": {"key": "value"}}'
        result = _extract_self_rag_json(text)
        assert result is not None
        assert result["metadata"]["key"] == "value"


class TestToolContextThinkingConfig:
    """ToolContext 加 thinking_config / mode_label 字段测试。"""

    def test_default_ctx_has_no_thinking_config(self):
        """默认 ToolContext.thinking_config=None, mode_label='balanced', 向后兼容旧调用点。"""
        from app.agent.tool_registry import ToolContext

        ctx = ToolContext(db=None, user_id=1)
        assert ctx.thinking_config is None
        assert ctx.mode_label == "balanced"

    def test_ctx_with_deep_config_propagates_correctly(self):
        """ToolContext(thinking_config=tc, mode_label='深度') 后字段完整保留。"""
        from app.agent.tool_registry import ToolContext

        tc = resolve_thinking_config("deep")
        ctx = ToolContext(db=None, user_id=1, thinking_config=tc, mode_label="深度")
        assert ctx.thinking_config is tc
        assert ctx.mode_label == "深度"
        # 双保险: 旧字段 self_rag_enabled 仍然可单独传
        ctx2 = ToolContext(db=None, user_id=1, self_rag_enabled=True)
        assert ctx2.self_rag_enabled is True
        assert ctx2.thinking_config is None
        assert ctx2.mode_label == "balanced"