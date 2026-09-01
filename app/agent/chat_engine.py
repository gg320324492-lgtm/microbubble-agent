"""ChatEngine — 方案 C 单阶段流式渐进综合（Stage 2 重写）

设计目标（2026-06-14 方案 C）：
- 主入口 `synthesize_stream()` 编排 4 个 Agent 模块（intent → agentic_loop → critique）
- 取消 brief/detail 双层：content = synthesis_text（单阶段综合输出）
- TraceCollector 用 `async with` 包裹：异常时同步落库（铁律 4）
- 保留旧 API 签名（chat_stream / chat_with_brief_and_detail）以兼容 micro_bubble_agent

历史（2026-06-29 已删除）：
- chat_engine_legacy.py (30 天回滚资产，已在 2026-06-29 提前 15 天收官, commit 817f1ffa)
- AGENT_NEW_ARCHITECTURE_ENABLED 等 3 个 feature flag 已全部移除
- 真回滚路径: git revert 817f1ffa + 重新部署
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
        synthesis_model_override: Optional[str] = None,
        # 2026-07-13 #P1 三态推理模式 (fast/balanced/deep): 'fast' | 'balanced' | 'deep' | None (= settings 默认)
        thinking_mode: Optional[str] = None,
        # CHAT-P1-B: micro_bubble_agent 预分类后复用，避免 engine 二次分类
        preclassified_intent: Optional[IntentResult] = None,
        # #P5: 用户手动附加的知识库文档 ID 列表, 屏蔽 RAG 类工具
        attached_knowledge_ids: Optional[List[int]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """方案 C 单阶段流式综合主入口

        编排顺序：
        1. [snapshot] intent_detected（Haiku 分类）
        2. async with TraceCollector：异常时同步落库（铁律 4）
        3. AgenticLoop.run：tool loop → synthesis stream → critique → retry → done
        4. done 事件含 usage + duration_ms

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
        # 2026-07-13 #P1: 提前 resolve_thinking_config, 让 intent gates + ToolContext 都能读
        from app.agent.thinking_config import resolve_thinking_config

        thinking_config = resolve_thinking_config(thinking_mode)

        # 1. 意图分类
        ctx = ToolContext(
            db=db,
            user_id=user_id,
            channel_user_id=channel_user_id,
            # 2026-07-13 #P1: 注入 thinking_config 给 intent_classifier 等后续步骤
            thinking_config=thinking_config,
            mode_label=thinking_config.label,
            # #P5: 用户手动附加文档 → agentic_loop 屏蔽 RAG 类工具
            attached_knowledge_ids=attached_knowledge_ids,
        )
        intent: Optional[IntentResult] = preclassified_intent
        intent_category: Optional[str] = intent.category.value if intent else None
        try:
            if intent is None:
                intent = await classify_intent(
                    question=_last_user_text(messages),
                    ctx=ctx,
                )
            intent_category = intent.category.value
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
        # 2026-07-13 #P1: 优先读 thinking_config.intent_aware_prompts (mode-aware), 否则读 settings 默认
        if (thinking_config.intent_aware_prompts and settings.AGENT_INTENT_AWARE_PROMPTS
                and intent_category not in {"casual_chat", "follow_up"}):
            from app.agent.prompts import get_intent_aware_guidelines
            intent_section = get_intent_aware_guidelines(intent_category)
            if intent_section:
                system = system + "\n" + intent_section
                logger.debug(
                    f"intent-aware gate applied: intent={intent_category}, "
                    f"added {len(intent_section)} chars, mode={thinking_config.mode}"
                )

        # 1c. Primitive Recognition Gate (#083 - 2026-06-28 chat agent 质量优化)
        # 仅在深度场景（search_info / explain_concept / recommend_person）追加
        # 5 大原意识别 section，引导 LLM 先识别用户输入属于 任务/会议/知识/公式/假设
        # 中的哪一种，再决定调什么工具、如何回复。
        # 闲聊/数据场景不挂这个 section（避免干扰快速回答）。
        # feature flag AGENT_PRIMITIVE_RECOGNITION 控制开关，便于紧急回滚
        if thinking_config.primitive_recognition and settings.AGENT_PRIMITIVE_RECOGNITION and intent_category in {
            "search_info", "explain_concept", "recommend_person"
        }:
            from app.agent.prompts import get_primitive_recognition_section
            primitive_section = get_primitive_recognition_section()
            if primitive_section:
                system = system + "\n" + primitive_section
                logger.debug(
                    f"primitive-recognition gate applied: intent={intent_category}, "
                    f"added {len(primitive_section)} chars, mode={thinking_config.mode}"
                )

        # 1d. Cross-Domain Synthesis Gate (#086 - 2026-06-28 chat agent 质量优化)
        # 仅在 explain_concept 场景触发, 强制 LLM 调 4 工具跨 4 域
        # (知识 + 公式 + 假设 + 成员), 让概念问回答覆盖 5 维度
        # (原理+公式+我们的研究+我们的假设+我们的研究人员)
        # 不挂 search_info (找具体论文/资料) 和 recommend_person (找人) 场景
        # feature flag AGENT_CROSS_DOMAIN_SYNTHESIS 控制开关
        if thinking_config.cross_domain_synthesis and settings.AGENT_CROSS_DOMAIN_SYNTHESIS and intent_category == "explain_concept":
            from app.agent.prompts import get_cross_domain_synthesis_section
            cross_domain_section = get_cross_domain_synthesis_section()
            if cross_domain_section:
                system = system + "\n" + cross_domain_section
                logger.debug(
                    f"cross-domain-synthesis gate applied: intent={intent_category}, "
                    f"added {len(cross_domain_section)} chars, mode={thinking_config.mode}"
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
            synthesis_model_override=synthesis_model_override,
            # 2026-07-13 #P1: 注入 thinking_config 给 agentic_loop 5 处真分支
            thinking_config=thinking_config,
            mode_label=thinking_config.label,
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
        *,
        synthesis_model_override: Optional[str] = None,
        # 2026-07-13 #P1 三档推理模式透传
        thinking_mode: Optional[str] = None,
        preclassified_intent: Optional[IntentResult] = None,
        # #P5: 用户手动附加文档 → 屏蔽 RAG 工具
        attached_knowledge_ids: Optional[List[int]] = None,
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
            synthesis_model_override=synthesis_model_override,
            # 2026-07-13 #P1 透传
            thinking_mode=thinking_mode,
            preclassified_intent=preclassified_intent,
            # #P5: 透传附加文档 ID
            attached_knowledge_ids=attached_knowledge_ids,
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
        *,
        synthesis_model_override: Optional[str] = None,
        # 2026-07-13 #P1 三档推理模式透传
        thinking_mode: Optional[str] = None,
        # #P5: 透传附加文档 → 屏蔽 RAG 工具
        attached_knowledge_ids: Optional[List[int]] = None,
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
        # W100 P1 Self-RAG: 集成不可靠答案自动重检索
        self_rag_assessment: Optional[Dict[str, Any]] = None
        retrieved_chunks_for_assessment: List[Dict[str, Any]] = []

        async for evt in self.synthesize_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
            synthesis_model_override=synthesis_model_override,
            # 2026-07-13 #P1 透传
            thinking_mode=thinking_mode,
            # #P5: 透传附加文档 ID → 屏蔽 RAG 工具
            attached_knowledge_ids=attached_knowledge_ids,
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
                # W100 P1 Self-RAG: 从 hybrid_retrieve 工具结果收 chunks 用于事后评估
                if (
                    evt.tool_name in ("hybrid_retrieve", "search_knowledge", "rag_search")
                    and isinstance(evt.tool_output, dict)
                ):
                    items = evt.tool_output.get("results") or evt.tool_output.get("items") or []
                    if isinstance(items, list):
                        retrieved_chunks_for_assessment.extend(items)
            elif evt.type == "rich_block" and evt.block:
                rich_blocks.append(evt.block)
            elif evt.type == "intent_detected" and evt.intent:
                intent = evt.intent
            elif evt.type == "critique" and evt.critique:
                critique = evt.critique
            elif evt.type == "done":
                usage = evt.usage
                duration_ms = evt.duration_ms

        # W100 P1 Self-RAG: 不可靠信号评估 (独立分支调用, 不影响 streaming)
        if content and retrieved_chunks_for_assessment:
            try:
                from app.services.self_rag_service import SelfRAGService

                question = _last_user_text(messages)
                service = SelfRAGService(db=db)
                self_rag_assessment = await service.assess_answer(
                    question=question,
                    answer=content,
                    retrieved_chunks=retrieved_chunks_for_assessment,
                )
                # 不可靠时主动重检索 + 追加 warning (best-effort)
                if self_rag_assessment.get("should_retry"):
                    new_chunks = await service.retry_with_reformulation(
                        question=question,
                        original_chunks=retrieved_chunks_for_assessment,
                    )
                    self_rag_assessment["retry_chunks_returned"] = len(new_chunks)
                    logger.info(
                        f"self_rag triggered: reason={self_rag_assessment.get('reason')} "
                        f"retry_chunks={len(new_chunks)}"
                    )
                    # WP6 (2026-09-01): 重检索到新资料 → 追加一次 LLM 修正调用,
                    # 用修订版答案替换 content (失败/无新资料保持原答案, 不降级)
                    if new_chunks:
                        revised = await self._self_rag_revise_answer(
                            question=question,
                            original_answer=content,
                            chunks=new_chunks,
                            synthesis_model_override=synthesis_model_override,
                        )
                        if revised:
                            content = revised
                            self_rag_assessment["revised"] = True
                            logger.info("self_rag answer revised with refreshed chunks")
            except Exception as e:
                logger.warning(f"self_rag assessment failed: {e}")

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
            # W100 P1 Self-RAG: 评估结果 (供可观测 + 测试断言, 不影响既有字段)
            "self_rag_assessment": self_rag_assessment,
        }

    async def _self_rag_revise_answer(
        self,
        *,
        question: str,
        original_answer: str,
        chunks: List[Dict[str, Any]],
        synthesis_model_override: Optional[str] = None,
    ) -> str:
        """WP6 (2026-09-01): Self-RAG 修正调用 — 原答案 + 重检索 chunks → 修订版答案

        单轮 complete (thinking 关闭, 与 knowledge_qa_service._llm_synthesize 同模式),
        不发 tool_use。失败/无有效资料返回 "" (调用方保持原答案, 不降级)。
        """
        try:
            from app.core.llm import (
                extract_text_from_response,
                get_anthropic_client,
                get_default_model,
            )

            chunk_texts: List[str] = []
            for i, c in enumerate(chunks[:5], 1):
                if not isinstance(c, dict):
                    continue
                title = str(c.get("title") or "").strip()
                text = str(c.get("content") or c.get("chunk_content") or "").strip()
                if not text:
                    continue
                chunk_texts.append(f"[{i}] {title}\n{text[:500]}")
            if not chunk_texts:
                return ""

            prompt = SELF_RAG_REVISE_PROMPT.format(
                original_answer=original_answer[:3000],
                chunks="\n\n".join(chunk_texts),
                question=question,
            )
            client = get_anthropic_client()
            response = await client.messages.create(
                model=synthesis_model_override or get_default_model(),
                max_tokens=1500,
                timeout=30,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            return (extract_text_from_response(response) or "").strip()
        except Exception as e:
            logger.warning(f"self_rag revise answer failed (保持原答案): {e}")
            return ""


# ============================================================================
# 辅助函数（独立工具函数，供 chat_engine 各方法使用）
# ============================================================================

# WP6 (2026-09-01): Self-RAG 修正 prompt — 原答案 + 重检索 chunks → 修订版答案
SELF_RAG_REVISE_PROMPT = """你是一个严谨的知识库问答助手。系统检测到先前的回答可信度不足，并已重新检索到以下补充资料。请基于补充资料修订原回答。

## 原回答

{original_answer}

## 重新检索到的资料

{chunks}

## 用户问题

{question}

## 修订要求

1. 优先采用补充资料中与问题相关的信息修正或充实原回答
2. 补充资料不足的部分保留原回答内容，不要编造
3. 直接输出修订后的完整回答，不要输出修订说明"""


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


def _add_ref_snippets(data: Dict) -> Dict:
    """2026-07-31 #CHAT-P0-A A5: knowledge_ref 每项加 snippet（≤200 字 chunk 原文）

    前端引用卡反馈需要"引用了哪段原文"——content 可能很长, 显式派生 snippet
    字段（剥 HTML + 压缩空白 + 截 200 字）。只加字段不删原字段, LLM 侧
    tool_result 契约不变（此处只作用于 rich_block SSE 输出）。
    """
    import re as _re
    items = data.get("results") or data.get("refs") or data.get("items")
    if not isinstance(items, list):
        return data
    def to_snippet(content) -> str:
        if not isinstance(content, str) or not content.strip():
            return ""
        text = _re.sub(r"<[^>]+>", " ", content)
        text = _re.sub(r"\s+", " ", text).strip()
        return text[:200] + ("..." if len(text) > 200 else "")
    for item in items:
        if isinstance(item, dict) and not item.get("snippet"):
            item["snippet"] = to_snippet(item.get("content"))
    return data


def _extract_rich_block(tool_name: str, result: Dict) -> Optional[RichBlock]:
    """从工具结果中提取 RichBlock（与原实现兼容）"""
    from typing import get_args

    from app.agent.protocol import RichBlockType

    if not isinstance(result, dict):
        return None

    # 工具结果里显式标注 rich_block_type
    valid_types = frozenset(get_args(RichBlockType))
    rb_type = result.get("rich_block_type")
    if rb_type and rb_type in valid_types:
        data = {k: v for k, v in result.items() if k != "rich_block_type"}
        if rb_type == "knowledge_ref":
            data = _add_ref_snippets(data)
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
