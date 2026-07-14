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
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.protocol import RichBlock, StreamEvent
from app.agent.result_compressor import (
    CompressionResult,
    compression_to_sse_event,
    compress_tool_result,
    inject_compressed_to_messages,
)
from app.agent.tool_registry import (
    ToolContext,
    ToolNotFoundError,
    dispatch_tool,
    get_all_tool_schemas,
)
from app.config import settings
from app.core.llm import LLMClient
# 2026-07-02 Phase I.3 取证 hook
from app.agent.llm_input_dumper import maybe_dump

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


def _build_plan_step_input(tool_name: str, intent, messages: list[dict]) -> dict:
    """Phase 0: 基于 intent.keywords 智能补全 tool input (#041)

    规则 (按优先级):
    1. 工具无必填字段 → {}
    2. 工具有必填 query 类字段 (query / keyword / search_text / q / text / search) → intent.keywords[0] 或 _last_user_text(messages)
    3. 工具有必填 name 类字段 → intent.keywords[0] (允许 None 让 Pydantic 报错暴露给前端)
    4. 其他必填字段 → {} (让 Pydantic 报错, 优雅降级, 不假数据)

    设计原则:
    - 不假数据: 宁可 Pydantic 报错让前端看到 status=error, 也不要 LLM 凭"想当然"填假值
    - 不读 ctx 注入字段: user_id / channel_user_id / ctx 是 dispatcher 自动注入, 不能出现在 input 里
    """
    from app.agent.tool_registry import TOOL_REGISTRY

    td = TOOL_REGISTRY.get(tool_name)
    if not td:
        return {}
    fields = td.input_model.model_fields
    required_fields = [
        fname for fname, finfo in fields.items()
        if finfo.is_required() and fname not in {"user_id", "channel_user_id", "ctx"}
    ]
    if not required_fields:
        return {}

    query_field_names = {"query", "keyword", "search_text", "q", "text", "search"}
    name_field_names = {"name", "member_name", "task_name", "formula_name"}

    # 优先用 keywords[0], fallback _last_user_text (前 50 字符)
    keyword = (
        intent.keywords[0] if intent.keywords else _last_user_text(messages)[:50]
    )

    for rf in required_fields:
        if rf in query_field_names:
            return {rf: keyword}
        if rf in name_field_names:
            return {rf: keyword}
        # 其他必填字段返回空 (让 Pydantic 报错)
        return {}
    return {}


# 概念问 4 域 → 4 tool 硬下限 (#042 - 2026-06-28 chat agent 架构级集成)
# 对齐 prompts.py _CROSS_DOMAIN_SYNTHESIS_SECTION 章节顺序 (知识 → 公式 → 假设 → 成员)
# 与 #086 prompt 软规则协同: prompt 让 LLM 写"4 域综合", 代码保证 context 全
CONCEPT_DOMAIN_TOOLS: tuple[str, ...] = (
    "search_knowledge",   # 知识域
    "list_formulas",      # 公式域
    "list_hypotheses",    # 假设域
    "query_members",      # 成员域
)


def _expand_concept_to_four_domain(planned: list[str]) -> list[str]:
    """explain_concept 4 域代码强制 fan-out (#042)

    规则:
      1. 保留 planned 原顺序 + 原 tool (不删 LLM 已 planned 的, 包括非 4 域 tool)
      2. 追加缺失的 4 域 tool, 按 CONCEPT_DOMAIN_TOOLS 顺序补
      3. P2-3 fix (2026-07-08): 截断时**优先保留 4 域 tool**, 非 4 域被砍.
         之前实现: 简单 slice [:MAX], 当 LLM planned 6 个工具时按原顺序砍第 6 个,
         可能砍掉 query_members (4 域) 而保留 LLM 最后选的 get_meeting_transcript.
         修复: 4 域工具永远在结果前部, 截断时优先保留.
      4. 返回新 list (不修改原参数)

    示例:
      planned=['search_knowledge']
        → 4 域前移: [search_k, list_f, list_h, query_m] = 4
      planned=['search_knowledge', 'get_meeting_transcript']
        → 4 域前移: [list_f, list_h, query_m, search_k, get_meeting_transcript] = 5 (get_meeting 在尾)
      planned=['search_knowledge', 'list_formulas', 'query_members']
        → 4 域前移: [list_f, list_h, query_m, search_k] = 4 (search_k 排尾)
      planned=['a', 'b', 'c', 'd', 'e', 'f'] (6 个非 4 域)
        → 4 域前移: [search_k, list_f, list_h, query_m, a] = 5 (b/c/d/e/f 砍, 4 域全保)

    不变量:
      - len(result) ≤ AGENT_PLAN_STEP_MAX
      - **4 域 tool 全部保留** (除非 LLM 已 planned 5+ 个 4 域 tool)
      - 原 planned 中非 4 域 tool 优先被砍 (4 域优先)
    """
    planned_set = set(planned)
    expanded = list(planned)
    for tool in CONCEPT_DOMAIN_TOOLS:
        if tool not in planned_set:
            expanded.append(tool)
    # P2-3 fix: 把 4 域工具移到前部, LLM planned 的非 4 域保留在尾部 (按 LLM 顺序).
    # 截断 [:MAX] 时优先保留前部 (4 域), 尾部非 4 域被砍.
    four_domain = [t for t in expanded if t in CONCEPT_DOMAIN_TOOLS]
    others = [t for t in expanded if t not in CONCEPT_DOMAIN_TOOLS]
    return (four_domain + others)[: settings.AGENT_PLAN_STEP_MAX]


