"""ChatEngine — 双层回复编排 + 流式生成 + 工具循环

负责：
- 调用 LLMClient 生成响应
- 处理 tool_use 循环（最多 N 轮 + 截断续写）
- 生成【简要】+【详细】双层回复
- yield StreamEvent 给前端 SSE
- 把每个工具调用记录到 TraceCollector
- 收集 rich_blocks 用于前端富文本渲染

设计原则：
- 完全异步（async）
- 与 LLMClient 解耦（接收 client 实例）
- 与 ToolContext 集成（传递 db/user_id/trace/event_callback）
- 与 session_manager 集成（messages 持久化）
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from app.agent.protocol import (
    RichBlock,
    StreamEvent,
    ToolError,
    ToolInputError,
    ToolNotFoundError,
)
from app.agent.session_manager import session_manager
from app.agent.tool_registry import (
    ToolContext,
    dispatch_tool,
    get_all_tool_schemas,
)
from app.agent.tracing import TraceCollector
from app.config import settings
from app.core.llm import LLMClient, llm_client

logger = logging.getLogger("microbubble.agent.engine")


# 工具循环最大轮数（防止无限循环）
MAX_TOOL_ROUNDS = 5
# 截断续写最大次数
MAX_CONTINUES = 3


class ChatEngine:
    """双层回复引擎"""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or llm_client

    # =========================================================================
    # 核心：双层回复（brief → 后台 detail）
    # =========================================================================

    async def chat_with_brief_and_detail(
        self,
        messages: List[Dict],
        system: str,
        user_id: Optional[int] = None,
        db=None,
        channel_user_id: Optional[str] = None,
        session_id: str = "default",
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
    ) -> Dict[str, Any]:
        """非流式：先返回 brief，后台跑 detail

        返回 dict 兼容旧 MicroBubbleAgent.chat() 接口：
        {
            "content": "<brief 文本>",
            "content_blocks": [...],
            "tool_calls": [...],
            "tool_results": [...],
            "rich_blocks": [...],  # 新增
            "tool_trace": [...],   # 新增
            "usage": {...},        # 新增
            "duration_ms": 3200,   # 新增
        }
        """
        t0 = time.monotonic()
        rich_blocks: List[RichBlock] = []
        trace = TraceCollector(user_id=user_id, session_id=session_id, message=_last_user_text(messages))

        # 构造 ToolContext
        ctx = ToolContext(
            db=db,
            user_id=user_id,
            channel_user_id=channel_user_id,
            trace=trace,
        )

        # 1. 生成 brief（带工具调用，可能产生 rich_blocks）
        brief_text, brief_rich_blocks, tool_calls, tool_results = await self._generate_with_tools(
            messages=messages,
            system=system,
            tools=get_all_tool_schemas(),
            max_tokens=500,
            ctx=ctx,
        )
        rich_blocks.extend(brief_rich_blocks)
        trace.set_brief(brief_text)

        # 2. 后台跑 detail（无工具，更长 max_tokens）
        asyncio.create_task(self._append_detail_background(
            messages=messages,
            brief=brief_text,
            session_id=session_id,
            user_id=user_id,
        ))

        # 3. 统计 + 返回
        duration_ms = int((time.monotonic() - t0) * 1000)
        return {
            "content": brief_text,
            "content_blocks": [{"type": "text", "text": brief_text}],
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "rich_blocks": [rb.model_dump() for rb in rich_blocks],
            "tool_trace": [tc.__dict__ for tc in trace.tool_calls],
            "usage": trace.usage,
            "duration_ms": duration_ms,
        }

    # =========================================================================
    # 核心：流式
    # =========================================================================

    async def chat_stream(
        self,
        messages: List[Dict],
        system: str,
        user_id: Optional[int] = None,
        db=None,
        channel_user_id: Optional[str] = None,
        session_id: str = "default",
    ) -> AsyncIterator[StreamEvent]:
        """流式：yield StreamEvent 序列

        事件流（典型）：
        1. thinking: "正在分析问题..."
        2. tool_use: {name, input}
        3. tool_result: {name, output, duration_ms}
        4. rich_block: {type, data}
        5. text_delta: "你好" / brief: "简要..."
        6. detail: "详细..."  (后续)
        7. done: {usage, duration_ms}
        """
        t0 = time.monotonic()
        trace = TraceCollector(user_id=user_id, session_id=session_id, message=_last_user_text(messages))
        ctx = ToolContext(
            db=db,
            user_id=user_id,
            channel_user_id=channel_user_id,
            trace=trace,
        )

        try:
            yield StreamEvent(type="thinking", label="🔍 正在分析问题...")

            # 1. 调用 LLM 流式
            accumulated_text = ""
            tool_uses_buffer: Dict[str, Dict] = {}  # id -> {name, input_json}
            current_tool_id: Optional[str] = None

            kwargs = {
                "messages": messages,
                "system": system,
                "tools": get_all_tool_schemas(),
                "max_tokens": 500,
            }
            async with self.llm.client.messages.stream(
                model=self.llm.models[0],
                **kwargs,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool_id = event.content_block.id
                            tool_uses_buffer[current_tool_id] = {
                                "name": event.content_block.name,
                                "input_json": "",
                            }
                            yield StreamEvent(
                                type="tool_use",
                                tool_name=event.content_block.name,
                                tool_use_id=current_tool_id,
                            )
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            accumulated_text += event.delta.text
                            yield StreamEvent(
                                type="text_delta",
                                delta=event.delta.text,
                            )
                        elif event.delta.type == "input_json_delta" and current_tool_id:
                            tool_uses_buffer[current_tool_id]["input_json"] += getattr(
                                event.delta, "partial_json", ""
                            )
                    elif event.type == "content_block_stop":
                        if current_tool_id and current_tool_id in tool_uses_buffer:
                            tu = tool_uses_buffer[current_tool_id]
                            try:
                                tu["input"] = json.loads(tu["input_json"]) if tu["input_json"] else {}
                            except json.JSONDecodeError:
                                tu["input"] = {}
                            del tu["input_json"]
                            current_tool_id = None

                response = await stream.get_final_message()
                # token 统计（Anthropic 响应里有 usage）
                if hasattr(response, "usage") and response.usage:
                    trace.set_usage(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                    )

            # 2. 处理工具调用（brief 阶段可能 0-1 个 tool_use）
            if tool_uses_buffer:
                for tool_use_id, tu in tool_uses_buffer.items():
                    input_data = tu.get("input", {})
                    yield StreamEvent(
                        type="thinking",
                        label=f"🔧 正在调用工具：{tu['name']}",
                    )
                    result = await dispatch_tool(tu["name"], input_data, ctx)
                    yield StreamEvent(
                        type="tool_result",
                        tool_name=tu["name"],
                        tool_use_id=tool_use_id,
                        tool_output=result if isinstance(result, dict) else {"result": str(result)},
                    )
                    # 检测 rich block
                    rb = _extract_rich_block(tu["name"], result)
                    if rb:
                        trace.record_rich_block(rb.type, rb.title)
                        yield StreamEvent(type="rich_block", block=rb)

            # 3. brief 标记
            if accumulated_text:
                yield StreamEvent(type="brief", delta=accumulated_text)

            # 4. 流式结束
            duration_ms = int((time.time() - t0) * 1000)
            yield StreamEvent(
                type="done",
                usage=trace.usage,
                duration_ms=duration_ms,
                session_id=session_id,
            )

        except Exception as e:
            logger.error(f"流式 chat 失败: {e}", exc_info=True)
            trace.set_error(f"{type(e).__name__}: {e}")
            yield StreamEvent(
                type="error",
                code="STREAM_ERROR",
                message=str(e),
            )

    # =========================================================================
    # 内部：带工具的完整生成（brief 阶段用）
    # =========================================================================

    async def _generate_with_tools(
        self,
        messages: List[Dict],
        system: str,
        tools: List[Dict],
        max_tokens: int,
        ctx: ToolContext,
    ) -> tuple[str, List[RichBlock], List[Dict], List[Dict]]:
        """一次完整 LLM 调用 + 工具循环（brief 阶段）"""
        accumulated_text = ""
        rich_blocks: List[RichBlock] = []
        all_tool_calls: List[Dict] = []
        all_tool_results: List[Dict] = []

        for round_idx in range(MAX_TOOL_ROUNDS):
            try:
                response = await self.llm.complete(
                    messages=messages,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                logger.error(f"LLM 调用失败（round {round_idx}）: {e}", exc_info=True)
                ctx.trace.set_error(f"{type(e).__name__}: {e}")
                break

            # 提取文本 + 工具调用
            round_text = ""
            round_tool_calls = []
            for block in response.content:
                if block.type == "text":
                    round_text += block.text
                elif block.type == "tool_use":
                    round_tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            accumulated_text += round_text
            all_tool_calls.extend(round_tool_calls)

            # 无工具调用 → 结束
            if not round_tool_calls:
                # 截断检测
                if response.stop_reason == "max_tokens":
                    logger.warning("brief 阶段 max_tokens 截断")
                break

            # 处理工具调用
            tool_results = []
            for call in round_tool_calls:
                result = await dispatch_tool(call["name"], call["input"], ctx)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
                all_tool_results.append({
                    "tool_use_id": call["id"],
                    "name": call["name"],
                    "result": result,
                })
                rb = _extract_rich_block(call["name"], result)
                if rb:
                    rich_blocks.append(rb)
                    ctx.trace.record_rich_block(rb.type, rb.title)

            # 把这一轮 append 到 messages
            messages = list(messages)
            messages.append({
                "role": "assistant",
                "content": [_block_dump(b) for b in response.content],
            })
            messages.append({
                "role": "user",
                "content": tool_results,
            })

        return accumulated_text, rich_blocks, all_tool_calls, all_tool_results

    # =========================================================================
    # 后台 detail 任务
    # =========================================================================

    async def _append_detail_background(
        self,
        messages: List[Dict],
        brief: str,
        session_id: str,
        user_id: Optional[int],
    ):
        """后台跑 detail 回复（无工具，更长 max_tokens）"""
        try:
            from app.agent.prompts import get_detail_prompt, _weekdays
            from datetime import datetime
            from app.models.base import BEIJING_TZ

            now = datetime.now(BEIJING_TZ)
            today_str = f"{now.year}年{now.month}月{now.day}日（{_weekdays[now.weekday()]}）"
            time_str = now.strftime('%H:%M')
            system_detail = get_detail_prompt().format(today_str=today_str, time_str=time_str)

            # 把 brief 加到 messages 最后
            messages = list(messages)
            messages.append({"role": "assistant", "content": brief})

            response = await self.llm.complete(
                messages=messages,
                system=system_detail,
                max_tokens=settings.CLAUDE_MAX_TOKENS,
            )

            detail_text = ""
            for block in response.content:
                if block.type == "text":
                    detail_text += block.text

            if detail_text:
                # 追加到 session
                await session_manager.append_message(session_id, {
                    "role": "assistant",
                    "content": detail_text,
                })
                logger.info(f"detail 已追加到 session {session_id}")
        except Exception as e:
            logger.error(f"detail 后台生成失败: {e}", exc_info=True)


# ============================================================================
# 辅助函数
# ============================================================================


def _last_user_text(messages: List[Dict]) -> str:
    """提取最后一条 user 消息的纯文本"""
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


def _block_dump(block) -> Dict:
    """把 Anthropic content block 转 dict"""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if isinstance(block, dict):
        return block
    return {"type": getattr(block, "type", "unknown"), "text": getattr(block, "text", str(block))}


def _extract_rich_block(tool_name: str, result: Dict) -> Optional[RichBlock]:
    """从工具结果中提取 RichBlock（如果工具在结果中标注了 rich_block_type）"""
    if not isinstance(result, dict):
        return None

    # 工具结果里显式标注 rich_block_type
    if "rich_block_type" in result:
        rb_type = result["rich_block_type"]
        # 复制 data（去掉 rich_block_type 字段本身）
        data = {k: v for k, v in result.items() if k != "rich_block_type"}
        return RichBlock(
            type=rb_type,
            data=data,
            title=result.get("title"),
        )

    # 隐式映射：某些工具默认产生某种 block
    implicit_map = {
        "query_meetings": ("meeting", "会议列表"),
        "query_tasks": ("task_list", "任务列表"),
        "search_knowledge": ("knowledge_ref", "知识引用"),
        "get_meeting_detail": ("meeting", "会议详情"),
        "get_meeting_transcript": ("transcript", "会议转录"),
        "get_member_profile": ("member", "成员资料"),
        "get_project_summary": ("project", "项目摘要"),
        "list_formulas": ("formula", "公式列表"),
        "list_hypotheses": ("hypothesis", "假设列表"),
        "get_recent_meeting_conclusions": ("meeting", "近期会议结论"),
    }
    if tool_name in implicit_map and result.get("status") == "success":
        rb_type, default_title = implicit_map[tool_name]
        return RichBlock(
            type=rb_type,
            data=result,
            title=default_title,
        )

    return None
