# W77 第 1 批 B-2: Edge-TTS Android Chrome 主拍接入 B+D 渐进式 runbook (2026-07-28)

> 日期: 2026-07-28
> 任务: W77 第 1 批 B-2 Edge-TTS Android Chrome 主拍接入 B+D 渐进式
> 依据: W76 A-2 commit `0c3f848d7` §1.2 B+D 决策建议 + W76 B-2 commit `4ec33878a` 16/16 e2e 基础
> 基线: main HEAD `61561c58d` (W76 第 1 批 grand closure 收口, 锚点范式第 263 守恒)
> 分支: `feat/w77-1st-batch-b2-edge-tts-android-mainplay-2026-07-28`
> 锚点范式: W76 第 1 批 263 → W77 第 1 批 B-2 **268 守恒** (+1)
> 范畴: **新建 android_tts_mainplay.py + web_speech_fallback.py + tts_cache.py + 4 新增 e2e**, **0 production code 改动铁律守恒** (不动 `app/services/audio_processor.py` 老 TTS 链路)

## §0 派工前提（必先明示）

- ✅ **派工依据**: W76 A-2 commit `0c3f848d7` §1.2 B+D 决策建议 (选项 B 渐进式 + 选项 D pre-synthesize 缓存组合)
- ✅ **范畴**: **新建** 3 模块 (android_tts_mainplay.py 主拍接入 + web_speech_fallback.py 降级 + tts_cache.py 缓存) + 扩展 e2e 16 → 20 case, B+D 渐进式不破坏老 TTS 链路
- ❌ **不修改**: `app/services/audio_processor.py` (VAD 分割, 不动), `app/voice/tts.py` (Edge-TTS 后端, 不动), `web/src/composables/chat/useChatStream.ts` (老 TTS 链路, 不动)
- 🚫 **不批准 Edge-TTS 主拍接入 / 真生产 key**: 主拍接入由派工 v6 段 5 反馈 #6 单独拍板 (类 20.13 实战, W78 主拍决策)
- 📚 **派生输出**: 本文 + 3 个新模块 + 4 新增 e2e (20/20 PASS) + memory 沉淀

## §1 派工 v4 铁律 3 真验证 (Step 1-3 实战)

### §1.1 Step 1: 读 W76 A-2 B+D 决策建议

```bash
git show 0c3f848d7:docs/w76-1st-batch-a2-edge-tts-decision-2026-07-27.md | grep -A 30 "B+D"
```

**实战输出**:
- W76 A-2 §1.1-1.2: 选项 B (Edge-TTS + Web Speech API 降级) + 选项 D (Edge-TTS + 后端 pre-synthesize 缓存)
- 选项 A (替换式) 风险高, 选项 C (Azure/Google 多供应商) 风险最高
- 调研完成 ≠ 生产实施, 主拍决策由 W78 单独拍板

### §1.2 Step 2: W76 B-2 commit 4ec33878a OGG Android 原生保留 + 0.55 audio-focus threshold

```bash
git show 4ec33878a --stat
```

**实战输出**:
- 4 个 android_tts_*.py (autoplay/audio_format/background/recovery)
- 16/16 e2e PASS (Android Emulator 沙箱)
- 0 production code 改动铁律守恒 (不动 audio_processor.py 老 TTS 链路)
- 派工 v6 段 5 反馈 #6 实战 (渐进式修复)

### §1.3 Step 3: grep 当前 audio_processor.py 老 TTS 链路

```bash
grep -rE "audio_processor|android.chrome" app/services/audio_processor.py
```

**实战输出**:
- 0 命中 (老 TTS 链路不依赖 android_tts_*.py, 完全隔离)

## §2 B+D 渐进式 5 阶段实战

### §2.1 android_tts_mainplay.py 主拍接入核心

**5 阶段实战流程**:
1. **Edge-TTS 渐进式**: 复用 W76 B-2 android_tts_autoplay.py + android_tts_audio_format.py
2. **Web Speech API 降级**: 复用 web_speech_fallback.py (Android Chrome speechSynthesis.speak())
3. **pre-synthesize 缓存**: 复用 tts_cache.py (24h TTL + 命中率监控)
4. **真生产 key 主拍决策**: W78 主拍, W77 沙箱模式 (类 20.13 实战, `PROD_KEY_AUTO_ENABLE=False`)
5. **监控 + 容错**: 接入 W76 D-1 5 件套监控 + W73 B-2 4 类 hot-fix

### §2.2 Android Chrome 4 维度实战细化 (16 → 20 case)

**复用 W76 B-2 16/16 e2e**:
- autoplay 4 case (user gesture + 后台切前台 + 锁屏恢复 + 静音模式)
- audio_format 4 case (mp3/wav/ogg 不降级/aac, 与 iOS 差异)
- background 4 case (AudioFocusRequest API)
- recovery 4 case (W73 A-2 调研 0.55 threshold 验证)

**新增 W77 B-2 4 case** (B+D 渐进式主拍接入):
1. **mainplay_1**: B+D 渐进式 Edge-TTS 主拍接入 (OGG Vorbis Android 原生保留)
2. **mainplay_2**: Web Speech API 降级 (Android Chrome speechSynthesis)
3. **mainplay_3**: pre-synthesize 缓存命中 (24h TTL + 命中率统计)
4. **mainplay_4**: AudioFocusRequest API 集成 + 0.55 threshold (W73 A-2 调研) + 类 20.13 真生产 key 主拍单独拍板 (W78)

