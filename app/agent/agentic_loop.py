"""Agentic Loop — 真正的多轮工具循环 + 流式综合 + Reflection（方案 C Stage 1）

设计要点：
- 5 阶段：tool loop → synthesis stream → critique → retry → done
- 跨进程安全（铁律 1）：所有外部 IO 通过 ctx 注入，模块顶部不创建 client
- 悬空 tool_use 防御（铁律 4）：max_rounds 触发或 CancelledError 时 sanitize
- SSE delta 语义铁律：每事件类型 yield 时都标注 [increment]/[snapshot]

事件流顺序：
1. [snapshot] tool_use / tool_result / tool_compressed (循环 N 轮)
2. [snapshot] synthesis_start
3. [increment] text_delta (流式输出)
4. [snapshot] rich_block
5. [snapshot] critique (含 score)
6. [snapshot] retry (如 score < 阈值)
7. [increment] text_delta (重试输出，前端必须先清空 content)
8. [snapshot] done
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Optional

from app.agent.critic import (
    CritiqueResult,
    critique_response,
    critique_to_sse_event,
    inject_suggestion_to_system,
    should_retry,
)
from app.agent.intent_classifier import IntentResult
from app.agent.protocol import RichBlock, StreamEvent
from app.agent.result_compressor import (
    CompressionResult,
    compression_to_sse_event,
    compress_tool_result,
    inject_compressed_to_messages,
)
from app.agent.tool_registry import (
    ToolContext,
    dispatch_tool,
    get_all_tool_schemas,
)
from app.config import settings
from app.core.llm import LLMClient

logger = logging.getLogger("microbubble.agent.agentic_loop")


def _sanitize_pending_tool_uses(messages: list[dict], reason: str = "max_rounds_reached") -> int:
    """扫描 messages，给悬空的 tool_use 追加哨兵 tool_result

    返回被 sanitize 的 tool_use 数量
    必须在调 LLM 前调（否则下次 Anthropic API 报 400）
    """
    # 收集所有已出现的 tool_use id
    pending_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, str):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                pending_ids.add(block.get("id", ""))

    # 收集所有已出现的 tool_result id
    closed_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if isinstance(content, str):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                closed_ids.add(block.get("tool_use_id", ""))

    # 找到悬空的 id
    dangling = pending_ids - closed_ids
    if not dangling:
        return 0

    # 追加哨兵 tool_result 到 messages
    sentinel_results = [
        {
            "type": "tool_result",
            "tool_use_id": tu_id,
            "content": f"[strange close: {reason}]",
        }
        for tu_id in dangling
    ]
    messages.append({"role": "user", "content": sentinel_results})
    logger.warning(f"sanitize_pending_tool_uses: {len(dangling)} dangling (reason={reason})")
    return len(dangling)


def _extract_tool_uses(response) -> list[dict]:
    """从 Anthropic Message 响应中提取 tool_use 列表"""
    tool_uses = []
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            tool_uses.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return tool_uses


def _extract_rich_block(tool_name: str, result: dict) -> Optional[RichBlock]:
    """从工具结果中提取 RichBlock（与 chat_engine._extract_rich_block 同源逻辑）"""
    from app.agent.chat_engine import _extract_rich_block as _orig_extract
    return _orig_extract(tool_name, result)


class AgenticLoop:
    """真正的多轮工具循环 + 流式综合 + Reflection"""

    def __init__(self):
        pass  # 全部通过 ctx 注入（铁律 1）

    async def run(
        self,
        messages: list[dict],
        system: str,
        intent: IntentResult,
        ctx: ToolContext,
        max_rounds: Optional[int] = None,
    ) -> AsyncIterator[StreamEvent]:
        """主入口 — 5 阶段编排

        Yields StreamEvent:
        - tool_use / tool_result / tool_compressed (循环 N 轮)
        - synthesis_start
        - text_delta (流式)
        - rich_block
        - critique
        - retry (条件性)
        - text_delta (重试流式)
        - done
        """
        if max_rounds is None:
            max_rounds = settings.AGENT_MAX_TOOL_ROUNDS

        llm = ctx.llm or LLMClient()
        accumulated_text = ""
        rich_blocks: list[RichBlock] = []
        tool_calls: list[dict] = []
        t0 = time.monotonic()

        try:
            # ===== Phase 1: 工具循环 =====
            for round_idx in range(max_rounds):
                try:
                    response = await llm.complete(
                        messages=messages,
                        system=system,
                        tools=get_all_tool_schemas(),
                        max_tokens=500,
                        temperature=0.3,
                    )
                except Exception as e:
                    logger.error(f"LLM tool decision round {round_idx} failed: {e}", exc_info=True)
                    break

                # 提取 tool_use
                tool_uses = _extract_tool_uses(response)
                if not tool_uses:
                    # LLM 决定不调工具 → 进入 synthesis
                    break

                # 对每个 tool_use: dispatch + 压缩 + 注入
                round_results: list[dict] = []
                for tu in tool_uses:
                    # [snapshot] tool_use
                    yield StreamEvent(
                        type="tool_use",
                        tool_name=tu["name"],
                        tool_input=tu["input"],
                        tool_use_id=tu["id"],
                    )

                    # 调度
                    try:
                        result = await dispatch_tool(tu["name"], tu["input"], ctx)
                    except Exception as e:
                        logger.error(f"dispatch_tool {tu['name']} failed: {e}", exc_info=True)
                        result = {
                            "status": "error",
                            "code": "TOOL_EXECUTION_ERROR",
                            "message": str(e),
                        }

                    # [snapshot] tool_result
                    yield StreamEvent(
                        type="tool_result",
                        tool_name=tu["name"],
                        tool_use_id=tu["id"],
                        tool_output=result if isinstance(result, dict) else {"result": str(result)},
                    )
                    tool_calls.append({
                        "name": tu["name"],
                        "input": tu["input"],
                        "output": result,
                    })

                    # Rich Block 检测
                    rb = _extract_rich_block(tu["name"], result)
                    if rb:
                        rich_blocks.append(rb)
                        # [snapshot] rich_block
                        yield StreamEvent(type="rich_block", block=rb)

                    # 压缩（如启用 + 触发条件满足）
                    compression: Optional[CompressionResult] = None
                    if settings.AGENT_COMPRESSION_ENABLED:
                        try:
                            compression = await compress_tool_result(
                                user_question=_last_user_text(messages),
                                intent=intent,
                                tool_name=tu["name"],
                                raw_result=result if isinstance(result, dict) else {},
                                ctx=ctx,
                            )
                        except Exception as e:
                            logger.warning(f"compress_tool_result failed: {e}")

                    if compression:
                        # [snapshot] tool_compressed
                        yield compression_to_sse_event(tu["name"], tu["id"], compression)
                        # 把压缩信息注入 messages
                        inject_compressed_to_messages(messages, tu["name"], tu["id"], compression)

                    round_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })

                # 把本轮 tool_use + tool_result 灌回 messages
                messages.append({
                    "role": "assistant",
                    "content": [_block_dump(b) for b in response.content],
                })
                messages.append({"role": "user", "content": round_results})

            # ===== Phase 1.5: 悬空 tool_use 防御 =====
            _sanitize_pending_tool_uses(messages, reason="max_rounds_reached")

            # ===== Phase 2: Synthesis（流式综合输出） =====
            # [snapshot] synthesis_start
            yield StreamEvent(type="synthesis_start", label="✨ 综合分析中...")

            synthesis_text = ""
            synthesis_blocks: list[RichBlock] = []
            async for evt in self._synthesize_stream(
                messages=messages,
                system=system,
                llm=llm,
            ):
                if evt.type == "text_delta":
                    synthesis_text += evt.delta or ""
                elif evt.type == "rich_block" and evt.block:
                    synthesis_blocks.append(evt.block)
                    rich_blocks.append(evt.block)
                yield evt

            accumulated_text = synthesis_text

            # ===== Phase 3: Critique =====
            critique: CritiqueResult = await critique_response(
                user_question=_last_user_text(messages),
                intent=intent,
                response_text=accumulated_text,
                rich_blocks=rich_blocks,
                tool_calls=tool_calls,
                ctx=ctx,
            )
            # [snapshot] critique
            yield critique_to_sse_event(critique)

            # ===== Phase 4: Retry（如需） =====
            retry_count = 0
            while (
                should_retry(critique)
                and retry_count < settings.AGENT_MAX_REFLECTION_RETRIES
            ):
                retry_count += 1
                # [snapshot] retry
                yield StreamEvent(
                    type="retry",
                    retry_reason=critique.suggestion or f"score {critique.score} < {settings.AGENT_REFLECTION_THRESHOLD}",
                    retry_count=retry_count,
                )
                # 注入建议到 system
                new_system = inject_suggestion_to_system(system, critique.suggestion)
                # 重新 synthesis
                retry_text = ""
                async for evt in self._synthesize_stream(
                    messages=messages,
                    system=new_system,
                    llm=llm,
                ):
                    if evt.type == "text_delta":
                        retry_text += evt.delta or ""
                    yield evt
                # 重评
                critique = await critique_response(
                    user_question=_last_user_text(messages),
                    intent=intent,
                    response_text=retry_text,
                    rich_blocks=rich_blocks,
                    tool_calls=tool_calls,
                    ctx=ctx,
                )
                yield critique_to_sse_event(critique)
                accumulated_text = retry_text

            # ===== Phase 5: done =====
            duration_ms = int((time.monotonic() - t0) * 1000)
            yield StreamEvent(
                type="done",
                duration_ms=duration_ms,
                session_id=ctx.trace.session_id if ctx.trace else None,
            )

        except asyncio.CancelledError:
            # 铁律 4：用户中断时 sanitize + 同步落库 + re-raise
            logger.warning("agentic_loop cancelled, sanitizing messages")
            _sanitize_pending_tool_uses(messages, reason="cancelled")
            raise  # 让上层 TraceCollector.__aexit__ 收到 exc_value 走同步落库
        except Exception as e:
            logger.error(f"agentic_loop failed: {e}", exc_info=True)
            yield StreamEvent(type="error", code="AGENTIC_LOOP_ERROR", message=str(e))
            raise

    async def _synthesize_stream(
        self,
        messages: list[dict],
        system: str,
        llm: LLMClient,
    ) -> AsyncIterator[StreamEvent]:
        """流式综合输出 — 无 tools，仅生成最终答案

        Yields:
        - text_delta [increment] 流式 token
        - rich_block [snapshot]（如果 LLM 主动输出，方案 C 暂未启用）
        """
        kwargs = {
            "messages": messages,
            "system": system,
            "max_tokens": settings.AGENT_MAX_SYNTHESIS_TOKENS,
            "temperature": 0.5,
        }
        chosen_model = settings.AGENT_SYNTHESIS_MODEL or None
        try:
            stream_ctx = await llm.stream(**kwargs, model=chosen_model)
            async with stream_ctx as stream:
                accumulated = ""
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        delta = event.delta.text
                        accumulated += delta
                        # [increment] text_delta
                        yield StreamEvent(type="text_delta", delta=delta)
                # 流结束 — 提取 final response 用于 usage
                final = await stream.get_final_message()
                if hasattr(final, "usage") and final.usage and getattr(ctx_or_trace := None, "trace", None):
                    # 简化：trace 通过 ctx 传递，但这里 _synthesize_stream 不直接接 ctx
                    # 留作扩展
                    pass
        except Exception as e:
            logger.error(f"_synthesize_stream failed: {e}", exc_info=True)
            raise


# ============================================================================
# 辅助函数
# ============================================================================


def _last_user_text(messages: list[dict]) -> str:
    """从最后一条 user 消息提取纯文本"""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    return ""


def _block_dump(block) -> dict:
    """把 Anthropic content block 转 dict"""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if isinstance(block, dict):
        return block
    return {"type": getattr(block, "type", "unknown"), "text": getattr(block, "text", str(block))}
