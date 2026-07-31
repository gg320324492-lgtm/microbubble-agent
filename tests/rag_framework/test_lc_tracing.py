"""tests/rag_framework/test_lc_tracing.py — LangFuse tracing 3 场景

场景 1: 无 API key → LANGFUSE_TRACE_ENABLED=False → handler None (静默禁用)
场景 2: ImportError → 框架未安装 → 回退 None
场景 3: 正常启用 → 返回 CallbackHandler 单例 + TraceSpan 记录检索 I/O

设计原则 (与 tests/rag_framework/conftest.py 一致):
- 用 unittest.mock.patch.dict('sys.modules', ...) 注入 mock langfuse, 不实际导入框架
- 测试只测"我们的胶水代码逻辑", 不测框架行为
- 无需数据库 — 本地跑用 SKIP_DB_SETUP=1 (root conftest 头注释标准模式)
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

import app.rag.lc_tracing as lc_tracing
from app.rag import config

# ── 工具: mock langfuse 模块 (与 conftest mock_langfuse fixture 同款) ──────────


def _mock_langfuse_modules(handler_cls=None):
    """构造 langfuse 家族 sys.modules mock, 返回 (handler_cls, callback_module)"""
    handler_cls = handler_cls or MagicMock()
    callback_module = MagicMock()
    callback_module.CallbackHandler = handler_cls
    return handler_cls, {
        "langfuse": MagicMock(),
        "langfuse.callback": callback_module,
        "langfuse.callback.langfuse_callback_handler": MagicMock(),
    }


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_handler():
    """每个测试前重置模块级 _handler 单例 (config 由各测试独立 monkeypatch)"""
    lc_tracing._reset_langfuse_handler()
    yield
    lc_tracing._reset_langfuse_handler()


# ── 场景 1: 无 API key → 禁用 ───────────────────────────────────────────────


class TestDisabled:
    """无 API key 时静默禁用 — LANGFUSE_TRACE_ENABLED=False"""

    @pytest.fixture(autouse=True)
    def _no_keys(self, monkeypatch):
        monkeypatch.setattr(config, "LANGFUSE_PUBLIC_KEY", "")
        monkeypatch.setattr(config, "LANGFUSE_SECRET_KEY", "")
        monkeypatch.setattr(config, "LANGFUSE_TRACE_ENABLED", False)

    def test_handler_none_when_disabled(self):
        """场景 1a: 无 key → get_langfuse_handler 返回 None"""
        assert config.LANGFUSE_TRACE_ENABLED is False
        handler = lc_tracing.get_langfuse_handler()
        assert handler is None

    def test_flush_noop_when_disabled(self):
        """场景 1b: 禁用时 flush 是 no-op (不抛异常)"""
        lc_tracing.flush_langfuse()  # 不应抛异常

    def test_trace_retrieval_null_span_when_disabled(self):
        """场景 1c: handler None → trace_retrieval 返回 NullSpan"""
        span = lc_tracing.trace_retrieval(None, name="retrieval", query="测试")
        assert isinstance(span, lc_tracing.NullSpan)
        assert span.observation is None
        # NullSpan 可安全作为上下文管理器使用
        with span as s:
            assert s is span


# ── 场景 2: ImportError → 回退 None ─────────────────────────────────────────


class TestImportError:
    """langfuse 未安装 → 回退 None"""

    @pytest.fixture(autouse=True)
    def _keys_set(self, monkeypatch):
        monkeypatch.setattr(config, "LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setattr(config, "LANGFUSE_SECRET_KEY", "sk-test")
        monkeypatch.setattr(config, "LANGFUSE_TRACE_ENABLED", True)

    def test_handler_none_on_import_error(self):
        """场景 2a: import langfuse 失败 → 返回 None"""
        with patch.dict("sys.modules", {
            "langfuse": None,
            "langfuse.callback": None,
        }):
            # 确保模块级 _handler 仍为 None (frozen 模块兜底路径)
            assert lc_tracing._handler is None
            handler = lc_tracing.get_langfuse_handler()
            assert handler is None

    def test_handler_none_when_import_fails(self, monkeypatch):
        """场景 2b: langfuse.callback import 抛 ImportError → 返回 None"""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "langfuse.callback":
                raise ImportError("No module named 'langfuse'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        handler = lc_tracing.get_langfuse_handler()
        assert handler is None


# ── 场景 3: 正常启用 → 单例 + span 记录 ─────────────────────────────────────


class TestEnabled:
    """key 齐全 + langfuse 可导入 → 正常启用"""

    @pytest.fixture(autouse=True)
    def _keys_set(self, monkeypatch):
        monkeypatch.setattr(config, "LANGFUSE_PUBLIC_KEY", "pk-test")
        monkeypatch.setattr(config, "LANGFUSE_SECRET_KEY", "sk-test")
        monkeypatch.setattr(config, "LANGFUSE_HOST", "http://localhost:3000")
        monkeypatch.setattr(config, "LANGFUSE_TRACE_ENABLED", True)

    def test_handler_created_with_keys(self):
        """场景 3a: 正常启用 → CallbackHandler 用 pk/sk/host 构造"""
        handler_cls, modules = _mock_langfuse_modules()
        with patch.dict(sys.modules, modules):
            handler = lc_tracing.get_langfuse_handler(name="hybrid_retrieval")
        assert handler is handler_cls.return_value
        handler_cls.assert_called_once_with(
            public_key="pk-test",
            secret_key="sk-test",
            host="http://localhost:3000",
            name="hybrid_retrieval",
        )

    def test_handler_singleton(self):
        """场景 3b: 多次调用返回同一 handler (模块级单例)"""
        handler_cls, modules = _mock_langfuse_modules()
        with patch.dict(sys.modules, modules):
            h1 = lc_tracing.get_langfuse_handler()
            h2 = lc_tracing.get_langfuse_handler()
        assert h1 is h2
        handler_cls.assert_called_once()

    def test_flush_calls_handler_flush(self):
        """场景 3c: flush_langfuse 调 handler.flush()"""
        handler_cls, modules = _mock_langfuse_modules()
        with patch.dict(sys.modules, modules):
            lc_tracing.get_langfuse_handler()
            lc_tracing.flush_langfuse()
        handler_cls.return_value.flush.assert_called_once()

    def test_trace_span_sync_records_io(self):
        """场景 3d: TraceSpan 同步 — start_span(input=query) + end + observation"""
        handler_cls, modules = _mock_langfuse_modules()
        with patch.dict(sys.modules, modules):
            handler = lc_tracing.get_langfuse_handler()
            span = lc_tracing.TraceSpan(handler, name="retrieval", query="气泡粒径")
            with span as s:
                assert s.observation is handler_cls.return_value.start_span.return_value
                s.observation.output = {"count": 5}
        handler_cls.return_value.start_span.assert_called_once_with(
            name="retrieval",
            input="气泡粒径",
        )
        handler_cls.return_value.start_span.return_value.end.assert_called_once()
        # observation.output 写入了 span (mock 上可见)
        assert handler_cls.return_value.start_span.return_value.output == {"count": 5}

    def test_trace_retrieval_sync(self):
        """场景 3e: trace_retrieval 返回 TraceSpan, 可同步使用"""
        handler_cls, modules = _mock_langfuse_modules()
        with patch.dict(sys.modules, modules):
            handler = lc_tracing.get_langfuse_handler()
            ctx = lc_tracing.trace_retrieval(handler, name="hybrid", query="q1")
        assert isinstance(ctx, lc_tracing.TraceSpan)
        with ctx as span:
            span.observation.output = {"count": 3}

    def test_trace_span_async(self):
        """场景 3f: TraceSpan 异步上下文管理器 — async with 正常记录"""
        handler_cls, modules = _mock_langfuse_modules()
        with patch.dict(sys.modules, modules):
            handler = lc_tracing.get_langfuse_handler()
            async def use_span():
                async with lc_tracing.trace_retrieval(handler, name="hybrid", query="q2") as span:
                    span.observation.output = {"count": 7}
            asyncio.run(use_span())
        handler_cls.return_value.start_span.return_value.end.assert_called_once()

    def test_trace_span_survives_handler_exception(self):
        """场景 3g: start_span 抛异常 → 不炸, 上下文继续可用 (observation None)"""
        handler_cls, modules = _mock_langfuse_modules()
        handler_cls.return_value.start_span.side_effect = RuntimeError("boom")
        with patch.dict(sys.modules, modules):
            handler = lc_tracing.get_langfuse_handler()
            with lc_tracing.trace_retrieval(handler, name="hybrid", query="q3") as span:
                assert span.observation is None
                # 检索主逻辑不受影响
