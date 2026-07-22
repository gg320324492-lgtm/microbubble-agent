"""Agent 7 5th-wave 教训加固测试 — safe_minio_intake

覆盖:
- SafeIntakeContext env 守卫 (test/ci 强制关闭)
- grayscale 规范化 (负数/超 100/非整数)
- from_env() 自动解析 (production/development/staging/未知值)
- IntakeDecision 不可变 (dataclass frozen)
- 5th-wave 真实场景: grayscale=100 + env=test → 强制 dry-run

跑法 (无 DB 依赖):
    pytest tests/test_safe_minio_intake.py -v
"""
import os
import sys
from pathlib import Path

import pytest

# 让 app/ 可 import (纯函数, 不需要 DB)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.safe_minio_intake import (  # noqa: E402
    IntakeDecision,
    SafeIntakeContext,
    _DEFAULT_MAX_PCT,
    _VALID_ENVS,
)


# ============================================================================
# TestSafeIntakeContextInit — 初始化 / env 白名单
# ============================================================================

class TestSafeIntakeContextInit:
    """SafeIntakeContext(env) 初始化 + env 白名单"""

    def test_default_env_is_test(self):
        """默认 env='test' (最保守)"""
        ctx = SafeIntakeContext()
        assert ctx.env == "test"
        assert ctx.max_intake_pct == 0

    def test_test_env_forces_max_pct_zero(self):
        """test env 强制 max_intake_pct=0 (防测环境污染生产 KB)"""
        ctx = SafeIntakeContext(env="test")
        assert ctx.env == "test"
        assert ctx.max_intake_pct == 0

    def test_ci_env_forces_max_pct_zero(self):
        """ci env 强制 max_intake_pct=0 (CI PR 测试)"""
        ctx = SafeIntakeContext(env="ci")
        assert ctx.env == "ci"
        assert ctx.max_intake_pct == 0

    def test_prod_env_allows_full_pct(self):
        """prod env 默认 max_intake_pct=100 (灰度全开)"""
        ctx = SafeIntakeContext(env="prod")
        assert ctx.env == "prod"
        assert ctx.max_intake_pct == 100

    def test_explicit_max_pct_override(self):
        """可显式覆盖 max_intake_pct (测试 / 特殊场景)"""
        ctx = SafeIntakeContext(env="test", max_intake_pct=50)
        assert ctx.max_intake_pct == 50

    def test_invalid_env_raises_valueerror(self):
        """未知 env → ValueError (防 typo 静默走 prod)"""
        with pytest.raises(ValueError, match="not in"):
            SafeIntakeContext(env="production_typo")

    def test_valid_envs_constant(self):
        """_VALID_ENVS 包含 test/ci/prod"""
        assert "test" in _VALID_ENVS
        assert "ci" in _VALID_ENVS
        assert "prod" in _VALID_ENVS

    def test_default_max_pct_constant(self):
        """_DEFAULT_MAX_PCT 三档正确"""
        assert _DEFAULT_MAX_PCT["test"] == 0
        assert _DEFAULT_MAX_PCT["ci"] == 0
        assert _DEFAULT_MAX_PCT["prod"] == 100

    def test_repr_format(self):
        """__repr__ 包含 env + max_pct"""
        ctx = SafeIntakeContext(env="prod")
        assert "env='prod'" in repr(ctx)
        assert "max_intake_pct=100" in repr(ctx)


# ============================================================================
# TestCheckIntakeAllowed — 核心决策逻辑 (5th-wave 真实场景)
# ============================================================================

