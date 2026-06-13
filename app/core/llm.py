"""LLM 客户端 — fallback 链 + LRU 缓存 + 统一接口

设计目标：
- LLMClient 单例管理所有 LLM 调用
- 失败自动 fallback（CLAUDE_MODEL -> CLAUDE_FALLBACK_MODEL）
- 简单 LRU 缓存（避免重复提问）
- 统一 complete() / stream() 接口

保持向后兼容：
- get_anthropic_client() / get_default_model() / parse_llm_json() / extract_text_from_response()
  保留为旧 API，新代码用 LLMClient
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, AsyncIterator, Optional

import anthropic

from app.config import settings

logger = logging.getLogger("microbubble.llm")


# ============================================================================
# 旧 API（保留）
# ============================================================================


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """创建异步 Anthropic 客户端（兼容旧代码）"""
    return anthropic.AsyncAnthropic(
        api_key=settings.CLAUDE_API_KEY,
        base_url=settings.CLAUDE_BASE_URL or None,
    )


def get_default_model() -> str:
    """获取默认 LLM 模型名称（兼容旧代码）"""
    return settings.CLAUDE_MODEL or "mimo-v2.5"


def parse_llm_json(text: str) -> dict:
    """解析 LLM 返回的 JSON 文本，自动处理 markdown 代码块包裹"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1])
        else:
            text = "\n".join(lines[1:])
        text = text.strip()
    return json.loads(text)


def extract_text_from_response(response) -> str:
    """从 Claude API 响应中提取文本内容（兼容 ThinkingBlock）"""
    text_content = ""
    thinking_content = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            text_content = block.text.strip()
        elif hasattr(block, "thinking") and block.thinking:
            thinking_content = block.thinking.strip()
    if not text_content and thinking_content:
        logger.debug("响应只有 ThinkingBlock，使用 thinking 内容")
    return text_content or thinking_content


# ============================================================================
# LRU 缓存
# ============================================================================


class LRUResponseCache:
    """简单 LRU 缓存：仅缓存纯文本/简单响应，避免 tool_use 缓存错乱"""

    def __init__(self, max_size: int = 256, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()

    def _key(self, messages: list, system: Optional[str], tools: Optional[list], **kwargs) -> str:
        # 简化：只 hash messages + system + max_tokens + model + temperature
        # 2026-06-14 方案 C：加 model 维度（不同模型不能共用缓存项）
        payload = {
            "messages": messages,
            "system": system,
            "max_tokens": kwargs.get("max_tokens"),
            "temperature": kwargs.get("temperature", 0.3),
            "model": kwargs.get("model", ""),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            ts, value = self._cache[key]
            if time.time() - ts > self.ttl_seconds:
                del self._cache[key]
                return None
            # LRU: 移到末尾
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any):
        with self._lock:
            self._cache[key] = (time.time(), value)
            self._cache.move_to_end(key)
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)


# ============================================================================
# LLMClient：统一入口（含 fallback + 缓存）
# ============================================================================


class LLMClient:
    """LLM 客户端单例

    用法：
        client = LLMClient()
        resp = await client.complete(
            messages=[{"role": "user", "content": "..."}],
            system="...",
            max_tokens=4096,
        )
        # 流式
        async for chunk in client.stream(messages=..., system=...):
            print(chunk)
    """

    _instance: Optional["LLMClient"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.CLAUDE_API_KEY,
            base_url=settings.CLAUDE_BASE_URL or None,
        )
        # 模型 fallback 链：主模型 -> 备用模型
        self.models: list[str] = []
        primary = settings.CLAUDE_MODEL or "mimo-v2.5"
        self.models.append(primary)
        fallback = getattr(settings, "CLAUDE_FALLBACK_MODEL", "")
        if fallback and fallback != primary:
            self.models.append(fallback)
        # 简单 LRU 缓存
        self.cache = LRUResponseCache(max_size=256, ttl_seconds=3600)
        self._initialized = True
        logger.info(f"LLMClient 初始化完成: models={self.models}")

    async def complete(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        use_cache: bool = False,
    ) -> Any:
        """同步调用：返回 Anthropic Message 响应对象

        参数：
        - model: 指定模型名（如 "claude-haiku-4-5-20251001"），None 时走 self.models[0] + fallback 链
                 keyword-only（铁律 5）：禁止位置传 model，防止老代码静默走错模型
        - 其他参数同 Anthropic SDK messages.create

        行为：
        - model 显式指定时：只用该模型，失败不 fallback（调用方明确意图，不应擅自降级）
        - model 为 None 时：走 self.models[0] → fallback 链
        - 失败重试：同模型连续 3 次（实际为 for-loop 切模型，每模型一次）
        """
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        # 选择模型链：显式 model 时只用一个，否则走 fallback 链
        models_to_try = [model] if model else self.models

        # 缓存键（仅在无 tools 时启用缓存，避免 tool_use 缓存错乱）
        cache_key = None
        if use_cache and not tools:
            cache_key = self.cache._key(
                messages, system, None,
                max_tokens=max_tokens, temperature=temperature,
                model=model or self.models[0],  # 加 model 维度
            )
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"LLM 缓存命中: {cache_key[:8]} (model={model or self.models[0]})")
                return cached

        # 尝试每个模型
        last_exc: Optional[Exception] = None
        for m in models_to_try:
            try:
                resp = await self.client.messages.create(model=m, **kwargs)
                if cache_key:
                    self.cache.set(cache_key, resp)
                if not model and m != self.models[0]:
                    logger.info(f"LLM fallback 成功: {self.models[0]} → {m}")
                return resp
            except (anthropic.APIError, anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
                logger.warning(f"模型 {m} 失败: {type(e).__name__}: {e}")
                last_exc = e
                continue
            except Exception as e:
                # 其他异常（参数错误等）不切换模型，直接抛
                logger.error(f"LLM 调用异常（非网络错误）: {e}", exc_info=True)
                raise

        # 所有模型都失败
        logger.error(f"所有 LLM 模型失败: {models_to_try}")
        raise last_exc  # type: ignore

    async def stream(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> AsyncIterator[Any]:
        """流式调用：返回 Anthropic MessageStream 上下文管理器

        参数：
        - model: 指定模型名，None 时走 self.models[0]（流式不做 fallback，因为流到一半切换体验差）
                 keyword-only（铁律 5）

        用法：
            async with (await client.stream(messages=...)) as stream:
                async for event in stream:
                    ...
        """
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        # 流式不做缓存，不做 fallback 链（流式 fallback 体验差）
        chosen = model or self.models[0]
        async with self.client.messages.stream(model=chosen, **kwargs) as stream:
            yield stream

    async def stream_raw(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        """流式 + fallback：返回 async iterator 包装后的 chunk 字典

        参数：
        - model: keyword-only（铁律 5），None 时用 self.models[0]

        用法：
            async for chunk in client.stream_raw(messages=...):
                chunk == {"type": "text_delta", "text": "..."}
        """
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        chosen = model or self.models[0]
        async with self.client.messages.stream(model=chosen, **kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        yield {
                            "type": "tool_use_start",
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                        }
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield {"type": "text_delta", "text": event.delta.text}
                    elif event.delta.type == "input_json_delta":
                        yield {
                            "type": "tool_input_delta",
                            "partial_json": getattr(event.delta, "partial_json", ""),
                        }


# 全局单例
llm_client = LLMClient()
