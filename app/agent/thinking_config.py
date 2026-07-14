"""2026-07-13 #P1: 三态推理模式 (fast / balanced / deep) 配置。

设计目标：
- 把 toggle 行为从「半成品 UI 包装」升级为「真区分」
- 每档 mode 在 4 个维度同时变化：model / thinking / max_tokens / Self-RAG
- balanced = 当前默认行为逐字段对齐，作为迁移期兜底
- fast / deep 是「真不同」，qa-bench 100 题可量化区分

调用方：
- chat_engine.synthesize_stream 入口根据 thinking_mode 参数 → resolve_thinking_config() → 注入 ToolContext
- agentic_loop 5 处真分支 (L1019 self_rag gate / L1050 Phase 1 tool loop / L1334 synthesis model / L1422 synthesis stream / done event) 读 ctx.thinking_config
- intent_aware_prompts / primitive_recognition / cross_domain_synthesis 三段 prompt gate 从 settings 切换到 ctx.thinking_config

复用：
- _AnthropicMsgDict wrapper (app/core/tool_call_converter.py P0-#1.5) 自动处理 reasoning_content → thinking block 转换，无需改动
- LLMClient.complete/stream/stream_raw 已支持 per-call model/thinking/max_tokens keyword-only 参数，无需改动
"""

from dataclasses import dataclass
from typing import Literal, Optional

from app.config import settings


# ============================================================================
# ThinkingConfig frozen dataclass
# ============================================================================


@dataclass(frozen=True)
class ThinkingConfig:
    """三态推理模式配置 — frozen 保证不运行时修改。

    字段说明：
    - mode: 'fast' | 'balanced' | 'deep'
    - model: Ollama model tag (qwen3:8b / deepseek-r1-distill-qwen:7b)
    - thinking: Anthropic SDK thinking 字段 (disabled / enabled+budget_tokens); ollama backend
      在 deep 模式实际走 reasoning_content 通道，此字段仅作类型合规占位
    - max_tokens: synthesis 阶段 LLMClient.stream 的 max_tokens
    - max_tool_tokens: Phase 1 tool loop 的 max_tokens
    - max_tool_rounds: Phase 1 agentic_loop 最大轮数（覆盖 settings.AGENT_MAX_TOOL_ROUNDS）；
      fast 模式设为 0 直接跳过 tool loop，节省 1-7.5s
    - skip_plan_step: 是否跳过 Phase 0 强制 plan_step (Haiku suggested_tools → agentic_loop
      主动 dispatch); fast=True 跳过让用户感知"快速"语义
    - skip_critique: 是否跳过 Phase 3 critique + Phase 4 retry; fast=True 跳过节省 0.5-3s
    - self_rag_enabled: 是否跑 Phase 0.5 Self-RAG judge
    - self_rag_max_reretrieve: Self-RAG judge parse-fail 时最多重检索次数 (0/1/2)
    - intent_aware_prompts: 是否按 intent 分类追加「闲聊/数据/深度」prompt section
    - primitive_recognition: 是否在深度场景追加 5 大原意识别 section
    - cross_domain_synthesis: 是否在 explain_concept 场景追加跨域综合规则
    - json_protocol_strength: 'none' (跳过 rich_block schema) | 'full' (正常 JSON 协议)
    - label: UI 展示名 (快速/平衡/深度)
    - cost_factor: 相对 haiku 的成本倍数，给未来 rate limit / 配额统计用
    """

    mode: Literal["fast", "balanced", "deep"]
    model: str
    thinking: dict
    max_tokens: int
    max_tool_tokens: int
    max_tool_rounds: int
    skip_plan_step: bool
    skip_critique: bool
    self_rag_enabled: bool
    self_rag_max_reretrieve: int
    intent_aware_prompts: bool
    primitive_recognition: bool
    cross_domain_synthesis: bool
    json_protocol_strength: Literal["none", "full"]
    label: str
    cost_factor: float


# ============================================================================
# resolve_thinking_config: mode 字符串 → ThinkingConfig
# ============================================================================


