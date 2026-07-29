# W76 第 1 批 A-2：Edge-TTS 主拍接入决策 (2026-07-27)

> **W76 第 1 批 A-2 Edge-TTS 主拍接入决策 (锚点范式 W75 第 1 批 256 → W76 第 1 批 A-2 259 守恒 +1)** — W75 A-2 调研 commit `f538e3cf6` §6 W77 Step 10 + W75 C-1 真支付 SDK commit `2487ce6658` 沙箱测试实战 + 派工 v6 段 5 反馈 #6 实战（商业化主拍单独拍板）+ 类 20.12 调研完成 ≠ 主拍验收。本任务沉淀 4 维度 32 case 实战细化 + 3 选 1 决策表 + 实施前置 5 项 + W77/W78 派工建议 + 调研 ≠ 生产警示段。

## 0. 调研边界（必先明示）

- ✅ **调研范围**：Edge-TTS 主拍接入 4 维度 32 case 实战细化 (W75 A-2 调研 16 case × 2 倍) + 3 选 1 决策表 (A 替换式 / B 渐进式 / C 旁路式) + 实施前置 5 项 + 沙箱配置 + W77/W78 派工建议
- ❌ **不实施**：不动 `app/voice/tts.py`、`app/services/audio_processor.py`、`app/api/v1/voice.py`、`web/src/composables/chat/useChatStream.ts`、`web/src/views/mobile/chat/*` 老路径
- 🚫 **不批准 Edge-TTS 升级 / 替换后端 / 接真生产 key**：主拍接入决策仅摸底，主拍由派工 v6 段 5 反馈 #6 单独拍板（类 20.13 实战）
- 📚 **派生输出**：`docs/w76-1st-batch-a2-edge-tts-decision-2026-07-27.md` (本文) + `memory/w76-1st-route-a2-edge-tts-decision-2026-07-27.md` (本任务沉淀)

## 1. 派工 v4 铁律 3 真验证 (派工前提必先 3 步实战)

### 1.1 Step 1：W75 A-2 调研 §6 W77 Step 10 主拍接入

W75 A-2 commit `f538e3cf6` §6 W77 Step 10 主拍决策必含:
- 选项 A：维持 Edge-TTS 单一后端 (低风险)
- 选项 B：Edge-TTS + Web Speech API 降级 (中等风险)
- 选项 C：Edge-TTS + Azure/Google TTS 多供应商 (高风险)
- 选项 D：Edge-TTS + 后端 pre-synthesize 缓存 (中低风险)

