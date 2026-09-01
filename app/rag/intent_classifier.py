"""app/rag/intent_classifier.py — W100-RAG-3 Query Intent 分类

5 类 query 意图分类 (LLM-as-judge):
  1. factual             — 寻求具体事实/数据/定义
  2. conceptual          — 寻求概念解释/原理理解
  3. procedural          — 寻求操作步骤/方法流程
  4. multi_doc_synthesis — 跨多文档综合分析/对比
  5. hypothesis_generation — 科研假设/方案设计

设计:
  - LLM-as-judge (类 20.125 铁律: 必 5 类 + 失败回退 INTENT_FALLBACK)
  - 失败回退: INTENT_FALLBACK (默认 factual)
  - 复用 LLMClient (单例, 与 query_translator / llm_analysis_service 对齐)
  - Prompt: 5 类定义 + few-shot + JSON 输出
  - 最佳努力 (LLM 异常不抛, 上层取 fallback)

类 20.125 (W100-RAG-3): intent 分类必 5 类 + 失败回退 INTENT_FALLBACK
类 20.123 (W100-RAG-3): 派工 plan 偏差据实 (LLMAnalysisService 实测只有 analyze_content)

W100-RAG-3 用法:
    classifier = IntentClassifier()
    intent = await classifier.classify("臭氧微气泡消毒效果如何?")
    # → "factual" / "conceptual" / "procedural" / "multi_doc_synthesis" / "hypothesis_generation"
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger("microbubble.rag.intent_classifier")


# ===== 5 类意图枚举 =====
INTENT_FACTUAL: str = "factual"
INTENT_CONCEPTUAL: str = "conceptual"
INTENT_PROCEDURAL: str = "procedural"
INTENT_MULTI_DOC_SYNTHESIS: str = "multi_doc_synthesis"
INTENT_HYPOTHESIS_GENERATION: str = "hypothesis_generation"

# 全部合法 intent 集合 (类 20.125: 必 5 类)
VALID_INTENTS: List[str] = [
    INTENT_FACTUAL,
    INTENT_CONCEPTUAL,
    INTENT_PROCEDURAL,
    INTENT_MULTI_DOC_SYNTHESIS,
    INTENT_HYPOTHESIS_GENERATION,
]


# ===== Prompt 模板 =====
# 设计: 5 类定义 + few-shot 5 例 (1 例/类) + JSON 输出
# 字段: {query} 替换为用户原始 query
INTENT_CLASSIFY_PROMPT = """你是一个科研文献检索查询意图分类助手。

任务: 把用户的问题归入 5 类意图之一。

5 类意图定义:
1. factual — 寻求具体事实/数据/定义 (例: "臭氧微气泡的粒径是多少?", "NTA 测量下限是几纳米?")
2. conceptual — 寻求概念解释/原理理解 (例: "微气泡为什么能提高臭氧溶解效率?", "zeta 电位的物理意义是什么?")
3. procedural — 寻求操作步骤/方法流程 (例: "微气泡发生装置怎么搭建?", "如何用 ImageJ 测粒径?")
4. multi_doc_synthesis — 跨多文档综合分析/对比 (例: "比较 3 种臭氧微气泡发生器的优缺点", "综述微气泡在不同水处理场景的应用")
5. hypothesis_generation — 科研假设/方案设计 (例: "微气泡能否用于去除重金属?", "如果提高臭氧投加量能否提升消毒率?")

只输出严格的 JSON (不要其他文字):
{{"intent": "<5 类之一: factual | conceptual | procedural | multi_doc_synthesis | hypothesis_generation>"}}

示例 1:
用户问题: 臭氧微气泡的平均粒径是多少?
输出: {{"intent": "factual"}}

示例 2:
用户问题: 为什么微气泡能提高气体溶解速率?
输出: {{"intent": "conceptual"}}

示例 3:
用户问题: 微气泡发生装置的搭建步骤?
输出: {{"intent": "procedural"}}

示例 4:
用户问题: 综述臭氧微气泡在水处理领域的应用进展
输出: {{"intent": "multi_doc_synthesis"}}

