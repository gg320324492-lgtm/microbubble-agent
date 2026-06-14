"""自评模块 — Agentic Loop 阶段 4（方案 C Stage 1）

设计要点：
- 用 Sonnet 调用（accuracy critical，错评分误伤用户体验）
- 评分 < AGENT_REFLECTION_THRESHOLD（默认 7）触发 retry
- Reflection 失败时不阻塞主流程：吞掉异常，返回 score=0 + addresses_question=True
  （Plan agent 5c：仍 yield critique 事件让前端知道）
- 低分 fallback 出口时 UI 显示警告（前端 toolTrace 折叠区 ⚠️ 徽章）
- 2026-06-14 收官：加 grounded_in_tools 评分维度 + 喂 tool_results 给 critic

跨进程安全（铁律 1）：
- llm 从 ctx.llm 拿，None 时调用方临时创建
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agent.intent_classifier import IntentResult
from app.agent.protocol import RichBlock, StreamEvent
from app.agent.tool_registry import ToolContext
from app.config import settings
from app.core.llm import LLMClient

logger = logging.getLogger("microbubble.agent.critic")


class CritiqueResult(BaseModel):
    """自评结果"""
    score: int = Field(default=0, ge=0, le=10)  # 0=未评分（Reflection 失败），1-10=实际评分
    addresses_question: bool = True
    has_synthesis: bool = False  # 是否做了筛选/推理（不是单纯展示数据）
    has_citations: bool = False  # 是否引用了具体数据
    grounded_in_tools: int = Field(default=10, ge=0, le=10)  # 2026-06-14 收官：防 hallucination
    missing: list[str] = Field(default_factory=list)  # 缺失的方面
    suggestion: str = ""  # 改进建议（注入下一轮 system prompt）


_CRITIQUE_PROMPT = """你是响应质量评审员。基于以下 4 维度给 1-10 分。

## 评分维度
1. **addresses_question (1-10)**: 是否直接回答了用户的问题？
   - 1-3：答非所问 / 跑题
   - 4-6：部分相关但没正面回答
   - 7-10：直接、明确、完整地回答

2. **has_synthesis (boolean)**: 是否做了筛选/推理/推荐（vs 单纯展示数据）？
   - true：做了综合分析、推荐、建议
   - false：单纯罗列数据

3. **has_citations (boolean)**: 是否引用了具体数据/事实/来源？
   - true：引用了具体工具返回的字段、ID、标题等
   - false：泛泛而谈

4. **grounded_in_tools (1-10)**: 回答中出现的具体信息（姓名/研究方向/技能/项目名/会议标题）是否严格来自本轮工具调用结果？
   - 1-3：含编造的人名/字段/标题（hallucination），或使用"暂无详细信息"/"待补充"等占位符
   - 4-6：部分信息无工具支撑，混入了凭印象/归纳的内容
   - 7-10：所有具体信息都可追溯到 tool_results 中的字段

## 输入
用户问题：{question}
用户意图：{intent_category} ({intent_reasoning})
助手响应：{response_text}
调用的工具：{tool_calls}
工具实际返回（用于 grounding 校验）：{tool_results}
生成的富文本块数：{rich_block_count}