class TestCheckIntakeAllowed:
    """check_intake_allowed(grayscale_pct) 返回 IntakeDecision"""

    def test_test_env_with_grayscale_100_still_blocks(self):
        """5th-wave 教训: test env 即使 grayscale=100 也强制关闭"""
        ctx = SafeIntakeContext(env="test")
        decision = ctx.check_intake_allowed(grayscale_pct=100)

        assert decision.allowed is False
        assert decision.effective_pct == 0
        assert decision.env == "test"
        assert "强制关闭" in decision.reason

    def test_ci_env_with_grayscale_50_still_blocks(self):
        """CI env 即使 grayscale=50 也强制关闭"""
        ctx = SafeIntakeContext(env="ci")
        decision = ctx.check_intake_allowed(grayscale_pct=50)

        assert decision.allowed is False
        assert decision.effective_pct == 0

    def test_prod_env_with_grayscale_50_allowed(self):
        """prod env + grayscale=50 允许"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=50)

        assert decision.allowed is True
        assert decision.effective_pct == 50
        assert decision.env == "prod"

    def test_prod_env_with_grayscale_100_allowed(self):
        """prod env + grayscale=100 (全量) 允许"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=100)

        assert decision.allowed is True
        assert decision.effective_pct == 100

    def test_prod_env_with_grayscale_0_allowed(self):
        """prod env + grayscale=0 (完全关闭) 仍 allowed (透传, 不污染)"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=0)

        assert decision.allowed is True
        assert decision.effective_pct == 0

    def test_prod_env_custom_max_pct_caps(self):
        """prod env 显式 max_pct=30, grayscale=50 被拒绝"""
        ctx = SafeIntakeContext(env="prod", max_intake_pct=30)
        decision = ctx.check_intake_allowed(grayscale_pct=50)

        assert decision.allowed is False
        assert decision.effective_pct == 30  # 降级到 max
        assert "超过" in decision.reason


# ============================================================================
# TestGrayscaleNormalization — 灰度值规范化 (容错)
# ============================================================================

class TestGrayscaleNormalization:
    """grayscale_pct 输入容错 (admin 误传防御)"""

    def test_negative_normalized_to_zero(self):
        """负数 → 0"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=-5)

        assert decision.effective_pct == 0
        assert decision.allowed is True  # 0 透传 prod

    def test_over_100_normalized_to_100(self):
        """>100 → 100"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=150)

        assert decision.effective_pct == 100

    def test_string_normalized_to_zero(self):
        """字符串非整数 → 0 (防 admin 误传 'abc')"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct="abc")  # type: ignore[arg-type]

        assert decision.effective_pct == 0

    def test_numeric_string_accepted(self):
        """数字字符串 (e.g. '50') → 解析为 50"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct="50")  # type: ignore[arg-type]

        assert decision.effective_pct == 50
        assert decision.allowed is True

    def test_none_normalized_to_zero(self):
        """None → 0"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=None)  # type: ignore[arg-type]

        assert decision.effective_pct == 0


# ============================================================================
# TestFromEnv — 自动 env 解析
# ============================================================================

class TestFromEnv:
    """SafeIntakeContext.from_env() 自动解析 MICROBUBBLE_ENV / APP_ENV"""

    def test_production_aliases(self):
        """production/prod/live → env='prod'"""
        for alias in ("production", "PROD", "Production", "live"):
            os.environ["MICROBUBBLE_ENV"] = alias
            ctx = SafeIntakeContext.from_env()
            assert ctx.env == "prod", f"alias={alias!r} failed"
            assert ctx.max_intake_pct == 100

    def test_test_aliases(self):
        """test/testing/pytest → env='test'"""
        for alias in ("test", "TEST", "testing", "pytest"):
            os.environ["MICROBUBBLE_ENV"] = alias
            ctx = SafeIntakeContext.from_env()
            assert ctx.env == "test", f"alias={alias!r} failed"
            assert ctx.max_intake_pct == 0

    def test_unknown_env_falls_back_to_test(self):
        """未知 env (development/staging) → 保守按 test 处理"""
        os.environ["MICROBUBBLE_ENV"] = "development"
        ctx = SafeIntakeContext.from_env()
        assert ctx.env == "test"
        assert ctx.max_intake_pct == 0

    def test_no_env_var_falls_back_to_test(self):
        """无 env var → 保守按 test 处理"""
        os.environ.pop("MICROBUBBLE_ENV", None)
        os.environ.pop("APP_ENV", None)
        ctx = SafeIntakeContext.from_env()
        assert ctx.env == "test"
        assert ctx.max_intake_pct == 0

    def test_app_env_fallback(self):
        """APP_ENV 作为 fallback"""
        os.environ.pop("MICROBUBBLE_ENV", None)
        os.environ["APP_ENV"] = "production"
        ctx = SafeIntakeContext.from_env()
        assert ctx.env == "prod"
        # 清理
        os.environ.pop("APP_ENV", None)


