"""chat warmup 端点 + ollama 首 token 看门狗测试 (2026-09-18 冷启动事故防御)

事故背景: Windows 更新 NVIDIA 驱动后 WSL2 VM 未重启 → 容器 CUDA 初始化失败
静默回退 CPU, 17GB 模型纯 CPU 加载 3.5min+ → SSE 被链路中间层掐断
(ERR_CONNECTION_CLOSED) → 前端 "抱歉，我暂时无法回复 + network error".

防御三层 (本文件覆盖前两层):
1. POST /chat/warmup — 聊天页挂载时后台预热, 覆盖冷加载窗口
2. LLMClient._stream_ollama_first_token_guard — 首 token 超时降级云端
3. scripts/local-watchdog.ps1 — CUDA 失败日志告警 (脚本, 无单测)

全部 mock IO, 不依赖 DB / 真实 ollama.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import settings


# =========================================================================
# 工具: httpx.AsyncClient 假件 (chat.warmup 用 with 块, 需要上下文管理器)
# =========================================================================


def _make_fake_httpx_factory(ps_text: str = "", ps_error: Exception = None,
                             post_error: Exception = None):
    """构造可替换 chat 模块 httpx.AsyncClient 的假工厂.

    - get()  返回 ps_text (模拟 /api/ps 响应体) 或抛 ps_error
    - post() 记录调用到 calls 或抛 post_error
    每个实例的调用记录进 calls 列表, 方便断言后台任务真的发了 /api/generate.
    """
    calls = {"gets": [], "posts": []}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self._kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            calls["gets"].append(url)
            if ps_error is not None:
                raise ps_error
            return SimpleNamespace(text=ps_text)

        async def post(self, url, json=None):
            calls["posts"].append((url, json))
            if post_error is not None:
                raise post_error
            return SimpleNamespace(status_code=200)

    return FakeAsyncClient, calls


# =========================================================================
# POST /chat/warmup
# =========================================================================


def test_warmup_route_registered():
    """POST /chat/warmup 必须注册在 chat router"""
    from app.api.v1 import chat
    paths = {r.path: r for r in chat.router.routes if hasattr(r, "path")}
    assert "/chat/warmup" in paths
    assert "POST" in paths["/chat/warmup"].methods


async def test_warmup_ready_when_model_loaded(monkeypatch):
    """模型已驻留 (/api/ps 含模型名) → ready, 不起后台任务"""
    from app.api.v1 import chat

    model = settings.OLLAMA_MODEL or "qwen3.8:27b"
    FakeClient, calls = _make_fake_httpx_factory(
        ps_text=f'[{{"name":"{model}","model":"{model}","size":1}}]'
    )
    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(chat, "_OLLAMA_WARMUP_IN_FLIGHT", False)

    resp = await chat.chat_warmup(current_user=None)

    assert resp == {"status": "ready", "model": model}
    assert calls["posts"] == []  # 不起后台预热
    assert "/api/ps" in calls["gets"][0]


async def test_warmup_triggers_background_generate(monkeypatch):
    """模型未驻留 → 立即返回 warming, 后台任务发 /api/generate (num_predict=1)"""
    from app.api.v1 import chat

    FakeClient, calls = _make_fake_httpx_factory(ps_text='{"models":[]}')
    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(chat, "_OLLAMA_WARMUP_IN_FLIGHT", False)

    resp = await chat.chat_warmup(current_user=None)

    assert resp["status"] == "warming"
    # 让 asyncio.create_task 的后台任务跑到 post
    for _ in range(5):
        await asyncio.sleep(0)
    assert len(calls["posts"]) == 1
    url, payload = calls["posts"][0]
    assert url.endswith("/api/generate")
    assert payload["model"] == settings.OLLAMA_MODEL
    assert payload["options"]["num_predict"] == 1
    assert payload["stream"] is False
    # 预热完成后 in_flight 复位 (下次请求可再触发)
    assert chat._OLLAMA_WARMUP_IN_FLIGHT is False


async def test_warmup_dedup_while_in_flight(monkeypatch):
    """预热进行中 → 第二次调用直接 warming, 不重复起任务"""
    from app.api.v1 import chat

    FakeClient, calls = _make_fake_httpx_factory(ps_text='{"models":[]}')
    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(chat, "_OLLAMA_WARMUP_IN_FLIGHT", False)

    first = await chat.chat_warmup(current_user=None)
    assert first["status"] == "warming"
    assert chat._OLLAMA_WARMUP_IN_FLIGHT is True  # 任务还没跑完 (未 sleep)

    second = await chat.chat_warmup(current_user=None)
    assert second["status"] == "warming"

    for _ in range(5):
        await asyncio.sleep(0)
    assert len(calls["posts"]) == 1  # 只有第一次起了任务


async def test_warmup_unavailable_when_ps_probe_fails(monkeypatch):
    """/api/ps 探测失败 (ollama 挂了) → unavailable, 永不 5xx"""
    from app.api.v1 import chat

    FakeClient, calls = _make_fake_httpx_factory(
        ps_error=ConnectionError("ollama down")
    )
    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(chat, "_OLLAMA_WARMUP_IN_FLIGHT", False)

    resp = await chat.chat_warmup(current_user=None)

    assert resp == {"status": "unavailable", "model": settings.OLLAMA_MODEL}
    assert calls["posts"] == []


async def test_warmup_background_failure_is_swallowed(monkeypatch):
    """后台 /api/generate 失败 → 只记日志, in_flight 必须复位 (不卡死后续预热)"""
    from app.api.v1 import chat

    FakeClient, calls = _make_fake_httpx_factory(
        ps_text='{"models":[]}', post_error=RuntimeError("load failed")
    )
    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(chat, "_OLLAMA_WARMUP_IN_FLIGHT", False)

    resp = await chat.chat_warmup(current_user=None)
    assert resp["status"] == "warming"

    for _ in range(5):
        await asyncio.sleep(0)
    assert chat._OLLAMA_WARMUP_IN_FLIGHT is False


async def test_warmup_base_url_strips_v1(monkeypatch):
    """OLLAMA_BASE_URL 带 /v1 后缀时, 预热请求必须打到原生 API (去掉 /v1)"""
    from app.api.v1 import chat

    FakeClient, calls = _make_fake_httpx_factory(ps_text='{"models":[]}')
    monkeypatch.setattr(chat.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(chat, "_OLLAMA_WARMUP_IN_FLIGHT", False)
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama:11434/v1")

    await chat.chat_warmup(current_user=None)
    for _ in range(5):
        await asyncio.sleep(0)

    assert calls["gets"][0] == "http://ollama:11434/api/ps"
    assert calls["posts"][0][0] == "http://ollama:11434/api/generate"


# =========================================================================
# LLMClient._stream_ollama_first_token_guard (首 token 看门狗 + 云端降级)
# =========================================================================


def _bare_llm_client(openai_client):
    """绕过单例 __init__ 构造最小可测实例 (guard 方法只依赖 openai_client)"""
    from app.core.llm import LLMClient
    client = LLMClient.__new__(LLMClient)
    client.backend = "ollama"
    client.openai_client = openai_client
    return client


def _fake_oai(behavior):
    """behavior(params) → 协程结果的假 AsyncOpenAI"""
    completions = MagicMock()
    completions.create = behavior
    client = MagicMock()
    client.chat.completions = completions
    return client


async def test_guard_passthrough_when_create_fast(monkeypatch):
    """create() 在超时内返回 → 原样透传 (不降级、不改模型名)"""
    from app.core.llm import LLMClient

    monkeypatch.setattr(settings, "OLLAMA_FIRST_TOKEN_TIMEOUT", 5)
    seen = {}

    async def fast_create(**params):
        seen.update(params)
        return {"ok": True}

    client = _bare_llm_client(_fake_oai(fast_create))
    result = await client._stream_ollama_first_token_guard({"model": "qwen3.8:27b"})

    assert result == {"ok": True}
    assert seen["model"] == "qwen3.8:27b"


async def test_guard_falls_back_to_cloud_on_timeout(monkeypatch):
    """create() 卡死超时 → 用云端 (mimo) 客户端重试, 模型名换成云端模型"""
    from app.core import llm as llm_mod

    monkeypatch.setattr(settings, "OLLAMA_FIRST_TOKEN_TIMEOUT", 1)
    monkeypatch.setattr(settings, "OLLAMA_CLOUD_FALLBACK", True)
    monkeypatch.setattr(settings, "LLM_OPENAI_COMPAT_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_OPENAI_COMPAT_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_OPENAI_COMPAT_MODEL", "")
    monkeypatch.setattr(settings, "MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setattr(settings, "MIMO_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "MIMO_MODEL", "mimo-v2.5")

    async def hang_create(**params):
        await asyncio.sleep(3600)  # 模拟 ollama 加载卡死

    cloud_calls = {}

    class FakeCloudClient:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "sk-test"
            assert kwargs["base_url"] == "https://mimo.example/v1"
            self.chat = MagicMock()

            async def cloud_create(**params):
                cloud_calls.update(params)
                return {"ok": "from-cloud"}

            self.chat.completions.create = cloud_create

    monkeypatch.setattr(llm_mod, "AsyncOpenAI", FakeCloudClient)

    client = _bare_llm_client(_fake_oai(hang_create))
    result = await client._stream_ollama_first_token_guard({"model": "qwen3.8:27b"})

    assert result == {"ok": "from-cloud"}
    assert cloud_calls["model"] == "mimo-v2.5"  # 模型名必须换成云端模型


async def test_guard_raises_when_fallback_disabled(monkeypatch):
    """OLLAMA_CLOUD_FALLBACK=False → 超时直接抛 TimeoutError, 不降级"""
    from app.core import llm as llm_mod

    monkeypatch.setattr(settings, "OLLAMA_FIRST_TOKEN_TIMEOUT", 1)
    monkeypatch.setattr(settings, "OLLAMA_CLOUD_FALLBACK", False)

    async def hang_create(**params):
        await asyncio.sleep(3600)

    client = _bare_llm_client(_fake_oai(hang_create))
    with pytest.raises(asyncio.TimeoutError):
        await client._stream_ollama_first_token_guard({"model": "qwen3.8:27b"})


async def test_guard_raises_when_no_cloud_config(monkeypatch):
    """超时但 MIMO_API_KEY 未配置 (无云端可降) → 透传 TimeoutError"""
    from app.core import llm as llm_mod

    monkeypatch.setattr(settings, "OLLAMA_FIRST_TOKEN_TIMEOUT", 1)
    monkeypatch.setattr(settings, "OLLAMA_CLOUD_FALLBACK", True)
    monkeypatch.setattr(settings, "LLM_OPENAI_COMPAT_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_OPENAI_COMPAT_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_OPENAI_COMPAT_MODEL", "")
    monkeypatch.setattr(settings, "MIMO_API_KEY", "")

    async def hang_create(**params):
        await asyncio.sleep(3600)

    client = _bare_llm_client(_fake_oai(hang_create))
    with pytest.raises(asyncio.TimeoutError):
        await client._stream_ollama_first_token_guard({"model": "qwen3.8:27b"})
