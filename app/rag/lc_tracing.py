"""app/rag/lc_tracing.py — LangFuse 开源 Tracing

开源替代 LangSmith: AGPL 自托管 (docker-compose langfuse 服务, 端口 3000)。
trace 数据落自有 PostgreSQL, 无需外部 API Key。

LangSmith 对比:
- LangSmith: 专有 SaaS, 仅支持 LangChain
- LangFuse: AGPL 开源自托管, 同时支持 LangChain + LlamaIndex + 手写

使用:
    from app.rag.lc_tracing import get_langfuse_handler, trace_retrieval
    handler = get_langfuse_handler(name="hybrid_retrieval")
    async with trace_retrieval(query, handler) as span:
        results = await hybrid_retriever.retrieve(query, ...)
        span.observation.output = {"count": len(results)}
"""

import logging
from typing import Optional

from app.rag import config

logger = logging.getLogger("microbubble.rag.tracing")

_handler = None


def _reset_langfuse_handler():
    """重置 handler 单例 — 仅供测试/配置热更新使用"""
    global _handler
    _handler = None


def get_langfuse_handler(name: str = "rag"):
    """获取 LangFuse callback handler 单例 (lazy init)

    - 无 API key 时静默禁用 (LANGFUSE_TRACE_ENABLED=False)
    - ImportError 时回退 None (框架未安装)
    - 配置在调用时读取 (config.py 模块属性), 支持测试用 monkeypatch 覆盖
    """
    global _handler
    if not config.LANGFUSE_TRACE_ENABLED:
        return None
    if _handler is not None:
        return _handler
    try:
        from langfuse.callback import CallbackHandler
        _handler = CallbackHandler(
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            host=config.LANGFUSE_HOST,
            name=name,
        )
        logger.info(f"LangFuse tracing 启用: {config.LANGFUSE_HOST}")
        return _handler
    except ImportError as e:
        logger.warning(f"LangFuse 未安装, tracing 禁用: {e}")
        return None
    except Exception as e:
        logger.error(f"LangFuse 初始化失败, tracing 禁用: {e}", exc_info=True)
        return None


def flush_langfuse():
    """冲刷 LangFuse buffer (Celery 任务 / app shutdown 时调用)"""
    if _handler is not None:
        try:
            _handler.flush()
        except Exception as e:
            logger.warning(f"LangFuse flush 失败: {e}")


class NullSpan:
    """无 tracing 时的 no-op span

    observation 恒为 None — 与 TraceSpan 保持同构 API,
    通用调用方 (可能拿到任一 span 类型) 可无分支访问 span.observation。
    """

    observation = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __aenter__(self):
        return self

    def __aexit__(self, *args):
        return False


class TraceSpan:
    """LangFuse span 包装 — 记录检索阶段 I/O"""

    def __init__(self, handler, name: str, query: str, **kwargs):
        self._handler = handler
        self._name = name
        self._query = query
        self._kwargs = kwargs
        self._span = None
        self.observation = None

    def __enter__(self):
        try:
            self._span = self._handler.start_span(
                name=self._name,
                input=self._query,
                **self._kwargs,
            )
            self.observation = self._span
        except Exception:
            self._span = None
        return self

    def __exit__(self, *args):
        try:
            if self._span is not None:
                self._span.end()
        except Exception:
            pass
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *args):
        return self.__exit__(*args)


def trace_retrieval(handler, name: str, query: str, **kwargs):
    """返回可用的 span 上下文管理器 (NullSpan 兜底)"""
    if handler is None:
        return NullSpan()
    return TraceSpan(handler, name, query, **kwargs)
