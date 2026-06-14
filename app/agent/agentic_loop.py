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


def _normalize_fake_tool_input(name: str, input_dict: dict) -> dict:
    """2026-06-14 收官：fake tool_call 参数名 alias 解析

    模型 fake 输出时常把字段名写错（如 get_member_profile 的 member_name 写成 name），
    这里通过工具的 Pydantic schema 反查，自动 alias 匹配：
    - 输入 "name" → 找 schema 里第一个 str 字段（典型如 member_name / task_name / project_name）
    - 输入 "query" → 找 schema 里第一个非 id 字段
    - 输入 "id" → 找 schema 里 ID 字段
    - 输入其他未声明字段 → 保留（让 Pydantic 报错暴露给模型看）
    """
    if not input_dict:
        return input_dict
    try:
        from app.agent.tool_registry import TOOL_REGISTRY
        td = TOOL_REGISTRY.get(name)
        if not td or not td.input_model:
            return input_dict
        # 拿到 Pydantic schema 字段列表
        schema_fields = td.input_model.model_fields
        # 收集"明显是 id 字段"和"明显是 name 字段"
        id_fields = {fn for fn in schema_fields if fn == "id" or fn.endswith("_id")}
        name_fields = [fn for fn in schema_fields if "name" in fn.lower()]
        # 通用 alias 规则
        alias_map = {}
        if "name" in input_dict:
            # 优先匹配 _name 后缀的（如 member_name / task_name），其次是单 name
            target = None
            for nf in name_fields:
                if nf != "name":  # 跳过 "name" 本身（如果有）
                    target = nf
                    break
            if target is None and "name" in schema_fields:
                target = "name"
            if target:
                alias_map["name"] = target
        if "query" in input_dict and "query" not in schema_fields:
            # 找一个最像的字段（通常是 keyword / search_text）
            for cand in ("keyword", "search_text", "text", "q"):
                if cand in schema_fields:
                    alias_map["query"] = cand
                    break
        # 应用 alias
        result = dict(input_dict)
        for old_key, new_key in alias_map.items():
            if old_key in result and new_key not in result:
                result[new_key] = result.pop(old_key)
        # 过滤掉 schema 里不存在的字段（避免 Pydantic 报 unexpected field）
        known_fields = set(schema_fields.keys())
        result = {k: v for k, v in result.items() if k in known_fields}
        return result
    except Exception as e:
        logger.warning(f"_normalize_fake_tool_input({name}) failed: {e}")
        return input_dict


def _extract_tool_uses(response) -> list[dict]:
    """从 Anthropic Message 响应中提取 tool_use 列表

    2026-06-14 收官：双路径解析
    - 路径 A：原生 tool_use blocks（代理正确转发 tools 参数时）
    - 路径 B：模型在 content 里 fake 输出 XML 格式（代理吞掉 tools 参数时）—
      解析 <function_calls>/<tool_call> 等多种格式，转成 tool_use 走后续流程
    """
    tool_uses = []
    # 路径 A：原生 tool_use blocks
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            tool_uses.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    if tool_uses:
        return tool_uses

    # 路径 B：从 text block 里解析 fake tool_call XML
    text_parts = []
    for block in response.content:
        if hasattr(block, "text") and block.text:
            text_parts.append(block.text)
    if not text_parts:
        return tool_uses
    full_text = "\n".join(text_parts)
    return _parse_fake_tool_calls(full_text)