def _extract_tool_uses(response) -> list[dict]:
    """从 LLM 响应中提取 tool_use 列表

    2026-06-14 收官: 双路径解析
    - 路径 A: 原生 tool_use blocks (代理正确转发 tools 参数时)
    - 路径 B: 模型在 content 里 fake 输出 XML 格式 (代理吞掉 tools 参数时) —
      解析 <function_calls>/<tool_call> 等多种格式, 转成 tool_use 走后续流程

    2026-07-02 Phase I.0 backend dispatch 修复: 兼容 Pydantic model (anthropic)
    + dict (openai_compat via openai_response_to_anthropic_message) 两种返回类型
    """
    tool_uses = []
    # 兼容 Pydantic model + dict 两种返回
    def _block_get(block, key, default=None):
        if isinstance(block, dict):
            return block.get(key, default)
        return getattr(block, key, default)

    content = _block_get(response, "content", []) or []
    # 路径 A: 原生 tool_use blocks
    for block in content:
        if _block_get(block, "type") == "tool_use":
            tool_uses.append({
                "id": _block_get(block, "id", ""),
                "name": _block_get(block, "name", ""),
                "input": _block_get(block, "input", {}) or {},
            })
    if tool_uses:
        return tool_uses

    # 路径 B: 从 text block 里解析 fake tool_call XML
    text_parts = []
    for block in content:
        block_text = _block_get(block, "text", "")
        if block_text:
            text_parts.append(block_text)
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


# 元话语前缀模式（2026-06-15 修复，防御 LLM 在正文里写 thinking 独白）
_META_PREFIX_PATTERNS = [
    r"我需要[把将按]?",  # "我需要介绍..." / "我将..." / "我需要按..."
    r"我应该[把将]?",
    r"我会[把将]?",
    r"我要[把将]?",
    r"我先[来按]?",
    r"用户问的?[是什]?",
    r"用户想知道",
    r"用户可能想[要知道]?",
    r"开始回答吧",
    r"现在我需要",
    r"现在让我",
    r"现在[，,]我来",
    r"那么[，,]",
    r"好的[，,。 ]?我来回答",
    r"好的[，,。 ]?让我",
    r"让我[先来整组]?",  # "让我先..." / "让我整理..." / "让我组织..."
    r"首先我需要",
    r"让我整理[一]?下",
    r"让我组织[一]?下[回答]*",
    r"工具返回了",
    r"工具返回[成功后]*",
    r"根据工具返回",
    r"从工具返回来看",
    r"经过思考",
    r"思考后",
    r"经过分析",
    r"按照[一]?[下个]?Synthesis Output Discipline[的，, ]?[要求]*",
    r"现在按照",
    r"现在[，,]?先写",
    r"先写文本[摘回]",
]


def _strip_meta_thinking(text: str) -> str:
    """2026-06-15 修复：剥除 LLM 在正文里写的 thinking/元话语独白

    触发场景：即使 prompts.py 已加硬规则，LLM 偶尔仍会输出：
    "用户问的是 X。我需要介绍她的基本信息。从工具返回来看，她的研究方向是 Y。开始回答吧。X 是我们的成员..."

    剥除策略：
    - 在 text 里**只剥开头的元话语**（前 800 字符范围内）—— 不影响正文中间的元话语引用
    - 每次匹配到元话语句 → 删掉那个元话语开头的句子（到下一个 "。" 句号为止）
    - 最多剥除 3 次（防无限循环）—— 使用 while 循环（不是 for），
      每次剥完重新检测新开头是否还有元话语
    - 不剥除正常回复里的 "我建议" / "我认为" 等**实质**第一人称表达

    边界情况：
    - 如果整段都是元话语（用户看到空文本）→ 保留原文（兜底）
    - 如果剥除后剩余 < 30 字符 → 保留原文（兜底）
    """
    import re
    if not text or len(text) < 10:
        return text

    # 只检查前 800 字符内的元话语
    head = text[:800]
    rest = text[800:]

    new_head = head
    stripped_count = 0
    max_strip = 3

    # 关键：while 而非 for —— 每次剥完重新检测新开头是否还有元话语
    while stripped_count < max_strip:
        matched = False
        for pattern in _META_PREFIX_PATTERNS:
            m = re.match(
                r"^(" + pattern + r")[^。]*?。\s*",
                new_head.lstrip(),
            )
            if m:
                stripped = m.group(0)
                new_head = new_head.lstrip()[len(stripped):]
                stripped_count += 1
                matched = True
                break  # 跳出内层 for，重新 while 检测新开头
        if not matched:
            break  # 没匹配到任何 pattern，退出

    result = new_head + rest
    # 清理残留前导空白
    result = result.lstrip()

    # 兜底：剥除后过短 → 保留原文
    # 但不能把"整个文本都是元话语"的情况也兜底回去（会泄露元话语）
    # 判断：剥除后只剩标点/空白 → 说明原文全是元话语 → 返回空串
    #        剥除后有少量实质内容（如"赵航佳是成员。"）→ 保留
    if stripped_count > 0:
        # 去掉标点和空白后看剩余长度
        meaningful = result.strip().rstrip("。，、；！？ \n\t")
        if len(meaningful) < 2:
            # 全是元话语，不要兜底回原文
            return ""

    return result


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


# ============================================================================
# 2026-07-13 #P1: 三档推理模式 helper (MagicMock truthy 但属性不是合法 Literal — 用 isinstance 守卫)
# ============================================================================
from app.agent.thinking_config import ThinkingConfig as _TC


def _has_thinking_config(ctx) -> bool:
    """安全判断 ctx.thinking_config 是不是真 ThinkingConfig 实例。

    普通 ctx 走 True 分支;测试用 MagicMock ctx 走 False 分支,避免 StreamEvent Literal 校验炸测试。
    """
    return isinstance(getattr(ctx, "thinking_config", None), _TC)


