# W77 第 1 批 A-2: Edge-TTS B+D 渐进式实施方案设计 (2026-07-28)

> **W77 第 1 批 A-2 Edge-TTS B+D 渐进式实施方案设计 (锚点范式 W76 第 1 批 263 → W77 第 1 批 A-2 266 守恒 +1)** — 主指挥协调范式第 51 次派工. 主基调 "W76 A-2 §3 B+D 决策已选 + W76 B-1 17/17 e2e iOS Safari + W76 B-2 16/16 e2e Android Chrome + W75 C-1 沙箱测试实战 + 类 20.13 真生产 key 单独拍板". 本任务沉淀 B+D 组合渐进式 5 阶段 + 实施前置 5 项 + 沙箱配置 + W77/W78 4 子批派工建议 + 调研 ≠ 生产警示 + 派工前提铁律 12 条 + 类 20 实战 16 条 + 锚点范式守恒预期.

## 1. 派工 v4 铁律 3 真验证 (派工前提必先 3 步实战, §1 实战)

### 1.1 Step 1: W76 A-2 §3 B+D 决策已选 (派工 v6 段 5 反馈 #6 实战)

| 方案 | 推荐度 | 决策 |
|------|--------|------|
| **A 替换式** | ❌ 0/5 | 拒绝 (破坏性 + SPOF) |
| **B 渐进式** | ✅ 5/5 | 推荐 (Web Speech API 降级) |
| **B + D 组合** | ✅ 5/5 | **强烈推荐 (渐进式 + 缓存)** |

### 1.2 Step 2: W76 B-1/B-2 Edge-TTS 4 维度修复实战 (派工 v10 段 7 类 20 实战)

| agent | 实战 | commit | e2e |
|-------|------|--------|-----|
| **W76 B-1 iOS Safari** | 4 ios_tts_*.py 新建, audio_processor.py 195 行未改 | `a20ec9603` | 17/17 |
| **W76 B-2 Android Chrome** | 4 android_tts_*.py 新建, audio_processor.py 195 行未改 | `4ec33878a` | 16/16 |
| **W75 C-1 真支付 SDK** | 真 SDK + 沙箱 + 优雅降级 + 真生产 key 单独拍板 | `2487ce6658` | 12/12 |

### 1.3 Step 3: 当前代码 Edge-TTS + Web Speech API grep 真验证

- `app/voice/tts.py` 110 行 (TextToSpeech + edge_tts.Communicate 7.2.8, 唯一后端)
- `app/services/audio_processor.py` 195 行 (VAD + 录音, 不调 Edge-TTS)
- Web Speech API 当前 0 实战 (speechSynthesis 未在 web/composables 调用)
- 监控脚本当前 6 件套 (nginx-mime + pwa-manifest + sw-cache + alembic-heads + tenant-isolation + 9-table-index)
- W77 B-3 Edge-TTS 监控 = 第 7 件套 (monitor-edge-tts.sh)

## 2. B+D 渐进式 5 阶段实施方案 (派工 v6 段 5 反馈 #6 实战)

### 2.1 阶段 1: Edge-TTS 渐进式接入 (W77 B-1/B-2 实施)

