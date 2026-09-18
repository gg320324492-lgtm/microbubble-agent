"""asr_service._transcribe_remote 重试逻辑测试 (2026-09-18 会议 253 事故防御)

事故: sensevoice CUDA 上下文损坏 → 首段推理 500 → 整场会议失败, error_reason
只有泛化的 "500 Internal Server Error", 真实原因 (CUDA error) 只留在服务端日志。

修复后行为:
- 5xx / 网络错误: 指数退避重试 (共 3 次)
- 最终失败: RuntimeError 带服务端 detail (error_reason 可读)
- 4xx: 不重试直接抛
- 期间任一次成功: 直接返回

全部 mock httpx, 不发真实网络请求。
"""

import types
from unittest.mock import MagicMock

import httpx
import pytest

from app.voice import asr as asr_module
from app.voice.asr import asr_service


class FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"text": "你好", "segments": []}
        self.text = text or f"body-{status_code}"

    def raise_for_status(self):
        if self.status_code >= 400:
            req = MagicMock()
            raise httpx.HTTPStatusError(f"error {self.status_code}", request=req, response=self)

    def json(self):
        if self._payload == "BAD_JSON":
            raise ValueError("invalid json")
        return self._payload


class FakeAsyncClient:
    """按脚本顺序返回响应; 记录调用次数"""

    script = []  # 类级: 每次 new client 复用同一脚本
    calls = []

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        FakeAsyncClient.calls.append(url)
        step = FakeAsyncClient.script[min(len(FakeAsyncClient.calls) - 1, len(FakeAsyncClient.script) - 1)]
        if isinstance(step, Exception):
            raise step
        return step


@pytest.fixture
def fast_sleep(monkeypatch):
    """把 asr 模块内的 asyncio.sleep 替换为立即返回 (不拖慢测试)"""
    monkeypatch.setattr(
        asr_module, "asyncio", types.SimpleNamespace(sleep=lambda *_: _noop())
    )


async def _noop():
    return None


def _install(monkeypatch, script):
    FakeAsyncClient.script = script
    FakeAsyncClient.calls = []
    monkeypatch.setattr(asr_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(asr_service, "_check_remote", _true_async)


async def _true_async():
    return True


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(monkeypatch, fast_sleep):
    """第 1 次 500 → 第 2 次 200: 返回结果, 共 2 次调用"""
    _install(monkeypatch, [
        FakeResp(500, text="CUDA error"),
        FakeResp(200, payload={"text": "会议内容", "segments": []}),
    ])
    result = await asr_service._transcribe_remote(b"x" * 2048, "zh", "transcribe", skip_convert=True)
    assert result["text"].startswith("会议内容")
    assert len(FakeAsyncClient.calls) == 2


@pytest.mark.asyncio
async def test_retry_exhausted_raises_with_detail(monkeypatch, fast_sleep):
    """3 次全 500: 抛 RuntimeError 且带服务端 detail (CUDA error 透传)"""
    _install(monkeypatch, [
        FakeResp(500, text='{"detail":"Inference failed: CUDA error: unknown error"}'),
    ] * 3)
    with pytest.raises(RuntimeError) as ei:
        await asr_service._transcribe_remote(b"x" * 2048, "zh", "transcribe", skip_convert=True)
    msg = str(ei.value)
    assert "重试 3 次仍失败" in msg
    assert "CUDA error" in msg  # 服务端 detail 必须透传
    assert len(FakeAsyncClient.calls) == 3


@pytest.mark.asyncio
async def test_4xx_no_retry(monkeypatch, fast_sleep):
    """400 (音频非法): 不重试, 立即抛且只调 1 次"""
    _install(monkeypatch, [FakeResp(400, text="Audio too small")])
    with pytest.raises(RuntimeError) as ei:
        await asr_service._transcribe_remote(b"x" * 2048, "zh", "transcribe", skip_convert=True)
    assert "不重试" in str(ei.value)
    assert len(FakeAsyncClient.calls) == 1


@pytest.mark.asyncio
async def test_network_error_retries(monkeypatch, fast_sleep):
    """连接错误也算可重试: 1 次网络错误 + 1 次成功"""
    _install(monkeypatch, [
        httpx.ConnectError("connection refused"),
        FakeResp(200, payload={"text": "ok", "segments": []}),
    ])
    result = await asr_service._transcribe_remote(b"x" * 2048, "zh", "transcribe", skip_convert=True)
    assert "ok" in result["text"]
    assert len(FakeAsyncClient.calls) == 2