class AgenticLoop:
    """真正的多轮工具循环 + 流式综合 + Reflection"""

    def __init__(self):
        pass  # 全部通过 ctx 注入（铁律 1）

    async def _run_self_rag_gate(
        self,
        user_message: str,
        tool_calls: list[dict],
        plan_step_results: list[dict],
        messages: list[dict],
        intent: IntentResult,
        ctx: ToolContext,
        # 2026-07-13 #P1: 三档 mode — max_reretrieve 可 per-call 覆盖 (deep 模式 2 次, balanced/fast 用 settings 默认)
        max_reretrieve: Optional[int] = None,
    ) -> AsyncIterator[StreamEvent]:
        """2026-06-30 #009 Self-RAG Phase 0.5 gate

        评估 plan_step 阶段 search_knowledge 检索质量.
        低质量时改写 query 重检索, 最多 settings.AGENT_SELF_RAG_MAX_RERETRIEVE 次 (deep 模式可 per-call 覆盖为 2).
        每次重检索 yield tool_use + tool_result + messages.append 配对 (CLAUDE.md 2026-06-14 铁律: 必须 balanced).
        """
        from app.services.self_rag import (
            get_context_compressor,
            get_self_rag_checker,
        )

        # 1. 提取 plan_step 里 search_knowledge 工具结果
        search_k_results: list[dict] = []
        for tc in tool_calls:
            if tc.get("name") == "search_knowledge":
                output = tc.get("output")
                if isinstance(output, dict) and output.get("status") == "success":
                    for r in output.get("results", []):
                        if isinstance(r, dict):
                            search_k_results.append(r)

        if not search_k_results:
            return  # 没 search_knowledge 调过, gate 无意义

        # 2. 限定 doc 数 (避免单轮太多 doc 把 judge 撑爆)
        max_docs = settings.AGENT_SELF_RAG_MAX_CONTEXT_DOCS
        if len(search_k_results) > max_docs:
            search_k_results = search_k_results[:max_docs]

        # 3. 压缩成 judge 用的 context 字符串
        compressor = get_context_compressor()
        judge_model = (
            settings.AGENT_SELF_RAG_MODEL
            if settings.AGENT_SELF_RAG_MODEL
            else settings.AGENT_REFLECTION_MODEL
        )
        checker = get_self_rag_checker()
        reretrieve_count = 0
        refined_queries: list[str] = []
        final_assessment: dict = {}
        # 4. Phase 0.5 循环: 每次重检索后再 judge (最多 MAX 次)
        while True:
            compressed = await compressor.compress(user_message, search_k_results)
            if compressed == "知识库中暂无相关内容。":
                # 检索没结果, judge 默认通过即可, 不浪费 LLM call
                break

            assessment = await checker.check_relevance(
                user_message, compressed, model=judge_model
            )
            confidence = assessment.get("confidence", 0.0)
            can_answer = assessment.get("can_answer", False)
            final_assessment = assessment

            # 5. 决策: 通过 / 重检索 / 强制退出
            # W4 T3.4: 3-tier 分级 (高≥0.8 直接出 / 中≥0.6 不重检索 / 低<0.4 触发重检索)
            HIGH_CONFIDENCE = 0.8
            tier = "unknown"
            if confidence >= HIGH_CONFIDENCE:
                # 高置信度: 直接出, 跳过 RAG reretrieve
                tier = "high"
                logger.info(f"✅ [self_rag] high_confidence={confidence:.2f} (≥{HIGH_CONFIDENCE}), skip reretrieve")
            elif confidence >= settings.AGENT_SELF_RAG_THRESHOLD:
                # 中高置信度 (>= 0.6): 跳出
                tier = "mid_high"
                logger.info(f"✓ [self_rag] mid_high_confidence={confidence:.2f} (≥{settings.AGENT_SELF_RAG_THRESHOLD})")
            elif can_answer and confidence >= settings.AGENT_SELF_RAG_RELAXED_THRESHOLD:
                # 中置信度 (>= 0.4) + can_answer: 跳出
                tier = "mid"
                logger.info(f"~ [self_rag] mid_confidence={confidence:.2f} can_answer=True, accept anyway")
            else:
                # 低置信度: 触发重检索 (除非已达上限)
                tier = "low"
                if reretrieve_count >= (max_reretrieve if max_reretrieve is not None else settings.AGENT_SELF_RAG_MAX_RERETRIEVE):
                    logger.warning(
                        f"🛑 [self_rag] max_reretrieve_reached: query='{user_message[:50]}...' "
                        f"final_confidence={confidence:.2f} attempts={reretrieve_count+1}"
                    )
                    tier = "low_max_reached"
                else:
                    logger.info(f"↻ [self_rag] low_confidence={confidence:.2f}, triggering reretrieve #{reretrieve_count+1}")
                    # [snapshot] retrieval_assessment (重检索前先报告当前评估)
                    yield StreamEvent(
                        type="retrieval_assessment",
                        retrieval={
                            "phase": "assessment",
                            "confidence": confidence,
                            "can_answer": can_answer,
                            "missing": assessment.get("missing", ""),
                            "reason": assessment.get("reason", ""),
                            "reretrieved": False,  # W4 T3.4: 还未真正 reretrieve
                            "attempt": reretrieve_count,
                            "tier": tier,
                            "latency_ms": assessment.get("latency_ms", 0),
                        },
                    )
                    # 继续循环, 进入重检索流程 (注意: break/continue 由外层 for 控制)
            # 决策标记结束, 继续到外层循环
            # 跳出内层: 如果是高/中/中低, 我们退出 Self-RAG; 如果是 low, 外层 for 继续
            if tier in ("high", "mid_high", "mid", "low_max_reached"):
                break
            # 否则 tier == "low" 且未到 max, 继续外层 for
            # 不 break, 但需要在重检索前计算 refined_query (W4 T3.4 集成)
            refined_query = checker.refine_query(
                user_message, assessment.get("missing", ""), intent.keywords
            )
            refined_queries.append(refined_query)

            # [snapshot] retrieval_assessment
            yield StreamEvent(
                type="retrieval_assessment",
                retrieval={
                    "phase": "assessment",
                    "confidence": confidence,
                    "can_answer": can_answer,
                    "missing": assessment.get("missing", ""),
                    "reason": assessment.get("reason", ""),
                    "reretrieved": True,
                    "attempt": reretrieve_count,
                    "tier": tier,
                    "latency_ms": assessment.get("latency_ms", 0),
                },
            )

            # [snapshot] reretrieval
            yield StreamEvent(
                type="reretrieval",
                retrieval={
                    "phase": "reretrieval",
                    "refined_query": refined_query,
                    "attempt": reretrieve_count,
                },
            )

            # 7. 调 search_knowledge 重检索
            tool_use_id = f"reretrieve_{reretrieve_count}_search_knowledge"
            input_payload = {"query": refined_query}
            yield StreamEvent(
                type="tool_use",
                tool_name="search_knowledge",
                tool_use_id=tool_use_id,
                tool_input=input_payload,
            )
            try:
                new_result = await dispatch_tool("search_knowledge", input_payload, ctx)
            except Exception as e:
                logger.error(f"self_rag reretrieve {reretrieve_count} failed: {e}", exc_info=True)
                new_result = {
                    "status": "error",
                    "code": "TOOL_EXECUTION_ERROR",
                    "message": str(e),
                }
            yield StreamEvent(
                type="tool_result",
                tool_name="search_knowledge",
                tool_use_id=tool_use_id,
                tool_output=new_result if isinstance(new_result, dict) else {"result": str(new_result)},
            )

            # 8. 合并到 messages + tool_calls + plan_step_results
            new_content = json.dumps(new_result, ensure_ascii=False, default=str)
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": f"[Self-RAG 重检索 #{reretrieve_count}] 使用改写 query 重检索"}],
            })
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": new_content,
                }],
            })
            tool_calls.append({
                "name": "search_knowledge",
                "input": input_payload,
                "output": new_result,
            })
            plan_step_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": new_content,
            })

            # 9. 更新 search_k_results (合并去重, 按 rerank_score 降序)
            new_results = []
            if isinstance(new_result, dict) and new_result.get("status") == "success":
                new_results = new_result.get("results", []) or []
            existing_ids = {r.get("id") for r in search_k_results if r.get("id") is not None}
            for r in new_results:
                if isinstance(r, dict) and r.get("id") not in existing_ids:
                    search_k_results.append(r)
                    existing_ids.add(r.get("id"))
            search_k_results.sort(
                key=lambda r: r.get("rerank_score") or r.get("normalized_score") or 0,
                reverse=True,
            )
            if len(search_k_results) > max_docs:
                search_k_results = search_k_results[:max_docs]

            reretrieve_count += 1

        # 10. 出口: yield 最终 retrieval_assessment
        yield StreamEvent(
            type="retrieval_assessment",
            retrieval={
                "phase": "assessment",
                "confidence": final_assessment.get("confidence", 0.0),
                "can_answer": final_assessment.get("can_answer", True),
                "missing": final_assessment.get("missing", ""),
                "reason": final_assessment.get("reason", ""),
                "reretrieved": reretrieve_count > 0,
                "attempt": reretrieve_count,
                "latency_ms": final_assessment.get("latency_ms", 0),
            },
        )

        # 11. 持久化到 trace
        if ctx.trace is not None:
            try:
                ctx.trace.set_retrieval_quality(
                    score=final_assessment.get("confidence", 0.0),
                    attempts=reretrieve_count,
                )
            except Exception as e:
                logger.warning(f"set_retrieval_quality failed: {e}")

    async def run(
        self,
        messages: list[dict],
        system: str,
        intent: IntentResult,
        ctx: ToolContext,
        max_rounds: Optional[int] = None,
        user_message: str = "",  # 2026-06-30 #009: Self-RAG gate 用, 留空时降级为不跑 gate
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

        2026-07-02 Round 5a 修复：整个生成器外包 try/finally 兜底保证 done event 至少
        yield 一次。否则 CancelledError / Exception 路径只 raise 不 yield done → 前端
        useChatStream.ts:638 text_without_json 替换逻辑不跑 → fake XML 永久泄露
        → qa-bench runner 检测到 stream_no_done 触发 FAIL。
        """
        # 2026-07-13 #P1: deep 模式 rate limit (每用户每小时限 30 次, 防 DeepSeek-R1-Distill 满载)
        if _has_thinking_config(ctx) and ctx.thinking_config.mode == "deep":
            import time as _time
            now = _time.monotonic()
            # sliding window: 保留最近 1 小时
            if not hasattr(ctx, "deep_call_timestamps"):
                ctx.deep_call_timestamps = []
            ctx.deep_call_timestamps = [t for t in ctx.deep_call_timestamps if now - t < 3600]
            if len(ctx.deep_call_timestamps) >= settings.AGENT_THINKING_MODE_DEEP_RATE_LIMIT_PER_HOUR:
                logger.warning(
                    f"deep mode rate limit hit: user_id={ctx.user_id}, "
                    f"calls_in_last_hour={len(ctx.deep_call_timestamps)}"
                )
                yield StreamEvent(
                    type="error",
                    code="RATE_LIMIT_DEEP",
                    message=f"深度模式每小时限 {settings.AGENT_THINKING_MODE_DEEP_RATE_LIMIT_PER_HOUR} 次, 请稍后再试或切换平衡模式",
                    mode="deep",
                    model=ctx.thinking_config.model,
                )
                return  # 不继续执行
            ctx.deep_call_timestamps.append(now)

        if max_rounds is None:
            max_rounds = settings.AGENT_MAX_TOOL_ROUNDS

        # 2026-07-15 #P2: thinking_config.max_tool_rounds 覆盖 (fast 模式 = 0 直接跳过 tool loop)
        if _has_thinking_config(ctx):
            max_rounds = min(max_rounds, ctx.thinking_config.max_tool_rounds)
            logger.debug(
                f"[thinking_config] max_rounds clamped: "
                f"settings.AGENT_MAX_TOOL_ROUNDS={settings.AGENT_MAX_TOOL_ROUNDS} "
                f"thinking_config.max_tool_rounds={ctx.thinking_config.max_tool_rounds} "
                f"effective={max_rounds} mode={ctx.thinking_config.mode}"
            )

        llm = ctx.llm or LLMClient()
        accumulated_text = ""
        rich_blocks: list[RichBlock] = []
        tool_calls: list[dict] = []
        t0 = time.monotonic()
        done_event_yielded = False  # 2026-07-02 Round 5a: 标记 done 是否已 yield

        # 2026-07-02 Round 5a: 用 _run_inner 包内部逻辑，外层 try/finally 兜底
        async def _run_inner() -> AsyncIterator[StreamEvent]:
            nonlocal done_event_yielded
            async for evt in self._run_legacy(messages, system, intent, ctx, max_rounds, user_message,
                                             llm, t0=t0):
                if evt.type == "done":
                    done_event_yielded = True
                yield evt

        try:
            async for evt in _run_inner():
                yield evt
        finally:
            # 2026-07-02 Round 5a: 兜底保证 done event 一定 yield 一次
            # 适用场景: CancelledError / Exception / 任何提前退出的路径
            if not done_event_yielded:
                duration_ms = int((time.monotonic() - t0) * 1000)
                logger.warning(
                    f"agentic_loop run() 流被中断但 done 未 yield，兜底 yield minimal done event "
                    f"(duration_ms={duration_ms})"
                )
                yield StreamEvent(
                    type="done",
                    duration_ms=duration_ms,
                    session_id=ctx.trace.session_id if ctx.trace else None,
                    text_without_json=None,  # 无干净文本，前端不替换 content
                    # 2026-07-13 #P1: cancelled 兜底也带 mode/model
                    mode=(ctx.thinking_config.mode if _has_thinking_config(ctx) else "balanced"),
                    # 从 ctx 推导 model (chosen_model 在 _synthesize_stream 内, finally 不可见)
                    model=(
                        ctx.thinking_config.model
                        if _has_thinking_config(ctx)
                        else (settings.AGENT_SYNTHESIS_MODEL or settings.CLAUDE_MODEL or "mimo-v2.5")
                    ),
                )

    async def _run_legacy(
        self,
        messages: list[dict],
        system: str,
        intent: IntentResult,
        ctx: ToolContext,
        max_rounds: int,
        user_message: str,
        llm,
        t0: float,
    ) -> AsyncIterator[StreamEvent]:
        """2026-07-02 Round 5a: 原始 run() 逻辑重构到内部方法

        所有原代码不变，仅 try/except/finally 块稍作调整（最外层已包 try/finally）。
        """
        accumulated_text = ""
        rich_blocks: list[RichBlock] = []
        tool_calls: list[dict] = []
        t0 = time.monotonic()

        try:
            # ===== Phase 0: 强制 plan_step (#041 - 2026-06-28 chat agent 架构级集成) =====
            # Haiku 输出的 suggested_tools → agentic_loop 主动 dispatch (代码层强制, 不靠 LLM)
            # 仅 deep intent 走 Phase 0: search_info / explain_concept / team_overview
            # (data_query / execute_action / recommend_person / casual_chat 跳过, 避免误调)
            # feature flag AGENT_PLAN_STEP_ENABLED 控制总开关
            # 2026-07-15 #P2: fast mode (thinking_config.skip_plan_step=True) 跳过, 节省 0.5-7.5s
            # 2026-07-15 #P2: 新增 team_overview → 强制 query_members + list_projects + search_knowledge 三件套
            if (not (_has_thinking_config(ctx) and ctx.thinking_config.skip_plan_step)
                and settings.AGENT_PLAN_STEP_ENABLED
                and intent.category in {
                    IntentCategory.SEARCH_INFO,
                    IntentCategory.EXPLAIN_CONCEPT,
                    IntentCategory.TEAM_OVERVIEW,  # 2026-07-15 #P2 新增
                }
                and intent.suggested_tools
                and intent.confidence >= settings.AGENT_PLAN_STEP_MIN_CONFIDENCE):
                # dedup (保留首次出现顺序) + 截断到 AGENT_PLAN_STEP_MAX
                planned = list(dict.fromkeys(intent.suggested_tools))[: settings.AGENT_PLAN_STEP_MAX]

                # ===== #042: explain_concept 4 域代码强制 fan-out =====
                # 仅 explain_concept + flag 开启时, 检测缺 4 域 → 强制补齐
                # (与 #086 prompt 软规则协同, prompt 让 LLM 写得好, 代码保证 context 全)
                if (settings.AGENT_CROSS_DOMAIN_FANOUT_ENABLED
                    and intent.category == IntentCategory.EXPLAIN_CONCEPT):
                    expanded = _expand_concept_to_four_domain(planned)
                    if len(expanded) > len(planned):
                        logger.info(
                            f"#042 fan-out: planned {len(planned)} → {len(expanded)} tools "
                            f"(added: {[t for t in expanded if t not in planned]})"
                        )
                        planned = expanded

                # [snapshot] plan_step pending (让前端先看到意图)
                yield StreamEvent(
                    type="plan_step",
                    step="phase0_plan",
                    plan_status="pending",
                    label=f"📋 准备执行计划 ({len(planned)} 个工具)...",
                )
                # [snapshot] plan_step running (启动第一个 tool 前)
                yield StreamEvent(
                    type="plan_step",
                    step="phase0_plan",
                    plan_status="running",
                    label=f"📋 执行计划中 (0/{len(planned)})...",
                )

                plan_step_results: list[dict] = []
                success_count = 0
                for idx, tool_name in enumerate(planned):
                    tool_use_id = f"plan_{idx:02d}_{tool_name}"

                    # 智能补全 tool input (基于 intent.keywords)
                    input_payload = _build_plan_step_input(tool_name, intent, messages)

                    # [snapshot] tool_use
                    yield StreamEvent(
                        type="tool_use",
                        tool_name=tool_name,
                        tool_use_id=tool_use_id,
                        tool_input=input_payload,
                    )

                    # dispatch (dispatch_tool 内置完整错误处理: ToolNotFoundError 会抛, 其他包成 dict)
                    try:
                        result = await dispatch_tool(tool_name, input_payload, ctx)
                    except ToolNotFoundError:
                        # LLM 输出非法工具名 → warning + 跳过, 不阻断 Phase 0
                        logger.warning(f"plan_step tool {tool_name} not found, skip")
                        yield StreamEvent(
                            type="plan_step",
                            step="phase0_plan",
                            plan_status="running",
                            label=f"⚠️ 工具 {tool_name} 不存在, 跳过",
                        )
                        continue
                    except Exception as e:
                        result = {"status": "error", "code": "TOOL_EXECUTION_ERROR", "message": str(e)}
                        logger.error(f"plan_step {tool_name} failed: {e}", exc_info=True)

                    # [snapshot] tool_result
                    yield StreamEvent(
                        type="tool_result",
                        tool_name=tool_name,
                        tool_use_id=tool_use_id,
                        tool_output=result if isinstance(result, dict) else {"result": str(result)},
                    )

                    # Rich Block 检测 (复用 Phase 1 同一函数)
                    rb = _extract_rich_block(tool_name, result)
                    if rb:
                        rich_blocks.append(rb)
                        yield StreamEvent(type="rich_block", block=rb)

                    tool_calls.append({"name": tool_name, "input": input_payload, "output": result})
                    plan_step_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
                    success_count += 1

                    # [snapshot] plan_step running (每个 tool 完成后更新进度)
                    yield StreamEvent(
                        type="plan_step",
                        step="phase0_plan",
                        plan_status="running",
                        label=f"📋 执行计划中 ({success_count}/{len(planned)})...",
                    )

                # 注入 messages (Anthropic tool_use 协议格式, 与 Phase 1 一致)
                # 关键: 每个 tool_result 是独立 block + tool_use_id 对应 (让 Phase 2 grounding 看得到)
                if plan_step_results:
                    messages.append({
                        "role": "assistant",
                        "content": [{
                            "type": "text",
                            "text": f"[计划阶段] 我已主动查询 {success_count} 个工具获取背景信息。",
                        }],
                    })
                    messages.append({"role": "user", "content": plan_step_results})

                # [snapshot] plan_step done
                yield StreamEvent(
                    type="plan_step",
                    step="phase0_plan",
                    plan_status="done",
                    label=f"📋 计划完成 ({success_count}/{len(planned)})",
                )

                # ===== Phase 0.5: Self-RAG Retrieval Gate (#009 - 2026-06-30) =====
                # plan_step 完成后, 用 Haiku judge 评估检索质量.
                # 低质量时改写 query 重检索 (最多 AGENT_SELF_RAG_MAX_RERETRIEVE 次, 默认 1).
                # 双层控制: ctx.self_rag_enabled (per-request, 用户 toggle) > settings.AGENT_SELF_RAG_ENABLED (全局).
                # 2026-07-13 #P1: 三档 mode — thinking_config 优先级最高, per-request 全包覆盖
                if _has_thinking_config(ctx):
                    self_rag_active = ctx.thinking_config.self_rag_enabled
                    self_rag_max_reretrieve = ctx.thinking_config.self_rag_max_reretrieve
                else:
                    self_rag_active = (
                        ctx.self_rag_enabled
                        if ctx.self_rag_enabled is not None
                        else settings.AGENT_SELF_RAG_ENABLED
                    )
                    self_rag_max_reretrieve = settings.AGENT_SELF_RAG_MAX_RERETRIEVE
                if self_rag_active and intent.category in {IntentCategory.SEARCH_INFO, IntentCategory.EXPLAIN_CONCEPT}:
                    async for gate_evt in self._run_self_rag_gate(
                        user_message=user_message,
                        tool_calls=tool_calls,
                        plan_step_results=plan_step_results,
                        messages=messages,
                        intent=intent,
                        ctx=ctx,
                        max_reretrieve=self_rag_max_reretrieve,  # 2026-07-13 #P1: 透传 mode-aware 重检索次数
                    ):
                        yield gate_evt

            # ===== Phase 1: 工具循环 =====
            for round_idx in range(max_rounds):
                try:
                    # 2026-07-02 Phase I.3 取证: dump LLM 真实输入 (DEBUG_DUMP_LLM_INPUT=1 启用)
                    maybe_dump(
                        messages=messages,
                        system=system,
                        tools=get_all_tool_schemas(),
                        model=getattr(settings, "AGENT_SYNTHESIS_MODEL", None)
                            or getattr(settings, "CLAUDE_MODEL", None)
                            or "mimo-v2.5",
                        phase_label=f"phase1-round{round_idx}",
                        extra={"intent_category": str(intent.category) if intent else "unknown"},
                    )
                    response = await llm.complete(
                        messages=messages,
                        system=system,
                        tools=get_all_tool_schemas(),
                        max_tokens=(ctx.thinking_config.max_tool_tokens if _has_thinking_config(ctx) else 500),
                        temperature=0.3,
                        # 2026-07-13 #P1: 透传 mode-aware model + thinking (None 时用 LLMClient 默认 fallback chain)
                        model=(ctx.thinking_config.model if _has_thinking_config(ctx) else None),
                        thinking=(ctx.thinking_config.thinking if _has_thinking_config(ctx) else None),
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

                    # 压缩（如触发条件满足）
                    compression: Optional[CompressionResult] = None
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
                # 2026-06-14 收官: strip 掉 response content 里的 fake tool_call XML,
                # 否则 Phase 2 synthesis 看到这种 pattern 会复制到最终输出 (fake_xml_leaked)
                # 2026-07-02 Phase I.0 修复: 兼容 Pydantic + dict 两种返回
                if isinstance(response, dict):
                    _resp_content = response.get("content", []) or []
                else:
                    _resp_content = getattr(response, "content", []) or []
                if not isinstance(_resp_content, list):
                    _resp_content = []
                cleaned_content = []
                for b in _resp_content:
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
                thinking_config=ctx.thinking_config,  # 2026-07-13 #P1: 透传
            ):
                if evt.type == "text_delta":
                    synthesis_text += evt.delta or ""
                elif evt.type == "rich_block" and evt.block:
                    synthesis_blocks.append(evt.block)
                    rich_blocks.append(evt.block)
                yield evt

            accumulated_text = synthesis_text

            # ===== Phase 3: Critique =====
            # 2026-07-15 #P2: fast mode (thinking_config.skip_critique=True) 跳过 critique + retry, 节省 0.5-3s
            critique_skipped = _has_thinking_config(ctx) and ctx.thinking_config.skip_critique
            if not critique_skipped:
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
            else:
                logger.debug("[thinking_config] skip_critique=True, skipping Phase 3 critique")

            # ===== Phase 4: Retry（如需） =====
            retry_count = 0
            while (
                not critique_skipped
                and should_retry(critique)
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
                    thinking_config=ctx.thinking_config,  # 2026-07-13 #P1: 透传
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

            # 2026-07-13 #P1 修复: final_text 在 try 内定义, except 块 (异常兜底) 引用会 UnboundLocalError
            # 提前初始化, 让 except 块安全访问 (L1360 `not final_text.strip()`)
            final_text = ""

            # ===== Phase 4.5: 在 done 之前重算 text_without_json（retry 后文本可能已变）=====
            # 2026-06-15 修复元话语泄露：把"剥除 JSON 段 + fake tool_call + 元话语"的最终干净文本
            # 传给前端，让前端在 done 时**替换** content（流式过程已发出无法撤销）
            # 流程：accumulated_text → 剥 JSON 段 → 剥 fake tool_call → 剥元话语
            # 与 _synthesize_stream 内部后处理**完全镜像**——必须保持一致
            final_text, _ = _extract_rich_block_json(accumulated_text)
            final_text = _strip_fake_tool_calls(final_text)
            pre_strip_len = len(final_text)
            final_text = _strip_meta_thinking(final_text)
            meta_was_stripped = len(final_text) < pre_strip_len  # 元话语被剥掉了

            # 2026-06-15 兜底：text 为空，或 text 被元话语剥除后只剩残片 → 用 rich blocks 生成摘要
            # 防 LLM synthesis 只输出 ```json[...]``` 或只输出 fake tool_call，正文为空
            # 两个来源：
            # - rich_blocks（Phase 1 工具结果，RichBlock 对象列表）
            # - synthesis_json_blocks（Phase 2 JSON 段解析，dict 列表）
            # 注意：fallback 文本不走 _strip_meta_thinking（它是服务端生成的，不是 LLM 元话语）
            # 触发条件：
            # 1. final_text 为空（LLM 没写正文）
            # 2. meta_was_stripped 且有 rich blocks（LLM 写了"工具返回了..."元话语，剥掉后只剩残片）
            if not final_text.strip() or (meta_was_stripped and rich_blocks):
                _, synthesis_json_blocks = _extract_rich_block_json(accumulated_text)
                all_rb = []
                if rich_blocks:
                    all_rb.extend(rb.model_dump() if hasattr(rb, "model_dump") else rb for rb in rich_blocks)
                if synthesis_json_blocks and isinstance(synthesis_json_blocks, list):
                    all_rb.extend(synthesis_json_blocks)
                if all_rb:
                    fallback = _summarize_rich_blocks_for_empty_text(all_rb)
                    if fallback:
                        logger.info(
                            f"Phase 4.5 兜底：synthesis text 为空但有 {len(all_rb)} 个 rich block，"
                            f"自动生成 {len(fallback)} 字摘要"
                        )
                        # 直接用 fallback 作为 final_text，不走 _strip_meta_thinking
                        # 因为 fallback 是服务端生成的结构化摘要，不是 LLM 的元话语
                        final_text = fallback
                    else:
                        logger.warning(
                            f"Phase 4.5 兜底：{len(all_rb)} 个 rich block 但摘要生成为空"
                        )
                else:
                    logger.warning(
                        f"Phase 4.5 兜底：synthesis text 为空且无 rich blocks"
                        f"（rich_blocks={len(rich_blocks)}，synthesis_json_blocks={len(synthesis_json_blocks) if synthesis_json_blocks else 0}）"
                    )

            # ===== Phase 5: done =====
            duration_ms = int((time.monotonic() - t0) * 1000)
            # 2026-07-13 #P1: 三档 mode 反馈字段 (run 主入口, chosen_model 是 _synthesize_stream 内部变量不可见)
            _tc = ctx.thinking_config if _has_thinking_config(ctx) else None
            _model = (
                _tc.model if _tc and _tc.model
                else (settings.AGENT_SYNTHESIS_MODEL or settings.CLAUDE_MODEL or "unknown")
            )
            yield StreamEvent(
                type="done",
                duration_ms=duration_ms,
                session_id=ctx.trace.session_id if ctx.trace else None,
                text_without_json=final_text,
                mode=(_tc.mode if _tc else "balanced"),
                model=_model,
                thinking_tokens_used=0,
                self_rag_reretrieve_count=0,
            )

        except asyncio.CancelledError:
            # 铁律 4：用户中断时 sanitize + 同步落库 + re-raise
            logger.warning("agentic_loop cancelled, sanitizing messages")
            _sanitize_pending_tool_uses(messages, reason="cancelled")
            raise  # 让上层 TraceCollector.__aexit__ 收到 exc_value 走同步落库
        except Exception as e:
            logger.error(f"agentic_loop failed: {e}", exc_info=True)
            # 2026-06-15 兜底：即使 synthesis 阶段失败（429/超时等），
            # 如果 Phase 1 工具结果有 rich blocks，仍生成文本摘要给用户
            # 防用户只看到空内容 + rich block 卡片
            if rich_blocks and not final_text.strip():
                rb_dicts = [rb.model_dump() if hasattr(rb, "model_dump") else rb for rb in rich_blocks]
                fallback = _summarize_rich_blocks_for_empty_text(rb_dicts)
                if fallback:
                    logger.info(f"异常兜底：{len(rich_blocks)} 个 rich block，自动生成 {len(fallback)} 字摘要")
                    yield StreamEvent(type="text_delta", delta=fallback)
                    yield StreamEvent(
                        type="done",
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        # 2026-07-13 #P1 修复: 异常兜底原本引用 ctx.trace, 但 _synthesize_stream 没 ctx 参数
                        # 改用 thinking_config 形参 (None 时回退 balanced)
                        session_id=None,
                        text_without_json=fallback,
                        mode=("deep" if thinking_config and thinking_config.mode == "deep" else (
                            "fast" if thinking_config and thinking_config.mode == "fast" else "balanced"
                        )),
                        model=(chosen_model or "unknown"),
                    )
                    return  # 兜底成功，不 raise
            yield StreamEvent(type="error", code="AGENTIC_LOOP_ERROR", message=str(e))
            raise

    async def _synthesize_stream(
        self,
        messages: list[dict],
        system: str,
        llm: LLMClient,
        # 2026-07-13 #P1: 三档 mode 反馈字段 (传 None 时 fallback balanced, 保持向后兼容)
        thinking_config=None,  # ThinkingConfig | None
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
        # 2026-07-13 #P1: 三档 mode — thinking_config 覆盖 settings 默认 (修复 synthesis_model_override 死代码)
        # _synthesize_stream 没 ctx 参数, 直接读 thinking_config 形参
        if thinking_config is not None:
            kwargs["max_tokens"] = thinking_config.max_tokens  # 覆盖 settings 默认
            chosen_model = thinking_config.model
        else:
            chosen_model = settings.AGENT_SYNTHESIS_MODEL or None  # 旧 behavior 向后兼容

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

### 铁律 5（2026-06-14 收官）：综合阶段禁止写工具调用
- 不要再写 `<function=...>...`、`<tool_call>{...}</tool_call>`、`<function_calls>...` 等任何"伪工具调用"语法
- 工具调用已在前面阶段完成，本阶段只负责把工具结果**组织成自然语言回复**
- 如果你发现自己在写 `<function` 开头的内容 → 停下来，直接用自然语言写正文

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
        # 2026-06-14 收官：检查本轮所有工具结果是否都为空
        # 如果是，注入显式"无可用数据"提示，逼模型不要 fake 写 tool_call，直接回答
        empty_tools = []
        for msg in messages[-6:]:  # 只看最后几轮
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict) and blk.get("type") == "tool_result":
                            inner = blk.get("content", "")
                            # 检查 tool_result 是否表示"无数据"
                            try:
                                inner_data = json.loads(inner) if isinstance(inner, str) else inner
                                if isinstance(inner_data, dict):
                                    count = inner_data.get("count", 0)
                                    if count == 0 or inner_data.get("status") == "error":
                                        empty_tools.append(blk.get("tool_use_id", "?"))
                            except Exception:
                                pass
        if empty_tools:
            kwargs["system"] = kwargs["system"] + (
                "\n\n## ⚠️ 数据缺失警告\n"
                f"本轮工具调用（{len(empty_tools)} 个）全部返回空/错误。**严禁**再次 fake 写工具调用语法，"
                "直接告诉用户：本地知识库和联网都没找到相关资料，**不要**编造。\n"
                "如果用户允许，可以把对话保存为新知识。"
            )

        try:
            # 2026-07-02 Phase I.3 取证: dump LLM 真实输入 (synthesis 阶段)
            maybe_dump(
                messages=messages,
                system=kwargs.get("system", ""),
                tools=None,  # Phase 2 没有 tools
                model=chosen_model or "unknown",
                phase_label="phase2-synth",
                extra={"round_idx": round_idx if "round_idx" in dir() else -1},
            )
            # llm.stream() 是 AsyncIterator（不是 async context manager），
            # 正确用法：async for 拿 stream 后再 async with
            # 2026-06-14 Stage 5 收尾：mimo 等思考型模型显式禁用 thinking（避免只返 thinking）
            async for stream in llm.stream(
                **kwargs,
                model=chosen_model,
                # 2026-07-13 #P1 修复: _synthesize_stream 没 ctx, 改读 thinking_config 形参
                thinking=(thinking_config.thinking if thinking_config is not None else {"type": "disabled"}),
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
            # 2026-06-15 修复：剥除 LLM 写在正文开头的元话语/thinking 文本
            # 即使 prompts.py 加了硬规则，LLM 偶尔仍会输出"我需要..."、"用户问的是..."、
            # "开始回答吧"等内部独白。后端兜底剥除，避免泄露到用户视野
            text_without_json = _strip_meta_thinking(text_without_json)
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

    # 2026-06-15 修复：text 为空但有 rich block → 自动从 rich block 生成文本摘要
    # 防 LLM 把所有内容都塞进 JSON 段，正文一个字不写，用户只看到 "👥 成员 1 人 ▸ 展开"
    if not text_without_json.strip() and blocks:
        fallback = _summarize_rich_blocks_for_empty_text(blocks)
        if fallback:
            logger.info(
                f"synthesis 兜底：text 为空但有 {len(blocks)} 个 rich block，"
                f"自动生成 {len(fallback)} 字摘要"
            )
            text_without_json = fallback

    return text_without_json, blocks


def _summarize_rich_blocks_for_empty_text(blocks: list) -> str:
    """当 LLM 只输出 rich block JSON 没写文本时，从 rich block 数据生成简洁摘要

    覆盖类型（2026-06-15 当前 12 类 Rich Block 中的高频 4 类）：
    - member: "找到 N 位成员：姓名1（方向1）、姓名2（方向2）..."
    - task_list: "有 N 个任务在进行中..."
    - meeting: "找到 N 个相关会议：标题1、标题2..."
    - knowledge_ref: "找到 N 篇相关知识..."

    其他类型（formula/hypothesis/transcript/chart/fallback/project_summary）：
    返回通用提示
    """
    if not blocks:
        return ""
    parts = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        bdata = block.get("data") or {}

        if btype == "member":
            members = bdata.get("members") or []
            if not members:
                parts.append("暂未找到相关成员")
                continue
            n = len(members)
            if n == 1:
                m = members[0]
                name = m.get("name", "")
                ra = m.get("research_area") or "未明确研究方向"
                parts.append(f"找到 1 位成员：**{name}**，研究方向是 **{ra}**")
            else:
                names_with_ra = []
                for m in members[:5]:
                    name = m.get("name", "")
                    ra = m.get("research_area") or "未明确"
                    names_with_ra.append(f"**{name}**（{ra}）")
                more = f"等共 {n} 位" if n > 5 else f"共 {n} 位"
                parts.append(f"找到 {more}：" + "、".join(names_with_ra))

        elif btype == "task_list":
            tasks = bdata.get("tasks") or []
            n = len(tasks)
            if not tasks:
                parts.append("暂未找到相关任务")
            else:
                parts.append(f"找到 {n} 个相关任务")

        elif btype == "meeting":
            meetings = bdata.get("meetings") or []
            n = len(meetings)
            if not meetings:
                parts.append("暂未找到相关会议")
            else:
                titles = [m.get("title", "") for m in meetings[:3] if m.get("title")]
                more = f"等共 {n} 个" if n > 3 else f"共 {n} 个"
                if titles:
                    parts.append(f"找到 {more}会议：" + "、".join(f"《{t}》" for t in titles))
                else:
                    parts.append(f"找到 {n} 个相关会议")

        elif btype == "knowledge_ref":
            refs = bdata.get("refs") or bdata.get("items") or []
            n = len(refs)
            if not refs:
                parts.append("暂未找到相关知识")
            else:
                parts.append(f"找到 {n} 篇相关知识")

        elif btype in ("formula", "hypothesis", "transcript", "chart", "fallback", "project_summary"):
            title = block.get("title") or "相关内容"
            parts.append(f"已为您整理：{title}")
        else:
            # 未知类型：给通用提示
            title = block.get("title") or "相关内容"
            parts.append(f"已为您整理：{title}")

    return "\n\n".join(parts) if parts else ""


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
