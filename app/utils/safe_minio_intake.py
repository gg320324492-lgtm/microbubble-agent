"""app/utils/safe_minio_intake.py — 安全 KB intake 上下文

W62 D2 灰度机制教训 (2026-07-23):
- 第五波 runner 集成测试 grayscale=100 + AUTO_KB_INTAKE=true 污染 KB 表
- 缺一个"强制关闭 intake"开关, 测环境就会污染生产数据
- 修法: SafeIntakeContext 强制 grayscale < 100 在 test env 直接拒绝

核心设计:
1. SafeIntakeContext(env: str) — env 决定 max_intake_pct (test=0, prod=100)
2. check_intake_allowed() — 强制 grayscale 阈值 + env 守卫
3. save_to_kb.py 的 run_intake() 集成此 helper, 测环境 dry-run 永远不写库

5 新铁律:
① intake env 必须显式传 (test/prod), 不要 auto-detect 环境变量 (误判风险)
② test env 默认 max_intake_pct=0, 即使 grayscale=100 也被强制降级为 0
③ check_intake_allowed 必须返回 tuple[bool, str] (允许 + 原因), 方便日志
④ SafeIntakeContext 不依赖 settings (避免循环 import + 简化 mock)
⑤ grayscale 解析容错: 负数→0, >100→100, 非整数→0 (防 admin 误传)

部署必做:
- 测环境 (pytest CI / docker test profile) 必须传 env="test"
- 生产 (docker compose 启动 app) 必须传 env="prod"
- save_to_kb.py 集成: grayscale > max_intake_pct → return False + log warning
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# 允许的 env 值白名单 (防 typo 静默走 prod)
_VALID_ENVS = frozenset({"test", "prod", "ci"})

# 默认上限 (按 env)
_DEFAULT_MAX_PCT = {
    "test": 0,     # 测试环境永远关闭 intake (避免污染 KB)
    "ci": 0,       # CI 同 test (避免 PR 跑测试污染 staging)
    "prod": 100,   # 生产全开 (灰度 100%)
}


@dataclass(frozen=True)
class IntakeDecision:
    """intake 决策结果 (不可变, 方便 JSON 序列化 + 测试断言)"""
    allowed: bool
    reason: str           # 决策原因 (中文 OK, 用于日志)
    effective_pct: int    # 实际生效的 grayscale (可能被降级)
    env: str              # 解析后的 env


class SafeIntakeContext:
    """KB intake 安全上下文 — 强制 env 守卫 + grayscale 阈值检查

    用法:
        ctx = SafeIntakeContext(env="test")
        decision = ctx.check_intake_allowed(grayscale_pct=100)
        if decision.allowed:
            # 真正调用 save_to_kb.run_intake()
        else:
            logger.info("intake skipped: %s", decision.reason)

    env 解析:
        - "test" → max_intake_pct=0 (测环境强制关闭)
        - "ci"   → max_intake_pct=0 (CI 强制关闭)
        - "prod" → max_intake_pct=100 (生产全开)

    grayscale_pct 解析容错:
        - 负数 → 0
        - >100 → 100
        - 非整数 → 0 (防 admin 误传字符串)
    """

    def __init__(self, env: str = "test", max_intake_pct: int | None = None):
        """初始化

        Args:
            env: "test" / "ci" / "prod", 默认 test (最保守)
            max_intake_pct: 可选显式覆盖默认上限 (测试用)
        """
        if env not in _VALID_ENVS:
            raise ValueError(
                f"env={env!r} not in {_VALID_ENVS}. "
                f"用 SafeIntakeContext.from_env() 自动解析 (含 'development'/'staging')"
            )
        self.env = env
        self.max_intake_pct = (
            max_intake_pct if max_intake_pct is not None
            else _DEFAULT_MAX_PCT[env]
        )

    @classmethod
    def from_env(cls, env_var: str = "MICROBUBBLE_ENV") -> "SafeIntakeContext":
        """从环境变量自动解析 env

        优先显式 env, 然后 MICROBUBBLE_ENV, 然后 APP_ENV, 最后 fallback "test"
        (最保守, 永远不会污染生产)
        """
        env = (
            os.getenv(env_var)
            or os.getenv("APP_ENV")
            or "test"  # 默认保守: 关闭 intake
        )
        # 规范化
        env_lower = env.lower().strip()
        if env_lower in ("production", "prod", "live"):
            env = "prod"
        elif env_lower in ("ci", "test", "testing", "pytest"):
            env = "test"
        elif env_lower in ("ci",):
            env = "ci"
        else:
            # 未知 env (development / staging) → 保守按 test 处理
            logger.warning(
                "未知 env=%r, 按 test 处理 (max_intake_pct=0)", env
            )
            env = "test"
        return cls(env=env)

    def check_intake_allowed(self, grayscale_pct: int) -> IntakeDecision:
        """检查 intake 是否允许执行

        强制规则:
        1. grayscale_pct 规范化 (负数→0, >100→100, 非整数→0)
        2. test/ci env: 即使 grayscale=100 强制降级为 0
        3. prod env: 透传 grayscale_pct (但仍规范化)

        Args:
            grayscale_pct: 0-100 整数, 来自 save_to_kb 的 --grayscale / KB_INTAKE_GRAYSCALE

        Returns:
            IntakeDecision(allowed, reason, effective_pct, env)
        """
        # 规范化 grayscale
        try:
            pct = int(grayscale_pct)
        except (TypeError, ValueError):
            logger.warning("grayscale_pct=%r 非整数, 强制 0", grayscale_pct)
            pct = 0
        if pct < 0:
            pct = 0
        elif pct > 100:
            pct = 100

        # env 守卫 (test/ci 强制关闭)
        if self.max_intake_pct == 0:
            return IntakeDecision(
                allowed=False,
                reason=(
                    f"env={self.env} 强制关闭 intake "
                    f"(max_intake_pct=0, requested grayscale={pct}%)"
                ),
                effective_pct=0,
                env=self.env,
            )

        # prod env: 阈值检查
        if pct > self.max_intake_pct:
            return IntakeDecision(
                allowed=False,
                reason=(
                    f"grayscale={pct}% 超过 env={self.env} "
                    f"max_intake_pct={self.max_intake_pct}%"
                ),
                effective_pct=self.max_intake_pct,
                env=self.env,
            )

        return IntakeDecision(
            allowed=True,
            reason=f"env={self.env} grayscale={pct}% (≤ max={self.max_intake_pct}%)",
            effective_pct=pct,
            env=self.env,
        )

    def __repr__(self) -> str:
        return (
            f"SafeIntakeContext(env={self.env!r}, "
            f"max_intake_pct={self.max_intake_pct})"
        )