"""Android Chrome Edge-TTS 4-dimension, 16-case sandbox matrix + B+D 渐进式 4-case 主拍接入.

W77 第 1 批 B-2 派工产物. 派工依据:
- W76 A-2 commit 0c3f848d7 §1.2 B+D 决策建议
- W76 B-2 commit 4ec33878a 16/16 e2e 基础 (4 维度 16 case)
- W77 A-2 B+D 渐进式实施方案设计
- 派工 v6 段 5 反馈 #6 渐进式实战 (类 20.13 真生产 key 主拍单独拍板)
- W73 A-2 调研 0.55 audio-focus threshold
"""

from app.services.android_tts_audio_format import AndroidTTSAudioFormatPolicy
from app.services.android_tts_autoplay import (
    AndroidAutoplayState,
    AndroidTTSAutoplayGuard,
    AutoplayAction,
)
from app.services.android_tts_background import (
    AndroidBackgroundState,
    AndroidTTSBackgroundPolicy,
    AudioFocusAction,
)
from app.services.android_tts_mainplay import (
    AndroidTTSMainplay,
    MainplayRequest,
    MainplayRoute,
)
from app.services.android_tts_recovery import AndroidTTSRecovery, RecoveryPoint
from app.services.tts_cache import TTSSynthesizeRequest, TTSCache
from app.services.web_speech_fallback import (
    WebSpeechConfig,
    WebSpeechFallback,
    WebSpeechResult,
)


def test_autoplay_1_user_gesture_immediate_play():
    state = AndroidAutoplayState(user_gesture=True, context_state="running")
    assert AndroidTTSAutoplayGuard().action(state) is AutoplayAction.PLAY
    assert '@click="triggerTTS"' in AndroidTTSAutoplayGuard.browser_hooks()


def test_autoplay_2_background_to_foreground_resumes():
    state = AndroidAutoplayState(user_gesture=True, visible=True, context_state="suspended")
    assert AndroidTTSAutoplayGuard().action(state) is AutoplayAction.RESUME
    assert "visibilitychange" in AndroidTTSAutoplayGuard.browser_hooks()


def test_autoplay_3_lock_screen_recovery_contract():
    hooks = AndroidTTSAutoplayGuard.browser_hooks()
    assert "wakeLock" in hooks and "mediaSession" in hooks


def test_autoplay_4_muted_audio_vibrates():
    state = AndroidAutoplayState(user_gesture=True, effective_gain=0)
    assert AndroidTTSAutoplayGuard().action(state) is AutoplayAction.VIBRATE
    assert "navigator.vibrate" in AndroidTTSAutoplayGuard.browser_hooks()


def test_format_1_mp3_24khz_native():
    fmt = AndroidTTSAudioFormatPolicy().select("mp3")
    assert fmt.native and fmt.sample_rate_hz == 24_000


def test_format_2_wav_16khz_native():
    fmt = AndroidTTSAudioFormatPolicy().select("wav")
    assert fmt.native and fmt.sample_rate_hz == 16_000


def test_format_3_ogg_vorbis_native_without_ios_fallback():
    policy = AndroidTTSAudioFormatPolicy()
    fmt = policy.select("ogg", "probably")
    assert fmt.native and fmt.name == "ogg" and "vorbis" in fmt.mime_type
    assert "canPlayType" in policy.can_play_type_probe()


def test_format_4_aac_native():
    assert AndroidTTSAudioFormatPolicy().select("aac").native


def test_background_1_foreground_context_running():
    state = AndroidBackgroundState(True, True, "running")
    assert AndroidTTSBackgroundPolicy().action(state) is AudioFocusAction.PLAY


def test_background_2_hidden_pauses_audio_focus():
    state = AndroidBackgroundState(False, True, "running")
    assert AndroidTTSBackgroundPolicy().action(state) is AudioFocusAction.PAUSE
    assert "AudioFocusRequest" in AndroidTTSBackgroundPolicy.browser_hooks()


def test_background_3_lock_screen_return_resumes_context():
    state = AndroidBackgroundState(True, True, "suspended")
    assert AndroidTTSBackgroundPolicy().action(state) is AudioFocusAction.RESUME
    assert "visibilitychange" in AndroidTTSBackgroundPolicy.browser_hooks()


def test_background_4_tab_blur_pauses():
    state = AndroidBackgroundState(True, False, "running")
    assert AndroidTTSBackgroundPolicy().action(state) is AudioFocusAction.PAUSE
    assert "addEventListener('blur'" in AndroidTTSBackgroundPolicy.browser_hooks()


def test_recovery_1_normal_interrupt_closes_context():
    assert "audioContext.close()" in AndroidTTSRecovery.browser_hooks()


def test_recovery_2_network_jitter_three_exponential_retries():
    assert AndroidTTSRecovery.max_retries == 3
    assert [AndroidTTSRecovery.backoff_seconds(i) for i in (1, 2, 3)] == [1.0, 2.0, 4.0]


def test_recovery_3_user_cancel_aborts_and_audio_focus_threshold_is_055():
    hooks = AndroidTTSRecovery.browser_hooks()
    assert "AbortController" in hooks and "controller.abort()" in hooks
    assert AndroidTTSRecovery.audio_focus_accepted(0.55)
    assert not AndroidTTSRecovery.audio_focus_accepted(0.549)


def test_recovery_4_browser_close_saves_recovery_point():
    point = RecoveryPoint("hello", 1.5)
    assert point.offset_seconds == 1.5
    hooks = AndroidTTSRecovery.browser_hooks()
    assert "beforeunload" in hooks and "sessionStorage" in hooks


