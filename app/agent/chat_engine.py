"""ChatEngine — 方案 C 单阶段流式渐进综合（Stage 2 重写）

设计目标（2026-06-14 方案 C）：
- 主入口 `synthesize_stream()` 编排 4 个 Agent 模块（intent → agentic_loop → critique）
- 取消 brief/detail 双层：content = synthesis_text（单阶段综合输出）
- TraceCollector 用 `async with` 包裹：异常时同步落库（铁律 4）
- Kill switch：AGENT_NEW_ARCHITECTURE_ENABLED=False 时走 chat_engine_legacy
- 保留旧 API 签名（chat_stream / chat_with_brief_and_detail）以兼容 micro_bubble_agent
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from app.agent.agentic_loop import AgenticLoop
from app.agent.intent_classifier import (
    IntentCategory,
    IntentResult,
    classify_intent,
    intent_to_sse_event,
)
from app.agent.protocol import RichBlock, StreamEvent
from app.agent.tool_registry import ToolContext
from app.agent.tracing import TraceCollector
from app.config import settings

logger = logging.getLogger("microbubble.agent.engine")


# ============================================================================
# 主类
# ============================================================================


class ChatEngine:
    """单阶段流式综合引擎

    Stage 2 重写后职责清晰：
    1. 入口：`synthesize_stream()` 编排 intent → agentic_loop → critique（流式 yield）
    2. 薄壳：`chat_stream()` / `chat_with_brief_and_detail()` 兼容老 API
    3. 旧实现：`chat_engine_legacy.py`（30 天回滚资产）
    """

    def __init__(self, llm=None):
        # Stage 2 仍可注入 llm（向后兼容），agentic_loop 内部用 ctx.llm 优先
        self.llm = llm

    # =========================================================================
    # 主入口：synthesize_stream（方案 C 核心）
    # =========================================================================

    async def synthesize_stream(
        self,
        messages: List[Dict],
        system: str,
        user_id: Optional[int] = None,
        db=None,
        channel_user_id: Optional[str] = None,
        session_id: str = "default",
    ) -> AsyncIterator[StreamEvent]:
        """方案 C 单阶段流式综合主入口

        编排顺序：
        1. [snapshot] intent_detected（Haiku 分类）
        2. async with TraceCollector：异常时同步落库（铁律 4）
        3. AgenticLoop.run：tool loop → synthesis stream → critique → retry → done
        4. done 事件含 usage + duration_ms

        Kill switch（铁律 6）：
        AGENT_NEW_ARCHITECTURE_ENABLED=False → 退到 chat_engine_legacy

        Yields:
        - intent_detected [snapshot]
        - tool_use / tool_result / tool_compressed (loop)
        - synthesis_start [snapshot]
        - text_delta [increment] 流式 token
        - rich_block [snapshot]
        - critique [snapshot]
        - retry [snapshot] (条件)
        - text_delta [increment] (retry 流式)
        - done [snapshot] | error [snapshot]
        """
        # Kill switch：紧急回滚到老路径（铁律 6）
        if not settings.AGENT_NEW_ARCHITECTURE_ENABLED:
            async for evt in self._legacy_chat_stream(
                messages, system, user_id, db, channel_user_id, session_id,
            ):
                yield evt
            return

        # 1. 意图分类
        ctx = ToolContext(
            db=db,
            user_id=user_id,
            channel_user_id=channel_user_id,
        )
        intent: Optional[IntentResult] = None
        try:
            intent = await classify_intent(
                question=_last_user_text(messages),
                ctx=ctx,
            )
            yield intent_to_sse_event(intent)
        except Exception as e:
            # intent 分类失败不阻塞（降级已在 classify_intent 内部处理）
            logger.warning(f"intent classification failed at top-level: {e}")

        # 1b. Intent-Aware Gate (#001b - 2026-06-28 chat agent 质量优化)
        # 根据意图分类附加对应回复指南 section：
        # - CASUAL_CHAT → ≤50 字简短回复（避免"你好"被硬塞 300 字）
        # - DATA_QUERY/EXECUTE_ACTION → 直接展示工具结果，不展开
        # - SEARCH_INFO/EXPLAIN_CONCEPT/RECOMMEND_PERSON → ≥300 字 + 三段式 + 引用
        # feature flag AGENT_INTENT_AWARE_PROMPTS 控制开关，便于紧急回滚
        if settings.AGENT_INTENT_AWARE_PROMPTS:
            from app.agent.prompts import get_intent_aware_guidelines
            intent_category = intent.category.value if intent else None
            intent_section = get_intent_aware_guidelines(intent_category)
            if intent_section:
                system = system + "\n" + intent_section
                logger.debug(
                    f"intent-aware gate applied: intent={intent_category}, "
                    f"added {len(intent_section)} chars"
                )

        # 1c. Primitive Recognition Gate (#083 - 2026-06-28 chat agent 质量优化)
        # 仅在深度场景（search_info / explain_concept / recommend_person）追加
        # 5 大原意识别 section，引导 LLM 先识别用户输入属于 任务/会议/知识/公式/假设
        # 中的哪一种，再决定调什么工具、如何回复。
        # 闲聊/数据场景不挂这个 section（避免干扰快速回答）。
        # feature flag AGENT_PRIMITIVE_RECOGNITION 控制开关，便于紧急回滚
        if settings.AGENT_PRIMITIVE_RECOGNITION and intent_category in {
            "search_info", "explain_concept", "recommend_person"
        }:
            from app.agent.prompts import get_primitive_recognition_section
            primitive_section = get_primitive_recognition_section()
            if primitive_section:
                system = system + "\n" + primitive_section
                logger.debug(
                    f"primitive-recognition gate applied: intent={intent_category}, "
                    f"added {len(primitive_section)} chars"
                )

        # 1d. Cross-Domain Synthesis Gate (#086 - 2026-06-28 chat agent 质量优化)
        # 仅在 explain_concept 场景触发, 强制 LLM 调 4 工具跨 4 域
        # (知识 + 公式 + 假设 + 成员), 让概念问回答覆盖 5 维度
        # (原理+公式+我们的研究+我们的假设+我们的研究人员)
        # 不挂 search_info (找具体论文/资料) 和 recommend_person (找人) 场景
        # feature flag AGENT_CROSS_DOMAIN_SYNTHESIS 控制开关
        if settings.AGENT_CROSS_DOMAIN_SYNTHESIS and intent_category == "explain_concept":
            from app.agent.prompts import get_cross_domain_synthesis_section
            cross_domain_section = get_cross_domain_synthesis_section()
            if cross_domain_section:
                system = system + "\n" + cross_domain_section
                logger.debug(
                    f"cross-domain-synthesis gate applied: intent={intent_category}, "
                    f"added {len(cross_domain_section)} chars"
                )

        # 2. Agentic Loop + Trace 持久化（async with 异常安全）
        trace = TraceCollector(
            user_id=user_id,
            session_id=session_id,
            message=_last_user_text(messages),
        )
        # 记录 intent 到 trace（Stage 3 数据库列完整生效）
        if intent is not None:
            trace.set_intent(intent.category.value, intent.confidence)

        # 构造带 LLM 的 ctx
        ctx = ToolContext(
            db=db,
            user_id=user_id,
            channel_user_id=channel_user_id,
            trace=trace,
            llm=self.llm,  # 显式注入，避免 agentic_loop 走全局 LLMClient 单例（跨 loop 安全）
        )

        loop = AgenticLoop()
        try:
            async with trace:
                async for evt in loop.run(
                    messages=messages,
                    system=system,
                    intent=intent or IntentResult(category=IntentCategory.SEARCH_INFO, confidence=0.0),
                    ctx=ctx,
                    max_rounds=settings.AGENT_MAX_TOOL_ROUNDS,
                ):
                    # 收集 trace 数据
                    if evt.type == "tool_use":
                        pass  # 已在 dispatch_tool 记录到 trace
                    elif evt.type == "tool_result":
                        # 从 StreamEvent 拿 duration 不方便，由 dispatch_tool 负责
                        pass
                    elif evt.type == "rich_block" and evt.block:
                        trace.record_rich_block(evt.block.type, evt.block.title)
                    elif evt.type == "critique" and evt.critique:
                        trace.set_critique(
                            score=int(evt.critique.get("score", 0)),
                            retry_count=int(evt.critique.get("retry_count", 0)),
                        )
                    yield evt
        except asyncio.CancelledError:
            # 铁律 4：用户中断，async with TraceCollector.__aexit__ 已同步落库
            logger.warning(f"synthesize_stream cancelled: user_id={user_id} session_id={session_id}")
            yield StreamEvent(type="error", code="USER_ABORTED", message="用户已中断生成")
            raise
        except Exception as e:
            logger.error(f"synthesize_stream failed: {e}", exc_info=True)
            # 把 error 事件也 yield 出去（前端 useChatStream 处理）
            yield StreamEvent(type="error", code="SYNTHESIZE_ERROR", message=str(e))
            raise

    # =========================================================================
    # 薄壳：chat_stream（向后兼容 micro_bubble_agent.py:136）
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
        """流式接口 — 内部转给 synthesize_stream

        向后兼容：micro_bubble_agent.chat_stream() 直接 for-await 此方法的 yield
        """
        async for evt in self.synthesize_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
        ):
            yield evt

    # =========================================================================
    # 薄壳：chat_with_brief_and_detail（向后兼容 ChatResponse 10 字段）
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
        """非流式接口 — 消费 synthesize_stream 收集为 dict

        返回 dict 字段（向后兼容 ChatResponse 10 字段）：
        {
          "content": str,                # synthesis_text（v2+ 唯一答案）
          "content_blocks": list,
          "tool_calls": list,
          "tool_results": list,
          "rich_blocks": list,
          "tool_trace": list,
          "usage": dict,
          "duration_ms": int,
          "intent": dict,                # 2026-06-14 新增
          "critique": dict,              # 2026-06-14 新增
          "is_brief": bool,              # deprecated 永远 False（v1 客户端兼容）
        }
        """
        t0 = time.monotonic()
        content = ""
        content_blocks: List[Dict] = []
        tool_calls: List[Dict] = []
        tool_results: List[Dict] = []
        rich_blocks: List[RichBlock] = []
        intent: Optional[Dict] = None
        critique: Optional[Dict] = None
        usage: Optional[Dict] = None
        duration_ms: Optional[int] = None

        async for evt in self.synthesize_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
        ):
            if evt.type == "text_delta":
                content += evt.delta or ""
                content_blocks.append({"type": "text", "text": content})
            elif evt.type == "tool_use":
                tool_calls.append({
                    "id": evt.tool_use_id,
                    "name": evt.tool_name,
                    "input": evt.tool_input,
                })
            elif evt.type == "tool_result":
                tool_results.append({
                    "tool_use_id": evt.tool_use_id,
                    "name": evt.tool_name,
                    "result": evt.tool_output,
                })
            elif evt.type == "rich_block" and evt.block:
                rich_blocks.append(evt.block)
            elif evt.type == "intent_detected" and evt.intent:
                intent = evt.intent
            elif evt.type == "critique" and evt.critique:
                critique = evt.critique
            elif evt.type == "done":
                usage = evt.usage
                duration_ms = evt.duration_ms

        return {
            "content": content,
            "content_blocks": content_blocks,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "rich_blocks": [rb.model_dump() for rb in rich_blocks],
            "tool_trace": tool_calls,  # alias for backward compat
            "usage": usage,
            "duration_ms": duration_ms if duration_ms is not None else int((time.monotonic() - t0) * 1000),
            "intent": intent,
            "critique": critique,
            "is_brief": False,  # deprecated 永远 False
        }

    # =========================================================================
    # 内部：legacy fallback（铁律 6 kill switch）
    # =========================================================================

    async def _legacy_chat_stream(
        self,
        messages: List[Dict],
        system: str,
        user_id: Optional[int],
        db,
        channel_user_id: Optional[str],
        session_id: str,
    ) -> AsyncIterator[StreamEvent]:
        """退到 chat_engine_legacy.py 的旧实现（30 天回滚资产）"""
        from app.agent.chat_engine_legacy import ChatEngine as LegacyChatEngine

        legacy = LegacyChatEngine()
        async for evt in legacy.chat_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
        ):
            yield evt


# ============================================================================
# 辅助函数（与 chat_engine_legacy 同源，供 legacy fallback 引用）
# ============================================================================


def _last_user_text(messages: List[Dict]) -> str:
    """从最后一条 user 消息抽取纯文本"""
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
    """从工具结果中提取 RichBlock（与原实现兼容，供 chat_engine_legacy 调用）"""
    from typing import get_args

    from app.agent.protocol import RichBlockType

    if not isinstance(result, dict):
        return None

    # 工具结果里显式标注 rich_block_type
    valid_types = frozenset(get_args(RichBlockType))
    rb_type = result.get("rich_block_type")
    if rb_type and rb_type in valid_types:
        data = {k: v for k, v in result.items() if k != "rich_block_type"}
        return RichBlock(
            type=rb_type,
            data=data,
            title=result.get("title"),
        )

    # 隐式映射
    implicit_map = {
        "query_meetings": ("meeting", "会议列表"),
        "query_tasks": ("task_list", "任务列表"),
        "query_members": ("member", "成员列表"),
        "query_projects": ("project", "项目列表"),
        "search_knowledge": ("knowledge_ref", "知识引用"),
        "get_meeting_detail": ("meeting", "会议详情"),
        "get_meeting_transcript": ("transcript", "会议转录"),
        "get_member_profile": ("member", "成员资料"),
        "get_project_summary": ("project", "项目摘要"),
        "list_formulas": ("formula", "公式列表"),
        "list_hypotheses": ("hypothesis", "假设列表"),
        "get_recent_meeting_conclusions": ("meeting", "近期会议结论"),
        "analyze_meeting_transcript": ("meeting", "会议分析"),
    }
    if tool_name in implicit_map and result.get("status") == "success":
        rb_type, default_title = implicit_map[tool_name]
        # 统一 member 类型为 {members: [...]} 形态（前端 MemberCardBlock 只认这个）
        if rb_type == "member":
            if "members" in result and isinstance(result["members"], list):
                data = result
            else:
                # get_member_profile 返回单成员对象 → 包装为数组
                member = {k: v for k, v in result.items() if k not in ("status",)}
                data = {"members": [member]}
            return RichBlock(type=rb_type, data=data, title=default_title)
        return RichBlock(
            type=rb_type,
            data=result,
            title=default_title,
        )

    return None
