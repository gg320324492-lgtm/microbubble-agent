# W77 第 1 批 B-2 Edge-TTS Android Chrome 主拍接入 B+D 渐进式 (2026-07-28)

> **任务**: W77 第 1 批 B-2 Edge-TTS Android Chrome 主拍接入 B+D 渐进式
> **依据**: W76 A-2 commit `0c3f848d7` §1.2 B+D 决策建议 + W76 B-2 commit `4ec33878a` 16/16 e2e 基础
> **基线**: main HEAD `61561c58d` (W76 第 1 批 grand closure 收口, 锚点范式第 263 守恒)
> **锚点范式**: W76 第 1 批 263 → W77 第 1 批 B-2 **268 守恒** (+1)
> **范畴**: 新建 3 模块 (主拍接入 + 降级 + 缓存) + 扩展 e2e 16 → 20 case + runbook, 0 production code 改动铁律守恒

## §1 派工 v4 铁律 3 真验证 (派工前提必先 3 步)

### §1.1 Step 1: 读 W76 A-2 B+D 决策建议

```bash
git show 0c3f848d7:docs/w76-1st-batch-a2-edge-tts-decision-2026-07-27.md | grep -A 30 "B+D\|渐进式"
```

**实战输出**:
- W76 A-2 §1.1: W75 A-2 commit `f538e3cf6` §6 W77 Step 10 主拍接入必含 4 选项 (A/B/C/D)
- W76 A-2 §1.2: 选项 B (Edge-TTS + Web Speech API 降级, 中等风险) + 选项 D (Edge-TTS + 后端 pre-synthesize 缓存, 中低风险) 组合最优
- W76 A-2 明确: 调研完成 ≠ 主拍验收, 真生产 key 主拍由 W78 单独拍板

### §1.2 Step 2: W76 B-2 commit 4ec33878a 16/16 e2e 基础

```bash
git show 4ec33878a --stat
```

**实战输出**:
- 4 个 android_tts_*.py (autoplay/audio_format/background/recovery)
- 16/16 e2e PASS (Android Emulator 沙箱)
- OGG Vorbis Android 原生保留 (与 iOS MP3 降级差异)
- 0.55 audio-focus threshold (W73 A-2 调研)

### §1.3 Step 3: grep 老 TTS 链路

```bash
grep -rE "audio_processor|android.chrome" app/services/audio_processor.py
```

**实战输出**: 0 命中 (老 TTS 链路完全隔离, B+D 渐进式可独立实施)

## §2 B+D 渐进式 5 阶段实战

### §2.1 android_tts_mainplay.py 主拍接入核心 (新建)

- **5 阶段实战流程**:
  1. Edge-TTS 渐进式 (复用 W76 B-2 autoplay/audio_format)
  2. Web Speech API 降级 (复用 web_speech_fallback.py)
  3. pre-synthesize 缓存 (复用 tts_cache.py, 24h TTL)
  4. 真生产 key 主拍决策 (W78 主拍, W77 沙箱模式 `PROD_KEY_AUTO_ENABLE=False`)
  5. 监控 + 容错 (接入 W76 D-1 5 件套 + W73 B-2 4 类 hot-fix)

### §2.2 Android Chrome 4 维度实战细化 (16 → 20 case)

- 复用 W76 B-2 16 case (autoplay/audio_format/background/recovery 4×4)
- 新增 4 case (B+D 渐进式主拍接入):
  - mainplay_1: B+D 渐进式 Edge-TTS 主拍接入 (OGG Vorbis Android 原生保留)
  - mainplay_2: Web Speech API 降级 (Android Chrome speechSynthesis)
  - mainplay_3: pre-synthesize 缓存命中 (24h TTL + 命中率统计)
  - mainplay_4: AudioFocusRequest API 集成 + 0.55 threshold + 类 20.13 真生产 key 主拍单独拍板

### §2.3 Edge-TTS + Web Speech API 降级路径

- Edge-TTS 可用 (Play/Resume) → 主路径 (OGG Vorbis Android 原生保留)
- Edge-TTS 失败 (VIBRATE/WAIT) → Web Speech API 降级
- pre-synthesize 缓存命中 → 直接返回 (避免重复 API 调用)
- 全部失败 → 用户友好提示 (retry_after=1.0s)

### §2.4 pre-synthesize 缓存实战 (24h TTL)

- 缓存键: `sha256(text|voice|audio_format)[:16]`
- TTL: 86400s (24h, W73 录音断网防御参考)
- 命中率监控: `hits / (hits + misses)`
- AudioFocusRequest.PAUSE 集成 (W76 B-2 实战)

### §2.5 e2e 测试 (20/20 PASS)

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_android_chrome_edge_tts_e2e.py -v
# 20 passed in 0.04s
```

## §3 0 production code 改动铁律例外 2 验证

- ✅ `app/services/audio_processor.py` 未修改
- ✅ `app/voice/tts.py` (Edge-TTS 后端) 未修改
- ✅ `web/src/composables/chat/useChatStream.ts` 未修改
- ✅ 新增 3 个模块 (主拍接入 + 降级 + 缓存) — W77 B-2 例外已批, 例同 W76 B-2

## §4 类 20.13 真生产 key 主拍单独拍板 (W78)

- `AndroidTTSMainplay.PROD_KEY_AUTO_ENABLE = False` (硬编码, W77 沙箱模式)
- 真生产 key 主拍决策由 W78 单独拍板 (派工 v6 段 5 反馈 #6 实战)
- 不在 W77 自动启用, 即使 PROD_KEY_AUTO_ENABLE=True 也走沙箱

## §5 锚点范式守恒

- W76 第 1 批: 263 守恒
- W77 第 1 批 B-2: 268 守恒 (+1, B+D 渐进式主拍接入)

## §6 沉淀与索引

- **runbook**: `docs/w77-1st-batch-b2-edge-tts-android-mainplay-runbook-2026-07-28.md`
- **新模块**:
  - `app/services/android_tts_mainplay.py` (B+D 渐进式主拍接入核心)
  - `app/services/web_speech_fallback.py` (Android Chrome Web Speech API 降级)
  - `app/services/tts_cache.py` (pre-synthesize 缓存层, 24h TTL)
- **e2e**: `tests/test_android_chrome_edge_tts_e2e.py` (16 → 20 case)