"""结果压缩器 — Agentic Loop 阶段 2（方案 C Stage 1）

设计要点：
- 工具结果超过 AGENT_COMPRESSION_THRESHOLD 条触发压缩（默认 5）
- 用 Haiku 调用（量大但浅，便宜快）
- 按工具名分流不同 prompt（query_members / search_knowledge / query_meetings / query_tasks）
- 压缩失败返回 None（不阻塞，主模型看原始结果）
- 注入到 messages 时附 <compressed reasoning="..."> 标签

跨进程安全（铁律 1）：
- llm 全部从 ctx.llm 拿，None 时调用方临时创建
- 不在模块顶部创建 LLMClient
"""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agent.intent_classifier import IntentResult
from app.agent.protocol import StreamEvent
from app.agent.tool_registry import ToolContext
from app.config import settings
from app.core.llm import LLMClient

logger = logging.getLogger("microbubble.agent.compressor")


class CompressionResult(BaseModel):
    """压缩结果"""
    selected: list[dict] = Field(default_factory=list)  # 筛选后的 top-N 条目
    reasoning: str  # 筛选标准说明
    original_count: int  # 原始条数
    selected_count: int  # 筛选后条数
    summary: str  # 折叠态一行摘要，如「成员推荐 3 人（27→3）」
    collapsed_by_default: bool = True  # LLM 决定（NICE TO HAVE 8b）


# 按工具名分流的 prompt 模板
_PROMPT_TEMPLATES: dict[str, str] = {
    "query_members": """你是相关度重排器。用户问题：{question}

下面是工具返回的 {n} 个成员（按研究方向匹配）：
{members_json}

从中筛选 {top_n} 个最相关的成员，返回 JSON：
{{
  "selected": [{{"id": int, "name": str, "research_area": str, "relevance": "1-2 句相关理由"}}],
  "reasoning": "筛选标准说明",
  "summary": "成员推荐 N 人（N→M）",
  "collapsed_by_default": true
}}
只输出 JSON，不解释。""",

    "search_knowledge": """你是相关度重排器。用户问题：{question}

下面是知识库返回的 {n} 条结果（按相关度排序）：
{results_json}

从中筛选 {top_n} 条最相关的知识条目，返回 JSON：
{{
  "selected": [{{"id": int, "title": str, "score": 0-1, "relevance": "1-2 句相关理由"}}],
  "reasoning": "筛选标准说明",
  "summary": "引用 N 条 / 共 M 条",
  "collapsed_by_default": true
}}
只输出 JSON，不解释。""",

    "query_meetings": """你是相关度重排器。用户问题：{question}

下面是工具返回的 {n} 场会议（按时间倒序）：
{meetings_json}

从中筛选 {top_n} 场最相关的会议，返回 JSON：
{{
  "selected": [{{"id": int, "title": str, "date": "YYYY-MM-DD", "relevance": "1-2 句相关理由"}}],
  "reasoning": "筛选标准说明",
  "summary": "会议 N 场",
  "collapsed_by_default": true
}}
只输出 JSON，不解释。""",

    "query_tasks": """你是相关度重排器。用户问题：{question}

下面是工具返回的 {n} 个任务：
{tasks_json}

从中筛选 {top_n} 个最相关的任务（按 priority + due_date 排序），返回 JSON：
{{
  "selected": [{{"id": int, "title": str, "status": str, "due_date": str, "relevance": "1-2 句相关理由"}}],
  "reasoning": "筛选标准说明",
  "summary": "任务 N 项（进行中 X · 待办 Y）",
  "collapsed_by_default": true
}}
只输出 JSON，不解释。""",
}

_DEFAULT_PROMPT = """你是相关度重排器。用户问题：{question}

下面是工具返回的 {n} 条数据（{tool_name}）：
{data_json}

从中筛选 {top_n} 条最相关的数据，返回 JSON：
{{
  "selected": [{{"id": int, "title": str, "relevance": "1-2 句相关理由"}}],
  "reasoning": "筛选标准说明",
  "summary": "数据 N 条 / 共 M 条",
  "collapsed_by_default": true
}}
只输出 JSON，不解释。"""


