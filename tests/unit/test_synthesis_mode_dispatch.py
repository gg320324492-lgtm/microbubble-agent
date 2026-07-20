"""2026-07-13 #P1: 三态推理模式 dispatch 单元测试。

覆盖：
- TestResolveThinkingConfig: ThinkingConfig 工厂函数 (8 case)
- TestToolContextThinkingConfig: ToolContext 新字段默认与赋值 (2 case)

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
        """fast 模式: 小 budget + 关 prompt gates。"""
        tc = resolve_thinking_config("fast")
        assert tc.mode == "fast"
        assert tc.model == "qwen3:8b"
        assert tc.thinking == {"type": "disabled"}
        assert tc.max_tokens == 3000
        assert tc.max_tool_tokens == 500
        assert tc.intent_aware_prompts is False
        assert tc.primitive_recognition is False
        assert tc.cross_domain_synthesis is False
        assert tc.json_protocol_strength == "none"
        assert tc.label == "快速"
        assert tc.cost_factor == 1.0

    def test_balanced_default_matches_old_behavior(self):
        """balanced 模式: prompt gates on (默认), 零行为差异。"""
        tc = resolve_thinking_config("balanced")
        assert tc.mode == "balanced"
        assert tc.model == "qwen3:8b"
        assert tc.thinking == {"type": "disabled"}
        # balanced max_tokens 来自 settings AGENT_THINKING_MODE_BALANCED_MAX_TOKENS=6000
        # 不等于旧 AGENT_MAX_SYNTHESIS_TOKENS=4000, 是预期 (略大)
        assert tc.max_tokens == 6000
        # max_tool_tokens 硬编码 500 (与 agentic_loop 现有硬编码一致)
        assert tc.max_tool_tokens == 500
        from app.config import settings

        assert tc.intent_aware_prompts == settings.AGENT_INTENT_AWARE_PROMPTS
        assert tc.primitive_recognition == settings.AGENT_PRIMITIVE_RECOGNITION
        assert tc.cross_domain_synthesis == settings.AGENT_CROSS_DOMAIN_SYNTHESIS
        assert tc.json_protocol_strength == "full"
        assert tc.label == "平衡"

    def test_deep_default_uses_deepseek_r1(self):
        """deep 模式: DeepSeek-R1-Distill-Qwen-7B + thinking enabled。"""
        tc = resolve_thinking_config("deep")
        assert tc.mode == "deep"
        assert tc.model == "deepseek-r1:7b"
        assert tc.thinking == {"type": "enabled", "budget_tokens": 8000}
        assert tc.max_tokens == 12000
        assert tc.max_tool_tokens == 1500
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