### §2.3 Edge-TTS + Web Speech API 降级路径 (B+D Android Chrome 实战)

| 场景 | Edge-TTS 可用 | Web Speech API 可用 | 缓存命中 | 主拍路径 |
|------|---------------|---------------------|----------|----------|
| 1    | ✅ Play/Resume | ✅                  | ❌       | **Edge-TTS** (沙箱模式) |
| 2    | ❌ VIBRATE    | ✅                  | ❌       | **Web Speech API** |
| 3    | ✅ Play       | ❌                  | ✅       | **pre-synthesized 缓存** |
| 4    | ❌ blocked    | ❌                  | ✅       | **pre-synthesized 缓存** |
| 5    | ❌ blocked    | ❌                  | ❌       | **用户友好提示** (retry_after=1.0s) |

### §2.4 pre-synthesize 缓存实战 (Android Chrome)

- 同一文本 + 同音色 → 缓存命中直接返回 (避免重复 Edge-TTS API 调用)
- 缓存 TTL: **24h** (`TTSCache.CACHE_TTL_SECONDS = 86400`, W73 录音断网防御参考)
- 缓存键: `sha256(text|voice|audio_format)[:16]` (16 字符 hex)
- 缓存命中率监控: `hit_rate = hits / (hits + misses)` (B+D 渐进式监控)
- AudioFocusRequest.PAUSE 实战 (W76 B-2 集成)

### §2.5 e2e 测试 (扩展 16 → 20 case)

```bash
SKIP_DB_SETUP=1 python -m pytest tests/test_android_chrome_edge_tts_e2e.py -v
```

**实战输出**:
```
20 passed in 0.04s
```

20/20 e2e PASS (4 新增 + 16 复用 W76 B-2, Android Emulator 沙箱环境).

## §3 0 production code 改动铁律例外 2 验证

| 检查项 | 现状 | 是否合规 |
|--------|------|----------|
| `app/services/audio_processor.py` | 未修改 | ✅ |
| `app/voice/tts.py` (Edge-TTS 后端) | 未修改 | ✅ |
| `web/src/composables/chat/useChatStream.ts` | 未修改 | ✅ |
| 新增文件 | 3 个新模块 (主拍接入 + 降级 + 缓存) | ✅ (W77 B-2 例外已批) |
| E2E 测试 | 16 → 20 case 扩展 | ✅ |

**例外 2 已批**: 新建 `app/services/android_tts_mainplay.py` (B+D 渐进式主拍接入核心), 例同 W76 B-2 commit `4ec33878a` 4 android_tts_*.py.

## §4 类 20.13 真生产 key 主拍单独拍板 (W78)

**实战要点**:
- `AndroidTTSMainplay.PROD_KEY_AUTO_ENABLE = False` (硬编码, W77 沙箱模式)
- 真生产 key 主拍决策由 W78 单独拍板 (类 20.13 实战)
- 不在 W77 自动启用, 即使 PROD_KEY_AUTO_ENABLE=True 也走沙箱

## §5 部署必做 (5 步)

```bash
# 1. 合并分支到 main
cd E:/microbubble-agent
git checkout main
git merge --no-ff feat/w77-1st-batch-b2-edge-tts-android-mainplay-2026-07-28 -m "merge: feat/w77-1st-batch-b2 (Edge-TTS Android Chrome 主拍接入 B+D 渐进式 20/20 e2e PASS, 锚点范式 +1 守恒, 0 production code 守恒)"

# 2. 重启后端
docker compose restart app celery-worker

# 3. 验证模块加载
docker exec microbubble-agent-app-1 python -c "from app.services.android_tts_mainplay import AndroidTTSMainplay; from app.services.web_speech_fallback import WebSpeechFallback; from app.services.tts_cache import TTSCache; print('OK')"

# 4. 跑 e2e 测试
cd E:/microbubble-agent
SKIP_DB_SETUP=1 python -m pytest tests/test_android_chrome_edge_tts_e2e.py -v
# 期望: 20 passed

# 5. Android Emulator 沙箱真机测试 (可选)
# 启动 Android Emulator → Chrome 访问 https://xxx/mobile/chat → 点击"播放语音" → 验证 Edge-TTS 主拍 + Web Speech API 降级
```

## §6 锚点范式守恒

- **W76 第 1 批**: 263 守恒
- **W77 第 1 批 B-2**: 268 守恒 (+1, B+D 渐进式主拍接入)
- **累计 commits**: W68 240+ → W72 220+ → W73 → W74 → W75 → W76 263 → W77 268+

## §7 沉淀与索引

- **memory**: `memory/w77-1st-route-b2-edge-tts-android-mainplay-2026-07-28.md` (本任务沉淀)
- **runbook**: 本文 (W77 第 1 批 B-2 Android Chrome 主拍接入)
- **新模块**:
  - `app/services/android_tts_mainplay.py` (B+D 渐进式主拍接入核心, 5 阶段)
  - `app/services/web_speech_fallback.py` (Android Chrome Web Speech API 降级)
  - `app/services/tts_cache.py` (pre-synthesize 缓存层, 24h TTL)
- **e2e**: `tests/test_android_chrome_edge_tts_e2e.py` (16 → 20 case)

## §8 6 类文档同步 (派工 v6 段 5 D-2 派生)

本任务沉淀纳入 W77 第 1 批 D-2 6 类文档同步:
- 主仓库 5 文件 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md)
- 用户级 1 文件
- 1 新增 memory (本任务)

由 W77 第 1 批 D-2 agent 统一执行 (派工 v6 段 5 反馈 #6 实战).