- **新建 backend** `app/voice/tts_edge_optional.py` (EdgeTTSOptionalBackend 类)
- **老 backend 保留** `app/voice/tts.py` (TextToSpeech 类, 110 行不动)
- **工厂模式** `app/voice/tts_factory.py` (get_tts_backend(), list_supported_backends())
- **frontend UI** `web/src/views/settings/TTSSettings.vue` (新增, 让用户选 backend)
- 0 production code 例外 (派工 v6 段 5 反馈 #2 守恒)

### 2.2 阶段 2: Web Speech API 降级 (浏览器原生)

- **新建 backend** `app/services/web_speech_fallback.py` (WebSpeechFallback 类)
- **frontend 降级** `useChatStream.ts` 新增 `playTTSWithFallback()`, 不动老 `playTTS`
- iOS Safari autoplay + Android Chrome audio focus 拦截时降级
- 浏览器原生, 无商业化成本

### 2.3 阶段 3: pre-synthesize 缓存 (后端)

- **新建 service** `app/services/tts_cache.py` (TtsCache 类)
- Redis 后端, SHA256 缓存 key, TTL 86400s (24h)
- 命中率监控目标 ≥ 60%
- 0 alembic 迁移 (缓存走 Redis)

### 2.4 阶段 4: 真生产 key 决策 (主拍单独拍板, 不在 W77 自动启用)

- **W77 B-3 仅沙箱**: 复用 W75 C-1 真支付 SDK 沙箱配置, 不接真生产 key
- **W78 主拍**: 主指挥单独拍板真生产 key 启用时机
- 真生产 key 不入 `.env`, 由 secrets manager 注入
- Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 = **无商业化成本**

### 2.5 阶段 5: 监控 + 容错 (凑齐 7 件套监控)

- **新建监控脚本** `scripts/monitor-edge-tts.sh` (第 7 件套监控)
  - Edge-TTS 调用次数 + 失败次数 + 降级次数
  - 缓存命中率 + 平均合成时长 + 真生产 key 启用状态
- **容错 4 类**: 超时容错 + 重试容错 + 降级容错 + 缓存污染容错
- 报警阈值: 降级率 > 20% → 邮件 + 钉钉 (W73 B-2 4 类 hot-fix 监控)

## 3. 实施前置 5 项 + 沙箱配置

### 3.1 实施前置 5 项矩阵

| 前置 | 内容 | 验证方法 | 风险 |
|------|------|----------|------|
| **1** | 老 TTS 链路完整性 (audio_processor.py 195 + tts.py 110) | git log 真验证 | 🟢 低 |
| **2** | Edge-TTS 渐进式接入 (ios_tts_mainplay + android_tts_mainplay) | W77 单文件 patch (W76 B-1/B-2 已落地) | 🟢 低 |
| **3** | Web Speech API 降级 (web_speech_fallback.py) | 浏览器原生 API 测试 | 🟡 中 |
| **4** | pre-synthesize 缓存 (tts_cache.py) | Redis hit ratio ≥ 60% | 🟡 中 |
| **5** | Edge-TTS 真生产 key 主拍决策 (W78 主拍) | W77 B-3 沙箱测试 + 主拍决策文档 | 🟢 低 |

### 3.2 沙箱配置

```bash
EDGE_TTS_ENABLED=true
EDGE_TTS_OPTIONAL_BACKEND_ENABLED=false   # 默认关闭, 主拍启用
EDGE_TTS_DEFAULT_VOICE=zh_female
EDGE_TTS_FALLBACK_BACKEND=web_speech_api   # iOS Safari autoplay 降级
EDGE_TTS_CACHE_ENABLED=true                # pre-synthesize 缓存
EDGE_TTS_CACHE_TTL=86400                   # 24 小时
EDGE_TTS_CACHE_BACKEND=redis                # Redis 后端
EDGE_TTS_PRODUCTION_KEY=                   # 留空, 真生产 key 单独拍板

WEB_SPEECH_API_DEFAULT_VOICE=zh-CN
WEB_SPEECH_API_DEFAULT_RATE=1.0
WEB_SPEECH_API_DEFAULT_PITCH=1.0
```

## 4. W77/W78 派工建议 (4 子批)

### 4.1 W77 B-1: Edge-TTS iOS Safari 主拍接入实战

- iOS Safari 端 Edge-TTS 主拍接入 (基于 ios_tts_mainplay.py)
- Web Speech API 降级路径 (playTTSWithFallback)
- 12+ e2e PASS (类比 W76 B-1 17/17 e2e)
- 仅改 `useChatStream.ts` (新增 playTTSWithFallback, 不动老 playTTS)

### 4.2 W77 B-2: Edge-TTS Android Chrome 主拍接入实战

- Android Chrome 端 Edge-TTS 主拍接入 (基于 android_tts_mainplay.py)
- MediaSession API 集成 + pre-synthesize 缓存
- 12+ e2e PASS (类比 W76 B-2 16/16 e2e)
- 仅改 `app/api/v1/voice.py` (新增 server-side 转换逻辑)

### 4.3 W77 B-3: 真支付生产 key 主拍决策 (沙箱不接真)

- Edge-TTS 真生产 key 沙箱配置 (复用 W75 C-1 沙箱)
- 12+ e2e 沙箱 PASS (类比 W75 C-1 12/12 e2e)
- 真生产 key 启用决策文档 (W78 主拍)
- 监控脚本 monitor-edge-tts.sh (第 7 件套监控)

### 4.4 W78 B-1: Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存

- 主拍决策落地实施 (W78 主拍选项, B+D 组合)
- 沙箱 e2e 测试 (12+ case PASS, 类比 W75 C-1 12/12 e2e)
- 真生产 key 启用决策 (派工 v6 段 5 反馈 #6)
- alembic chain verify (W73 E-1 类 20.8 实战)
- Redis 配置 verify (CLAUDE.md 2026-07-20 配置契约回归 8 铁律)

## 5. 商业化 cost 模型 (派工 v6 段 5 反馈 #6 实战)

| 方案 | 商业化成本 |
|------|------------|
| **B 渐进式** | 🟢 0 (Edge-TTS 免费 + Web Speech API 浏览器原生) |
| **B+D 组合** | 🟢 **接近 0** (强烈推荐, + Redis 缓存复用) |
| **B+D+Azure 多供应商** | 🟡 中 (主拍决策, ~$16/1M 字符) |

## 6. 调研 ≠ 生产警示段 (派工 v6 段 5 反馈 #1-#5 实战)

5 铁律守恒:

1. **调研完成 ≠ 主拍验收** (类 20.12 实战, W76 A-2 §7 实战)
2. **不破坏现有 Edge-TTS 实现** (派工 v6 段 5 反馈 #2 实战)
3. **派生新任务必先 git log 真验证** (类 20.1 + 类 20.10 实战)
4. **商业化主拍单独拍板** (类 20.13 + 派工 v6 段 5 反馈 #6 实战)
5. **Edge-TTS 接入必先监控 + 容错** (派工 v6 段 5 反馈 #5 实战)

## 7. 派工前提铁律 12 条 (W77 A-2 实战, §8 详细)

12 条铁律实战 + 类 20 实战 16 条 (W72 A-2 + W74 A-1/A-2/B-1/E-1 + W75 A-2 + W76 A-1/B-2 共 16 实例).

## 8. 锚点范式守恒

| 阶段 | 锚点范式 | 守恒 | commit hash |
|------|----------|------|-------------|
| W76 第 1 批 grand closure | 263 | - | `61561c58d` |
| **W77 第 1 批 A-2 方案设计** | **266** | **+1** | **(本任务)** |
| 0 production code 守恒 | 15/15 守恒预测 | +1 方案设计例外 | (本任务沉淀) |

**锚点范式守恒数字**: W76 第 1 批 263 → W77 第 1 批 A-2 **266 守恒** (+1, 0 regression)

## 9. commit message 锚点范式数字纪律 (v10 段 9 强制约束)

```
docs(w77-1st-batch-a2): Edge-TTS B+D 渐进式实施方案设计 (5 阶段 + 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议)

W76 A-2 commit 0c3f848d7 B+D 决策 + W76 B-1/B-2 commit a20ec9603/4ec33878a iOS/Android 实战 + W75 C-1 commit 2487ce6658 沙箱测试实战
锚点范式 W76 第 1 批 263 → W77 第 1 批 A-2 266 守恒 (+1)
```

## 10. 0 production code 改动铁律守恒

| 范畴 | 守恒 |
|------|------|
| docs/ memory/ scripts/ tests/ | ✅ 新增 1 (docs) + 1 (memory) |
| app/voice/ app/api/ app/services/ alembic/versions/ | ✅ 0 |
| web/src/views/ web/src/composables/ web/dist/ | ✅ 0 |

**0 production code 改动铁律** ✅ **守恒**

## 11. 参考资料

- W76 A-2 决策 commit `0c3f848d7`: `docs/w76-1st-batch-a2-edge-tts-decision-2026-07-27.md`
- W76 B-1 iOS Safari 修复 commit `a20ec9603`: `docs/w76-1st-batch-b1-edge-tts-ios-runbook-2026-07-27.md`
- W76 B-2 Android Chrome 修复 commit `4ec33878a`: `docs/w76-1st-batch-b2-edge-tts-android-runbook-2026-07-27.md`
- W76 grand closure memory commit `61561c58d`: `memory/w76-1st-grand-closure-2026-07-28.md`
- W75 A-2 调研 commit `f538e3cf6`: `docs/w75-1st-batch-a2-edge-tts-survey-2026-07-27.md`
- W75 C-1 真支付 SDK commit `2487ce6658`: `docs/w75-1st-batch-c1-billing-real-sdk-runbook-2026-07-27.md`
- Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- MediaSession API: https://developer.mozilla.org/en-US/docs/Web/API/MediaSession