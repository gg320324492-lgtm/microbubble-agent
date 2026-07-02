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
import logging

logger = logging.getLogger("microbubble.llm")

# 2026-07-02 openai_compat backend dispatch
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("openai 包未安装, openai_compat backend 不可用")

from app.config import settings
from app.core.tool_call_converter import (
    anthropic_to_openai_tools,
    anthropic_messages_to_openai,
    openai_response_to_anthropic_message,
    OpenAIToolCallAccumulator,
    openai_streaming_delta_to_anthropic_events,
)


# ============================================================================
# 流式 shim — 把 OpenAI 异步流包装成 Anthropic MessageStream 接口
# ============================================================================

class _OAIEventShim:
    """把 dict (tool_call_converter 返回的 Anthropic event 形状) 转成对象属性访问.

    agentic_loop 调用方式: event.type / event.delta.type / event.delta.text /
    event.content_block.type / event.content_block.id / event.content_block.name
    """

    def __init__(self, d: dict):
        # 嵌套 dict / list 递归转换
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, _OAIEventShim(v))
            elif isinstance(v, list):
                setattr(self, k, [
                    _OAIEventShim(x) if isinstance(x, dict) else x
                    for x in v
                ])
            else:
                setattr(self, k, v)


class _OAIStreamShim:
    """Anthropic MessageStream 接口 shim — 用于 openai_compat / ollama.

    用法:
        async for stream in llm.stream(...):
            async with stream as s:
                async for event in s:
                    if event.type == "content_block_delta" ...

    内部: 调用 openai_client.chat.completions.create(stream=True),
    每个 chunk 转成 1+ 个 Anthropic-style event (经 openai_streaming_delta_to_anthropic_events),
    按顺序 yield 出去.

    边界处理:
    - 多个 events 来自同一 chunk: 首个 event 立即 yield, 其余 buffer 下次 __anext__ 返回
    - 空 chunk (没产生 event): 最多跳过 1000 个连续空 chunk 后退出
      (qwen3 thinking 模型 reasoning 阶段可能持续 200+ chunks 不出 content, 10 不够)
    - Pydantic v2 ChatCompletionChunk: 自动 .model_dump() 转 dict
    - reasoning chars 累积到 tool_acc.reasoning_chars 供 caller debug
    """

    def __init__(self, oai_stream_coro, tool_acc):
        self._oai_coro = oai_stream_coro
        self._tool_acc = tool_acc
        self._oai_iter = None
        self._buffered = []
        self._entered = False

    async def __aenter__(self):
        self._entered = True
        # 触发 openai stream 创建 (返回 AsyncStream[ChatCompletionChunk])
        self._oai_iter = await self._oai_coro
        return self

    async def __aexit__(self, *args):
        # openai AsyncStream 不需要显式 close, async for 结束自动清理
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._entered:
            raise RuntimeError("必须 'async with stream as s:' 后再迭代")
        # 优先返回 buffer 里的 events
        if self._buffered:
            return _OAIEventShim(self._buffered.pop(0))
        # 拉下一个非空 chunk
        # qwen3 thinking 阶段可能持续 200+ chunks 不出 content, 1000 足够
        for _ in range(1000):
            try:
                chunk = await self._oai_iter.__anext__()
            except StopAsyncIteration:
                raise StopAsyncIteration
            chunk_dict = self._chunk_to_dict(chunk)
            events = openai_streaming_delta_to_anthropic_events(
                chunk_dict, "", self._tool_acc
            )
            if events:
                # 第一个 event 立即返, 后续 buffer 下次返
                self._buffered = events[1:]
                return _OAIEventShim(events[0])
        # 1000 个连续空 chunk — 异常但不该发生, 优雅退出
        # 真发生说明模型永久卡在 thinking 不出 content (可能 max_tokens 触顶)
        logger.warning(
            f"OAI stream: 1000 个连续空 chunk, 强制退出 "
            f"(reasoning_chars={getattr(self._tool_acc, 'reasoning_chars', 0)})"
        )
        raise StopAsyncIteration

    @staticmethod
    def _chunk_to_dict(chunk) -> dict:
        if isinstance(chunk, dict):
            return chunk
        # Pydantic v2 model (openai SDK 默认返回)
        if hasattr(chunk, "model_dump"):
            return chunk.model_dump()
        # 兜底
        return dict(chunk)


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
        # 2026-07-02 openai_compat backend dispatch
        # LLM_BACKEND: "anthropic" (默认) / "openai_compat" (mimo /v1, 抗 429) / "ollama" (本地)
        self.backend: str = getattr(settings, "LLM_BACKEND", "anthropic")
        if self.backend == "openai_compat":
            if not HAS_OPENAI:
                raise ImportError("LLM_BACKEND=openai_compat 但 openai 包未装. requirements.txt 加 openai>=1.0.0,<2.0.0")
            base_url = (
                getattr(settings, "LLM_OPENAI_COMPAT_BASE_URL", "")
                or settings.MIMO_BASE_URL
            )
            api_key = (
                getattr(settings, "LLM_OPENAI_COMPAT_API_KEY", "")
                or settings.MIMO_API_KEY
            )
            self.openai_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.client = None  # anthropic client 不创建
            primary = getattr(settings, "LLM_OPENAI_COMPAT_MODEL", "") or "mimo-v2.5"
        elif self.backend == "ollama":
            if not HAS_OPENAI:
                raise ImportError("LLM_BACKEND=ollama 但 openai 包未装")
            base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.openai_client = AsyncOpenAI(api_key="ollama", base_url=base_url)
            self.client = None
            primary = getattr(settings, "OLLAMA_MODEL", "") or "qwen3-embedding-0.6b"
        else:  # "anthropic" 默认
            self.client = anthropic.AsyncAnthropic(
                api_key=settings.CLAUDE_API_KEY,
                base_url=settings.CLAUDE_BASE_URL or None,
            )
            self.openai_client = None
            primary = settings.CLAUDE_MODEL or "mimo-v2.5"
        # 模型 fallback 链
        self.models: list[str] = [primary]
        fallback = getattr(settings, "CLAUDE_FALLBACK_MODEL", "")
        if fallback and fallback != primary:
            self.models.append(fallback)
        # 简单 LRU 缓存
        self.cache = LRUResponseCache(max_size=256, ttl_seconds=3600)
        self._initialized = True
        logger.info(
            f"LLMClient 初始化完成: backend={self.backend}, models={self.models}, "
            f"openai_client={'set' if self.openai_client else 'None'}"
        )

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
        thinking: Optional[dict] = None,
    ) -> Any:
        """同步调用：返回 Anthropic Message 响应对象

        参数：
        - model: 指定模型名（如 "claude-haiku-4-5-20251001"），None 时走 self.models[0] + fallback 链
                 keyword-only（铁律 5）：禁止位置传 model，防止老代码静默走错模型
        - thinking: 2026-06-14 Stage 5 收尾新增 — 控制 thinking block
                 思考型模型（mimo-v2.5）必须显式传 {"type": "disabled"} 否则只返 thinking 不返 text
                 {"type": "enabled", "budget_tokens": int} 启用 thinking
        - 其他参数同 Anthropic SDK messages.create

        行为：
        - model 显式指定时：只用该模型，失败不 fallback（调用方明确意图，不应擅自降级）
        - model 为 None 时：走 self.models[0] → fallback 链
        - 失败重试：同模型连续 3 次（实际为 for-loop 切模型，每模型一次）

        2026-07-02 backend dispatch 收尾: 当 self.backend in ("openai_compat", "ollama")
        自动转 anthropic_messages_to_openai + 调 openai_client.chat.completions.create,
        包装 openai_response_to_anthropic_message 为 Anthropic Message 形状.
        调用方 30+ caller 零感知 backend 差异.
        """
        if self.backend in ("openai_compat", "ollama"):
            return await self._complete_openai_compat(
                messages, model=model, system=system, tools=tools,
                max_tokens=max_tokens, temperature=temperature,
            )
        # 默认 anthropic 路径
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if thinking is not None:
            # 思考型模型控制：disabled=不思考（适合 JSON 输出）
            # enabled+budget_tokens=允许思考（适合复杂推理）
            kwargs["thinking"] = thinking

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

    async def _complete_openai_compat(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> Any:
        """OpenAI 兼容路径 (mimo /v1 / Ollama /v1 同样协议).

        调用 tool_call_converter 做双向转换, 包装成 Anthropic Message 形状.
        """
        oai_messages = anthropic_messages_to_openai(messages, system)
        oai_tools = anthropic_to_openai_tools(tools) if tools else None

        params = {
            "model": model or self.models[0],
            "messages": oai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if oai_tools:
            params["tools"] = oai_tools

        models_to_try = [model] if model else self.models
        last_exc: Optional[Exception] = None
        for m in models_to_try:
            try:
                params["model"] = m
                resp = await self.openai_client.chat.completions.create(**params)
                # 包装 OpenAI ChatCompletion 响应为 Anthropic Message 形状
                return openai_response_to_anthropic_message(resp)
            except Exception as e:
                logger.warning(f"openai_compat 模型 {m} 失败: {type(e).__name__}: {e}")
                last_exc = e
                continue
        logger.error(f"openai_compat 所有模型失败: {models_to_try}")
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
        thinking: Optional[dict] = None,
    ) -> AsyncIterator[Any]:
        """流式调用：返回 Anthropic MessageStream 上下文管理器

        参数：
        - model: 指定模型名，None 时走 self.models[0]（流式不做 fallback，因为流到一半切换体验差）
                 keyword-only（铁律 5）
        - thinking: 2026-06-14 Stage 5 收尾新增 — 思考型模型控制
                 {"type": "disabled"} 强制不思考 / {"type": "enabled", "budget_tokens": int} 允许思考

        用法：
            async for stream in client.stream(messages=...):
                async with stream as s:
                    async for event in s:
                        ...

        2026-07-02 backend dispatch 收尾 (openai_compat / ollama):
        用 _OAIStreamShim 包装 openai_client.stream 调 Anthropic MessageStream 接口,
        caller (agentic_loop) 零感知 backend 差异.
        """
        if self.backend in ("openai_compat", "ollama"):
            oai_messages = anthropic_messages_to_openai(messages, system)
            oai_tools = anthropic_to_openai_tools(tools) if tools else None
            chosen = model or self.models[0]

            async def _oai_call():
                params = {
                    "model": chosen,
                    "messages": oai_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                }
                if oai_tools:
                    params["tools"] = oai_tools
                return await self.openai_client.chat.completions.create(**params)

            tool_acc = OpenAIToolCallAccumulator()
            yield _OAIStreamShim(_oai_call(), tool_acc)
            return

        # 默认 anthropic 路径
        kwargs = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if thinking is not None:
            kwargs["thinking"] = thinking

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

        2026-07-02 backend dispatch 收尾 (openai_compat / ollama):
        复用 openai_streaming_delta_to_anthropic_events, 转回 stream_raw 的 dict chunk 格式.
        """
        if self.backend in ("openai_compat", "ollama"):
            oai_messages = anthropic_messages_to_openai(messages, system)
            oai_tools = anthropic_to_openai_tools(tools) if tools else None
            chosen = model or self.models[0]
            params = {
                "model": chosen,
                "messages": oai_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            if oai_tools:
                params["tools"] = oai_tools
            stream = await self.openai_client.chat.completions.create(**params)
            tool_acc = OpenAIToolCallAccumulator()
            async for chunk in stream:
                # Pydantic v2 ChatCompletionChunk -> dict
                chunk_dict = (
                    chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
                )
                for event in openai_streaming_delta_to_anthropic_events(
                    chunk_dict, "", tool_acc
                ):
                    if event["type"] == "content_block_start":
                        if event["content_block"]["type"] == "tool_use":
                            yield {
                                "type": "tool_use_start",
                                "id": event["content_block"]["id"],
                                "name": event["content_block"]["name"],
                            }
                    elif event["type"] == "content_block_delta":
                        if event["delta"]["type"] == "text_delta":
                            yield {
                                "type": "text_delta",
                                "text": event["delta"]["text"],
                            }
                        elif event["delta"]["type"] == "input_json_delta":
                            yield {
                                "type": "tool_input_delta",
                                "partial_json": event["delta"]["partial_json"],
                            }
            return

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
