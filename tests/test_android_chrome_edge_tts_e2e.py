"""Android Chrome Edge-TTS 4-dimension, 16-case sandbox matrix."""

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
from app.services.android_tts_recovery import AndroidTTSRecovery, RecoveryPoint


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