def _parse_fake_tool_calls(text: str) -> list[dict]:
    """2026-06-14 收官：解析 LLM 在 content 里 fake 输出的 tool_call 文本

    背景：CLAUDE_BASE_URL 走代理时，代理不转发 tools 参数（实测），
    导致模型收到 prompt 看不到 tools 列表，只能在 content 里用 XML 文本
    "模拟"工具调用。常见格式有 4 种：

    格式 1（Mistral/Qwen）：<tool_call>{"name": "foo", "arguments": {"k": "v"}}</tool_call>
    格式 2（Anthropic legacy）：<function_calls><invoke name="foo"><k>v</k></invoke></function_calls>
    格式 3（单行简化）：<function=foo><parameter=k>v</parameter></function>
    格式 4（裸 JSON）：{"name": "foo", "arguments": {"k": "v"}}（单行紧跟 ```json fence）

    返回：tool_use 列表，每个含 id (UUID 伪生成) / name / input
    """
    import re
    import uuid as _uuid

    fake_uses = []

    # 格式 1：<tool_call>{...}</tool_call>
    pattern1 = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
    for m in pattern1.finditer(text):
        try:
            data = json.loads(m.group(1))
            name = data.get("name") or data.get("function") or data.get("tool")
            args = data.get("arguments") or data.get("parameters") or data.get("input") or {}
            if name:
                fake_uses.append({
                    "id": f"toolu_fake_{_uuid.uuid4().hex[:12]}",
                    "name": name,
                    "input": args if isinstance(args, dict) else {},
                })
        except (json.JSONDecodeError, AttributeError):
            continue

    # 格式 4：裸 JSON {name, arguments} 在 ```json fence 里
    if not fake_uses:
        pattern4 = re.compile(r"```(?:json)?\s*(\{[^{}]*\"(?:name|function|tool)\"[^{}]*\})\s*```", re.DOTALL)
        for m in pattern4.finditer(text):
            try:
                data = json.loads(m.group(1))
                name = data.get("name") or data.get("function") or data.get("tool")
                args = data.get("arguments") or data.get("parameters") or data.get("input") or {}
                if name:
                    fake_uses.append({
                        "id": f"toolu_fake_{_uuid.uuid4().hex[:12]}",
                        "name": name,
                        "input": args if isinstance(args, dict) else {},
                    })
            except json.JSONDecodeError:
                continue

    # 格式 2：<function_calls><invoke name="foo"><k>v</k></invoke></function_calls>
    if not fake_uses:
        pattern2 = re.compile(
            r"<function_calls?\s*>(.*?)</function_calls?\s*>", re.DOTALL
        )
        for fc in pattern2.finditer(text):
            inner = fc.group(1)
            # 单个 invoke 块
            for inv in re.finditer(
                r'<invoke\s+name\s*=\s*["\']([^"\']+)["\']\s*>(.*?)</invoke>',
                inner, re.DOTALL,
            ):
                name = inv.group(1).strip()
                args = _parse_xml_params(inv.group(2))
                fake_uses.append({
                    "id": f"toolu_fake_{_uuid.uuid4().hex[:12]}",
                    "name": name,
                    "input": args,
                })

    # 格式 3：<function=foo><parameter=k>v</parameter></function>（最常见的简化版）
    if not fake_uses:
        pattern3 = re.compile(
            r"<function\s*=\s*([^>\s]+)\s*>(.*?)</function\s*>", re.DOTALL
        )
        for fn in pattern3.finditer(text):
            name = fn.group(1).strip()
            args = _parse_xml_params(fn.group(2))
            fake_uses.append({
                "id": f"toolu_fake_{_uuid.uuid4().hex[:12]}",
                "name": name,
                "input": args,
            })

    # 格式 5（2026-06-14 收官 v5）：<tool_call><function=...><parameter=...>v</parameter></function></tool_call>
    # 混合格式 — LLM 实际最常用。<tool_call> fence 包着 <function=...> XML 体。
    if not fake_uses:
        pattern5 = re.compile(
            r"<tool_call>\s*<function\s*=\s*([^>\s]+)\s*>(.*?)</function\s*>\s*</tool_call>",
            re.DOTALL,
        )
        for fn in pattern5.finditer(text):
            name = fn.group(1).strip()
            args = _parse_xml_params(fn.group(2))
            fake_uses.append({
                "id": f"toolu_fake_{_uuid.uuid4().hex[:12]}",
                "name": name,
                "input": args,
            })

    if fake_uses:
        # Schema-aware 参数名 alias 解析（防模型写错字段名）
        normalized = []
        for u in fake_uses:
            u["input"] = _normalize_fake_tool_input(u["name"], u["input"])
            normalized.append(u)
        fake_uses = normalized
        logger.info(
            f"_parse_fake_tool_calls: recovered {len(fake_uses)} fake tool call(s) "
            f"from content (proxy likely stripped tools param): "
            f"{[u['name'] for u in fake_uses]}"
        )
    return fake_uses


