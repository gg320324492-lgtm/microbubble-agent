"""意图分类器 — Agentic Loop 阶段 1（方案 C Stage 1）

设计要点：
- 8 类闭集分类（recommend_person / search_info / explain_concept /
  execute_action / data_query / casual_chat / team_overview / follow_up）
- 用 Haiku 调用（闭集任务，accuracy 损失 < 3%，延迟 ~150ms vs Sonnet ~800ms）
- Redis 5min 缓存：同 question 5min 内复用
- follow_up 续讲意图正则前置（C2 2026-07-31）：LLM 调用前先查正则表，零额外 LLM 延迟
- 失败降级：默认 CASUAL_CHAT + confidence=0.0（C1 2026-07-31），
  query 同时含疑问词+领域词（检索特征）时仍走 SEARCH_INFO，
  但仍 yield intent_detected SSE 事件（Plan agent 5b：前端 UI 不至于 undefined）

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
from app.core.llm import LLMClient, parse_llm_json

logger = logging.getLogger("microbubble.agent.intent")


class IntentCategory(str, Enum):
    """8 种闭集意图"""
    RECOMMEND_PERSON = "recommend_person"   # 找人/请教谁/谁能帮忙
    SEARCH_INFO = "search_info"             # 找资料/文献/方法
    EXPLAIN_CONCEPT = "explain_concept"     # 解释概念/原理/是什么
    EXECUTE_ACTION = "execute_action"       # 创建/修改/删除 任务/会议/项目
    DATA_QUERY = "data_query"               # 查询 任务列表/会议列表/统计
    CASUAL_CHAT = "casual_chat"             # 闲聊/问候/不确定
    TEAM_OVERVIEW = "team_overview"         # 2026-07-15 #P2: 课题组/团队介绍 (强制 query_members+list_projects+search_knowledge 三件套)
    FOLLOW_UP = "follow_up"                 # 2026-07-31 CHAT-P0-C: 续讲/展开上轮话题 (如「再多介绍一些」「继续」「展开讲讲」)


class IntentResult(BaseModel):
    """意图分类结果"""
    category: IntentCategory = IntentCategory.SEARCH_INFO
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    reasoning: str = ""


# Prompt 模板（精简：闭集 7 选 1，不需要长 prompt）
_INTENT_PROMPT = """你是意图分类器。把用户问题分成以下 7 类之一：

- recommend_person: 用户想找人/请教谁/谁能帮忙（如「请教谁」「谁能指导」）
- search_info: 用户想找资料/文献/方法/知识（如「怎么检测」「有什么方案」）
- explain_concept: 用户想理解概念/原理/定义（如「什么是」「原理」「如何工作」）
- execute_action: 用户想执行操作。包括：
  - 任务/会议/项目的增删改（如「创建任务」「删除会议」「立项」）
  - **记忆操作**（如「记住：XX」「忘掉XX」「以后XX」「不要XX」→ save_memory / forget_memory）
  - **保存知识**（如「保存到知识库」→ save_conversation_knowledge）
  - 提醒/通知（如「提醒我」）
- data_query: 用户想查询数据（任务列表/会议列表/统计「多少」「几个」）
- casual_chat: 闲聊/问候/无法分类（如「你好」「谢谢」「天气」）
- team_overview: 用户想了解课题组/团队本身（成员构成、研究方向、项目）。如「详细介绍本课题组」「我们组研究什么」「组里有哪些人」「我们实验室做什么方向」「组里的研究方向」「我们组的项目」「课题组介绍」。**核心特征**：query 明确以"组/团队/课题组/实验室"为主语，而不是具体成员/项目/概念
- follow_up: 用户要求继续/展开上轮话题（如「再多介绍一些」「继续」「展开讲讲」「然后呢」「具体点」）。**前置规则已拦截多数触发词，此处仅兜底**。注意与 explain_concept 区分：follow_up 不含新概念词，只是要求接着讲

