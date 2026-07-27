# W76 第 1 批 B-2 Edge-TTS Android Chrome 修复记忆

- 日期：2026-07-27。
- 新增四个 opt-in 策略模块：`app/services/android_tts_autoplay.py`、`android_tts_audio_format.py`、`android_tts_background.py`、`android_tts_recovery.py`。
- 16 case sandbox matrix 在 `tests/test_android_chrome_edge_tts_e2e.py`，覆盖 autoplay、格式、后台、恢复各 4 项。
- Android OGG Vorbis 在 `canPlayType` 为 `maybe`/`probably` 时原生保留，不沿用 iOS MP3 fallback。
- 中断恢复最多 3 次指数退避（1/2/4s），W73 A-2 audio-focus threshold 为 0.55。
- 未修改 `app/services/audio_processor.py`，老 Edge-TTS 链路不变。
- pytest 是策略/浏览器 hook 契约验证；Android Emulator/真机步骤见 `docs/w76-1st-batch-b2-edge-tts-android-runbook-2026-07-27.md`，不能把沙箱结果伪报为已连接真机。