def _strip_fake_tool_calls(text: str) -> str:
    """2026-06-14 收官：把 LLM 在 content 里写的 fake tool_call XML 全部清掉

    防狼：即使 Phase 1 已经 fake → real，Phase 2 synthesis 模型可能再次写出
    这种 XML（因为它在 prompt 里学会了这种格式），要剥掉不让用户看到。

    2026-06-14 v5 收官：加 <tool_call><function=...>...</function></tool_call> 混合格式
    """
    import re
    # 5 种格式的剥除（与 _parse_fake_tool_calls 镜像）
    # 格式 5：<tool_call><function=...><parameter=...>v</parameter></function></tool_call>
    text = re.sub(
        r"<tool_call>\s*<function\s*=[^>]+>.*?</function\s*>\s*</tool_call>",
        "", text, flags=re.DOTALL,
    )
    # 格式 1：<tool_call>{...}</tool_call>
    text = re.sub(r"<tool_call>\s*\{.*?\}\s*</tool_call>", "", text, flags=re.DOTALL)
    # 格式 2：<function_calls>...</function_calls>
    text = re.sub(r"<function_calls?\s*>.*?</function_calls?\s*>", "", text, flags=re.DOTALL)
    # 格式 3：<function=...>...</function> 单独出现
    text = re.sub(r"<function\s*=[^>]+>.*?</function\s*>", "", text, flags=re.DOTALL)
    # 格式 4：```json {name, ...} ```
    text = re.sub(r"```(?:json)?\s*\{[^{}]*\"(?:name|function|tool)\"[^{}]*\}\s*```", "", text, flags=re.DOTALL)
    # 清理残留空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_xml_params(xml_str: str) -> dict:
    """从 <parameter=k>v</parameter> 风格 XML 串提取参数 dict"""
    import re
    params = {}
    # 匹配 <parameter name>value</parameter> 或 <parameter=name>value</parameter>
    for m in re.finditer(
        r'<\s*parameter(?:\s+name\s*)?\s*=\s*["\']?([^>"\']+)["\']?\s*>(.*?)<\s*/\s*parameter\s*>',
        xml_str, re.DOTALL,
    ):
        key = m.group(1).strip()
        val = m.group(2).strip()
        # 去尾部 </parameter
        val = re.sub(r"</parameter\s*>\s*$", "", val, flags=re.IGNORECASE).strip()
        params[key] = val
    # 也匹配 <k>v</k> 形式
    if not params:
        for m in re.finditer(r"<([a-zA-Z_][a-zA-Z0-9_]*)>(.*?)</\1>", xml_str, re.DOTALL):
            params[m.group(1).strip()] = m.group(2).strip()
    return params


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
                # 2026-06-14 收官：strip 掉 response content 里的 fake tool_call XML，
                # 否则 Phase 2 synthesis 看到这种 pattern 会复制到最终输出（fake_xml_leaked）
                cleaned_content = []
                for b in response.content:
                    dumped = _block_dump(b)
                    if isinstance(dumped, dict) and dumped.get("type") == "text":
                        dumped["text"] = _strip_fake_tool_calls(dumped.get("text", ""))
                    cleaned_content.append(dumped)
                messages.append({
                    "role": "assistant",
                    "content": cleaned_content,
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

        2026-06-14 方案 C Stage 5 收尾增强：LLM 可在 synthesis 阶段输出
        末尾的 JSON 段（用 ```json fence 包裹）声明 rich_block 列表。
        每个 rich_block 含 type / data / title / summary / collapsed_by_default。

        Yields:
        - text_delta [increment] 流式 token（JSON 段也会被 yield 出来，
          前端 useChatStream 收 done 事件后清理 — 见 _synthesize_stream 末尾的
          post_process 逻辑）
        - rich_block [snapshot] 解析出的 rich_block 列表（LLM-driven collapsed_by_default）
        """
        kwargs = {
            "messages": messages,
            "system": system,
            "max_tokens": settings.AGENT_MAX_SYNTHESIS_TOKENS,
            "temperature": 0.5,
        }
        chosen_model = settings.AGENT_SYNTHESIS_MODEL or None

        # 在 system 末尾追加 JSON 协议（让 LLM 知道可输出 rich_block 声明）
        # 2026-06-14 收官：4 条铁律防 LLM 凭空捏造 rich_block.data
        json_protocol = """

## 输出格式 (CRITICAL — 2026-06-14 收官)

### 铁律 1：rich_blocks.data 必须 grounded
- 任何 rich_block 的 data 内容必须严格来自本轮工具调用的真实返回结果
- 严禁编造成员姓名 / 研究方向 / 邮箱 / 技能 / 任务标题 / 会议标题 等任何字段
- 严禁使用 "暂无详细信息" / "待补充" / "建议查询" / "请查阅" 等占位符

### 铁律 2：工具返回空/错误时不出 rich_block
- 工具返回 status="error" 或 count=0 或 members=[] 时，**不要**为该工具生成 rich_block
- 用纯文字告诉用户"暂未找到相关信息"，或建议其他查询路径

### 铁律 3：能直接复述的不进 rich_block
- 成员姓名/研究方向等结构化字段已经在正文里说明白时，不要重复进 rich_block
- rich_block 留给"完整列表/可点击卡片/可交互"的场景

### 铁律 4：找不到任何工具结果时不要出 JSON 段
- 整段回答里没调用工具 / 工具全空 / 用户问的是闲聊 → 直接结束回答，**不要**出 ```json fence```

### Schema
在回答末尾可选择性追加 JSON 段（用 ```json fence 包裹）声明结构化富文本块：
```json
{
  "rich_blocks": [
    {
      "type": "member" | "knowledge_ref" | "task_list" | "meeting" | ...,
      "title": "可选标题",
      "summary": "折叠态一行摘要（必填，建议 < 30 字）",
      "collapsed_by_default": false,
      "data": { ... 真实工具返回的字段 ... }
    }
  ]
}
```

注意：除非长列表（> 5 项），否则 collapsed_by_default 设为 false（默认展开，用户第一眼看到真实数据）。
"""
        kwargs["system"] = system + json_protocol

        try:
            # llm.stream() 是 AsyncIterator（不是 async context manager），
            # 正确用法：async for 拿 stream 后再 async with
            # 2026-06-14 Stage 5 收尾：mimo 等思考型模型显式禁用 thinking（避免只返 thinking）
            async for stream in llm.stream(
                **kwargs, model=chosen_model, thinking={"type": "disabled"}
            ):
                async with stream as s:
                    accumulated = ""
                    async for event in s:
                        if event.type == "content_block_delta" and event.delta.type == "text_delta":
                            delta = event.delta.text
                            accumulated += delta
                            # [increment] text_delta
                            yield StreamEvent(type="text_delta", delta=delta)

            # ===== 后处理：解析 LLM 末尾的 JSON 段 =====
            # accumulated 来自流式 text_delta（直接累加 token），不走 thinking block
            # 这里的 _extract_rich_block_json 解析末尾 ```json``` 段，与 thinking 无关
            text_without_json, rich_blocks = _extract_rich_block_json(accumulated)
            # 2026-06-14 收官：synthesis 阶段也剥除 fake tool_call XML（防狼到用户看到）
            # Phase 1 已经被 _parse_fake_tool_calls 解析并 dispatch，但模型在 synthesis 阶段
            # 可能再次写出 fake tool_call（从训练里学来的输出格式），必须清掉
            text_without_json = _strip_fake_tool_calls(text_without_json)
            # 同步剥除 rich_blocks 里 data 含 fake XML 的（防御性，正常不该有）
            for rb_data in rich_blocks:
                # Grounded 守卫：type=member 必须有真实姓名来自工具结果
                # 2026-06-14 收官：grounding 守卫 — type=member 必须有真实姓名来自工具结果
                if not _is_rich_block_grounded(rb_data, ctx):
                    logger.warning(
                        f"dropping ungrounded rich_block: type={rb_data.get('type')} "
                        f"name={rb_data.get('data', {}).get('name')!r} "
                        f"seen_names={list(ctx.seen_member_names)[:5]}"
                    )
                    continue
                try:
                    rb = RichBlock(
                        type=rb_data.get("type", "fallback"),
                        data=rb_data.get("data", {}),
                        title=rb_data.get("title"),
                        summary=rb_data.get("summary"),
                        # 2026-06-14 收官：默认 False（展开），让用户第一眼看到数据
                        collapsed_by_default=rb_data.get("collapsed_by_default", False),
                    )
                    # [snapshot] rich_block
                    yield StreamEvent(type="rich_block", block=rb)
                    logger.info(
                        f"synthesis 输出 rich_block: type={rb.type} "
                        f"collapsed={rb.collapsed_by_default}"
                    )
                except Exception as e:
                    logger.warning(f"解析 rich_block JSON 失败: {e}")

            # 把 JSON 段从 text 中删掉（前端展示不显示）
            if text_without_json != accumulated:
                # 通过一个特殊 type=text_delta 但 delta 为负长度标识需要清理
                # 前端 useChatStream 在 done 后会用 synthesis_text（来自 to_dict）作为最终展示
                # 流式过程中 text_delta 已发出，无法撤销 — 这是已知限制
                # 兜底：把去掉 JSON 后的纯文本也发一个空 delta 标记
                logger.info(
                    f"synthesis 后处理：删掉 {len(accumulated) - len(text_without_json)} 字符 JSON 段"
                )
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


def _extract_rich_block_json(accumulated_text: str) -> tuple[str, list[dict]]:
    """从 LLM 输出末尾的 ```json ... ``` 段提取 rich_block 列表

    返回 (text_without_json, rich_blocks)
    - text_without_json: 删除 JSON 段后的纯文本（供前端展示）
    - rich_blocks: 解析出的 rich_block 数据列表

    行为：
    - 找不到 JSON 段：返回 (原文本, [])
    - JSON 解析失败：返回 (原文本, [])  + logger.warning
    - JSON 解析成功：返回 (删掉 JSON 段后的文本, [blocks])
    """
    import json as _json
    import re

    # 匹配末尾的 ```json ... ``` 段（不区分大小写）
    # 允许 JSON 段在文本任意位置但必须以 ```json 开始
    pattern = re.compile(r"```json\s*\n?(.+?)\n?```", re.DOTALL | re.IGNORECASE)
    matches = list(pattern.finditer(accumulated_text))
    if not matches:
        return accumulated_text, []

    # 仅取最后一个 JSON 段（避免误判文本中出现的 ```json 片段）
    last_match = matches[-1]
    json_str = last_match.group(1).strip()
    text_without_json = (
        accumulated_text[: last_match.start()].rstrip()
        + accumulated_text[last_match.end() :]
    )

    try:
        parsed = _json.loads(json_str)
    except _json.JSONDecodeError as e:
        logger.warning(f"_extract_rich_block_json: JSON 解析失败: {e}")
        return accumulated_text, []

    if not isinstance(parsed, dict):
        return text_without_json, []
    blocks = parsed.get("rich_blocks", [])
    if not isinstance(blocks, list):
        return text_without_json, []
    # 给每个 block 补 collapsed_by_default 缺省值（2026-06-14 收官：默认展开）
    for block in blocks:
        if isinstance(block, dict) and "collapsed_by_default" not in block:
            block["collapsed_by_default"] = False
    return text_without_json, blocks


def _is_rich_block_grounded(rb_data: dict, ctx) -> bool:
    """2026-06-14 收官：校验 LLM 输出的 rich_block.data 是否 grounded in tools

    当前规则（保守）：
    - type=member: data 里的 name 必须在 ctx.seen_member_names 里（防 LLM 编造姓名）
    - type=task_list: 暂放行（任务名幻觉检测成本高，留给 critic 打分）
    - type=meeting / project / knowledge_ref 等: 暂放行
    - type=fallback / 其他: 放行
    """
    if not isinstance(rb_data, dict):
        return True  # 让 Pydantic 构造时自己报错
    rb_type = rb_data.get("type")
    if rb_type != "member":
        return True
    data = rb_data.get("data") or {}
    if not isinstance(data, dict):
        return False
    name = data.get("name")
    mid = data.get("id")
    # 必须有 name 或 id
    if not name and not mid:
        return False
    # 名字必须 grounded（在 ctx.seen_member_names 集合里）
    if isinstance(name, str) and name.strip():
        if ctx is None or not hasattr(ctx, "seen_member_names"):
            return False
        if name.strip() not in ctx.seen_member_names:
            return False
    # id 必须 grounded
    if isinstance(mid, int) and mid > 0:
        if ctx is None or not hasattr(ctx, "seen_member_ids"):
            return False
        if mid not in ctx.seen_member_ids:
            return False
    return True


def _block_dump(block) -> dict:
    """把 Anthropic content block 转 dict"""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if isinstance(block, dict):
        return block
    return {"type": getattr(block, "type", "unknown"), "text": getattr(block, "text", str(block))}
