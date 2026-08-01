"""HTTP TTS streaming endpoint tests.

The endpoint is intentionally tested with a small, deterministic async generator so
these checks do not require an Edge-TTS network call or audio credentials.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.api.v1.voice import router
from app.core.security import get_current_user
from app.voice.tts import tts_service


MP3_CHUNKS = (
    b"ID3\x04\x00\x00\x00\x00\x00\x15",
    b"\xff\xfb\x90\x64middle-mp3-frame",
    b"final-mp3-frame",
)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def _fake_current_user():
        # The endpoint only requires the dependency to resolve; it does not read
        # the member for TTS synthesis.
        return object()

    app.dependency_overrides[get_current_user] = _fake_current_user
    return app


def _install_chunked_tts(monkeypatch, chunks=MP3_CHUNKS):
    yielded = []

    async def _synthesize_stream(**kwargs):
        for chunk in chunks:
            yielded.append(chunk)
            yield chunk

    monkeypatch.setattr(tts_service, "synthesize_stream", _synthesize_stream)
    return yielded


def _assert_streaming_headers(response):
    """A streaming response must not be converted into a buffered body."""
    assert (
        response.headers.get("transfer-encoding", "").lower() == "chunked"
        or "content-length" not in response.headers
    )
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["content-disposition"] == (
        "attachment; filename=speech.mp3"
    )


async def test_voice_tts_http_streaming_returns_mp3_without_content_length(monkeypatch):
    """Async HTTP clients receive audio bytes without a precomputed length."""
    yielded = _install_chunked_tts(monkeypatch)
    app = _build_test_app()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/voice/tts",
            json={"text": "流式测试", "voice": "xiaoxiao"},
        )

    _assert_streaming_headers(response)
    assert response.content == b"".join(MP3_CHUNKS)
    assert response.content.startswith(b"ID3")
    assert response.content
    assert len(yielded) == 3


def test_voice_tts_testclient_receives_all_intermediate_chunks(monkeypatch):
    """TestClient streaming reads the complete body produced by 3 async yields."""
    yielded = _install_chunked_tts(monkeypatch)
    app = _build_test_app()

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/voice/tts",
            json={"text": "三段音频", "rate": "+5%", "volume": "+0%"},
        ) as response:
            _assert_streaming_headers(response)
            received = b"".join(response.iter_bytes())

    assert received == b"".join(MP3_CHUNKS)
    assert received.startswith(b"ID3")
    assert yielded == list(MP3_CHUNKS)
    assert len(yielded) == 3


def test_voice_tts_streaming_yields_nonempty_audio_chunks(monkeypatch):
    """Each source chunk is forwarded unchanged rather than buffered first."""
    yielded = _install_chunked_tts(monkeypatch)
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/voice/tts",
            json={"text": "中间 chunk"},
        )

    _assert_streaming_headers(response)
    assert all(yielded)
    assert response.content == b"".join(yielded)
    assert len(yielded) >= 1