# ============================================================================
# TestIntakeDecision — 不可变 dataclass
# ============================================================================

class TestIntakeDecision:
    """IntakeDecision frozen 不可变 + 字段正确"""

    def test_decision_frozen(self):
        """frozen=True 阻止字段赋值"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=50)

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            decision.allowed = False  # type: ignore[misc]

    def test_decision_fields_complete(self):
        """字段完整 (allowed/reason/effective_pct/env)"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=50)

        assert hasattr(decision, "allowed")
        assert hasattr(decision, "reason")
        assert hasattr(decision, "effective_pct")
        assert hasattr(decision, "env")

    def test_decision_is_hashable(self):
        """frozen dataclass 应可 hash"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=50)

        # 不可变 + 可 hash (frozen 默认)
        assert hash(decision) is not None


# ============================================================================
# TestFifthWaveRegression — 5th-wave 真实场景回归
# ============================================================================

class TestFifthWaveRegression:
    """复现 W62 D2 第五波 runner 集成测试 grayscale=100 + AUTO_KB_INTAKE=true 污染"""

    def test_fifth_wave_scenario_test_env_blocks_intake(self):
        """第五波 runner 集成: test env 即使 grayscale=100 也强制 dry-run

        场景: save_to_kb.py 集成 grayscale=100 跑测试 → 污染 KB 表
        修法: SafeIntakeContext(env='test') → 强制关闭
        """
        # 模拟 save_to_kb.py 调用
        ctx = SafeIntakeContext(env="test")
        decision = ctx.check_intake_allowed(grayscale_pct=100)

        # 即使 grayscale=100, test env 必须拒绝
        assert decision.allowed is False
        assert decision.effective_pct == 0
        # 决策 reason 必须含可读信息 (便于 audit log)
        assert "env=test" in decision.reason or "test" in decision.reason
        assert "强制" in decision.reason or "max_intake_pct=0" in decision.reason

    def test_prod_env_with_5th_wave_config_allows(self):
        """生产环境 grayscale=100 + env=prod 允许 (不会误阻)"""
        ctx = SafeIntakeContext(env="prod")
        decision = ctx.check_intake_allowed(grayscale_pct=100)

        assert decision.allowed is True
        assert decision.effective_pct == 100

    def test_save_to_kb_integration_pattern(self):
        """save_to_kb.py 集成模式: 决策返回 false → 跳过 intake

        集成代码示例:
            ctx = SafeIntakeContext.from_env()  # 自动从 MICROBUBBLE_ENV 解析
            decision = ctx.check_intake_allowed(grayscale_pct=100)
            if not decision.allowed:
                logger.info(f"intake skipped: {decision.reason}")
                return  # dry-run, 不入库
        """
        # 模拟 CI 环境变量 (from_env 将 "ci" 归类为 test, 同样强制关闭)
        os.environ["MICROBUBBLE_ENV"] = "ci"
        ctx = SafeIntakeContext.from_env()
        decision = ctx.check_intake_allowed(grayscale_pct=100)

        # ci 归类为 test (保守, 都强制 max_intake_pct=0)
        assert ctx.env in ("ci", "test")
        assert ctx.max_intake_pct == 0
        assert decision.allowed is False
        assert "强制关闭" in decision.reason or "强制" in decision.reason

        # 清理
        os.environ.pop("MICROBUBBLE_ENV", None)