def resolve_thinking_config(mode: Optional[str]) -> ThinkingConfig:
    """根据 mode 字符串解析 ThinkingConfig。

    Args:
        mode: 'fast' | 'balanced' | 'deep' | None (None fallback 到 settings.AGENT_THINKING_MODE_DEFAULT)

    Returns:
        ThinkingConfig: frozen dataclass，调用方不可修改

    Unknown mode fallback 到 balanced（不抛错，避免前端脏数据炸后端）。
    """
    if mode is None or mode == "":
        mode = settings.AGENT_THINKING_MODE_DEFAULT

    if mode == "fast":
        return ThinkingConfig(
            mode="fast",
            model=settings.AGENT_THINKING_MODE_FAST_MODEL,
            thinking={"type": "disabled"},
            max_tokens=settings.AGENT_THINKING_MODE_FAST_MAX_TOKENS,
            max_tool_tokens=settings.AGENT_THINKING_MODE_FAST_MAX_TOOL_TOKENS,
            # 2026-07-15 #P2: fast mode 真·快速——跳过 plan_step / critique / Phase 1 tool loop
            # 用户选 fast = 明确要速度不要 quality control
            # max_tool_rounds=0 直接进 synthesis, 跳过整段 agentic_loop
            max_tool_rounds=0,
            skip_plan_step=True,
            skip_critique=True,
            self_rag_enabled=False,
            self_rag_max_reretrieve=0,
            intent_aware_prompts=False,
            primitive_recognition=False,
            cross_domain_synthesis=False,
            json_protocol_strength="none",
            label="快速",
            cost_factor=1.0,
        )

    if mode == "deep":
        return ThinkingConfig(
            mode="deep",
            model=settings.AGENT_THINKING_MODE_DEEP_MODEL,
            thinking={"type": "enabled", "budget_tokens": 8000},
            max_tokens=settings.AGENT_THINKING_MODE_DEEP_MAX_TOKENS,
            max_tool_tokens=settings.AGENT_THINKING_MODE_DEEP_MAX_TOOL_TOKENS,
            # 2026-07-15 #P2: deep 模式跑完整 plan_step + critique + 完整 tool rounds
            max_tool_rounds=settings.AGENT_MAX_TOOL_ROUNDS,
            skip_plan_step=False,
            skip_critique=False,
            self_rag_enabled=True,
            self_rag_max_reretrieve=settings.AGENT_THINKING_MODE_DEEP_MAX_RERETRIEVE,
            intent_aware_prompts=True,
            primitive_recognition=True,
            cross_domain_synthesis=True,
            json_protocol_strength="full",
            label="深度",
            cost_factor=3.0,  # 7B 本地推理相对 haiku 估 3x (实际取决于 GPU 利用率)
        )

    # balanced (default) — 与当前默认行为逐字段对齐，零行为差异
    return ThinkingConfig(
        mode="balanced",
        model=settings.AGENT_THINKING_MODE_BALANCED_MODEL,
        thinking={"type": "disabled"},
        max_tokens=settings.AGENT_THINKING_MODE_BALANCED_MAX_TOKENS,
        max_tool_tokens=500,  # 与 agentic_loop 现有硬编码 500 一致
        # 2026-07-15 #P2: balanced 默认全跑, max_tool_rounds 走 settings (5)
        max_tool_rounds=settings.AGENT_MAX_TOOL_ROUNDS,
        skip_plan_step=False,
        skip_critique=False,
        self_rag_enabled=settings.AGENT_SELF_RAG_ENABLED,
        self_rag_max_reretrieve=settings.AGENT_SELF_RAG_MAX_RERETRIEVE,
        intent_aware_prompts=settings.AGENT_INTENT_AWARE_PROMPTS,
        primitive_recognition=settings.AGENT_PRIMITIVE_RECOGNITION,
        cross_domain_synthesis=settings.AGENT_CROSS_DOMAIN_SYNTHESIS,
        json_protocol_strength="full",
        label="平衡",
        cost_factor=3.0,
    )