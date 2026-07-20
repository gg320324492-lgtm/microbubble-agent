"""测试 app.services.translation_service 翻译服务

覆盖场景 (2026-07-20 实装):
  1. 空文本 / 纯空白 → ValueError
  2. 超长文本 (>8000 字符) → ValueError
  3. 不支持的目标语言 → ValueError (白名单保护)
  4. 正常翻译流程 (mock LLMClient.complete 返回文本) → 翻译结果
  5. LLM 异常 → 兜底返原文, 不抛

SKIP_DB_SETUP=1 模式: mock LLMClient.complete + get_redis
跑法: SKIP_DB_SETUP=1 pytest tests/unit/test_translation_service.py -v
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import translation_service


# ============================================================
# Mock helpers
# ============================================================

class _FakeContentBlock:
    """模拟 Anthropic Response.content 列表中的 text block"""
    def __init__(self, text: str):
        self.text = text


def _fake_response(text: str):
    """构造 fake Anthropic Message: response.content = [block]"""
    return SimpleNamespace(content=[_FakeContentBlock(text)])


def _patch_llm(monkeypatch, return_text: str):
    """monkeypatch LLMClient().complete 返回指定文本"""
    fake_client = MagicMock()
    fake_client.complete = AsyncMock(return_value=_fake_response(return_text))
    # LLMClient() 是单例, 它的 __new__ 返同一个实例. 我们 patch 整个类的 __init__ 不必要,
    # 直接 patch LLMClient class 属性: 把类本身替换为返 fake_client 的 callable
    monkeypatch.setattr(translation_service, "LLMClient", lambda: fake_client)


def _patch_redis(monkeypatch, cached_value=None):
    """monkeypatch get_redis 返 fake Redis (None 表示 cache miss)"""
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=cached_value)
    fake_redis.set = AsyncMock(return_value=True)
    monkeypatch.setattr(translation_service, "get_redis", AsyncMock(return_value=fake_redis))
    return fake_redis


# ============================================================
# 1. 输入校验
# ============================================================

class TestInputValidation:
    """空文本 / 超长 / 不支持语言 必抛 ValueError (不浪费 LLM token)"""

    @pytest.mark.asyncio
    async def test_empty_text_raises(self, monkeypatch):
        """空字符串 → ValueError"""
        _patch_llm(monkeypatch, "ignored")
        _patch_redis(monkeypatch)
        with pytest.raises(ValueError, match="text 不能为空"):
            await translation_service.translate_text("", "en")

    @pytest.mark.asyncio
    async def test_whitespace_only_raises(self, monkeypatch):
        """纯空白也视作空 → ValueError"""
        _patch_llm(monkeypatch, "ignored")
        _patch_redis(monkeypatch)
        with pytest.raises(ValueError, match="text 不能为空"):
            await translation_service.translate_text("   \n\t  ", "en")

    @pytest.mark.asyncio
    async def test_text_too_long_raises(self, monkeypatch):
        """超 8000 字符 → ValueError (硬上限, 不调 LLM)"""
        _patch_llm(monkeypatch, "ignored")
        _patch_redis(monkeypatch)
        long_text = "x" * 8001
        with pytest.raises(ValueError, match="超过最大长度"):
            await translation_service.translate_text(long_text, "en")

    @pytest.mark.asyncio
    async def test_unsupported_lang_raises(self, monkeypatch):
        """不在白名单的 lang → ValueError"""
        _patch_llm(monkeypatch, "ignored")
        _patch_redis(monkeypatch)
        with pytest.raises(ValueError, match="不支持的目标语言"):
            await translation_service.translate_text("hello", "klingon")

    @pytest.mark.asyncio
    async def test_lang_case_insensitive(self, monkeypatch):
        """EN / En / eN 都视作 'en' (大写友好)"""
        _patch_llm(monkeypatch, "你好")
        _patch_redis(monkeypatch)
        result = await translation_service.translate_text("hello", "EN")
        assert result == "你好"


# ============================================================
# 2. 正常翻译流程
# ============================================================

class TestHappyPath:
    """mock LLMClient 返文本 → 验证 service 调用与返回"""

    @pytest.mark.asyncio
    async def test_successful_translation(self, monkeypatch):
        """正常 LLM 翻译 → 返 translated_text (去 strip)"""
        _patch_llm(monkeypatch, "  你好世界  ")  # 多余空白应被 strip
        _patch_redis(monkeypatch)
        result = await translation_service.translate_text("Hello world", "zh")
        assert result == "你好世界"

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_llm(self, monkeypatch):
        """缓存 miss → 调 LLM.complete 1 次"""
        _patch_llm(monkeypatch, "translation_result")
        fake_redis = _patch_redis(monkeypatch, cached_value=None)
        result = await translation_service.translate_text("Hello", "en")
        assert result == "translation_result"
        # cache 读 1 次
        assert fake_redis.get.call_count == 1
        # cache 写 1 次 (24h TTL)
        assert fake_redis.set.call_count == 1
        # TTL 是 86400s
        call_kwargs = fake_redis.set.call_args.kwargs
        assert call_kwargs.get("ex") == 86400


# ============================================================
# 3. 缓存命中
# ============================================================

class TestCache:
    """Redis 缓存命中时不应调 LLM (节省 token)"""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, monkeypatch):
        """缓存命中 → 不调 LLM, 直接返缓存"""
        fake_client = MagicMock()
        fake_client.complete = AsyncMock(side_effect=AssertionError("不应调 LLM"))
        monkeypatch.setattr(translation_service, "LLMClient", lambda: fake_client)
        _patch_redis(monkeypatch, cached_value=b"cached translation")
        result = await translation_service.translate_text("Hello", "en")
        assert result == "cached translation"
        # LLM 未被调用
        assert fake_client.complete.call_count == 0


# ============================================================
# 4. LLM 错误兜底
# ============================================================

class TestLLMErrorFallback:
    """LLM 异常时不抛, 返原文 (前端不显示空白)"""

    @pytest.mark.asyncio
    async def test_llm_exception_returns_original(self, monkeypatch):
        """LLM 抛任意异常 → 兜底返原文, 不抛"""
        fake_client = MagicMock()
        fake_client.complete = AsyncMock(side_effect=RuntimeError("API 429"))
        monkeypatch.setattr(translation_service, "LLMClient", lambda: fake_client)
        _patch_redis(monkeypatch)
        result = await translation_service.translate_text("original text", "en")
        assert result == "original text"  # 原文被 strip 过, 返 stripped 版本

    @pytest.mark.asyncio
    async def test_llm_empty_response_returns_original(self, monkeypatch):
        """LLM 返空字符串 → 兜底返原文"""
        _patch_llm(monkeypatch, "   ")  # 纯空白
        _patch_redis(monkeypatch)
        result = await translation_service.translate_text("original", "en")
        assert result == "original"


# ============================================================
# 5. 边界
# ============================================================

class TestEdgeCases:
    """边界 / 防御性"""

    @pytest.mark.asyncio
    async def test_use_cache_false_skips_redis(self, monkeypatch):
        """use_cache=False → 不读写 Redis (测试场景)"""
        _patch_llm(monkeypatch, "translated")
        fake_redis = _patch_redis(monkeypatch)
        result = await translation_service.translate_text(
            "hi", "en", use_cache=False
        )
        assert result == "translated"
        # get_redis 完全没被调
        assert fake_redis.get.call_count == 0
        assert fake_redis.set.call_count == 0

    def test_supported_langs_constant(self):
        """白名单至少含 zh/en/ja (本项目核心需求)"""
        for lang in ("en", "zh", "ja", "ko", "fr", "de", "es", "ru", "zh-TW"):
            assert lang in translation_service.SUPPORTED_LANGS
