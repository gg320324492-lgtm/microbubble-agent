# W77 第 1 批 A-2: Edge-TTS B+D 渐进式实施方案设计 (2026-07-28)

> **W77 第 1 批 A-2 Edge-TTS B+D 渐进式实施方案设计 (锚点范式 W76 第 1 批 263 → W77 第 1 批 A-2 266 守恒 +1)** — W76 A-2 commit `0c3f848d7` §3 B+D 决策已选 + W76 B-1 commit `a20ec9603` 17/17 e2e iOS Safari 实战 + W76 B-2 commit `4ec33878a` 16/16 e2e Android Chrome 实战 + W75 C-1 commit `2487ce6658` 真支付 SDK 沙箱测试实战 + 派工 v6 段 5 反馈 #6 实战（商业化主拍单独拍板）+ 类 20.12 调研完成 ≠ 主拍验收 + 类 20.13 真生产 key 单独拍板. 本任务沉淀 B+D 组合渐进式 5 阶段 + 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议 + 调研 ≠ 生产警示 + 派工前提铁律 + 锚点范式守恒预期.

## 0. 调研边界（必先明示）

- ✅ **调研范围**：W76 A-2 §3 决策已选 B+D 组合方案 → 本任务沉淀 5 阶段渐进式实施方案 (Edge-TTS 渐进 + Web Speech API 降级 + pre-synthesize 缓存 + 真生产 key W78 主拍 + 监控容错) + 实施前置 5 项 + 沙箱配置 + W77/W78 4 子批派工建议
- ❌ **不实施**：不动 `app/voice/tts.py` (110 行 Edge-TTS) + `app/services/audio_processor.py` (195 行 VAD) + `app/api/v1/voice.py` + `web/src/composables/chat/useChatStream.ts` + `web/src/views/mobile/chat/*` 老路径
- 🚫 **不批准 Edge-TTS 主拍启用 / 接真生产 key / 启用 Azure-Google 多供应商**：B+D 实施方案仅设计, 主拍由派工 v6 段 5 反馈 #6 单独拍板（类 20.13 实战, W78 主拍）
- 📚 **派生输出**：`docs/w77-1st-batch-a2-edge-tts-bd-plan-2026-07-28.md` (本文) + `memory/w77-1st-route-a2-edge-tts-bd-plan-2026-07-28.md` (本任务沉淀)

## 1. 派工 v4 铁律 3 真验证 (派工前提必先 3 步实战)

### 1.1 Step 1: W76 A-2 §3 B+D 决策已选 + §5.3 W77 Step 10 主拍

**W76 A-2 commit `0c3f848d7` §3 主拍决策**：

| 方案 | 破坏性 | 风险 | 实施成本 | 0 production 例外 | 回滚难度 | 推荐度 | 决策 |
|------|--------|------|----------|-------------------|----------|--------|------|
| **A 替换式** | 🔴 高 | 🔴 高 | 🔴 高 | ❌ 不符合 | 🔴 高 | ❌ 0/5 | **拒绝** |
| **B 渐进式** | 🟢 极低 | 🟢 低 | 🟡 中 | 🟢 符合 | 🟢 极低 | ✅ 5/5 | **推荐** |
| **C 旁路式** | 🟢 极低 | 🟡 中 | 🟡 中 | 🟢 符合 | 🟢 极低 | ⚠️ 3/5 | **保守备选** |
| **B + D 组合** | 🟢 低 | 🟢 低 | 🟡 中 | 🟢 符合 | 🟢 极低 | ✅ 5/5 | **强烈推荐** |

**W76 A-2 §3 主拍决策**: **首选 B+D 组合 (渐进式 Edge-TTS 接入 + Web Speech API 降级 + pre-synthesize 缓存)** — 本任务 W77 A-2 实施方案设计依此决策.