## 输出（严格 JSON）
{{
  "score": 1-10,
  "addresses_question": bool,
  "has_synthesis": bool,
  "has_citations": bool,
  "grounded_in_tools": 1-10,
  "missing": ["缺失的方面 1", "缺失的方面 2"],
  "suggestion": "具体改进建议（注入到下一轮 system prompt）"
}}
只输出 JSON，不解释。"""


async def critique_response(
    user_question: str,
    intent: IntentResult,
    response_text: str,
    rich_blocks: list[RichBlock],
    tool_calls: list[dict],
    ctx: ToolContext,
) -> CritiqueResult:
    """对 LLM 综合响应做自评

    行为：
    - 成功：返回正常 CritiqueResult
    - 失败：返回 score=0 + addresses_question=True（Plan agent 5c：吞掉异常，不阻塞主流程）
    - 不直接 yield SSE 事件，由调用方决定
    """
    if not settings.AGENT_REFLECTION_ENABLED:
        # 关闭 Reflection 时直接返回「通过」
        return CritiqueResult(
            score=10,
            addresses_question=True,
            has_synthesis=True,
            has_citations=True,
            missing=[],
            suggestion="",
        )

    # 1. 准备 prompt
    tool_call_summary = "\n".join(
        f"- {tc.get('name', '?')}({list(tc.get('input', {}).keys())})"
        for tc in tool_calls[:10]
    ) or "（无）"
    # 2026-06-14 收官：把 tool_calls 的 output 字段也喂给 critic（截断到 6KB），
    # 让它能 cross-check 回答里出现的姓名/字段是否在工具返回里
    tool_results_text = "\n".join(
        f"[{tc.get('name', '?')}] {json.dumps(tc.get('output', {}), ensure_ascii=False, default=str)[:1500]}"
        for tc in tool_calls[:5] if tc.get("output")
    ) or "（无工具返回）"
    prompt = _CRITIQUE_PROMPT.format(
        question=user_question,
        intent_category=intent.category.value,
        intent_reasoning=intent.reasoning,
        response_text=response_text[:3000],  # 截断避免 token 爆炸
        tool_calls=tool_call_summary,
        tool_results=tool_results_text[:6000],
        rich_block_count=len(rich_blocks),
    )

    # 2. LLM 调
    llm = ctx.llm or LLMClient()
    try:
        resp = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=settings.AGENT_REFLECTION_MODEL,
            # 2026-06-14 Stage 5 收尾：mimo 等思考型模型显式禁用 thinking
            system="你是质量评审员。直接输出纯 JSON。",
            max_tokens=500,
            temperature=0.0,
            thinking={"type": "disabled"},
        )
        # 提取文本
        text = ""
        for block in resp.content:
            if hasattr(block, "text") and block.text:
                text = block.text.strip()
                break
        if not text:
            raise ValueError("LLM returned empty text")

        result_dict = _parse_json_response(text)
        result = CritiqueResult(
            score=max(0, min(10, int(result_dict.get("score", 0)))),
            addresses_question=bool(result_dict.get("addresses_question", True)),
            has_synthesis=bool(result_dict.get("has_synthesis", False)),
            has_citations=bool(result_dict.get("has_citations", False)),
            grounded_in_tools=max(0, min(10, int(result_dict.get("grounded_in_tools", 10)))),
            missing=result_dict.get("missing", []),
            suggestion=result_dict.get("suggestion", ""),
        )
        logger.info(
            f"critique: score={result.score}/10 grounded={result.grounded_in_tools}/10 "
            f"synthesis={result.has_synthesis} citations={result.has_citations} "
            f"intent={intent.category.value}"
        )
        return result
    except Exception as e:
        # Plan agent 5c：Reflection 失败不阻塞主流程，吞掉异常
        logger.warning(f"critique failed: {type(e).__name__}: {e}")
        return CritiqueResult(
            score=0,
            addresses_question=True,  # 视为通过
            has_synthesis=True,
            has_citations=False,
            missing=[],
            suggestion=f"critique failed: {e}",
        )


def critique_to_sse_event(result: CritiqueResult) -> StreamEvent:
    """CritiqueResult → StreamEvent（前端展示自评分 + 警告）

    2026-06-14 收官：label 字段保留（前端 toggle 开启时显示），off 时由前端 v-if 隐藏
    """
    return StreamEvent(
        type="critique",
        critique=result.model_dump(),
        label=(
            f"📊 自评 {result.score}/10"
            + (f" ⚠️ 建议：{result.suggestion[:50]}" if result.score < settings.AGENT_REFLECTION_THRESHOLD else "")
        ),
    )


def should_retry(result: CritiqueResult) -> bool:
    """判断是否需要重试"""
    return (
        result.score > 0  # score=0 表示 Reflection 失败，不重试
        and result.score < settings.AGENT_REFLECTION_THRESHOLD
    )


def inject_suggestion_to_system(system: str, suggestion: str) -> str:
    """把建议注入到下一轮的 system prompt（用于 retry）"""
    if not suggestion:
        return system
    return (
        f"{system}\n\n"
        f"## ⚠️ 上轮自评建议（请改进）\n{suggestion}\n"
    )


# ============================================================================
# 辅助函数
# ============================================================================


def _parse_json_response(text: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON 文本"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
        else:
            text = "\n".join(lines[1:])
        text = text.strip()
    return json.loads(text)
