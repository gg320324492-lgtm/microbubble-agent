"""Edge-TTS B+D 组合渐进式跨平台整合 e2e (W78 第 1 批 B-1).

依据:
- A-2 W77 commit 44cf83581 §5.3 W78 B-1
- W77 B-1 commit bedcd4594 (iOS Safari 20/20 e2e 基础)
- W77 B-2 commit cc3326409 (Android Chrome 20/20 e2e 基础)

5 新增跨平台整合 case:
- 1: 跨平台统一接口 (iOS Safari + Android Chrome + UA 判定 + 音频格式差异)
- 2: Edge-TTS 渐进式 (真生产 key 启用后主路径 + 缓存回写)
- 3: Web Speech API 降级 (类 20.13 沙箱守门改判)
- 4: pre-synthesize 缓存 (跨平台隔离 + 24h TTL + P95 SLA)
- 5: 监控容错 (指标快照 + 全路径耗尽优雅降级)

渐进式守恒: W77 B-1/B-2 老 adapter 一行不改, 40 e2e 复用 (见
tests/test_ios_safari_edge_tts_e2e.py + tests/test_android_chrome_edge_tts_e2e.py)

运行: SKIP_DB_SETUP=1 pytest tests/test_tts_mainplay_pipeline_e2e.py -v
预期: 5/5 PASS (无 DB / 无网络依赖, 沙箱)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.services.tts_mainplay_pipeline import (
    PipelineBackend,
    PipelineConfig,
    PipelineStage,
    Platform,
    build_tts_mainplay_pipeline,
)

IOS_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)


def test_pipeline_1_cross_platform_unified_interface():
    """1: 跨平台统一接口 — 同一 synthesize() 调用覆盖 iOS Safari + Android Chrome.

    验证 W78 B-1 核心价值: 调用方不再需要自己判平台 + 写两套分支。
    音频格式差异 (iOS MP3 降级 / Android OGG Vorbis 原生) 由 pipeline 内部收敛。
    """
    pipeline = build_tts_mainplay_pipeline()

    # UA 自动判定 (Android 必须先判 — Android Chrome UA 同时含 "Safari")
    assert pipeline.detect_platform(IOS_UA) is Platform.IOS_SAFARI
    assert pipeline.detect_platform(ANDROID_UA) is Platform.ANDROID_CHROME
    assert pipeline.detect_platform(None) is Platform.UNKNOWN
    assert pipeline.detect_platform("curl/8.0") is Platform.UNKNOWN

    # 同一入口, 两个平台各自拿到正确音频格式 (W76 B-1/B-2 4 维度实战差异)
    ios = pipeline.synthesize("会议纪要已生成", user_agent=IOS_UA)
    android = pipeline.synthesize("会议纪要已生成", user_agent=ANDROID_UA)

    assert ios.platform is Platform.IOS_SAFARI
    assert ios.audio_format == "mp3"          # iOS Safari OGG→MP3 降级 (W76 B-1)
    assert android.platform is Platform.ANDROID_CHROME
    assert android.audio_format == "ogg"      # Android OGG Vorbis 原生保留 (W76 B-2)

    # 跨平台整合阶段必在 fallback_chain 首位
    assert ios.fallback_chain[0] == PipelineStage.CROSS_PLATFORM_UNIFY.value
    assert android.fallback_chain[0] == PipelineStage.CROSS_PLATFORM_UNIFY.value

    # 显式 platform 入参优先于 UA (调用方可覆盖)
    forced = pipeline.synthesize("强制安卓", platform=Platform.ANDROID_CHROME, user_agent=IOS_UA)
    assert forced.platform is Platform.ANDROID_CHROME

    # UNKNOWN 平台取最保守 MP3 (兼容面最广), 不抛异常
    unknown = pipeline.synthesize("未知平台", user_agent="curl/8.0")
    assert unknown.platform is Platform.UNKNOWN
    assert unknown.audio_format == "mp3"
    assert unknown.passed is True


def test_pipeline_2_edge_tts_progressive_primary_path():
    """2: Edge-TTS 渐进式主路径 — 真生产 key 启用后走 B 选项 + 缓存回写."""
    pipeline = build_tts_mainplay_pipeline(
        config=PipelineConfig(production_key_enabled=True),  # 模拟 W78-B-2 拍板后
    )

    result = pipeline.synthesize("Edge-TTS 主路径", user_agent=ANDROID_UA)

    assert result.backend_used is PipelineBackend.EDGE_TTS
    assert result.passed is True
    assert PipelineStage.EDGE_TTS_PROGRESSIVE.value in result.fallback_chain
    # audio_url 带平台音频格式后缀
    assert result.audio_url == f"blob:edge-tts/{result.cache_key}.ogg"

    # Edge-TTS 成功后必须回写缓存 (供下次命中) → 第二次同参走 CACHE
    second = pipeline.synthesize("Edge-TTS 主路径", user_agent=ANDROID_UA)
    assert second.backend_used is PipelineBackend.CACHE
    assert second.cache_key == result.cache_key
    assert second.audio_url == result.audio_url

    assert pipeline.metrics.edge_tts_used == 1
    assert pipeline.metrics.cache_hits == 1

    # 渐进式守恒: 老 adapter 未被改写, iOS 侧仍可独立工作
    ios_result = pipeline.synthesize("iOS 主路径", user_agent=IOS_UA)
    assert ios_result.backend_used is PipelineBackend.EDGE_TTS
    assert ios_result.audio_format == "mp3"


def test_pipeline_3_web_speech_fallback_and_prod_key_gate():
    """3: Web Speech API 降级 + 类 20.13 真生产 key 沙箱守门改判.

    W78 B-1 默认 production_key_enabled=False (真生产 key 由 W78-B-2 单独拍板)。
    沙箱下无有效凭证, Edge-TTS 必然 timeout, 故提前改判 Web Speech 原生降级,
    避免用户白等 edge_tts_timeout_ms。
    """
    pipeline = build_tts_mainplay_pipeline()
    # 类 20.13 守门默认关闭 (不在 W78 B-1 自动启用)
    assert pipeline.PROD_KEY_AUTO_ENABLE is False

    android = pipeline.synthesize("沙箱降级", user_agent=ANDROID_UA)
    assert android.backend_used is PipelineBackend.WEB_SPEECH
    assert android.passed is True
    assert android.audio_url is None          # Web Speech 走浏览器原生, 无 blob URL
    assert PipelineStage.WEB_SPEECH_FALLBACK.value in android.fallback_chain
    # Android adapter 自身判 EDGE_TTS → pipeline 守门改判, 留痕可追溯
    assert "prod_key_gate" in android.metadata
    assert "W78-B-2" in android.metadata["prod_key_gate"]
    assert pipeline.metrics.prod_key_gate_downgrades == 1

    # iOS adapter 沙箱内部已自行降级 (W77 B-1 _try_edge_tts 沙箱返回失败),
    # 故无需 pipeline 守门 → downgrades 计数不增
    ios = pipeline.synthesize("iOS 沙箱降级", user_agent=IOS_UA)
    assert ios.backend_used is PipelineBackend.WEB_SPEECH
    assert pipeline.metrics.prod_key_gate_downgrades == 1

    assert pipeline.metrics.web_speech_used == 2

    # web_speech 也禁用时 → 无可用后端, 优雅降级为用户提示 (不抛异常)
    no_fallback = build_tts_mainplay_pipeline(
        config=PipelineConfig(production_key_enabled=False, web_speech_enabled=False),
    )
    dead = no_fallback.synthesize("无降级可用", user_agent=ANDROID_UA)
    assert dead.backend_used is PipelineBackend.NONE
    assert dead.passed is False
    assert "user_message" in dead.metadata


def test_pipeline_4_presynthesize_cache_cross_platform_isolation():
    """4: pre-synthesize 缓存 — 跨平台 key 隔离 + 24h TTL + P95 SLA."""
    pipeline = build_tts_mainplay_pipeline()

    text, voice = "缓存隔离验证", "zh-CN-XiaoxiaoNeural"
    ios_key = pipeline.cache_key(text, voice, "mp3")
    android_key = pipeline.cache_key(text, voice, "ogg")

    # 同文本 + 同音色, 不同平台格式 → key 必须不同
    # (否则 iOS Safari 会拿到 Android 的 OGG, 触发 W76 B-1 §2.2 格式拦截)
    assert ios_key != android_key

    # prewarm 只回填 iOS, Android 侧不应命中
    pipeline.prewarm(text, voice, platform=Platform.IOS_SAFARI, audio_url="blob:pre/ios.mp3")

    ios_hit = pipeline.synthesize(text, voice=voice, user_agent=IOS_UA)
    assert ios_hit.backend_used is PipelineBackend.CACHE
    assert ios_hit.audio_url == "blob:pre/ios.mp3"
    assert ios_hit.cache_key == ios_key
    assert ios_hit.metadata["hit"] is True
    assert ios_hit.metadata["ttl_seconds"] == 86400          # 24h TTL
    # 缓存命中 P95 SLA < 50ms
    assert ios_hit.metadata["within_p95_budget"] is True

    android_miss = pipeline.synthesize(text, voice=voice, user_agent=ANDROID_UA)
    assert android_miss.backend_used is not PipelineBackend.CACHE

    # 不同音色也必须隔离
    assert pipeline.cache_key(text, "zh-CN-YunxiNeural", "mp3") != ios_key

    # prefer_cached=False 可强制绕过缓存 (调试 / 重新合成)
    bypass = pipeline.synthesize(text, voice=voice, user_agent=IOS_UA, prefer_cached=False)
    assert bypass.backend_used is not PipelineBackend.CACHE

    # cache_enabled=False 时完全不查缓存
    nocache = build_tts_mainplay_pipeline(config=PipelineConfig(cache_enabled=False))
    nocache.prewarm(text, voice, platform=Platform.IOS_SAFARI, audio_url="blob:pre/x.mp3")
    assert nocache.synthesize(text, voice=voice, user_agent=IOS_UA).backend_used is not (
        PipelineBackend.CACHE
    )


def test_pipeline_5_monitoring_and_fault_tolerance():
    """5: 监控容错 — 指标快照 + 空输入防御 + 8 件套监控接入点."""
    pipeline = build_tts_mainplay_pipeline(
        config=PipelineConfig(production_key_enabled=True),
    )

    pipeline.synthesize("监控 A", user_agent=IOS_UA)
    pipeline.synthesize("监控 A", user_agent=IOS_UA)      # 缓存命中
    pipeline.synthesize("监控 B", user_agent=ANDROID_UA)

    snapshot = pipeline.monitoring_snapshot()
    metrics = snapshot["pipeline"]
    assert metrics["calls"] == 3
    assert metrics["cache_hits"] == 1
    assert metrics["cache_misses"] == 2
    assert metrics["cache_hit_rate"] == pytest.approx(1 / 3)
    assert metrics["edge_tts_used"] == 2

    # 缓存 store 指标透出 (24h TTL + 1 万条目上限)
    assert snapshot["cache_store"]["max_size"] == 10_000
    assert snapshot["cache_store"]["size"] >= 2

    # 类 20.13 决策状态必须可观测 (主拍归属明确)
    assert snapshot["production_key_enabled"] is True
    assert "W78-B-2" in snapshot["prod_key_decision"]
    assert snapshot["cache_p95_within_budget"] is True

    # 容错: 空 / 纯空白文本不抛异常, 返回 passed=False
    for bad in ("", "   ", "\n"):
        result = pipeline.synthesize(bad, user_agent=IOS_UA)
        assert result.passed is False
        assert result.backend_used is PipelineBackend.NONE
        assert result.metadata["error"] == "empty_text"

    # 全路径耗尽 → 监控容错阶段留痕 + 用户友好提示
    exhausted_pipeline = build_tts_mainplay_pipeline(
        config=PipelineConfig(production_key_enabled=False, web_speech_enabled=False),
    )
    exhausted = exhausted_pipeline.synthesize("全部失败", user_agent=ANDROID_UA)
    assert exhausted.passed is False
    assert PipelineStage.MONITORING_FAULT_TOLERANCE.value in exhausted.fallback_chain
    assert exhausted.metadata["user_message"] == "TTS 暂时不可用, 请稍后重试或检查网络"
    assert exhausted_pipeline.metrics.exhausted == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