示例 5:
用户问题: 微气泡在黑臭水体治理中能替代传统曝气吗?
输出: {{"intent": "hypothesis_generation"}}

用户问题: {query}
输出:"""


# ===== 内部 helpers =====

def _extract_text(response: Any) -> str:
    """从 LLM 响应提取纯文本 (兼容 Anthropic Message 形状 / mock 形状)."""
    if response is None:
        return ""
    text = getattr(response, "text", None)
    if text:
        return str(text)
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif hasattr(block, "text") and getattr(block, "text"):
                parts.append(str(getattr(block, "text")))
        return "".join(parts)
    return ""


def _parse_intent_json(text: str) -> Optional[str]:
    """从 LLM 输出解析 intent 字段 (兼容 markdown / 前后夹带说明文字)

    Returns:
        合法 intent 字符串 (5 类之一) / None (解析失败)
    """
    if not text:
        return None
    text = text.strip()

    # 1) 完整 JSON 解析
    try:
        from app.core.llm import parse_llm_json
        parsed = parse_llm_json(text)
        if isinstance(parsed, dict):
            intent = parsed.get("intent")
            if isinstance(intent, str) and intent in VALID_INTENTS:
                return intent
    except Exception:
        pass

    # 2) regex 兜底: 提取 "intent" 字段
    m = re.search(
        r'"intent"\s*:\s*"([a-z_]+)"',
        text,
    )
    if m:
        candidate = m.group(1)
        if candidate in VALID_INTENTS:
            return candidate

    # 3) 纯字符串匹配兜底: 如果 LLM 直接输出 5 类之一单词
    for intent in VALID_INTENTS:
        if re.search(rf"\b{re.escape(intent)}\b", text):
            return intent

    return None


# ===== Intent cache key (2026-09-01 WP1.8, 镜像 app/agent/intent_classifier.py) =====

def _intent_cache_key(query: str) -> str:
    """query → Redis 缓存 key (sha256[:16])"""
    import hashlib
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    return f"rag:intent:{digest}"


# Redis 失败冷却 (2026-09-01): Redis 不可达时 (e.g. 非 compose 环境解析 'redis'
# 主机名每次都付 DNS 超时), 冷却期内直接跳过缓存读写, 不让缓存层拖慢分类链路
_INTENT_REDIS_COOLDOWN_SECONDS: float = 30.0
_intent_redis_cooldown_until: float = 0.0


def _intent_redis_cooling_down() -> bool:
    import time
    return time.monotonic() < _intent_redis_cooldown_until


def _mark_intent_redis_cooldown() -> None:
    import time
    global _intent_redis_cooldown_until
    _intent_redis_cooldown_until = (
        time.monotonic() + _INTENT_REDIS_COOLDOWN_SECONDS
    )


# ===== IntentClassifier 类 =====

class IntentClassifier:
    """W100-RAG-3 Query Intent 分类器 (LLM-as-judge)

    用法:
        classifier = IntentClassifier(llm=mock_client)  # 注入 mock 用于测试
        intent = await classifier.classify("臭氧微气泡粒径")

    Args:
        llm: 可选 LLM client (None 走 LLMClient() 单例)
        fallback: 失败时返回的 intent (类 20.125 铁律, 默认 INTENT_FACTUAL)
    """

    def __init__(self, llm: Any = None, fallback: str = INTENT_FACTUAL) -> None:
        self.llm = llm
        self.fallback = fallback if fallback in VALID_INTENTS else INTENT_FACTUAL

    def _get_llm(self) -> Any:
        """返回 LLM 客户端: 优先注入, 否则懒加载 LLMClient 单例"""
        if self.llm is not None:
            return self.llm
        from app.core.llm import LLMClient
        return LLMClient()

    async def _call_llm(self, prompt: str) -> str:
        """统一 LLM 调用: 失败抛异常, 由 classify 兜底

        2026-09-01 WP1.8: 包 asyncio.wait_for(3s) 超时 — ollama 冷加载时
        intent LLM 调用曾无上限阻塞检索链
        """
        llm = self._get_llm()
        response = await asyncio.wait_for(
            llm.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,  # 低温度保证分类稳定
                thinking={"type": "disabled"},
            ),
            timeout=3.0,
        )
        return _extract_text(response)

    async def classify(self, query: str) -> str:
        """分类 query 的 intent

        Args:
            query: 用户原始查询

        Returns:
            5 类 intent 之一 (factual / conceptual / procedural /
            multi_doc_synthesis / hypothesis_generation)
            失败回退: self.fallback (默认 INTENT_FACTUAL)

        类 20.125 铁律: 必 5 类之一 + 失败回退 INTENT_FALLBACK
        2026-09-01 WP1.8: 加 Redis 缓存 (镜像 app/agent/intent_classifier.py 模式,
        TTL 24h) — 同 query 不重复调 LLM
        """
        query = (query or "").strip()
        if not query:
            # 空 query: 直接 fallback (不调 LLM 浪费)
            return self.fallback

        # 0) Redis 缓存 (best-effort, 失败静默走 LLM; 冷却期内跳过防 DNS/连接超时拖累)
        cache_key = _intent_cache_key(query)
        if not _intent_redis_cooling_down():
            try:
                from app.core.redis import get_redis
                redis = await get_redis()
                cached_raw = await redis.get(cache_key)
                if cached_raw:
                    cached = json.loads(cached_raw)
                    if cached in VALID_INTENTS:
                        return cached
            except Exception as e:
                _mark_intent_redis_cooldown()
                logger.debug(f"[W100-RAG-3] intent cache lookup skip: {e}")

        try:
            prompt = INTENT_CLASSIFY_PROMPT.format(query=query)
            text = await self._call_llm(prompt)
            intent = _parse_intent_json(text)
            if intent is not None:
                # 写缓存 (best-effort; 冷却期内跳过)
                if not _intent_redis_cooling_down():
                    try:
                        from app.core.redis import get_redis
                        redis = await get_redis()
                        await redis.setex(cache_key, 86400, json.dumps(intent))
                    except Exception as e:
                        _mark_intent_redis_cooldown()
                        logger.debug(f"[W100-RAG-3] intent cache write skip: {e}")
                return intent
            # 解析失败 (LLM 输出格式异常): log + fallback
            logger.debug(
                f"[W100-RAG-3] classify parse 失败, 回退 {self.fallback} "
                f"(query={query[:30]!r}, text={text[:60]!r})"
            )
        except Exception as e:
            # LLM 异常 (网络/超时/parse 全挂): best-effort fallback
            logger.warning(
                f"[W100-RAG-3] classify LLM 失败, 回退 {self.fallback} "
                f"(query={query[:30]!r}): {type(e).__name__}: {str(e)[:120]}"
            )

        return self.fallback


# ===== 模块级工厂 (与 query_translator / rag_query_cache 对齐) =====

_classifier_instance: Optional[IntentClassifier] = None


def get_intent_classifier(llm: Any = None) -> IntentClassifier:
    """获取 IntentClassifier 实例 (单例, 复用 LLM client)

    Args:
        llm: 可选 LLM client (测试可注入, None 走单例)
    """
    global _classifier_instance
    if llm is not None:
        # 注入 llm 时返回新实例 (不污染单例)
        return IntentClassifier(llm=llm)
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier(llm=None)
    return _classifier_instance


def reset_classifier() -> None:
    """测试用: 重置单例"""
    global _classifier_instance
    _classifier_instance = None


__all__ = [
    "IntentClassifier",
    "get_intent_classifier",
    "reset_classifier",
    # 5 类常量
    "INTENT_FACTUAL",
    "INTENT_CONCEPTUAL",
    "INTENT_PROCEDURAL",
    "INTENT_MULTI_DOC_SYNTHESIS",
    "INTENT_HYPOTHESIS_GENERATION",
    "VALID_INTENTS",
    "INTENT_CLASSIFY_PROMPT",
    "_extract_text",
    "_parse_intent_json",
]
