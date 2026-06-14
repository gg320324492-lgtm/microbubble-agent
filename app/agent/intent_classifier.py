"""意图分类器 — Agentic Loop 阶段 1（方案 C Stage 1）

设计要点：
- 6 类闭集分类（recommend_person / search_info / explain_concept /
  execute_action / data_query / casual_chat）
- 用 Haiku 调用（闭集任务，accuracy 损失 < 3%，延迟 ~150ms vs Sonnet ~800ms）
- Redis 5min 缓存：同 question 5min 内复用
- 失败降级：返回 SEARCH_INFO + confidence=0.0，但仍 yield intent_detected SSE 事件
  （Plan agent 5b：前端 UI 不至于 undefined）

跨进程安全（铁律 1）：
- redis client 全部从 ctx.redis 拿，None 时调用方临时创建
- 不在模块顶部创建 aioredis / AsyncAnthropic
"""

import hashlib
import json
import logging
from enum import Enum
from typing import Any, Optional

from redis.asyncio import Redis as AsyncRedis
from pydantic import BaseModel, Field

from app.agent.protocol import StreamEvent
from app.agent.tool_registry import ToolContext
from app.config import settings
from app.core.llm import LLMClient

logger = logging.getLogger("microbubble.agent.intent")


class IntentCategory(str, Enum):
    """6 种闭集意图"""
    RECOMMEND_PERSON = "recommend_person"   # 找人/请教谁/谁能帮忙
    SEARCH_INFO = "search_info"             # 找资料/文献/方法
    EXPLAIN_CONCEPT = "explain_concept"     # 解释概念/原理/是什么
    EXECUTE_ACTION = "execute_action"       # 创建/修改/删除 任务/会议/项目
    DATA_QUERY = "data_query"               # 查询 任务列表/会议列表/统计
    CASUAL_CHAT = "casual_chat"             # 闲聊/问候/不确定


class IntentResult(BaseModel):
    """意图分类结果"""
    category: IntentCategory = IntentCategory.SEARCH_INFO
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    reasoning: str = ""


# Prompt 模板（精简：闭集 6 选 1，不需要长 prompt）
_INTENT_PROMPT = """你是意图分类器。把用户问题分成以下 6 类之一：

- recommend_person: 用户想找人/请教谁/谁能帮忙（如「请教谁」「谁能指导」）
- search_info: 用户想找资料/文献/方法/知识（如「怎么检测」「有什么方案」）
- explain_concept: 用户想理解概念/原理/定义（如「什么是」「原理」）
- execute_action: 用户想执行操作（创建/修改/删除 任务/会议/项目）
- data_query: 用户想查询数据（任务列表/会议列表/统计）
- casual_chat: 闲聊/问候/无法分类

输出严格 JSON（无其他文字）：
{{
  "category": "推荐人|找资料|解释概念|执行操作|数据查询|闲聊",
  "confidence": 0.0-1.0,
  "keywords": ["关键词1", "关键词2"],
  "suggested_tools": ["query_members", "search_knowledge"],
  "reasoning": "一句话分类理由"
}}

用户问题：{question}
"""


def _cache_key(question: str) -> str:
    """5min Redis 缓存 key"""
    h = hashlib.md5(question.encode("utf-8")).hexdigest()
    return f"intent:{h}"