# === W77 B-2: B+D 渐进式主拍接入 4 case (扩展 16 → 20) ===


def test_mainplay_1_bd_progressive_edge_tts_mainplay_path():
    """B+D 渐进式 Stage 1: Edge-TTS 主拍接入 (OGG Vorbis Android 原生保留)."""
    mainplay = AndroidTTSMainplay()
    request = MainplayRequest(
        text="B+D 渐进式 Edge-TTS 主拍接入",
        audio_focus_score=1.0,
        user_gesture=True,
        web_speech_available=True,
        cache_hit=False,
        request_id="bd-mainplay-1",
    )
    decision = mainplay.execute(request)
    # OGG Vorbis 格式 + autoplay 通过 → Edge-TTS 主路径
    assert decision.route is MainplayRoute.EDGE_TTS
    assert "edge_tts_progressive" in decision.fallback_chain
    assert "prod_key_decision_pending_w78" in decision.fallback_chain
    hooks = AndroidTTSMainplay.browser_hooks()
    assert "triggerMainplay" in hooks
    assert "/api/edge-tts/synthesize" in hooks


def test_mainplay_2_web_speech_api_fallback_when_edge_tts_unavailable():
    """B+D 渐进式 Stage 2: Web Speech API 降级 (Android Chrome speechSynthesis)."""
    mainplay = AndroidTTSMainplay()
    request = MainplayRequest(
        text="Web Speech API 降级测试",
        audio_focus_score=0.0,  # Edge-TTS 静默模式
        user_gesture=True,
        web_speech_available=True,
        cache_hit=False,
        request_id="bd-mainplay-2",
    )
    # gain=0 时 autoplay guard 返回 VIBRATE → Edge-TTS 跳过 → Web Speech API
    decision = mainplay.execute(request)
    assert decision.route is MainplayRoute.WEB_SPEECH_API
    assert "web_speech_fallback" in decision.fallback_chain
    fallback = WebSpeechFallback(WebSpeechConfig(lang="zh-CN"))
    assert fallback.should_use(web_speech_available=True, audio_focus_score=1.0)
    assert "speechSynthesis" in WebSpeechFallback.browser_hooks()
    assert "SpeechSynthesisUtterance" in WebSpeechFallback.browser_hooks()


def test_mainplay_3_pre_synthesize_cache_hit_skips_real_time_synthesis():
    """B+D 渐进式 Stage 3: pre-synthesize 缓存命中直接返回 (24h TTL)."""
    cache = TTSCache()
    cache_request = TTSSynthesizeRequest(
        text="pre-synthesize 缓存命中测试",
        voice="zh-CN-XiaoxiaoNeural",
        audio_format="ogg",
    )
    # 初始: miss
    assert not cache.has_cached(cache_request)
    assert cache.stats.misses == 1
    # store + 检查命中
    cache.store(cache_request, "https://cdn.example.com/cached.ogg")
    assert cache.has_cached(cache_request)
    assert cache.stats.hits == 1
    assert cache.stats.hit_rate == 0.5
    assert cache.size() == 1
    # 缓存键派生
    key1 = cache_request.cache_key()
    key2 = TTSSynthesizeRequest(
        text="pre-synthesize 缓存命中测试",
        voice="zh-CN-XiaoxiaoNeural",
        audio_format="ogg",
    ).cache_key()
    assert key1 == key2
    assert len(key1) == 16  # sha256[:16]
    # TTL 24h 验证
    assert TTSCache.CACHE_TTL_SECONDS == 86400


def test_mainplay_4_audio_focus_request_api_integration_with_recovery():
    """B+D 渐进式 Stage 4: AudioFocusRequest API 集成 + 0.55 threshold 验证 (W73 A-2 调研).

    实战:
    - Android Chrome AudioFocusRequest.PAUSE/RESUME 集成
    - 0.55 audio-focus threshold (W73 A-2 调研)
    - 类 20.13 真生产 key 主拍单独拍板 (W78, W77 沙箱模式)
    """
    # 0.55 threshold 验证 (W73 A-2 调研 + W76 B-2 16/16 e2e 实战)
    assert AndroidTTSRecovery.audio_focus_accepted(0.55)
    assert AndroidTTSRecovery.audio_focus_accepted(0.551)
    assert not AndroidTTSRecovery.audio_focus_accepted(0.549)
    # 3 次指数退避
    backoffs = [AndroidTTSRecovery.backoff_seconds(i) for i in (1, 2, 3)]
    assert backoffs == [1.0, 2.0, 4.0]
    # 类 20.13 实战: 真生产 key 主拍由 W78 单独拍板
    assert AndroidTTSMainplay.PROD_KEY_AUTO_ENABLE is False
    # AudioFocusRequest API 实战集成 (复用 W76 B-2 android_tts_background.py)
    background_hooks = AndroidTTSBackgroundPolicy.browser_hooks()
    assert "AudioFocusRequest" in background_hooks
    # 主拍接入: audio focus 阈值 + 中断恢复 + 缓存命中 → Edge-TTS 主路径
    mainplay = AndroidTTSMainplay()
    request = MainplayRequest(
        text="AudioFocusRequest API 集成测试",
        audio_focus_score=0.6,  # > 0.55 threshold
        user_gesture=True,
        web_speech_available=False,
        cache_hit=False,
        request_id="bd-mainplay-4",
    )
    decision = mainplay.execute(request)
    assert decision.route is MainplayRoute.EDGE_TTS
