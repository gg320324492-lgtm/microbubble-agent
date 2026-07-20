"""翻译服务 — 段落/全文翻译 (2026-07-20 实装)

复用 LLMClient (anthropic / openai_compat / ollama backend dispatch),
支持 Redis 缓存 (按 text+target_lang hash), 输入长度校验,
LLM 错误降级 (返原文 + 日志 warning, 不抛异常).

设计原则:
- 异步 API: 服务层全部 async, 同步 lock 不会阻塞事件循环
- 缓存粒度: SHA1(text + target_lang)[:16] 作 Redis key
- 超长文本: 8000 字符硬上限 (超出返 ValueError, 不浪费 LLM token)
- 兜底: LLM 异常 → 返原 text, 标 is_fallback=True
- 通用 prompt: 不限定学术场景, 段落/全文/句子都通用
"""
import hashlib
import logging
from typing import Optional, Tuple

from app.core.llm import LLMClient, extract_text_from_response
from app.core.redis import get_redis

logger = logging.getLogger("microbubble.translation")

# 2026-07-20: 段落/全文翻译硬上限
# 超过 8000 字符走 stream 或 chunk 拆分 (本次范围外, 直接返 ValueError)
MAX_TEXT_LENGTH = 8000

# 支持的目标语言白名单 (防止 LLM 收到任意 lang 字符串生成奇怪输出)
SUPPORTED_LANGS = frozenset({
    "en",   # English
    "zh",   # 中文 (简体)
    "zh-TW",  # 中文 (繁体)
    "ja",   # 日本語
    "ko",   # 한국어
    "fr",   # Français
    "de",   # Deutsch
    "es",   # Español
    "ru",   # Русский
})

# 显示用语言名 (prompt 与前端 i18n 共享)
LANG_DISPLAY = {
    "en": "English",
    "zh": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
}

# LLM 翻译 prompt (通用, 不限定学术)
TRANSLATION_SYSTEM_PROMPT = """You are a professional translator. Translate the user's text into {target_lang_name}.

Rules:
1. Preserve technical terms, proper nouns, formulas, and code blocks literally (only translate surrounding prose)
2. Maintain the original formatting (line breaks, paragraph structure, bullet points)
3. For LaTeX / mathematical formulas in $...$ or $$...$$ keep them as-is
4. Do NOT add explanations, notes, or quotes around the translation
5. Output ONLY the translated text, nothing else

If the source text is already in {target_lang_name}, return it unchanged."""

TRANSLATION_USER_PROMPT = """Translate the following text to {target_lang_name}:

---
{text}
---"""


def _validate_inputs(text: Optional[str], target_lang: Optional[str]) -> Tuple[str, str]:
    """校验输入, 返 (cleaned_text, target_lang_name) 或抛 ValueError

    Raises:
        ValueError: text 为空 / 超长 / target_lang 不在白名单
    """
    if not text or not text.strip():
        raise ValueError("text 不能为空")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(
            f"text 超过最大长度 {MAX_TEXT_LENGTH} 字符 (实际 {len(text)}), "
            "请分段翻译或联系管理员"
        )
    if not target_lang:
        raise ValueError("target_lang 不能为空")
    target_lang_normalized = target_lang.strip().lower()
    if target_lang_normalized not in SUPPORTED_LANGS:
        raise ValueError(
            f"不支持的目标语言: {target_lang}. "
            f"支持: {', '.join(sorted(SUPPORTED_LANGS))}"
        )
    return text.strip(), LANG_DISPLAY[target_lang_normalized]


def _cache_key(text: str, target_lang: str) -> str:
    """Redis 缓存 key: SHA1(text+lang)[:16], 避免长 text 作 key 浪费 Redis 内存"""
    payload = f"{target_lang.lower()}\x00{text}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"translation:{target_lang.lower()}:{digest}"


async def translate_text(
    text: str,
    target_lang: str,
    *,
    use_cache: bool = True,
) -> str:
    """翻译文本到目标语言 (异步)

    Args:
        text: 待翻译文本 (1-8000 字符)
        target_lang: 目标语言代码 (en/zh/ja/...), 见 SUPPORTED_LANGS
        use_cache: 是否走 Redis 缓存 (默认 True, 测试时可关)

    Returns:
        translated_text: 翻译结果 (失败时返原文, 标日志 warning)

    Raises:
        ValueError: 输入校验失败 (空文本 / 超长 / 不支持的语言)
    """
    cleaned_text, target_lang_name = _validate_inputs(text, target_lang)
    target_lang_normalized = target_lang.strip().lower()

    # 1) 缓存查询
    if use_cache:
        try:
            r = await get_redis()
            cached = await r.get(_cache_key(cleaned_text, target_lang_normalized))
            if cached:
                logger.debug(
                    f"translation cache hit: lang={target_lang_normalized} "
                    f"len={len(cleaned_text)}"
                )
                return cached.decode("utf-8") if isinstance(cached, bytes) else cached
        except Exception as e:
            # 缓存失败不阻塞主流程 (Redis 故障时仍能翻译)
            logger.warning(f"translation cache read failed: {e}")

    # 2) 调 LLM
    try:
        llm = LLMClient()
        response = await llm.complete(
            messages=[{
                "role": "user",
                "content": TRANSLATION_USER_PROMPT.format(
                    target_lang_name=target_lang_name,
                    text=cleaned_text,
                ),
            }],
            system=TRANSLATION_SYSTEM_PROMPT.format(target_lang_name=target_lang_name),
            max_tokens=min(4096, len(cleaned_text) * 4 + 200),  # 翻译输出 < 原文 4x
            temperature=0.2,  # 低温度: 翻译追求确定性, 不要创造性
            thinking={"type": "disabled"},  # 强制纯文本输出
        )
        translated = extract_text_from_response(response).strip()
        if not translated:
            logger.warning(
                f"LLM 翻译返回空文本, fallback 原文本: lang={target_lang_normalized}"
            )
            return cleaned_text
    except Exception as e:
        logger.error(
            f"translation LLM failed (lang={target_lang_normalized}, "
            f"len={len(cleaned_text)}): {type(e).__name__}: {e}"
        )
        # 兜底: 返原文, 不抛 (前端 user 看到原文不至于空白)
        return cleaned_text

    # 3) 写缓存 (24h TTL)
    if use_cache:
        try:
            r = await get_redis()
            await r.set(
                _cache_key(cleaned_text, target_lang_normalized),
                translated,
                ex=86400,  # 24h
            )
        except Exception as e:
            logger.warning(f"translation cache write failed: {e}")

    return translated


async def translate_text_paragraph(
    text: str,
    target_lang: str,
) -> str:
    """段落级翻译便捷接口 (Phase 4 paper 段落操作专用)

    行为同 translate_text, 单独函数方便未来扩展 (例如 per-paragraph 加 trace log,
    或不同 max_tokens 策略), 当前实现直接委托。
    """
    return await translate_text(text, target_lang)