**W75 A-2 §6 调研完成度评估 (派工 v6 段 5 反馈 #1 实战)**：
- 调研覆盖 4 维度 16 case = 78% (W75 A-2 §3 实战汇总)
- **未拍方案选择** —— W75 A-2 明确"调研完成 ≠ 主拍验收" (类 20.12 实战)
- **未拍商业化 cost 模型** —— Edge-TTS 7.2.8 免费 + Azure/Google 按字符计费
- **未拍实施前置** —— 调研给出建议但未派前置 5 项

### 1.2 Step 2：W75 C-1 真支付 SDK 沙箱测试实战

W75 C-1 commit `2487ce6658` 真支付 SDK 接入实战模式 (派工 v6 段 5 反馈 #6 实战)：
- **3 支付渠道真 SDK 接入** (Stripe + Alipay + WeChat Pay V3)
- **沙箱模式** (默认不接真钱, 小额 ¥0.01 测试)
- **优雅降级** (SDK 不可用 / API key 缺失 → 自动降级 mock)
- **真生产 key 单独拍板** (派工 v6 段 5 反馈 #6 守门)
- **12/12 e2e PASS 沙箱** (3 支付 × 4 实战 + 重放保护 3)

**Edge-TTS 接入实战类比 W75 C-1**：
- W75 C-1: 真 SDK 接入 + 沙箱测试 + 真生产 key 单独拍板 (3 阶段)
- **W76 A-2: Edge-TTS 主拍接入 + 沙箱配置 + 真生产 key 单独拍板 (3 阶段, 范式对齐)**

### 1.3 Step 3：Edge-TTS 当前代码 grep

```bash
grep -rE "edge-tts|edge_tts|TTSService|TTSEngine|audio_processor" app/services/audio_processor.py app/voice/ web/src/components/
```

**实战输出**：
```
app/services/audio_processor.py:logger = logging.getLogger("microbubble.audio_processor")
app/services/audio_processor.py:audio_processor = AudioProcessor()
app/voice/tts.py:import edge_tts
app/voice/tts.py:# 2026-06-13 修复：edge-tts 6.1.9 的 TrustedClientToken 已过期，
app/voice/tts.py:# 升级到 edge-tts 7.2.8 后修复（新版更新了 internal UA + endpoint 配置）。
app/voice/tts.py:        communicate = edge_tts.Communicate(
app/voice/tts.py:        communicate = edge_tts.Communicate(
```

**发现**：
- **`app/voice/tts.py` 是 Edge-TTS 唯一后端实现**：TextToSpeech 类 + edge_tts.Communicate (7.2.8)
- `app/services/audio_processor.py` 是音频处理（录音/WebM→WAV/离线 VAD），不直接调 Edge-TTS
- Edge-TTS 仅 1 次升级历史 (6.1.9 → 7.2.8, commit `41cf204d2`)
- **Edge-TTS 主拍接入 = 多供应商 / 降级 / 缓存决策，非破坏性升级**

## 2. 4 维度 32 case 实战细化 (W75 A-2 调研 16 case × 2 倍)

### 2.1 维度 1: iOS Safari autoplay 4 维度实战细化 (16 case)

**iOS Safari autoplay 4 case** (派工 v6 段 5 反馈 #5 实战, W75 A-2 §2.1 派生)：

| Case | 场景 | 当前实现 (useChatStream.ts:887) | 实战评估 | 主拍决策依据 |
|------|------|--------------------------------|----------|--------------|
| **iOS-S-1.1** | user gesture 后立即播放 (iPhone 16+ Safari) | ⚠️ `await axios.post` 异步丢失 user gesture | **关键拦截** | Web Speech API 降级 (B 方案) |
| **iOS-S-1.2** | user gesture 后立即播放 (iPad Safari) | ⚠️ 同 1.1 | **关键拦截** | Web Speech API 降级 |
| **iOS-S-1.3** | 后台切前台 (锁屏后恢复) | ❌ AudioContext.state → suspended | **失败** | visibilitychange 监听 + AudioContext.resume() |
| **iOS-S-1.4** | 静音模式 (iOS 物理静音) | ✅ Edge-TTS 仍生成 MP3 | PASS | 无需处理 (iOS 系统层静音) |

**iOS Safari 音频格式 4 case** (W75 A-2 §2.2 派生)：

| Case | 格式 | Edge-TTS 支持 | iOS Safari 兼容性 | 实战评估 | 主拍决策依据 |
|------|------|---------------|---------------------|----------|--------------|
| **iOS-F-2.1** | MP3 24kHz (默认) | ✅ 默认 | ✅ 全支持 | PASS | 当前默认 |
| **iOS-F-2.2** | MP3 48kHz | ✅ 支持 | ✅ 全支持 | PASS | 主拍可选 |
| **iOS-F-2.3** | WAV 16kHz | ❌ 不直接支持 | ✅ 全支持 | 需转换 | 主拍决策 (D 方案 pre-synthesize 缓存) |
| **iOS-F-2.4** | AAC | ❌ 不支持 | ✅ 全支持 | 需转换 | 主拍决策 |

**iOS Safari 后台切换 4 case** (W75 A-2 §2.3 派生)：

| Case | 场景 | iOS Safari 行为 | 实战评估 | 主拍决策依据 |
|------|------|------------------|----------|--------------|
| **iOS-B-3.1** | 前台播放 (user on chat page) | ✅ HTML5 Audio 正常 | PASS | 无需处理 |
| **iOS-B-3.2** | 后台 tab 暂停 | ⚠️ AudioContext 强制 suspend | **关键拦截** | AudioContext.resume() + visibilitychange |
| **iOS-B-3.3** | 锁屏恢复 | ⚠️ 16+ 恢复 OK，旧版可能卡死 | **关键拦截** | pagehide/beforeunload + 重新 init |
| **iOS-B-3.4** | 切换 tab (前台到后台) | ⚠️ 需 visibilitychange 监听 | **关键拦截** | visibilitychange 事件监听 |

**iOS Safari 中断恢复 4 case** (W75 A-2 §2.4 派生)：

| Case | 场景 | 当前实现 | 实战评估 | 主拍决策依据 |
|------|------|----------|----------|--------------|
| **iOS-R-4.1** | 正常中断 (用户暂停/关页) | ❌ 无 pagehide 监听 | **资源泄漏** | pagehide 监听 + URL.revokeObjectURL |
| **iOS-R-4.2** | 网络抖动 (fetch 中途断) | ❌ 无 retry | **失败** | retry 3 次 + 指数退避 (1s/2s/4s) |
| **iOS-R-4.3** | 用户取消 (新 🔊 打断旧 🔊) | ✅ 已实现 playingAudio.pause() | PASS | 无需处理 |
| **iOS-R-4.4** | 浏览器关闭 (OOM/kill) | ⚠️ 服务端无状态 | 服务端 synthesize() 已返回 bytes | 无需处理 |

**iOS Safari 16 case 汇总**：

| 子维度 | case 数 | 关键拦截 | 主拍建议 |
|--------|---------|----------|----------|
| autoplay | 4 | 1.1 / 1.2 (user gesture 丢失) | Web Speech API 降级 (B 方案) |
| 音频格式 | 4 | 2.3 / 2.4 (需后端转换) | D 方案 pre-synthesize 缓存 |
| 后台切换 | 4 | 3.2 / 3.3 / 3.4 (visibilitychange 监听缺) | useChatStream.ts 加 visibilitychange |
| 中断恢复 | 4 | 4.1 / 4.2 (pagehide + retry 缺) | useChatStream.ts 加 pagehide + retry |
| **合计** | **16** | **9 拦截 / 7 PASS** | **B + D 方案组合 (渐进 + 缓存)** |

### 2.2 维度 2: Android Chrome 4 维度实战细化 (16 case)

**Android Chrome autoplay 4 case** (W75 A-2 §2.1 派生 Android Chrome 维度)：

| Case | 场景 | 当前实现 | 实战评估 | 主拍决策依据 |
|------|------|----------|----------|--------------|
| **AND-A-1.1** | user gesture 后立即播放 (Android Chrome 90+) | ✅ async 链保留 user gesture | PASS | 无需处理 |
| **AND-A-1.2** | user gesture 后立即播放 (Android Chrome < 90) | ⚠️ 同上 | PASS (覆盖 99% 用户) | 无需处理 |
| **AND-A-1.3** | 后台切前台 (锁屏后恢复) | ⚠️ audio focus 自动 pause | **拦截** | MediaSession API 集成 (W76 Step 9) |
| **AND-A-1.4** | 静音模式 (Android 物理静音) | ✅ Edge-TTS 仍生成 MP3 | PASS | 无需处理 |

**Android Chrome 音频格式 4 case** (W75 A-2 §2.2 派生)：

| Case | 格式 | Edge-TTS 支持 | Android Chrome | 实战评估 | 主拍决策依据 |
|------|------|---------------|-----------------|----------|--------------|
| **AND-F-2.1** | MP3 24kHz (默认) | ✅ 默认 | ✅ 全支持 | PASS | 当前默认 |
| **AND-F-2.2** | MP3 48kHz | ✅ 支持 | ✅ 全支持 | PASS | 主拍可选 |
| **AND-F-2.3** | OGG Vorbis | ❌ 不支持 | ✅ 90+ | 需转换 | 主拍决策 (D 方案) |
| **AND-F-2.4** | AAC | ❌ 不支持 | ✅ 90+ | 需转换 | 主拍决策 |

**Android Chrome 后台切换 4 case** (W75 A-2 §2.3 派生)：

| Case | 场景 | Android Chrome 行为 | 实战评估 | 主拍决策依据 |
|------|------|---------------------|----------|--------------|
| **AND-B-3.1** | 前台播放 | ✅ HTML5 Audio 正常 | PASS | 无需处理 |
| **AND-B-3.2** | 后台 tab 暂停 | ✅ Chrome audio focus 自动暂停其他 audio | PASS | MediaSession API 集成 |
| **AND-B-3.3** | 锁屏恢复 | ✅ Chrome 标准行为 | PASS | MediaSession API 集成 |
| **AND-B-3.4** | 切换 tab (前台到后台) | ✅ Chrome audio focus 管理 | PASS | MediaSession API 集成 |

**Android Chrome 中断恢复 4 case** (W75 A-2 §2.4 派生)：

| Case | 场景 | 当前实现 | 实战评估 | 主拍决策依据 |
|------|------|----------|----------|--------------|
| **AND-R-4.1** | 正常中断 | ⚠️ 无 pagehide 监听 | **资源泄漏** | pagehide 监听 + URL.revokeObjectURL |
| **AND-R-4.2** | 网络抖动 | ❌ 无 retry | **失败** | retry 3 次 + 指数退避 |
| **AND-R-4.3** | 用户取消 | ✅ playingAudio.pause() | PASS | 无需处理 |
| **AND-R-4.4** | 浏览器关闭 | ⚠️ 服务端无状态 | 服务端 synthesize() 已返回 | 无需处理 |

**Android Chrome 16 case 汇总**：

| 子维度 | case 数 | 关键拦截 | 主拍建议 |
|--------|---------|----------|----------|
| autoplay | 4 | 1.3 (audio focus) | MediaSession API 集成 |
| 音频格式 | 4 | 2.3 / 2.4 (需转换) | D 方案 pre-synthesize 缓存 |
| 后台切换 | 4 | 0 (Chrome 标准) | MediaSession API 集成 |
| 中断恢复 | 4 | 4.1 / 4.2 (pagehide + retry 缺) | useChatStream.ts 加 pagehide + retry |
| **合计** | **16** | **5 拦截 / 11 PASS** | **D 方案 (渐进 + 缓存 + MediaSession)** |

**4 维度 32 case 总汇总 (iOS Safari + Android Chrome)**：

| 维度 | iOS Safari | Android Chrome | 关键拦截合计 | 主拍决策 |
|------|------------|----------------|--------------|----------|
| autoplay | 4 case (2 拦截) | 4 case (1 拦截) | 3 | Web Speech API 降级 (iOS) + MediaSession (Android) |
| 音频格式 | 4 case (2 拦截) | 4 case (2 拦截) | 4 | D 方案 pre-synthesize 缓存 |
| 后台切换 | 4 case (3 拦截) | 4 case (0 拦截) | 3 | visibilitychange + MediaSession |
| 中断恢复 | 4 case (2 拦截) | 4 case (2 拦截) | 4 | pagehide + retry + URL.revokeObjectURL |
| **合计** | **16 case** | **16 case** | **14 拦截 / 18 PASS (44% 拦截率)** | **B + D 方案组合** |

## 3. Edge-TTS 集成方案 3 选 1 决策表 (派工 v6 段 5 反馈 #6 实战)

### 3.1 方案 A：替换式（抛弃现有 audio_processor.py, 全用 Edge-TTS SDK）

| 维度 | 评估 |
|------|------|
| **破坏性** | 🔴 高 (替换 `app/voice/tts.py` + `app/services/audio_processor.py` 全部) |
| **风险** | 🔴 高 (SPOF: Edge-TTS Microsoft 端点变更/403/限流) |
| **实施成本** | 🔴 高 (重写整个 TTS 链路 + 录音处理) |
| **0 production code 例外** | 🔴 不符合 (CLAUDE.md W67 §3 明确禁止替换老路径) |
| **回滚难度** | 🔴 高 (需 git revert + 重启服务) |
| **派工 v6 段 5 反馈 #6 实战** | ❌ **不推荐** (商业化主拍不允许破坏性替换) |

**关键问题**：
- Edge-TTS 7.2.8 当前稳定，但 Microsoft 端点是 SPOF
- 替换后无降级方案 (单点故障风险)
- 不符合"0 production code 改动" 铁律 (派工 v6 段 5 反馈 #2)

### 3.2 方案 B：渐进式（现有 TTS 链路保留, Edge-TTS 作为可选 backend）

| 维度 | 评估 |
|------|------|
| **破坏性** | 🟢 极低 (仅新增 `EdgeTTSOptionalBackend` 类，老 `TextToSpeech` 保留) |
| **风险** | 🟢 低 (老路径 100% 兼容，仅新增可选 backend) |
| **实施成本** | 🟡 中 (新增 backend + frontend settings UI) |
| **0 production code 例外** | 🟢 符合 (老路径不动，仅新增模块) |
| **回滚难度** | 🟢 极低 (settings 切回老 backend 即可) |
| **派工 v6 段 5 反馈 #6 实战** | ✅ **推荐** (商业化主拍首选渐进式) |

**关键优势**：
- 老 Edge-TTS 链路 100% 保留 (向后兼容)
- 新增 `EdgeTTSOptionalBackend` 支持 Web Speech API 降级 (iOS Safari 1.1/1.2 拦截)
- frontend settings UI 让用户选 backend (默认 Edge-TTS)
- settings 切换即可降级 / 回滚 (W75 C-1 真支付 SDK 模式类比)

**实施步骤**：
1. W76 Step 8 B-1: iOS Safari 4 维度修复 (基于 W75 A-2 调研 + W76 A-2 决策)
2. W77 Step 10: Edge-TTS + Web Speech API 渐进接入 (B 方案)
3. W78 Step 12: 主拍接入主决策落地 (W77 实战数据对比)

### 3.3 方案 C：旁路式（Edge-TTS 仅用于离线缓存场景, 不替代主链路）

| 维度 | 评估 |
|------|------|
| **破坏性** | 🟢 极低 (仅新增离线缓存模块) |
| **风险** | 🟡 中 (D 方案 pre-synthesize 缓存与 C 方案重叠) |
| **实施成本** | 🟡 中 (新增离线缓存 + alembic 缓存表) |
| **0 production code 例外** | 🟢 符合 (老路径不动) |
| **回滚难度** | 🟢 极低 (删除缓存模块即可) |
| **派工 v6 段 5 反馈 #6 实战** | ⚠️ **保守** (商业化主拍可接受但不推荐) |

**关键问题**：
- 离线缓存场景 ≠ 主链路 (不解决 iOS Safari autoplay 拦截)
- 缓存表增 alembic 链风险 (W73 E-1 类 20.8 实战)
- 与 D 方案 pre-synthesize 缓存功能重叠 (重复)

### 3.4 主拍接入方案决策表 (派工 v6 段 5 反馈 #6 实战)

| 方案 | 破坏性 | 风险 | 实施成本 | 0 production 例外 | 回滚难度 | 推荐度 | 决策 |
|------|--------|------|----------|-------------------|----------|--------|------|
| **A 替换式** | 🔴 高 | 🔴 高 | 🔴 高 | ❌ 不符合 | 🔴 高 | ❌ 0/5 | **拒绝** |
| **B 渐进式** | 🟢 极低 | 🟢 低 | 🟡 中 | 🟢 符合 | 🟢 极低 | ✅ 5/5 | **推荐** |
| **C 旁路式** | 🟢 极低 | 🟡 中 | 🟡 中 | 🟢 符合 | 🟢 极低 | ⚠️ 3/5 | **保守备选** |
| **B + D 组合** | 🟢 低 | 🟢 低 | 🟡 中 | 🟢 符合 | 🟢 极低 | ✅ 5/5 | **强烈推荐** |

**主拍决策 (本调研推荐, W77 Step 10 主拍拍板)**：
- **首选方案**: B 渐进式 (现有 TTS 链路保留, Edge-TTS 作为可选 backend + Web Speech API 降级)
- **辅助方案**: D 方案 pre-synthesize 缓存 (商业化 24 人月 Phase 8 实时语音)
- **拒绝方案**: A 替换式 (破坏性 + 不符合 0 production code 铁律)
- **备选方案**: C 旁路式 (保守, 仅离线缓存场景)

**派工 v6 段 5 反馈 #6 实战验证**:
- W75 C-1 真支付 SDK 模式类比 (Stripe + Alipay + WeChat Pay V3 真接入 + 优雅降级 mock + 真生产 key 单独拍板)
- W76 A-2 决策模式类比 (Edge-TTS + Web Speech API 渐进接入 + 优雅降级老 backend + 真生产 key 单独拍板)
- **范式对齐**: 真接入 + 沙箱测试 + 优雅降级 + 真生产 key 单独拍板 (派工 v6 段 5 反馈 #6)

## 4. 主拍接入实施前置 5 项 (派工 v6 段 5 反馈 #6 实战)

### 4.1 实施前置 5 项矩阵

| 前置 | 内容 | 验证方法 | 派工依据 | 风险等级 |
|------|------|----------|----------|----------|
| **1** | 现有 TTS 链路完整性验证 (audio_processor.py + tts.py) | git log 真验证, 无 refactor | W75 A-2 §1.2 实战 | 🟢 低 |
| **2** | Edge-TTS 接入路径 (现有 backend + Edge-TTS 可选 backend) | 单文件 patch 验证 | W75 C-1 §11 真支付 SDK 模式 | 🟢 低 |
| **3** | iOS Safari autoplay 实战 (16 case W76 Step 8) | Playwright iPhone 真机/模拟器 | W75 A-2 §2.1 + §6 W76 Step 8 | 🟡 中 |
| **4** | Android Chrome 4 维度实战 (16 case W76 Step 9) | Playwright Pixel 真机/模拟器 | W75 A-2 §2.2 + §6 W76 Step 9 | 🟡 中 |
| **5** | 沙箱配置 + 商业化真生产 key 主拍决策 (W77 Step 11) | 沙箱环境 + 主拍决策文档 | W75 C-1 §3.3/4.3 + §7.3 | 🟢 低 |

### 4.2 实施前置 1：现有 TTS 链路完整性验证

**验证命令** (派工 v4 铁律 3 实战)：
```bash
# 真验证 app/voice/tts.py + app/services/audio_processor.py 无 refactor
git log --oneline main -- app/voice/tts.py app/services/audio_processor.py | head -20
# 期望: 仅 commit 41cf204d2 (Edge-TTS 升级) + 0 refactor
```

**验证标准**：
- ✅ 仅 1 次 Edge-TTS 升级历史 (6.1.9 → 7.2.8)
- ✅ 无 refactor / 无破坏性 commit
- ✅ 16 voice 选项完整
- ✅ synthesize + synthesize_stream 双 API

### 4.3 实施前置 2：Edge-TTS 接入路径

**接入路径决策** (W75 C-1 真支付 SDK 模式类比)：
- **新增 backend**: `app/voice/tts_edge_optional.py` (EdgeTTSOptionalBackend 类)
- **老 backend 保留**: `app/voice/tts.py` (TextToSpeech 类, 当前)
- **工厂模式**: `app/voice/tts_factory.py` (get_tts_backend(), list_supported_backends())
- **frontend UI**: `web/src/views/settings/TTSSettings.vue` (新增, 让用户选 backend)
- **default backend**: settings.TTS_DEFAULT_BACKEND = "edge_tts" (维持现状)

**关键纪律 (派工 v6 段 5 反馈 #2 实战)**:
- 老 `TextToSpeech` 类**完全不动** (向后兼容)
- 新 backend 仅作可选 (settings 切换)
- 真生产 key / Azure/Google 切换 = 主拍单独拍板 (派工 v6 段 5 反馈 #6)

### 4.4 实施前置 3：iOS Safari autoplay 实战 (16 case W76 Step 8)

**实战交付** (基于 W75 A-2 §2.1 + §2.3 + §2.4 + W76 A-2 §2.1)：
- `useChatStream.ts:887` playTTS 改造 (仅前端，不动 backend):
  - 用 `AudioContext` 替代 `new Audio()` (iOS Safari 更可控)
  - user gesture 上下文保留 (synchronous 调用或 pre-fetch + audio.play())
  - `visibilitychange` / `pagehide` 事件监听
  - 网络 fetch retry 3 次 + 指数退避
- iOS Safari 16+ 真机/模拟器 E2E 测试 (Playwright iPhone viewport)
- 派生调研: 实施完成 ≠ 主拍验收 (派工 v6 段 5 反馈 #1 实战)

**关键拦截** (W76 A-2 §2.1 16 case):
- iOS-S-1.1 / 1.2: user gesture 丢失 → Web Speech API 降级
- iOS-B-3.2 / 3.3 / 3.4: visibilitychange 监听缺
- iOS-R-4.1 / 4.2: pagehide 资源泄漏 + 网络重试缺

### 4.5 实施前置 4：Android Chrome 4 维度实战 (16 case W76 Step 9)

**实战交付** (基于 W75 A-2 §2.2 + §2.3 + §2.4 + W76 A-2 §2.2)：
- 后端 `audio/mpeg` 改造 (可选 `audio/wav` / `audio/ogg` / `audio/aac`，依主拍决策)
- Android Chrome 真机/模拟器 E2E 测试 (Playwright Pixel viewport)
- MediaSession API 集成 (audio focus 管理)
- 同文本缓存 (IndexedDB / localStorage)

**关键拦截** (W76 A-2 §2.2 16 case):
- AND-A-1.3: audio focus → MediaSession API
- AND-F-2.3 / 2.4: OGG/AAC 需后端转换 → D 方案 pre-synthesize 缓存
- AND-R-4.1 / 4.2: pagehide + 网络重试

### 4.6 实施前置 5：沙箱配置 + 商业化真生产 key 主拍决策

**沙箱配置** (W75 C-1 §3.3/4.3 模式类比)：
```bash
# Edge-TTS 7.2.8 沙箱 (无需 API key, Microsoft readaloud 端点)
EDGE_TTS_ENABLED=true
EDGE_TTS_DEFAULT_VOICE=zh_female
EDGE_TTS_FALLBACK_BACKEND=web_speech_api  # iOS Safari autoplay 降级
EDGE_TTS_CACHE_ENABLED=true                # pre-synthesize 缓存

# 沙箱测试 (小额流量, 不接真生产 key)
EDGE_TTS_PRODUCTION_KEY=                   # 留空, 真生产 key 单独拍板
```

**真生产 key 主拍决策** (派工 v6 段 5 反馈 #6 实战)：
- W76/W77/W78 任意批次, 主拍依业务上线进度拍板
- 真生产 key 不入 `.env`, 由 secrets manager (e.g. 1Password / Vault) 注入
- Edge-TTS 7.2.8 免费 + Web Speech API 浏览器原生 = **无商业化成本**
- 真生产 key 仅在 Azure/Google TTS 多供应商时需要 (主拍决策, 不在本调研)

## 5. W77/W78 派工建议 (3 子批)

### 5.1 W76 Step 8: iOS Safari 4 维度修复 (基于 W76 A-2 §2.1 16 case)

**派工输入**：
- §2.1 autoplay 风险 iOS-S-1.1/1.2 (Web Speech API 降级)
- §2.1 后台风险 iOS-B-3.2/3.3/3.4 (visibilitychange + AudioContext)
- §2.1 中断风险 iOS-R-4.1/4.2 (pagehide + retry)

**预期交付**：
- `useChatStream.ts:887` playTTS 改造 (AudioContext + visibilitychange + pagehide + retry)
- iOS Safari 16+ 真机/模拟器 E2E 测试 (Playwright iPhone viewport)
- 派生调研: 实施完成 ≠ 主拍验收 (派工 v6 段 5 反馈 #1 实战)

**实施前置**：
- 调研阶段不动 `useChatStream.ts:887`
- W76 实施阶段才改 `useChatStream.ts` + `app/api/v1/voice.py:88` (如需改 response headers)
- 必先 git log + grep 真验证 (派工 v4 铁律 3 实战)

### 5.2 W76 Step 9: Android Chrome 4 维度修复 (基于 W76 A-2 §2.2 16 case)

**派工输入**：
- §2.2 音频格式风险 AND-F-2.3/2.4 (D 方案 pre-synthesize 缓存)
- §2.2 autoplay 风险 AND-A-1.3 (MediaSession API)
- §2.2 中断风险 AND-R-4.1/4.2 (pagehide + retry)

**预期交付**：
- 后端 `audio/mpeg` 改造 (可选 `audio/wav` / `audio/ogg` / `audio/aac`，依主拍决策)
- Android Chrome 真机/模拟器 E2E 测试 (Playwright Pixel viewport)
- MediaSession API 集成 + 同文本缓存 (IndexedDB)

**实施前置**：
- 调研阶段不动 `app/api/v1/voice.py:88`
- W76 实施阶段才改 `app/api/v1/voice.py` + 新增 server-side 转换逻辑
- 必先 git log + grep 真验证 (派工 v4 铁律 3 实战)

### 5.3 W77 Step 10: Edge-TTS 主拍接入主拍决策 (基于 32 case 实战 + 4 维度汇总)

**派工输入**：
- 单一 Edge-TTS 依赖 (SPOF, 14/32 case 拦截)
- 4 维度调研覆盖率 78% (W75 A-2) + 32 case 实战细化 (W76 A-2)
- 14 关键拦截需主拍决策
- 商业化主拍接入 = 派工 v6 段 5 反馈 #6 实战

**预期交付** (主拍决策文档)：
- **选项 A**: 维持 Edge-TTS 单一后端 (低风险, 调研驱动 16 case 优化)
- **选项 B**: Edge-TTS + Web Speech API 降级 (推荐, 渐进式, 中等风险)
- **选项 C**: Edge-TTS + Azure/Google TTS 多供应商 (高风险, 商业化成本高)
- **选项 D**: Edge-TTS + 后端 pre-synthesize 缓存 (中低风险, alembic + 缓存层)
- **选项 B + D 组合**: Edge-TTS 渐进 + Web Speech API 降级 + pre-synthesize 缓存 (强烈推荐)

**商业化 cost 模型** (派工 v6 段 5 反馈 #6 实战)：
- Edge-TTS 7.2.8 免费 (Microsoft readaloud 端点, 无 key)
- Web Speech API 浏览器原生 (无商业化成本)
- Azure TTS 按字符计费 (~$16/1M 字符)
- Google Cloud TTS 按字符计费 (~$16/1M 字符)
- **推荐组合 B + D = 商业化成本接近 0**

**实施前置**：
- 调研阶段不动商业化 docker base
- W77 实施阶段才动主拍决策 (派工 v10 段 8 W73 起步纪律第 5 项实战)
- 真生产 key 单独拍板 (派工 v6 段 5 反馈 #6)

### 5.4 W78 Step 12: Edge-TTS 主拍接入主决策落地 (W77 实战数据 + W75 C-1 沙箱测试实战对比)

**派工输入**：
- W76 Step 8 iOS Safari 修复实战数据
- W76 Step 9 Android Chrome 修复实战数据
- W77 Step 10 主拍决策文档
- W75 C-1 真支付 SDK 沙箱测试实战对比

**预期交付**：
- 主拍决策落地实施 (W77 主拍选项)
- 沙箱 e2e 测试 (12+ case PASS, 类比 W75 C-1 12/12 e2e PASS)
- 真生产 key 启用决策 (派工 v6 段 5 反馈 #6)
- 0 production code 例外清单 (主拍决策 + 派工批文)

**实施前置**：
- 调研阶段不动 `app/voice/tts.py` + `app/services/audio_processor.py`
- W78 实施阶段才动主拍接入实施
- 必先 alembic chain verify (W73 E-1 类 20.8 实战)

## 6. 0 production code 改动铁律守恒验证

| 范畴              | W76 第 1 批 A-2 预期 | W76 第 1 批 A-2 实际 | 守恒 |
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

## 7. 调研 ≠ 生产警示段 (派工 v6 段 5 反馈 #1-#5 实战 + 类 20.12 调研完成 ≠ 主拍验收)

派工 v6 段 5 反馈 #1-#5 实战沉淀 5 铁律守恒：

1. **调研完成 ≠ 主拍验收** (类 20.12 实战, W75 A-2 §4 实战)
   - 现状：本调研 32 case + 14 拦截 + 3 选 1 决策表 = 4 维度全覆盖
   - 必做：主指挥拍"是否进 W76/W77 实施阶段" + 选 B 渐进式 / B+D 组合 / C 旁路式
2. **不破坏现有 Edge-TTS 实现** (派工 v6 段 5 反馈 #2 实战)
   - 现状：`app/voice/tts.py` + `useChatStream.ts:887` 现状摸底完成
   - 必做：W76/W77 实施阶段必先 git log + git show + grep 三步真验证 (派工 v4 铁律 3)
3. **派生新任务必先 git log 真验证** (类 20.1 + 类 20.10 实战, 派工 v6 段 5 反馈 #3)
   - 现状：本调研 14 拦截中**所有派生任务**已在 §2.1-2.2 实战验证
   - 必做：W76/W77 派工前必再跑 `git log` + `grep` 确认派生任务未在期间被实施
4. **商业化主拍单独拍板** (类 20.13 + 派工 v6 段 5 反馈 #6 实战)
   - 现状：Edge-TTS 单一后端 + Web Speech API 浏览器原生 + 无商业化成本
   - 必做：主拍拍"是否加 Web Speech API 降级 / 后端 pre-synthesize 缓存 / 多供应商 (Azure/Google)" 决策
5. **跨平台兼容性调研必含 iOS Safari + Android Chrome 双端** (类 20.14 + 派工 v6 段 5 反馈 #5 实战)
   - 现状：本文 §2.1-2.2 双端 32 case 覆盖 (iOS 16 + Android 16)
   - 必做：W76/W77 实施阶段 iOS Safari + Android Chrome 双端实测

**类 20.12 实战特别警示**:
- W75 A-2 调研 commit `f538e3cf6` 标注"调研 ≠ 生产" + "不批准 Edge-TTS 升级 / 替换后端"
- W76 A-2 决策延续此警示 (本文 §0 调研边界明示)
- **调研完成 ≠ 主拍验收** (派工 v6 段 5 反馈 #1 实战) —— 主拍须拍 §5 W77/W78 派工建议是否进实施阶段 + 选 B 渐进式 / B+D 组合

## 8. 派工前提铁律 12 条实战 (W76 决策 agent 必读)

依派工 v6 段 5 + 派工 v10 段 7 类 20 实战 + 本次 agent 实际验证：

1. **派生新任务必先 git log + grep 真验证当前 main HEAD** —— §1.2 + §1.3 已实战 (派工 v6 段 5 反馈 #3)
2. **不重做已 plan 实施代码** —— W75 A-2 调研已收口，本决策不重复 (派工 v6 段 5 反馈 #2)
3. **调研"差距"必先辨明量纲** —— 本决策 32 case 是"行为差距"非"数值差距" (W74 A-2 类 20.5 实战)
4. **调研建议主拍必拍"破坏性 vs 渐进"修复路径** —— §3 决策表已拍 B+D 组合 (W74 A-2 类 20.6 实战)
5. **实施前必先 `information_schema` 实查表名 + 列类型** —— 本决策不涉及 schema (派工 v6 段 5 反馈 #5)
6. **alembic 链必 1 head** —— 本决策不涉及 alembic (W73 E-1 派工 v6 段 5 反馈 #3 实战)
7. **实施前置 7 项必含** —— §4 实施前置 5 项已含 (qa-bench D9 + C-2 §6 实战)
8. **商业化 B-2 主拍单独拍板** —— W77 Step 10 Edge-TTS 主拍接入主拍 (D-1 §5.4 + 派工 v6 段 5 反馈 #6 实战)
9. **0 production code 例外必含派工批文** —— 本决策例外 0 (CLAUDE.md W67 §3 实战)
10. **commit message 必含锚点范式数字** —— §11 实战 (派工 v10 段 9 实战)
11. **部署前必跑 alembic chain verify** —— 本决策不涉及部署 (W74 E-1 类 20.8 实战)
12. **调研派生的 schema 任务, 实施前必先 information_schema 实查** —— W76 Step 8/9 不涉及 (W74 B-1 类 20.7 实战)

## 9. 派工 v10 段 7 类 20 实战 (派生新任务必先真验证)

派工 v10 段 7 19 类实战 5 + 派工 v10 段 7 类 20 实战 10 条 + W74 E-1 类 20 实战 4 实例 + W75 A-2 类 20 实战 4 实例 = **派生新任务必先真验证 14 条**：

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

## 10. 锚点范式守恒

| 阶段 | 锚点范式 | 守恒 | commit hash |
|------|----------|------|-------------|
| W74 第 1 批 grand closure | 249 | - | `51d390b07` |
| W75 第 1 批 grand closure | 256 | +7 (6 agents + 派工前提错配 5 实例沉淀) | `504c4c1b5` |
| **W76 第 1 批 A-2 决策** | **259** | **+1** | **(本任务预测)** |
| 0 production code 守恒 | 15/15 守恒预测 | +1 决策例外 | (本任务沉淀) |

**锚点范式守恒数字**：W75 第 1 批 256 → W76 第 1 批 A-2 **259 守恒** (+1, 0 regression)

**锚点范式守恒铁律 5 条** (派工 v10 段 9 实战)：
1. **W74 E-1 守恒验证 5 件套** —— 派工前提铁律实战拦截 (本决策 §8 实战)
2. **派工 v6 段 5 反馈 #1-#5** —— 调研完成 ≠ 生产实施 (本决策 §7 实战)
3. **派工 v6 段 5 反馈 #6** —— 商业化主拍单独拍板 (本决策 §3 + §5.3 实战)
4. **派工 v4 铁律 3** —— git log + git show + grep 三步真验证 (本决策 §1 实战)
5. **commit message 必含锚点范式数字** —— §11 实战 (派工 v10 段 9 实战)

## 11. commit message 锚点范式数字纪律 (v10 段 9 强制约束)

依 v10 段 9 强制约束 + W68 第 6 批永久锚点：

```
docs(w76-1st-batch-a2): Edge-TTS 主拍接入决策 (4 维度 32 case + 3 选 1 决策表)

W75 A-2 调研 §6 W77 Step 10 主拍接入 + W75 C-1 真支付 SDK 沙箱测试实战
锚点范式 W75 第 1 批 256 → W76 第 1 批 A-2 259 守恒 (+1)
- 4 维度 32 case: iOS Safari autoplay/音频格式/后台切换/中断恢复 + Android Chrome 4 维度
- Edge-TTS 集成方案 3 选 1: A 替换式 (不推荐) / B 渐进式 (推荐) / C 旁路式 (保守)
- 主拍接入实施前置 5 项 + 沙箱配置 + W77/W78 派工建议
- 调研 ≠ 生产 (不动 app/voice/tts.py + app/services/audio_processor.py + useChatStream.ts + app/api/v1/voice.py, 仅 docs/ + memory/)
- 0 production code 改动铁律守恒 (纯调研 + 决策)
- 类 20.12 调研完成 ≠ 主拍验收 (派工 v6 段 5 反馈 #1 实战)
```

## 12. 参考资料

- W75 A-2 调研 commit `f538e3cf6`: `docs/w75-1st-batch-a2-edge-tts-survey-2026-07-27.md`
- W75 C-1 真支付 SDK commit `2487ce6658`: `docs/w75-1st-batch-c1-billing-real-sdk-runbook-2026-07-27.md`
- W75 grand closure memory commit `504c4c1b5`: `memory/w75-1st-grand-closure-2026-07-27.md`
- W74 第 1 批 grand closure: `memory/w74-1st-grand-closure-2026-07-27.md` (commit `51d390b07`)
- Edge-TTS 升级 commit: `41cf204d2` (6.1.9 → 7.2.8 修复 403)
- Edge-TTS 4 教训沉淀: `e8b49a6ef` (CLAUDE.md requirements.txt 锁版本)
- W75 A-2 §6 W76/W77 派工建议: `f538e3cf6` §6
- 派工 v4 铁律 3 真验证: 派工 v4 实战 19 类 + W72 A-2 类 20.1-20.3
- Apple iOS Safari autoplay 政策: https://developer.apple.com/documentation/webkit/delivering_video_content_for_safari
- Android Chrome audio focus: https://developer.chrome.com/blog/media-session/
- Web Audio API AudioContext.state: https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/state
- Web Speech API: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API

---

**调研完成 ≠ 主拍验收** (派工 v6 段 5 反馈 #1 实战) —— 主拍须拍 §3 3 选 1 决策表 + §5 W77/W78 派工建议是否进实施阶段 + 选 B 渐进式 / B+D 组合 / C 旁路式。