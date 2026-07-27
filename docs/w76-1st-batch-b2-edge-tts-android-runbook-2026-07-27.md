# W76 第 1 批 B-2 Edge-TTS Android Chrome 修复 Runbook

日期：2026-07-27  
依据：W75 A-2 调研 §6 W76 Step 9、W73 A-2 Edge-TTS 单后端调研。  
范围：渐进式新增 Android Chrome 策略模块，不修改 `app/services/audio_processor.py` 或老 TTS 链路。

## 1. 组件

| 维度 | 模块 | 浏览器契约 |
|---|---|---|
| autoplay | `android_tts_autoplay.py` | 用户点击、visibility resume、Wake Lock、Media Session、静音振动 |
| 格式 | `android_tts_audio_format.py` | MP3 24 kHz、WAV 16 kHz、OGG Vorbis、AAC 原生支持 |
| 后台 | `android_tts_background.py` | running/pause/resume、visibility 与 blur/focus audio-focus 策略 |
| 恢复 | `android_tts_recovery.py` | close、3 次指数退避、AbortController、beforeunload 恢复点 |

`AudioFocusRequest` 在 Web 层是兼容策略枚举，不冒充 Android 原生 Java API；真正动作由标准 Web Audio API 的 `suspend()` / `resume()` 完成。

## 2. 16 case 验收矩阵

1. 用户手势后立即播放。
2. 后台返回前台时 resume。
3. 锁屏恢复使用 Wake Lock + Media Session 能力检测。
4. 有效增益为零时振动提示。
5. MP3 24 kHz 原生播放。
6. WAV 16 kHz 原生播放。
7. OGG Vorbis 经 `Audio.canPlayType('audio/ogg; codecs="vorbis"')` 检测后原生播放，不转 MP3。
8. AAC 原生播放。
9. 前台 AudioContext 为 running 时继续播放。
10. 页面隐藏时暂停 audio focus。
11. 锁屏返回、context suspended 时 resume。
12. tab blur 时暂停，focus 时恢复。
13. 正常中断关闭 AudioContext。
14. 网络抖动最多重试 3 次，退避 1/2/4 秒。
15. 用户取消触发 AbortController 并清理；audio-focus 接受阈值为 `0.55`。
16. beforeunload 保存文本与秒级恢复点。

沙箱命令：

```bash
python -m pytest tests/test_android_chrome_edge_tts_e2e.py -q
```

Android Emulator 真浏览器门禁（需安装 Chrome 的 Android SDK 环境）：

1. 启动 API 31+ Emulator，并确保 Chrome 为当前稳定版。
2. 通过 HTTPS 或 adb reverse 打开测试页面；不要用 `file://`，否则 Wake Lock/Media Session 能力结果失真。
3. 逐项执行上述 16 case，同时在 DevTools Remote Devices 观察 AudioContext 状态。
4. OGG case 记录 `canPlayType` 返回 `maybe`/`probably`；返回空串视为设备能力异常并停止，不静默转 MP3。
5. 后台、锁屏、tab 切换各重复三次；网络 case 用 DevTools Network Offline/Online 注入。

自动化 pytest 验证的是 Android Emulator 沙箱所用的策略与浏览器 hook 契约，不虚报本机已连接真机。发布前仍须完成上述 Emulator/真机步骤并保存日志。

## 3. 与 iOS Safari 差异

- Android Chrome 在 OGG Vorbis 能力检测通过时原生播放；iOS Safari 需降级 MP3。
- Android 可使用 `navigator.vibrate` 作为静音提示；iOS Safari 不提供同等振动 API。
- 两端都要求用户手势解锁音频，并在 visibility 恢复后调用 `AudioContext.resume()`。
- Wake Lock 与 Media Session 均必须能力检测，不可假设所有版本存在。

## 4. 回滚与非侵入保证

四个模块未被老链路强制导入，属于 opt-in 渐进策略。回滚只需停止前端接入并删除新模块；`audio_processor.py`、Edge-TTS 生成后端和既有 API 均不受影响。
