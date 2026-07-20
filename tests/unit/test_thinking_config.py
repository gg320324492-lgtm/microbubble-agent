"""测试 thinking_config.py（2026-07-15 #P2 fast mode 提速）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_thinking_config.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.agent.thinking_config import ThinkingConfig, resolve_thinking_config


class TestFastModeSkips:
    """2026-07-15 #P2: fast 模式真正快速——跳过 plan_step / critique / Phase 1 tool loop"""

    def test_fast_skip_plan_step_true(self):
        """fast mode 必须 skip plan_step, 让用户感知'快速'语义"""
        cfg = resolve_thinking_config("fast")
        assert cfg.mode == "fast"
        assert cfg.skip_plan_step is True

    def test_fast_skip_critique_true(self):
        """fast mode 必须 skip critique + retry"""
        cfg = resolve_thinking_config("fast")
        assert cfg.skip_critique is True

    def test_fast_max_tool_rounds_zero(self):
        """fast mode max_tool_rounds=0 → Phase 1 tool loop 直接跳过"""
        cfg = resolve_thinking_config("fast")
        assert cfg.max_tool_rounds == 0


class TestBalancedModeUnchanged:
    """2026-07-15 #P2: balanced 模式行为不变 (迁移期兜底, 与 settings 对齐)"""

    def test_balanced_no_skip(self):
        cfg = resolve_thinking_config("balanced")
        assert cfg.mode == "balanced"
        assert cfg.skip_plan_step is False
        assert cfg.skip_critique is False

    def test_balanced_max_tool_rounds_from_settings(self):
        """balanced 模式 max_tool_rounds 走 settings.AGENT_MAX_TOOL_ROUNDS (默认 5)"""
        from app.config import settings
        cfg = resolve_thinking_config("balanced")
        assert cfg.max_tool_rounds == settings.AGENT_MAX_TOOL_ROUNDS


class TestDeepModeUnchanged:
    """2026-07-15 #P2: deep 模式行为不变 (跑完整 plan_step + critique + tool rounds)"""

    def test_deep_no_skip(self):
        cfg = resolve_thinking_config("deep")
        assert cfg.mode == "deep"
        assert cfg.skip_plan_step is False
        assert cfg.skip_critique is False


class TestUnknownFallback:
    """Unknown mode / None fallback 到 balanced（不抛错, 避免前端脏数据炸后端）"""

    def test_none_falls_back_to_balanced(self):
        cfg = resolve_thinking_config(None)
        assert cfg.mode == "balanced"

    def test_empty_string_falls_back_to_balanced(self):
        cfg = resolve_thinking_config("")
        assert cfg.mode == "balanced"

    def test_unknown_falls_back_to_balanced(self):
        cfg = resolve_thinking_config("ultrafast")
        assert cfg.mode == "balanced"


class TestThinkingConfigFrozen:
    """frozen dataclass, 不可运行时修改（防 LLM 实时调整配置）"""

    def test_frozen_cannot_modify(self):
        cfg = resolve_thinking_config("fast")
        try:
            cfg.skip_plan_step = False  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except Exception as e:
            assert "FrozenInstanceError" in type(e).__name__ or "frozen" in str(e).lower()


class TestBackwardCompatibility:
    """新增字段向后兼容, 旧代码构造 ThinkingConfig 必须仍能 work"""

    def test_required_fields_complete(self):
        """所有字段必须在 resolve_* 函数里被赋值 (frozen dataclass 强制)"""
        for mode in ("fast", "balanced", "deep"):
            cfg = resolve_thinking_config(mode)
            # 13 字段 (mode + 12 others)
            assert cfg.mode == mode
            assert isinstance(cfg.model, str) and cfg.model
            assert isinstance(cfg.thinking, dict)
            assert isinstance(cfg.max_tokens, int) and cfg.max_tokens > 0
            assert isinstance(cfg.max_tool_tokens, int) and cfg.max_tool_tokens > 0
            assert isinstance(cfg.max_tool_rounds, int) and cfg.max_tool_rounds >= 0
            assert isinstance(cfg.skip_plan_step, bool)
            assert isinstance(cfg.skip_critique, bool)
            assert isinstance(cfg.intent_aware_prompts, bool)
            assert isinstance(cfg.primitive_recognition, bool)
            assert isinstance(cfg.cross_domain_synthesis, bool)
            assert cfg.json_protocol_strength in ("none", "full")
            assert isinstance(cfg.label, str) and cfg.label
            assert isinstance(cfg.cost_factor, (int, float))