关键区分点（容易混淆）：
- 「记住 X」/「忘掉 X」/「以后 X」→ execute_action（不是 casual_chat）
- 「保存 X 到知识库」→ execute_action
- 「X 是研究什么的」/「X 做什么研究」/「X 的研究方向」→ search_info（找人/找资料）
- **「X 呢？」/「X 怎么样」/「X 做什么」**（**简写延续**，无动词）→ search_info（默认理解为研究主题，除非上文明确在问任务）
- 「X 在做什么」→ **歧义**：默认 data_query（具体人员查具体任务），但**当上文在讨论研究方向/找人**时改为 search_info
- 「X 的任务」/「X 的工作清单」/「X 在做什么（任务）」→ data_query（显式问任务）
- 「什么是 X」/「X 的原理」→ explain_concept
- 「所有成员任务」/「团队任务」/「大家都在做什么任务」→ data_query（query_all_member_tasks）
- **「本课题组/我们组/组里/实验室」开头 → team_overview**（2026-07-15 #P2 新增）
  - 与 search_info 区分：search_info 问的是"找资料/文献/方法"，主语是外部知识；team_overview 问的是"我们自己组怎么样"，主语是本课题组
  - 与 recommend_person 区分：recommend_person 找具体一个人（如"谁做 XX 方向"）；team_overview 看整体

输出严格 JSON（无其他文字）：
{{
  "category": "推荐人|找资料|解释概念|执行操作|数据查询|闲聊|团队概览|续讲",
  "confidence": 0.0-1.0,
  "keywords": ["关键词1", "关键词2"],
  "suggested_tools": ["query_members", "list_projects", "search_knowledge"],
  "reasoning": "一句话分类理由"
}}

建议工具 (suggested_tools) 填写规则 (必读，影响 Phase 0 强制执行):
- 从 34 个工具里选 1-3 个最相关的（**不要超过 3 个**，避免过度调度）:
  检索类: search_knowledge / web_search
  公式类: list_formulas / get_formula
  假设类: get_hypothesis / list_hypotheses
  成员类: query_members / get_member_profile
  任务类: query_tasks / get_task_detail
  会议类: list_meetings / get_meeting_transcript
  项目类: list_projects / get_project_summary
- search_info → 必填 ["search_knowledge"] 或 ["web_search"]
- explain_concept → 必填 ["search_knowledge", "list_formulas"] 或 ["search_knowledge", "get_hypothesis"]
- **team_overview → 必填 ["query_members", "list_projects", "search_knowledge"]**（2026-07-15 #P2: 三件套, 必须并行 dispatch）
- casual_chat → 必填 []（**严禁**填工具）
- follow_up → 必填 []（与 casual_chat 同, 严禁填工具）
- 任何场景 confidence < 0.5 时 → suggested_tools 设为 []（避免 hallucinated tools）

