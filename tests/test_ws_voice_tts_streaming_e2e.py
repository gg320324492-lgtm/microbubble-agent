"""WebSocket 语音回复 TTS 逐 chunk 流式发送端到端测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.voice import router


class _FakeSessionContext:
    async def __aenter__(self):
        return MagicMock(name="db_session")

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def test_ws_voice_sends_each_tts_chunk_separately():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    expected_chunks = [
        b"a" * 1024,
        b"b" * 1024,
        b"c" * 1024,
    ]

    async def fake_synthesize_stream(*, text, voice="xiaoxiao", rate="+0%", volume="+0%"):
        assert text == "这是固定回复"
        assert voice == "xiaoxiao"
        assert rate == "+0%"
        assert volume == "+0%"
        for chunk in expected_chunks:
            yield chunk

    mock_asr = AsyncMock(return_value={"text": "这是固定问题"})
    mock_chat = AsyncMock(return_value={"content": "这是固定回复"})
    mock_clear_session = AsyncMock()

    with patch("app.api.v1.voice.decode_token", return_value={"type": "access"}), \
         patch("app.core.database.async_session", return_value=_FakeSessionContext()), \
         patch("app.api.v1.voice.asr_service.transcribe", mock_asr), \
         patch("app.api.v1.voice.agent.chat", mock_chat), \
         patch("app.api.v1.voice.agent.clear_session", mock_clear_session), \
         patch("app.api.v1.voice.tts_service.synthesize_stream", fake_synthesize_stream):
        with client.websocket_connect("/ws/voice/test-user?token=mock-auth-token") as websocket:
            websocket.send_bytes(b"mock-audio")

            assert websocket.receive_json() == {
                "type": "asr",
                "text": "这是固定问题",
            }
            assert websocket.receive_json() == {
                "type": "chat",
                "text": "这是固定回复",
            }

            received_chunks = [websocket.receive_bytes() for _ in expected_chunks]

    assert len(received_chunks) == 3
    assert received_chunks == expected_chunks
    assert b"".join(received_chunks) == b"".join(expected_chunks)
    mock_asr.assert_awaited_once_with(b"mock-audio")
    mock_chat.assert_awaited_once()
    mock_clear_session.assert_awaited_once_with("voice_test-user")