async def classify_intent(question: str, ctx: ToolContext) -> IntentResult:
    """分类用户问题意图

    行为：
    1. 查 Redis 缓存（命中即返回，0 API 调用）
    2. 用 ctx.llm 调 Haiku 做分类
    3. 失败时降级返回 SEARCH_INFO + confidence=0
    4. 成功时写 Redis 5min 缓存

    注意：本函数不直接 yield SSE 事件（不直接耦合 chat_engine）。
    返回 IntentResult 后由调用方决定是否 yield。
    """
    # 1. 缓存查
    redis = ctx.redis
    if redis is not None:
        try:
            cached_raw = await redis.get(_cache_key(question))
            if cached_raw:
                # redis-py 返回 bytes 或 str（取决于 decode_responses）
                if isinstance(cached_raw, bytes):
                    cached_raw = cached_raw.decode("utf-8")
                data = json.loads(cached_raw)
                logger.debug(f"intent cache hit: {question[:50]}")
                return IntentResult(**data)
        except (Exception, json.JSONDecodeError) as e:
            logger.warning(f"intent cache read failed: {type(e).__name__}: {e}")

    # 2. LLM 调
    llm = ctx.llm or LLMClient()
    prompt = _INTENT_PROMPT.format(question=question)
    try:
        resp = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=settings.AGENT_INTENT_MODEL,
            system="你是意图分类器。直接输出纯 JSON。",
            max_tokens=300,
            temperature=0.0,
            # 2026-06-14 Stage 5 收尾：mimo 等思考型模型必须显式禁用 thinking
            # 否则只返 thinking block 不返 text，JSON 解析失败
            thinking={"type": "disabled"},
        )
        # 只读 text block（不要 fallback 到 thinking，避免解析 thinking 内容当 JSON 失败）
        text = ""
        for block in resp.content:
            if hasattr(block, "text") and block.text:
                text = block.text.strip()
                break
        if not text:
            raise ValueError("LLM 返回空文本")

        # 解析 JSON
        result_dict = _parse_json_response(text)
        result = IntentResult(
            category=IntentCategory(_map_category(result_dict.get("category", "找资料"))),
            confidence=float(result_dict.get("confidence", 0.5)),
            keywords=result_dict.get("keywords", []),
            suggested_tools=result_dict.get("suggested_tools", []),
            reasoning=result_dict.get("reasoning", ""),
        )
    except Exception as e:
        # 失败降级（Plan agent 5b：仍返回 IntentResult，调用方会 yield intent_detected 事件）
        logger.warning(f"intent classification failed: {type(e).__name__}: {e}")
        result = IntentResult(
            category=IntentCategory.SEARCH_INFO,
            confidence=0.0,
            keywords=[],
            suggested_tools=[],
            reasoning=f"intent classification failed: {e}, falling back to search_info",
        )

    # 3. 写缓存（5min）
    if redis is not None and result.confidence > 0.5:
        try:
            await redis.setex(
                _cache_key(question),
                settings.AGENT_RESULT_CACHE_TTL_SEC,
                json.dumps(result.model_dump(), ensure_ascii=False, default=str),
            )
        except Exception as e:
            logger.warning(f"intent cache write failed: {type(e).__name__}: {e}")

    return result


def intent_to_sse_event(result: IntentResult) -> StreamEvent:
    """IntentResult → StreamEvent（让 chat_engine 直接 yield）"""
    return StreamEvent(
        type="intent_detected",
        intent=result.model_dump(),
        label=f"🧠 意图：{_category_zh(result.category)} (置信度 {result.confidence:.0%})",
    )


# ============================================================================
# 辅助函数
# ============================================================================


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


_CATEGORY_MAP = {
    "推荐人": "recommend_person",
    "找资料": "search_info",
    "解释概念": "explain_concept",
    "执行操作": "execute_action",
    "数据查询": "data_query",
    "闲聊": "casual_chat",
}


def _map_category(zh_or_en: str) -> str:
    """LLM 返回的中文类别 → enum 值"""
    if zh_or_en in _CATEGORY_MAP.values():
        return zh_or_en
    return _CATEGORY_MAP.get(zh_or_en, "search_info")


def _category_zh(cat: IntentCategory) -> str:
    """enum 值 → 中文显示"""
    return {
        IntentCategory.RECOMMEND_PERSON: "推荐人",
        IntentCategory.SEARCH_INFO: "找资料",
        IntentCategory.EXPLAIN_CONCEPT: "解释概念",
        IntentCategory.EXECUTE_ACTION: "执行操作",
        IntentCategory.DATA_QUERY: "数据查询",
        IntentCategory.CASUAL_CHAT: "闲聊",
    }.get(cat, "未知")