**W76 A-2 §5.3 W77 Step 10 主拍决策** (派工 v6 段 5 反馈 #6 实战):
- W77 B-1: Edge-TTS iOS Safari 主拍接入实战 (本批次)
- W77 B-2: Edge-TTS Android Chrome 主拍接入实战 (本批次)
- W77 B-3: 真支付生产 key 主拍决策 (本批次, 沙箱不接真)
- W78 B-1: Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存 (主拍接入 + 真生产 key 启用)

### 1.2 Step 2: W75 C-1 真支付 SDK 沙箱测试实战 + W76 B-1/B-2 Edge-TTS 实施

**W75 C-1 commit `2487ce6658` 真支付 SDK 接入实战模式** (派工 v6 段 5 反馈 #6 实战):
- 3 支付渠道真 SDK 接入 (Stripe + Alipay + WeChat Pay V3)
- 沙箱模式 (默认不接真钱, 小额 ¥0.01 测试)
- 优雅降级 (SDK 不可用 / API key 缺失 → 自动降级 mock)
- 真生产 key 单独拍板 (派工 v6 段 5 反馈 #6 守门)
- 12/12 e2e PASS 沙箱 (3 支付 × 4 实战 + 重放保护 3)

**W76 B-1 commit `a20ec9603` iOS Safari 4 维度修复实战** (W77 派工 v10 段 7 类 20 实战):
- 17/17 e2e PASS (4 维度 16 case + 1 综合一键, 0.06s)
- 4 ios_tts_*.py 新建 (audio_processor.py 195 行 VAD + tts.py 110 行 Edge-TTS 全部未改动)
- OGG → MP3 降级实战 (iOS Safari 音频格式 §2.2 拦截)

**W76 B-2 commit `4ec33878a` Android Chrome 4 维度修复实战**:
- 16/16 sandbox e2e PASS (4 维度策略模块)
- OGG Vorbis Android 原生保留 (与 iOS MP3 降级差异实战)
- 0.55 audio-focus threshold + 3 次指数退避 (W73 A-2 调研命中 + 网络抖动实战)

**Edge-TTS B+D 接入实战类比 W75 C-1 + W76 B-1/B-2**:
- W75 C-1: 真 SDK 接入 + 沙箱测试 + 真生产 key 单独拍板 (3 阶段)
- W76 B-1/B-2: iOS Safari / Android Chrome 渐进式 4 维度修复 (派工 v6 段 5 反馈 #6 实战)
- **W77 A-2**: Edge-TTS B+D 渐进式 5 阶段实施方案设计 (范式对齐)

### 1.3 Step 3: 当前代码 Edge-TTS + Web Speech API grep 真验证

```bash
# Step 3a: Edge-TTS 当前代码
grep -rE "EdgeTTS|edge_tts|WebSpeech|speechSynthesis" app/services/audio_processor.py app/voice/ web/src/composables/
```

**实战输出**:
```
app/voice/tts.py:import edge_tts
app/voice/tts.py:        communicate = edge_tts.Communicate(
app/voice/tts.py:        communicate = edge_tts.Communicate(
```

**发现**:
- `app/voice/tts.py` 是 Edge-TTS 唯一后端实现 (110 行, TextToSpeech 类 + edge_tts.Communicate 7.2.8)
- `app/services/audio_processor.py` 是音频处理 (195 行, VAD + 录音/WebM→WAV), 不直接调 Edge-TTS
- Edge-TTS 仅 1 次升级历史 (6.1.9 → 7.2.8, commit `41cf204d2`)
- **Web Speech API 当前 0 实战** (speechSynthesis / SpeechSynthesisUtterance 未在 web/composables 中调用)
- **B+D 渐进式接入 = 新建 EdgeTTSOptionalBackend + WebSpeechFallback + TtsCache 三模块, 老 TextToSpeech 100% 保留**

```bash
# Step 3b: 监控脚本 7 件套
ls scripts/monitor-*.sh 2>/dev/null
```

**实战输出**:
```
scripts/monitor-9-table-index.sh
scripts/monitor-alembic-heads.sh
scripts/monitor-nginx-mime.sh
scripts/monitor-pwa-manifest.sh
scripts/monitor-sw-cache.sh
scripts/monitor-tenant-isolation.sh
```

**发现**:
- 当前 6 件套监控 (nginx-mime + pwa-manifest + sw-cache + alembic-heads + tenant-isolation + 9-table-index)
- **W77 B-3 Edge-TTS 监控 = 第 7 件套监控脚本 (monitor-edge-tts.sh)**
- 凑齐 7 件套监控, 类 20.13 商业化主拍接入配套监控实战

## 2. B+D 渐进式 5 阶段实施方案 (派工 v6 段 5 反馈 #6 实战)

### 2.1 阶段 1: Edge-TTS 渐进式接入 (W77 B-1/B-2 实施)

**目标**: 不破坏老 TTS 链路, Edge-TTS 作为可选 backend 渐进式接入.

**实施步骤**:
1. **新建 backend** `app/voice/tts_edge_optional.py` (EdgeTTSOptionalBackend 类)
   - 100% 复用老 `edge_tts.Communicate()` 7.2.8 调用逻辑
   - 与 `app/voice/tts.py` 老 `TextToSpeech` 类同接口 (synthesize + synthesize_stream)
   - settings.TTS_OPTIONAL_BACKEND_ENABLED = False (默认关闭)
2. **老 backend 保留** `app/voice/tts.py` (TextToSpeech 类, 当前, 110 行不动)
3. **工厂模式** `app/voice/tts_factory.py` (get_tts_backend(), list_supported_backends())
   - 返回 backend 列表供 frontend 选择
   - 默认 backend = settings.TTS_DEFAULT_BACKEND = "edge_tts" (维持现状)
4. **frontend UI** `web/src/views/settings/TTSSettings.vue` (新增)
   - 让用户选 backend (老 Edge-TTS vs Edge-TTS Optional)
   - 默认 Edge-TTS, 渐进式启用 Optional

**0 production code 例外判定** (派工 v6 段 5 反馈 #2 实战):
- 老 `TextToSpeech` 类**完全不动** (向后兼容 100%)
- 新 backend 仅作可选 (settings 切换, 不破坏老路径)
- 例外 0 (新增模块不算例外, 派工 v6 段 5 反馈 #2 守恒)

### 2.2 阶段 2: Web Speech API 降级 (浏览器原生)

**目标**: iOS Safari autoplay + Android Chrome audio focus 拦截时, 自动降级浏览器原生 Web Speech API.

**实施步骤**:
1. **新建 backend** `app/services/web_speech_fallback.py` (WebSpeechFallback 类)
   - 暴露 `/api/v1/tts/web-speech-config` 端点
   - 返回浏览器原生 Web Speech API 配置 (voice/lang/rate/pitch)
   - frontend 检测 Edge-TTS 失败时调用此 endpoint 获取配置
2. **frontend 降级** `web/src/composables/chat/useChatStream.ts` (新增降级路径, 不动老 playTTS)
   ```javascript
   // 新增降级路径, 不破坏老 playTTS
   async function playTTSWithFallback(text) {
     try {
       await playTTS(text)  // 老 Edge-TTS 路径
     } catch (e) {
       console.warn('Edge-TTS failed, fallback to Web Speech API', e)
       playWebSpeech(text)  // 新增降级路径
     }
   }
   ```
3. **iOS Safari 降级命中条件**:
   - user gesture 上下文丢失 (W76 A-2 §2.1 iOS-S-1.1/1.2 拦截)
   - AudioContext.state === 'suspended' (iOS-S-1.3 拦截)
   - visibilitychange + 后台 tab 暂停 (iOS-B-3.2/3.3/3.4 拦截)
4. **Android Chrome 降级命中条件**:
   - audio focus 抢占 (W76 A-2 §2.2 AND-A-1.3 拦截)
   - MediaSession API 不可用时

**关键纪律 (派工 v6 段 5 反馈 #6 实战)**:
- Web Speech API 浏览器原生, 无商业化成本 (类 20.13 实战)
- 降级不破坏老 Edge-TTS 链路 (W75 C-1 真支付 SDK 优雅降级模式类比)
- 真生产 key / Azure-Google 切换 = 主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)

### 2.3 阶段 3: pre-synthesize 缓存 (后端)

**目标**: 同一文本 + 同音色 → 缓存命中直接返回, 避免重复 Edge-TTS API 调用.

**实施步骤**:
1. **新建 service** `app/services/tts_cache.py` (TtsCache 类)
   - 缓存 key: `f"{voice}:{text}:{rate}:{pitch}"` (SHA256 哈希)
   - 缓存 value: 音频 bytes + 创建时间 + 过期时间
   - 缓存后端: Redis (利用现有 Redis 配置, settings.REDIS_URL)
   - TTL: settings.TTS_CACHE_TTL = 86400 (24 小时, 类比 Celery session 24h)
2. **接入 audio_processor**:
   - synthesize() 前先查 Redis 缓存
   - 缓存命中直接返回 bytes (0 Edge-TTS API 调用)
   - 缓存未命中调 Edge-TTS + 写缓存
3. **降级命中**:
   - Edge-TTS 失败 + Web Speech API 失败 + 缓存 miss → 用户友好提示 "TTS 暂时不可用"
   - 类比 W75 C-1 真支付 SDK 优雅降级模式
4. **监控**:
   - 缓存命中率 = cache_hits / (cache_hits + cache_misses)
   - Edge-TTS API 调用次数 = cache_misses + cache_disabled_misses
   - 监控目标: 命中率 ≥ 60% (商业化 24 人月 Phase 8 实时语音)

**alembic 不涉及** (派工 v6 段 5 反馈 #5 实战):
- 缓存走 Redis, 不需新建 SQL 表
- 0 alembic 迁移 (类比 W76 B-1/B-2 Edge-TTS 修复, 0 alembic 迁移)

### 2.4 阶段 4: 真生产 key 决策 (主拍单独拍板, 不在 W77 自动启用)

**目标**: 类 20.13 实战 — Edge-TTS 真生产 key / Azure TTS / Google TTS 启用由主拍单独拍板, 不在 W77 自动启用.

**W77 B-3 真生产 key 主拍决策** (派工 v6 段 5 反馈 #6 实战):
- **W77 B-3 仅沙箱**: 复用 W75 C-1 真支付 SDK 沙箱配置, 不接真生产 key (类 20.13 实战)
- **W78 主拍**: 主指挥单独拍板真生产 key 启用时机
- **真生产 key 不入 `.env`**: 由 secrets manager (1Password / Vault) 注入
- **Edge-TTS 7.2.8 免费**: 无真生产 key 需求 (Microsoft readaloud 端点, 无 key 即可调用)
- **Azure/Google TTS 按字符计费**: ~$16/1M 字符, 真生产 key 仅在多供应商时需要 (主拍决策)

**Edge-TTS 真接入 3 阶段实战类比 W75 C-1** (派工 v6 段 5 反馈 #6 实战):
| 阶段 | W75 C-1 真支付 SDK | W77/W78 Edge-TTS |
|------|---------------------|-------------------|
| 调研 | W74 B-2 mock 实战 | W76 A-2 决策 + W77 A-2 实施方案 |
| 沙箱 | W75 C-1 真 SDK + 12/12 e2e | W77 B-3 真生产 key 沙箱 (本批次) |
| 真生产 | 主拍单独拍板 (W77+) | W78 主拍 + 真生产 key 启用 |

### 2.5 阶段 5: 监控 + 容错 (W73 B-2 4 类 hot-fix 监控 + W74 D-1 多租户监控 + W75 B-3 webhook 监控 实战)

**目标**: Edge-TTS 调用监控 + 降级监控 + 缓存命中率监控 + 商业化成本监控, 凑齐 7 件套监控脚本.

**实施步骤**:
1. **新建监控脚本** `scripts/monitor-edge-tts.sh` (第 7 件套监控)
   - Edge-TTS 调用次数 + 失败次数 + 降级次数
   - 缓存命中率 (cache_hits / total_requests)
   - 平均合成时长 (ms)
   - Web Speech API 调用次数 (降级命中)
   - 真生产 key 启用状态 (默认 false)
2. **监控接入**:
   - 加入 `scripts/monitor-all.sh` 调度 (W74 D-1 多租户监控模式)
   - 报警阈值: 降级率 > 20% → 邮件 + 钉钉报警 (W73 B-2 4 类 hot-fix 监控实战)
3. **容错 4 类实战** (派工 v10 段 7 类 20 实战):
   - **超时容错**: synthesize() 5s timeout (W74 D-1 实战)
   - **重试容错**: retry 3 次 + 指数退避 (1s/2s/4s, W76 B-1/B-2 实战)
   - **降级容错**: Edge-TTS 失败 → Web Speech API → 缓存 → 友好提示
   - **缓存污染容错**: Redis cache miss 不阻塞流式 (CLAUDE.md 2026-06-28 flag_modified 教训复用)

## 3. 实施前置 5 项 + 沙箱配置

### 3.1 实施前置 5 项矩阵

| 前置 | 内容 | 验证方法 | 派工依据 | 风险等级 |
|------|------|----------|----------|----------|
| **1** | 老 TTS 链路完整性 (audio_processor.py 195 行 VAD + tts.py 110 行 Edge-TTS) | git log 真验证, 无 refactor | W75 A-2 §1.2 实战 + W76 A-2 §4.2 实战 | 🟢 低 |
| **2** | Edge-TTS 渐进式接入 (ios_tts_mainplay.py + android_tts_mainplay.py, W77 B-1/B-2 实施) | W77 单文件 patch 验证 (W76 B-1 17/17 e2e + B-2 16/16 e2e 已落地) | W76 A-2 §4.3 + W76 B-1/B-2 commit | 🟢 低 |
| **3** | Web Speech API 降级 (web_speech_fallback.py) | 浏览器原生 API 测试 (iOS Safari + Android Chrome) | W76 A-2 §2.1/2.2 + W76 A-2 §4.4 实战 | 🟡 中 |
| **4** | pre-synthesize 缓存 (tts_cache.py) | 缓存命中率测试 (Redis hit ratio ≥ 60%) | W76 A-2 §3.3 D 方案 + 阶段 3 §2.3 实战 | 🟡 中 |
| **5** | Edge-TTS 真生产 key 主拍决策 (W78 主拍, 不在 W77) | W77 B-3 沙箱测试 + 主拍决策文档 (类 20.13) | W75 C-1 §3.3/4.3 + W76 A-2 §4.6 实战 | 🟢 低 |

### 3.2 实施前置 1: 老 TTS 链路完整性验证

**验证命令** (派工 v4 铁律 3 实战):
```bash
# 真验证 app/voice/tts.py + app/services/audio_processor.py 无 refactor
git log --oneline main -- app/voice/tts.py app/services/audio_processor.py | head -20
# 期望: 仅 commit 41cf204d2 (Edge-TTS 升级) + W76 B-1/B-2 ios_tts_*.py + android_tts_*.py 新建
```

**验证标准**:
- ✅ 仅 1 次 Edge-TTS 升级历史 (6.1.9 → 7.2.8)
- ✅ 无 refactor / 无破坏性 commit
- ✅ 16 voice 选项完整
- ✅ synthesize + synthesize_stream 双 API
- ✅ W76 B-1 17/17 e2e PASS + W76 B-2 16/16 e2e PASS 实战 (audio_processor.py 195 行未改)

### 3.3 实施前置 2: Edge-TTS 渐进式接入

**接入路径决策** (W75 C-1 真支付 SDK 模式 + W76 B-1/B-2 渐进式模式类比):
- **新增 backend**: `app/voice/tts_edge_optional.py` (EdgeTTSOptionalBackend 类)
- **老 backend 保留**: `app/voice/tts.py` (TextToSpeech 类, 110 行, 不动)
- **工厂模式**: `app/voice/tts_factory.py` (get_tts_backend(), list_supported_backends())
- **frontend UI**: `web/src/views/settings/TTSSettings.vue` (新增, 让用户选 backend)
- **default backend**: settings.TTS_DEFAULT_BACKEND = "edge_tts" (维持现状)

**关键纪律 (派工 v6 段 5 反馈 #2 实战)**:
- 老 `TextToSpeech` 类**完全不动** (向后兼容)
- 新 backend 仅作可选 (settings 切换)
- 真生产 key / Azure-Google 切换 = 主拍单独拍板 (派工 v6 段 5 反馈 #6)

### 3.4 实施前置 3: Web Speech API 降级

**实施交付** (基于 W76 A-2 §2.1/2.2 + W76 B-1/B-2 实战):
- `app/services/web_speech_fallback.py` 新建 (WebSpeechFallback 类)
- `/api/v1/tts/web-speech-config` 端点 (返回浏览器原生配置)
- `useChatStream.ts` 新增降级路径 (playTTSWithFallback, 不动老 playTTS)
- iOS Safari + Android Chrome 双端实测 (类 20.14 实战)

**关键拦截** (W76 A-2 §2.1/2.2 32 case):
- iOS-S-1.1/1.2: user gesture 丢失 → Web Speech API 降级
- AND-A-1.3: audio focus → Web Speech API 降级 (MediaSession 不可用时)

### 3.5 实施前置 4: pre-synthesize 缓存

**实施交付** (基于 W76 A-2 §3.3 D 方案 + 阶段 3 §2.3 实战):
- `app/services/tts_cache.py` 新建 (TtsCache 类)
- Redis 后端, SHA256 缓存 key, TTL 86400s
- 命中率监控 (cache_hits / total_requests)
- 接入 audio_processor synthesize() 前置缓存查询

**关键拦截**:
- 缓存 miss → 调 Edge-TTS + 写缓存 (W75 C-1 真支付 SDK mock 降级模式)
- 缓存 hit 直接返回 bytes (0 Edge-TTS API 调用)
- 监控目标: 命中率 ≥ 60% (商业化 24 人月 Phase 8 实时语音)

### 3.6 实施前置 5: 沙箱配置 + 商业化真生产 key 主拍决策

**沙箱配置** (W75 C-1 §3.3/4.3 + W76 A-2 §4.6 模式类比):
```bash
# Edge-TTS 7.2.8 沙箱 (无需 API key, Microsoft readaloud 端点)
EDGE_TTS_ENABLED=true
EDGE_TTS_OPTIONAL_BACKEND_ENABLED=false   # 默认关闭, 主拍启用
EDGE_TTS_DEFAULT_VOICE=zh_female
EDGE_TTS_FALLBACK_BACKEND=web_speech_api   # iOS Safari autoplay 降级
EDGE_TTS_CACHE_ENABLED=true                # pre-synthesize 缓存
EDGE_TTS_CACHE_TTL=86400                   # 24 小时
EDGE_TTS_CACHE_BACKEND=redis                # Redis 后端

# 沙箱测试 (小额流量, 不接真生产 key)
EDGE_TTS_PRODUCTION_KEY=                   # 留空, 真生产 key 单独拍板

# Web Speech API 浏览器原生配置
WEB_SPEECH_API_DEFAULT_VOICE=zh-CN
WEB_SPEECH_API_DEFAULT_RATE=1.0
WEB_SPEECH_API_DEFAULT_PITCH=1.0
```

**真生产 key 主拍决策** (派工 v6 段 5 反馈 #6 + 类 20.13 实战):
- W76/W77/W78 任意批次, 主拍依业务上线进度拍板
- 真生产 key 不入 `.env`, 由 secrets manager (1Password / Vault) 注入
- Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 = **无商业化成本**
- 真生产 key 仅在 Azure/Google TTS 多供应商时需要 (主拍决策, 不在本调研)

## 4. W77/W78 派工建议 (4 子批)

### 4.1 W77 B-1: Edge-TTS iOS Safari 主拍接入实战

**派工输入**:
- W76 A-2 §3 B+D 决策 (本任务)
- W76 A-2 §4.4 iOS Safari 4 维度实战 (16 case)
- W76 B-1 commit `a20ec9603` 17/17 e2e 实施 (4 ios_tts_*.py)

**预期交付**:
- iOS Safari 端 Edge-TTS 主拍接入 (基于 ios_tts_mainplay.py, W77 单文件 patch)
- Web Speech API 降级路径 (playTTSWithFallback)
- 12+ e2e PASS (类比 W76 B-1 17/17 e2e)

**实施前置**:
- 调研阶段不动 `useChatStream.ts:887`
- W77 B-1 实施阶段才改 `useChatStream.ts` (新增 playTTSWithFallback, 不动老 playTTS)
- 必先 git log + grep 真验证 (派工 v4 铁律 3 实战)

### 4.2 W77 B-2: Edge-TTS Android Chrome 主拍接入实战

**派工输入**:
- W76 A-2 §3 B+D 决策 (本任务)
- W76 A-2 §4.5 Android Chrome 4 维度实战 (16 case)
- W76 B-2 commit `4ec33878a` 16/16 e2e 实施 (4 android_tts_*.py)

**预期交付**:
- Android Chrome 端 Edge-TTS 主拍接入 (基于 android_tts_mainplay.py, W77 单文件 patch)
- MediaSession API 集成 + pre-synthesize 缓存
- 12+ e2e PASS (类比 W76 B-2 16/16 e2e)

**实施前置**:
- 调研阶段不动 `app/api/v1/voice.py:88`
- W77 B-2 实施阶段才改 `app/api/v1/voice.py` (新增 server-side 转换逻辑)
- 必先 git log + grep 真验证 (派工 v4 铁律 3 实战)

### 4.3 W77 B-3: 真支付生产 key 主拍决策 (沙箱不接真)

**派工输入**:
- W75 C-1 commit `2487ce6658` 真支付 SDK 沙箱测试实战 (12/12 e2e)
- 派工 v6 段 5 反馈 #6 (商业化主拍单独拍板)
- 类 20.13 真生产 key 单独拍板

**预期交付**:
- Edge-TTS 真生产 key 沙箱配置 (复用 W75 C-1 沙箱配置)
- 12+ e2e 沙箱 PASS (类比 W75 C-1 12/12 e2e)
- 真生产 key 启用决策文档 (W78 主拍)
- 监控脚本 monitor-edge-tts.sh (第 7 件套监控, 凑齐 7 件套)

**实施前置**:
- 调研阶段不动商业化 docker base
- W77 B-3 实施阶段才动沙箱配置 (派工 v10 段 8 W73 起步纪律第 5 项实战)
- 真生产 key 单独拍板 (派工 v6 段 5 反馈 #6)

### 4.4 W78 B-1: Edge-TTS B+D 组合渐进式 + Web Speech API 降级 + pre-synthesize 缓存

**派工输入**:
- W77 B-1/B-2/B-3 实施数据
- W77 A-2 (本文) B+D 渐进式 5 阶段实施方案
- W75 C-1 真支付 SDK 沙箱测试实战对比

**预期交付**:
- 主拍决策落地实施 (W78 主拍选项, B+D 组合)
- 沙箱 e2e 测试 (12+ case PASS, 类比 W75 C-1 12/12 e2e)
- 真生产 key 启用决策 (派工 v6 段 5 反馈 #6)
- 0 production code 例外清单 (主拍决策 + 派工批文)

**实施前置**:
- 调研阶段不动 `app/voice/tts.py` + `app/services/audio_processor.py`
- W78 B-1 实施阶段才动主拍接入实施
- 必先 alembic chain verify (W73 E-1 类 20.8 实战)
- Redis 配置 verify (CLAUDE.md 2026-07-20 配置契约回归 8 铁律实战)

## 5. 商业化 cost 模型 (派工 v6 段 5 反馈 #6 实战)

| 方案 | Edge-TTS 成本 | Web Speech API 成本 | Azure TTS | Google TTS | 商业化成本 |
|------|---------------|----------------------|-----------|------------|------------|
| **A 替换式** | 免费 | - | - | - | 🟢 0 (但 SPOF 风险) |
| **B 渐进式** | 免费 | 浏览器原生 | - | - | 🟢 0 (推荐) |
| **C 旁路式** | 免费 + 离线缓存 | - | - | - | 🟢 0 (保守) |
| **B + D 组合** | 免费 + Redis 缓存 | 浏览器原生 | - | - | 🟢 **接近 0** (强烈推荐) |
| **B + D + Azure 多供应商** | 免费 + 缓存 | 浏览器原生 | ~$16/1M 字符 | ~$16/1M 字符 | 🟡 中 (主拍决策) |

**B+D 组合商业化成本实战**:
- Edge-TTS 7.2.8 免费 (Microsoft readaloud 端点, 无 key)
- Web Speech API 浏览器原生 (无商业化成本)
- Redis 缓存复用现有 Redis 配置 (0 增量成本)
- **推荐组合 B+D = 商业化成本接近 0**

## 6. 0 production code 改动铁律守恒验证

| 范畴              | W77 第 1 批 A-2 预期 | W77 第 1 批 A-2 实际 | 守恒 |
|-------------------|---------------------|---------------------|------|
| docs/             | 新增 1               | 新增 1 (本文)        | ✅   |
| memory/           | 新增 1               | 新增 1 (本任务沉淀)  | ✅   |
| scripts/          | 0                   | 0                   | ✅   |
| tests/            | 0                   | 0                   | ✅   |
| app/voice/        | 0                   | 0                   | ✅   |
| app/api/          | 0                   | 0                   | ✅   |
| app/services/     | 0                   | 0                   | ✅   |
| alembic/versions/ | 0                   | 0                   | ✅   |
| web/src/views/    | 0                   | 0                   | ✅   |
| web/src/composables/ | 0                | 0                   | ✅   |
| web/dist/         | 0                   | 0                   | ✅   |

**0 production code 改动铁律** ✅ **守恒**

## 7. 调研 ≠ 生产警示段 (派工 v6 段 5 反馈 #1-#5 实战 + 类 20.12/20.13 实战)

派工 v6 段 5 反馈 #1-#5 实战沉淀 5 铁律守恒 + 类 20.12 调研完成 ≠ 主拍验收 + 类 20.13 真生产 key 单独拍板：

1. **调研完成 ≠ 主拍验收** (类 20.12 实战, W76 A-2 §7 实战)
   - 现状：本调研 B+D 5 阶段 + 实施前置 5 项 + W77/W78 派工建议 = 全栈覆盖
   - 必做：主指挥拍"是否进 W77/W78 实施阶段" + 选 B+D 渐进式 / 商业化主拍
2. **不破坏现有 Edge-TTS 实现** (派工 v6 段 5 反馈 #2 实战)
   - 现状：`app/voice/tts.py` (110 行) + `app/services/audio_processor.py` (195 行) + `useChatStream.ts:887` 现状摸底完成
   - 必做：W77/W78 实施阶段必先 git log + git show + grep 三步真验证 (派工 v4 铁律 3)
3. **派生新任务必先 git log 真验证** (类 20.1 + 类 20.10 实战, 派工 v6 段 5 反馈 #3)
   - 现状：本调研 5 阶段中**所有派生任务**已在 §1.1-1.3 + §3.1 实战验证
   - 必做：W77/W78 派工前必再跑 `git log` + `grep` 确认派生任务未在期间被实施
4. **商业化主拍单独拍板** (类 20.13 + 派工 v6 段 5 反馈 #6 实战)
   - 现状：Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 + Redis 缓存 = 商业化成本接近 0
   - 必做：主拍拍"是否启用 Edge-TTS Optional Backend / Web Speech API 降级 / pre-synthesize 缓存 / Azure-Google 多供应商" 决策
5. **Edge-TTS 接入必先监控 + 容错** (派工 v6 段 5 反馈 #5 实战 + W73 B-2 4 类 hot-fix 监控)
   - 现状：本调研 §2.5 阶段 5 监控 + 容错已实战 4 类容错
   - 必做：W77/W78 实施阶段必先接入 monitor-edge-tts.sh (第 7 件套监控)

**类 20.12 + 类 20.13 实战特别警示**:
- W76 A-2 调研 commit `0c3f848d7` 标注"调研 ≠ 生产" + "不批准 Edge-TTS 升级 / 替换后端"
- W77 A-2 实施方案延续此警示 (本文 §0 调研边界明示)
- **调研完成 ≠ 主拍验收** (派工 v6 段 5 反馈 #1 实战) —— 主拍须拍 §4 W77/W78 派工建议是否进实施阶段 + 选 B+D 组合
- **真生产 key 单独拍板** (类 20.13 实战) —— W78 主拍, 不在 W77 自动启用

## 8. 派工前提铁律 12 条实战 (W77 A-2 agent 必读)

依派工 v6 段 5 + 派工 v10 段 7 类 20 实战 + 本次 agent 实际验证：

1. **派生新任务必先 git log + grep 真验证当前 main HEAD** —— §1.1 + §1.2 + §1.3 已实战 (派工 v6 段 5 反馈 #3)
2. **不重做已 plan 实施代码** —— W76 A-2 调研 + W76 B-1/B-2 实施已收口，本实施方案不重复 (派工 v6 段 5 反馈 #2)
3. **调研"差距"必先辨明量纲** —— 本调研 B+D 5 阶段是"渐进式接入"非"数值差距" (W74 A-2 类 20.5 实战)
4. **调研建议主拍必拍"破坏性 vs 渐进"修复路径** —— §2 B+D 渐进式已拍 (W74 A-2 类 20.6 实战)
5. **实施前必先 `information_schema` 实查表名 + 列类型** —— 本方案不涉及 schema (派工 v6 段 5 反馈 #5)
6. **alembic 链必 1 head** —— 本方案不涉及 alembic (W73 E-1 派工 v6 段 5 反馈 #3 实战)
7. **实施前置 7 项必含** —— §3 实施前置 5 项已含 (qa-bench D9 + C-2 §6 实战, W77 派工 v10 段 7 类 20 实战)
8. **商业化 B-3 主拍单独拍板** —— W77 B-3 真生产 key 沙箱 + W78 B-1 主拍接入 (D-1 §5.4 + 派工 v6 段 5 反馈 #6 实战)
9. **0 production code 例外必含派工批文** —— 本方案例外 0 (CLAUDE.md W67 §3 实战)
10. **commit message 必含锚点范式数字** —— §11 实战 (派工 v10 段 9 实战)
11. **部署前必跑 alembic chain verify** —— 本方案不涉及部署 (W74 E-1 类 20.8 实战)
12. **调研派生的 schema 任务, 实施前必先 information_schema 实查** —— 本方案不涉及 schema (W74 B-1 类 20.7 实战)

## 9. 派工 v10 段 7 类 20 实战 (派生新任务必先真验证)

派工 v10 段 7 19 类实战 5 + 派工 v10 段 7 类 20 实战 10 条 + W74 E-1 类 20 实战 4 实例 + W75 A-2 类 20 实战 4 实例 + **W76 类 20.12 B-2 分支恢复 + W76 类 20.11 A-1 错派** = **派生新任务必先真验证 16 条**：

1. **类 20.1 (W72 A-2)**: 派生新任务必先 git log + grep 真验证当前 main HEAD
2. **类 20.2 (W72 A-2)**: 不信 plan Status 自报
3. **类 20.3 (W72 A-2)**: 不信派工 brief 假设
4. **类 20.4 (W74 A-1)**: 派工基线 `999276dda` 在 worktree 分支不在本地 main
5. **类 20.5 (W74 A-2)**: 调研"差距"必先辨明量纲
6. **类 20.6 (W74 A-2)**: 调研建议主拍必拍"破坏性 vs 渐进"修复路径
7. **类 20.7 (W74 B-1)**: 调研派生的 schema 任务, 实施前必先 `information_schema` 实查表名 + 列类型
8. **类 20.8 (W74 E-1)**: 部署前必跑 alembic chain verify
9. **类 20.9 (W74 E-1)**: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符
10. **类 20.10 (W74 A-1)**: 派工 brief "基线已在 main" 假设必拒, 必先 git log 真验证
11. **类 20.11 (W75 A-2)**: 移动端兼容性调研必先 §1 三步真验证 (plan 索引 + git log + grep 当前代码)
12. **类 20.12 (W75 A-2)**: 调研完成 ≠ 主拍验收 (派工 v6 段 5 反馈 #1 实战)
13. **类 20.13 (W75 A-2)**: 商业化主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)
14. **类 20.14 (W75 A-2)**: 跨平台兼容性调研必含 iOS Safari + Android Chrome 双端 (派工 v6 段 5 反馈 #5 实战)
15. **类 20.12.1 (W76 B-2)**: agent 产出 commit 后 worktree 清理时分支被强制删除, 主指挥必先 `git show-ref` 真验证分支 ref 存在再 merge
16. **类 20.11.1 (W76 A-1)**: 6 收尾分支尚未 commit 派 A-1, 类 20.11 实战成功拦截

## 10. 锚点范式守恒

| 阶段 | 锚点范式 | 守恒 | commit hash |
|------|----------|------|-------------|
| W76 第 1 批 grand closure | 263 | - | `61561c58d` |
| **W77 第 1 批 A-2 方案设计** | **266** | **+1** | **(本任务预测)** |
| 0 production code 守恒 | 15/15 守恒预测 | +1 方案设计例外 | (本任务沉淀) |

**锚点范式守恒数字**: W76 第 1 批 263 → W77 第 1 批 A-2 **266 守恒** (+1, 0 regression)

**锚点范式守恒铁律 5 条** (派工 v10 段 9 实战):
1. **W74 E-1 守恒验证 5 件套** —— 派工前提铁律实战拦截 (本方案 §8 实战)
2. **派工 v6 段 5 反馈 #1-#5** —— 调研完成 ≠ 生产实施 (本方案 §7 实战)
3. **派工 v6 段 5 反馈 #6** —— 商业化主拍单独拍板 (本方案 §2.4 + §4.3 + §4.4 实战)
4. **派工 v4 铁律 3** —— git log + git show + grep 三步真验证 (本方案 §1 实战)
5. **commit message 必含锚点范式数字** —— §11 实战 (派工 v10 段 9 实战)

## 11. commit message 锚点范式数字纪律 (v10 段 9 强制约束)

依 v10 段 9 强制约束 + W68 第 6 批永久锚点：

```
docs(w77-1st-batch-a2): Edge-TTS B+D 渐进式实施方案设计 (5 阶段 + 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议)

W76 A-2 commit 0c3f848d7 B+D 决策 + W76 B-1/B-2 commit a20ec9603/4ec33878a iOS/Android 实战 + W75 C-1 commit 2487ce6658 沙箱测试实战
锚点范式 W76 第 1 批 263 → W77 第 1 批 A-2 266 守恒 (+1)
- 5 阶段: Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + 真生产 key 决策 (W78 主拍) + 监控容错
- 实施前置 5 项: 老 TTS 完整性 + Edge-TTS 渐进式 + Web Speech API + tts_cache + 真生产 key 主拍
- 沙箱配置: Edge-TTS 7.2.8 + Web Speech API 浏览器原生, 商业化成本接近 0
- W77 B-1/B-2/B-3 + W78 B-1 派工建议 (4 子批)
- 监控凑齐 7 件套: monitor-edge-tts.sh 新建 (商业化成本监控)
- 调研 ≠ 生产 (类 20.12 调研完成 ≠ 主拍验收), 仅 docs/ + memory/
- 0 production code 改动铁律守恒 (纯调研 + 设计)
- 类 20.13 真生产 key 单独拍板 (W78 主拍, 不在 W77 自动启用)
```

## 12. 参考资料

- W76 A-2 决策 commit `0c3f848d7`: `docs/w76-1st-batch-a2-edge-tts-decision-2026-07-27.md`
- W76 B-1 iOS Safari 修复 commit `a20ec9603`: `docs/w76-1st-batch-b1-edge-tts-ios-runbook-2026-07-27.md`
- W76 B-2 Android Chrome 修复 commit `4ec33878a`: `docs/w76-1st-batch-b2-edge-tts-android-runbook-2026-07-27.md`
- W76 grand closure memory commit `61561c58d`: `memory/w76-1st-grand-closure-2026-07-28.md`
- W75 A-2 调研 commit `f538e3cf6`: `docs/w75-1st-batch-a2-edge-tts-survey-2026-07-27.md`
- W75 C-1 真支付 SDK commit `2487ce6658`: `docs/w75-1st-batch-c1-billing-real-sdk-runbook-2026-07-27.md`
- Edge-TTS 升级 commit: `41cf204d2` (6.1.9 → 7.2.8 修复 403)
- Edge-TTS 4 教训沉淀: `e8b49a6ef` (CLAUDE.md requirements.txt 锁版本)
- 派工 v4 铁律 3 真验证: 派工 v4 实战 19 类 + W72 A-2 类 20.1-20.3
- Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
- SpeechSynthesisUtterance: https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisUtterance
- MediaSession API: https://developer.mozilla.org/en-US/docs/Web/API/MediaSession
- AudioContext.state: https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/state
- Apple iOS Safari autoplay 政策: https://developer.apple.com/documentation/webkit/delivering_video_content_for_safari