用户问题：{question}
"""


def _cache_key(question: str) -> str:
    """5min Redis 缓存 key"""
    h = hashlib.md5(question.encode("utf-8")).hexdigest()
    return f"intent:{h}"


# ============================================================================
# C2 续讲意图 follow_up — 正则前置规则（2026-07-31 CHAT-P0-C）
# ============================================================================
# LLM 调用前先查正则表，命中直接返回 follow_up（零额外 LLM 延迟）：
# 「再多介绍一些」/「继续」/「展开讲讲」等续讲短语被当新问题 →
# 重进检索/重答路径, 丢失上轮上下文。此规则把它们归一为 follow_up 意图,
# 由 agentic_loop 基于对话历史继续上轮话题。
#
# 匹配策略: 前缀触发词（最长优先）+ 尾部仅允许语气/程度助词:
#   - 命中触发词且剩余部分为空或纯助词 (啊/呢/吧/些/点/下…) → follow_up
#   - 剩余部分含实质内容（"详细介绍本课题组"/"为什么微气泡稳定"）→ 不拦截,
#     交给 LLM 正常分类 (team_overview / explain_concept 等)
#   - 问候语天然排除: "再见"/"再会" 的 "再" 后面是实词不是助词 → 不匹配

import re

_FOLLOW_UP_TRIGGERS = [
    # 4 字触发词 (最长优先)
    "展开讲讲", "详细说说", "说详细点", "详细展开", "再多介绍",
    "展开说说", "展开一下", "详细一点", "再详细说", "详细讲讲", "那为什么",
    # 3 字触发词
    "继续说", "接着说", "再讲讲", "再说说", "再详细", "再展开", "再介绍",
    "多介绍", "再来点", "再多讲", "再说点", "再多说", "具体点", "还有呢",
    "那然后", "然后呢", "那为啥", "详细点",
    # 2 字触发词
    "继续", "详细", "展开", "再多", "再来", "再说", "再讲", "多说",
    "为啥", "然后",
    # 最短触发词 (放最后, 前缀匹配兜底)
    "为什么", "再",
]

# 触发词后的纯语气/程度助词尾: 剩余部分只含这些字符 → 视为续讲;
# 含其他字符 (实词/新内容) → 不拦截, 交 LLM 分类
_FOLLOW_UP_TRAIL = re.compile(
    r"^[\s！？。，,!?~～啊呀吧嘛呢哦哈咯啦了的些点下呗喔哇嗯唉哎一讲下说]*$"
)


def _match_follow_up(question: str) -> bool:
    """正则前置匹配：命中 → follow_up 意图（不调 LLM）

    匹配优先级: 最长触发词优先; 命中后剩余部分必须为空或纯语气/程度助词,
    否则视为带实质内容的新请求, 不拦截 (交给 LLM 分类)。

    注意: 普通疑问句（"什么是X"/"怎么测X"/"为什么微气泡稳定"）**不**匹配,
    保证「什么是微纳米气泡」仍走 SEARCH_INFO/EXPLAIN_CONCEPT,
    「详细介绍本课题组」仍走 TEAM_OVERVIEW。
    """
    q = (question or "").strip()
    if not q:
        return False
    for trigger in _FOLLOW_UP_TRIGGERS:
        if not q.startswith(trigger):
            continue
        trail = q[len(trigger):].strip()
        if _FOLLOW_UP_TRAIL.fullmatch(trail):
            return True
        # 触发词命中但尾部有实质内容 → 不是续讲, 交 LLM 分类
        break
    return False


# ============================================================================
# C1 降级修复 — 检索特征规则（2026-07-31 CHAT-P0-C）
# ============================================================================
# 原 bug: 分类失败/低置信一律降级 SEARCH_INFO → "你好" 掉进检索路径 (慢 + 答非所问)。
# 修复: 默认降级 CASUAL_CHAT (快、零副作用、不误检索);
# 但 query 同时含 疑问词 + 领域词（明显检索意图）→ 低置信也走 SEARCH_INFO。

_QUERY_WORDS = (
    "什么", "如何", "怎么", "为什么", "哪些", "多少", "区别",
    "原理", "方法", "机理", "作用", "影响", "怎样",
)
_DOMAIN_WORDS = (
    "微气泡", "纳米气泡", "气泡", "臭氧", "消毒", "降解", "传质",
    "羟基", "自由基", "膜", "水处理", "设备", "参数", "饮用水",
    "污染物", "浮选", "曝气", "清洗", "空化", "zeta", "ph",
    "表面活性", "气液", "效率", "去除率", "黑臭水体", "溶氧",
)


def _looks_like_retrieval(question: str) -> bool:
    """query 同时含疑问词 + 领域词 → 疑似检索意图"""
    q = (question or "").lower()
    return any(w in q for w in _QUERY_WORDS) and any(w in q for w in _DOMAIN_WORDS)


def _degraded_result(question: str, reason: str) -> IntentResult:
    """分类失败/低置信的降级结果

    - 默认 CASUAL_CHAT（快、零副作用、不误检索）
    - query 强匹配检索特征（疑问词 + 领域词）→ SEARCH_INFO
    """
    if _looks_like_retrieval(question):
        return IntentResult(
            category=IntentCategory.SEARCH_INFO,
            confidence=0.0,
            keywords=[],
            suggested_tools=[],
            reasoning=f"{reason}, query 含检索特征, 降级 search_info",
        )
    return IntentResult(
        category=IntentCategory.CASUAL_CHAT,
        confidence=0.0,
        keywords=[],
        suggested_tools=[],
        reasoning=f"{reason}, 降级 casual_chat (安全默认)",
    )


async def classify_intent(question: str, ctx: ToolContext) -> IntentResult:
    """分类用户问题意图

    行为：
    1. 查 Redis 缓存（命中即返回，0 API 调用）
    2. 正则前置匹配 follow_up（零额外 LLM 延迟，C2）
    3. 用 ctx.llm 调 Haiku 做分类
    4. 失败/低置信时降级（默认 CASUAL_CHAT，检索特征 query 走 SEARCH_INFO，C1）
    5. 成功时写 Redis 5min 缓存

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

    # 1.5. 正则前置 follow_up 匹配（C2，零额外 LLM 延迟）
    if _match_follow_up(question):
        logger.debug(f"follow_up pattern matched: {question[:50]}")
        result = IntentResult(
            category=IntentCategory.FOLLOW_UP,
            confidence=0.95,
            keywords=[],
            suggested_tools=[],
            reasoning="正则前置规则命中续讲短语 (follow_up)",
        )
        # follow_up 是确定性规则命中, 同样写 5min 缓存
        if redis is not None:
            try:
                await redis.setex(
                    _cache_key(question),
                    settings.AGENT_RESULT_CACHE_TTL_SEC,
                    json.dumps(result.model_dump(), ensure_ascii=False, default=str),
                )
            except Exception as e:
                logger.warning(f"intent cache write failed: {type(e).__name__}: {e}")
        return result

    # 2. LLM 调
    llm = ctx.llm or LLMClient()
    prompt = _INTENT_PROMPT.format(question=question)
    try:
        resp = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            model=settings.AGENT_INTENT_MODEL,
            system="你是意图分类器。直接输出纯 JSON。",
            # P0-#1.5 (2026-07-12): max_tokens 从 300 → 2048
            # mimo-v2.5 thinking 模型在 300 tokens 会被 reasoning_content 占满,
            # finish_reason="length" 时 content="" → 之前 wrapper 不处理 reasoning_content
            # → text 为空 → "LLM 返回空文本" fallback. 提到 2048 给足空间让 mimo 输出 JSON.
            max_tokens=2048,
            temperature=0.0,
            # 2026-06-14 Stage 5 收尾：mimo 等思考型模型必须显式禁用 thinking
            # 否则只返 thinking block 不返 text，JSON 解析失败
            # P0-#1.5 备注: openai_compat 路径下 thinking 参数被 _complete_openai_compat 丢,
            # mimo 实际行为受 OpenAI 协议 reasoning 控制 (此处只 Anthropic backend 生效).
            thinking={"type": "disabled"},
        )
        # 只读 text block（不要 fallback 到 thinking，避免解析 thinking 内容当 JSON 失败）
        # P0-#1.5 (2026-07-12): 即使 max_tokens 够, mimo 仍可能输出 reasoning_content 而非 content,
        # wrapper 加 thinking block (兼容 Anthropic SDK 标准), 这里 fallback 到 thinking 提取
        text = ""
        for block in resp.content:
            if hasattr(block, "text") and block.text:
                text = block.text.strip()
                break
        if not text:
            # fallback: mimo 等 thinking-only 响应, 从 thinking block 提 (parse JSON 也行)
            for block in resp.content:
                if hasattr(block, "thinking") and block.thinking:
                    text = block.thinking.strip()
                    logger.debug("intent_classifier 命中 thinking block fallback (mimo reasoning_content)")
                    break
        if not text:
            raise ValueError("LLM 返回空文本")

        # 解析 JSON
        result_dict = parse_llm_json(text)
        result = IntentResult(
            category=IntentCategory(_map_category(result_dict.get("category", "找资料"))),
            confidence=float(result_dict.get("confidence", 0.5)),
            keywords=result_dict.get("keywords", []),
            suggested_tools=result_dict.get("suggested_tools", []),
            reasoning=result_dict.get("reasoning", ""),
        )
    except Exception as e:
        # 失败降级（Plan agent 5b：仍返回 IntentResult，调用方会 yield intent_detected 事件）
        # C1 (2026-07-31): 降级目标从 SEARCH_INFO → CASUAL_CHAT（检索特征 query 例外）
        logger.warning(f"intent classification failed: {type(e).__name__}: {e}")
        result = _degraded_result(question, f"intent classification failed: {e}")

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


# 2026-07-12 死代码清理: 删本地 _parse_json_response, 复用 app.core.llm.parse_llm_json


_CATEGORY_MAP = {
    "推荐人": "recommend_person",
    "找资料": "search_info",
    "解释概念": "explain_concept",
    "执行操作": "execute_action",
    "数据查询": "data_query",
    "闲聊": "casual_chat",
    # 2026-07-15 #P2: 团队概览 (team_overview) 7 类
    "团队概览": "team_overview",
    # 2026-07-31 CHAT-P0-C: 续讲 (follow_up) 第 8 类
    "续讲": "follow_up",
}


def _map_category(zh_or_en: str) -> str:
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
        # 2026-07-15 #P2: 团队概览
        IntentCategory.TEAM_OVERVIEW: "团队概览",
        # 2026-07-31 CHAT-P0-C: 续讲
        IntentCategory.FOLLOW_UP: "续讲",
    }.get(cat, "未知")