async def compress_tool_result(
    user_question: str,
    intent: IntentResult,
    tool_name: str,
    raw_result: dict,
    ctx: ToolContext,
) -> Optional[CompressionResult]:
    """压缩工具返回结果

    触发条件：raw_result 包含 > AGENT_COMPRESSION_THRESHOLD 条记录
    失败行为：返回 None（不阻塞，主模型看原始结果）
    """
    # 1. 提取数据列表
    items, key_name = _extract_items(raw_result)
    if not items or len(items) <= settings.AGENT_COMPRESSION_THRESHOLD:
        return None  # 数量少不压缩

    # 2. 选择 prompt 模板
    top_n = min(5, len(items) // 2 + 1)  # 压缩到一半或 5 条
    data_json = json.dumps(items[:50], ensure_ascii=False, default=str)  # 最多送 50 条避免 token 爆炸

    template = _PROMPT_TEMPLATES.get(tool_name, _DEFAULT_PROMPT)
    prompt = template.format(
        question=user_question,
        n=len(items),
        top_n=top_n,
        members_json=data_json,
        results_json=data_json,
        meetings_json=data_json,
        tasks_json=data_json,
        data_json=data_json,
        tool_name=tool_name,
    )

    # 3. LLM 调
    llm = ctx.llm or LLMClient()
    try:
        resp = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=settings.AGENT_COMPRESSOR_MODEL,
            system="你是相关度重排器。直接输出纯 JSON。",
            max_tokens=1500,
            temperature=0.0,
            # 2026-06-14 Stage 5 收尾：mimo 等思考型模型显式禁用 thinking
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
        result = CompressionResult(
            selected=result_dict.get("selected", []),
            reasoning=result_dict.get("reasoning", ""),
            original_count=len(items),
            selected_count=len(result_dict.get("selected", [])),
            summary=result_dict.get(
                "summary",
                f"{key_name} {len(result_dict.get('selected', []))} 条 / 共 {len(items)} 条",
            ),
            collapsed_by_default=result_dict.get("collapsed_by_default", True),
        )
        logger.info(
            f"compressed {tool_name}: {len(items)} → {result.selected_count} "
            f"(intent={intent.category.value})"
        )
        return result
    except Exception as e:
        logger.warning(f"compress_tool_result failed: {type(e).__name__}: {e}")
        return None


def compression_to_sse_event(tool_name: str, tool_use_id: str, result: CompressionResult) -> StreamEvent:
    """CompressionResult → StreamEvent（前端用 tool_compressed 事件展示压缩信息）"""
    return StreamEvent(
        type="tool_compressed",
        tool_name=tool_name,
        tool_use_id=tool_use_id,
        compression=result.model_dump(),
        label=f"🗜️ 压缩：{result.summary}",
    )


def inject_compressed_to_messages(
    messages: list[dict],
    tool_name: str,
    tool_use_id: str,
    compression: CompressionResult,
) -> None:
    """把压缩结果追加到 messages 末尾（让主模型看到筛选后的数据 + 原因）

    格式：在最后一条 user 消息后追加 assistant 注释块，标注压缩信息
    """
    if not messages or messages[-1].get("role") != "user":
        return

    content = messages[-1].get("content", [])
    if isinstance(content, str):
        return  # 不修改字符串 content（chat_engine 内部用 list）

    # 在 tool_result 块后追加 <compressed> 标记
    compressed_note = {
        "type": "text",
        "text": (
            f"\n<compressed tool={tool_name} tool_use_id={tool_use_id} "
            f"original={compression.original_count} selected={compression.selected_count}>\n"
            f"筛选理由：{compression.reasoning}\n"
            f"Top 候选：{[s for s in compression.selected[:3]]}\n"
            f"</compressed>"
        ),
    }
    content.append(compressed_note)
    messages[-1]["content"] = content


# ============================================================================
# 辅助函数
# ============================================================================


def _extract_items(raw_result: dict) -> tuple[list, str]:
    """从工具结果中提取数据列表

    工具返回格式约定：
    - query_members: {status, count, members: [...]}
    - search_knowledge: {status, count, results: [...]}
    - query_meetings: {status, count, meetings: [...]}
    - query_tasks: {status, count, tasks: [...]}
    """
    for key in ("members", "results", "meetings", "tasks", "items", "data"):
        if key in raw_result and isinstance(raw_result[key], list):
            return raw_result[key], key
    # 兜底：找第一个 list 字段
    for k, v in raw_result.items():
        if isinstance(v, list) and v:
            return v, k
    return [], "items"


def _parse_json_response(text: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON 文本，自动处理 markdown 包裹"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
        else:
            text = "\n".join(lines[1:])
        text = text.strip()
    return json.loads(text)
