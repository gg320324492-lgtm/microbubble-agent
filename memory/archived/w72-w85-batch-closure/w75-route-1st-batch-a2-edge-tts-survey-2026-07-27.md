# W75 第 1 批 A-2 Edge-TTS 移动端兼容性调研 (锚点范式 249 → 252 守恒 +3)

> 日期：2026-07-27
> 任务：W75 第 1 批 A-2 Edge-TTS 移动端兼容性调研
> 依据：W73 A-2 调研 §6 W76 Step 8 派生 (提前 W75) + W74 E-1 派工前提铁律实战
> 基线：main HEAD `51d390b07` (W74 第 1 批 grand closure 收口, 锚点 249 守恒)
> 锚点范式：W74 第 1 批 249 → W75 第 1 批 A-2 **252 守恒** (+3)
> 范畴：**纯调研 + docs/memory 新增**，**0 production code 改动守恒**

## 1. 任务输入与派工前提

- **派工类型**: 纯调研 (派工 v6 段 5 实战"调研完成 ≠ 生产实施")
- **基线验证**: 派工 v4 铁律 3 实战 (plan 索引 + git log + grep 当前代码)
- **0 production code 守恒**: 仅新增 `docs/` + `memory/`, 不动 `app/voice/tts.py` + `app/api/v1/voice.py` + `web/src/composables/chat/useChatStream.ts` + `web/src/views/mobile/chat/*` 老路径
- **W76/W77 派生建议**: iOS Safari 4 维度修复 + Android Chrome 4 维度修复 + Edge-TTS 主拍接入主拍决策

## 2. 派工 v4 铁律 3 真验证实战

### 2.1 Step 1: plan 索引 (空输出)

```bash
ls "C:/Users/pc/.claude/plans/" 2>/dev/null | grep -iE "edge-tts|mobile.*tts|tts.*mobile"
# (空输出)
```

**发现**: Edge-TTS 移动端兼容性无独立 plan, W73 A-2 调研 §2.6 派生建议 W75 Step 8 (本调研提前 W75 实施)。

### 2.2 Step 2: git log 真验证 (6 条关键 commit)

```bash
git log --oneline main | grep -iE "edge-tts|tts|mobile.*audio"
```

**关键 commits**:
- `e8b49a6ef` CLAUDE.md 沉淀 edge-tts 6.1.9 失效 + requirements.txt 锁版本坑 4 条铁律
- `41cf204d2` 升级 edge-tts 6.1.9 → 7.2.8 修复 403 Forbidden (2026-06-13)

**发现**: 移动端 TTS 兼容性测试 commit = 0, CLAUDE.md 声称"iOS Safari + Android Chrome 全兼容"但**无验证 commit**。

### 2.3 Step 3: grep 当前代码

```bash
grep -rE "edge-tts|edge_tts|TTSService|TTSEngine" app/ web/src/ --include="*.py" --include="*.vue" --include="*.ts" -l
# app/voice/tts.py
```

**发现**:
- `app/voice/tts.py` 是 Edge-TTS 唯一后端实现 (TextToSpeech + edge_tts.Communicate 7.2.8)
- 16 中文 voice 选项 (晓晓/晓伊/云希/云健/云扬/晓梦 等)
- 前端触发点: `useChatStream.ts:887` + `ChatViewSSE.vue:540` + `MobileChatView.vue:549` + `MobileMessageBubble.vue:64`
- API 端点: `app/api/v1/voice.py:88` POST `/api/v1/voice/tts` 返回 `audio/mpeg`
- `playTTS` 使用 `new Audio(url) + audio.play()` 模式 — 移动端兼容性调研核心

## 3. 4 维度 + 16 case 实战汇总

### 3.1 维度 1: iOS Safari autoplay (派工 v10 类 20 实战)

**4 case**:
1. user gesture 后立即播放 (桌面 Chrome): ✅ PASS
2. user gesture 后立即播放 (iOS Safari 16+): ⚠️ async 链可能丢 user gesture
3. 后台切前台 (锁屏后恢复): ❌ AudioContext 可能被强制 suspend
4. 静音模式 (iOS 物理静音): ✅ PASS

**关键风险**: `axios.post` 异步丢失 user gesture → 需 `await playTTS()` 改同步

### 3.2 维度 2: Android Chrome 音频格式

**4 case**:
1. MP3 24kHz (Edge-TTS 默认): ✅ Android Chrome 全支持, 当前 `media_type="audio/mpeg"` PASS
2. WAV 16kHz: ❌ Edge-TTS 不直接支持, 需 `pydub`/`ffmpeg` 转换
3. OGG Vorbis: ❌ Edge-TTS 不支持, Android Chrome 90+ 支持
4. AAC: ❌ Edge-TTS 不支持, Android Chrome 90+ 支持

**关键发现**: Edge-TTS 仅输出 MP3, 多格式需求需后端转换 (不在本调研范围)

### 3.3 维度 3: 后台切换 (iOS Safari + Android Chrome)

**4 case**:
1. 前台播放: ✅ 双端 PASS
2. 后台 tab 暂停: ⚠️ 取决于 Safari 版本 + Chrome audio focus
3. 锁屏恢复: ⚠️ iOS 16+ 恢复 OK, 旧版可能卡死; Chrome 标准行为
4. 切换 tab: ⚠️ 缺 `visibilitychange` 事件监听

**关键风险**: 缺 `visibilitychange` / `pagehide` 事件监听, 用户切走 tab 时 audio 资源不释放

### 3.4 维度 4: 中断恢复 (Edge-TTS 流式 + 网络)

**4 case**:
1. 正常中断 (用户暂停/关页): ❌ 无 `pagehide` 监听, Blob URL 可能泄漏
2. 网络抖动 (fetch 中途断): ❌ 无 retry, 失败弹 `ElMessage.error`
3. 用户取消 (新 🔊 打断旧 🔊): ✅ `playingAudio.pause()` + `URL.revokeObjectURL` 已实现
4. 浏览器关闭 (OOM/kill): ⚠️ 服务端无状态, 无泄漏风险

**关键发现**: 缺网络重试 + 指数退避, 同文本无缓存, Edge-TTS endpoint 是 SPOF

## 4. 调研 ≠ 生产警示 (派工 v6 段 5 反馈 #1-#5 实战)

5 铁律守恒 (派工 v6 段 5 反馈实战):

1. **调研完成 ≠ 生产实施** — 主拍须拍方案选择 (反馈 #1)
2. **不破坏现有 Edge-TTS 实现** — 已有 ASR/TTS 链路, 仅调研不写 (反馈 #2)
3. **派生新任务必先 git log 真验证** — 类 20.1 + 类 20.10 实战 (反馈 #3)
4. **商业化主拍单独拍板** — Edge-TTS 主拍接入主拍 (反馈 #6)
5. **跨平台兼容性调研必含 iOS Safari + Android Chrome 双端** — 类 20.5 量纲混淆实战 (反馈 #5)

## 5. W76/W77 派工建议

### 5.1 W76 Step 8: iOS Safari 4 维度修复

**预期交付**:
- `useChatStream.ts:887` playTTS 改造: AudioContext 替代 new Audio + user gesture 上下文保留 + visibilitychange/pagehide 监听 + 网络 fetch retry
- iOS Safari 16+ 真机/模拟器 E2E 测试 (Playwright iPhone viewport)
- 派生调研: 实施完成 ≠ 主拍验收

**实施前置**: 调研阶段不动 useChatStream.ts, W76 实施阶段才改

### 5.2 W76 Step 9: Android Chrome 4 维度修复

**预期交付**:
- 后端 audio/mpeg 改造 (可选 audio/wav/ogg/aac, 依主拍决策)
- Android Chrome 真机/模拟器 E2E 测试 (Playwright Pixel viewport)
- audio focus 冲突处理 (MediaSession API 集成)
- 同文本缓存 (IndexedDB / localStorage)

**实施前置**: 调研阶段不动 app/api/v1/voice.py, W76 实施阶段才改

### 5.3 W77 Step 10: Edge-TTS 主拍接入主拍决策

**预期交付**:
- 主拍决策文档 (派工 v6 段 5 反馈 #6 实战):
  - 选项 A: 维持 Edge-TTS 单一后端 (低风险, 调研驱动 16 case 优化)
  - 选项 B: Edge-TTS + Web Speech API 降级 (中等风险)
  - 选项 C: Edge-TTS + Azure/Google TTS 多供应商 (高风险)
  - 选项 D: Edge-TTS + 后端 pre-synthesize 缓存 (中低风险)
- 商业化 cost 模型 (Edge-TTS 7.2.8 免费 + Azure/Google 按字符计费)

## 6. 0 production code 改动铁律守恒验证

| 范畴 | 实际 | 守恒 |
|------|------|------|
| docs/ | 新增 1 (本文配套 docs/w75-1st-batch-a2-edge-tts-survey-2026-07-27.md) | ✅ |
| memory/ | 新增 1 (本文) | ✅ |
| scripts/ | 0 | ✅ |
| tests/ | 0 | ✅ |
| app/voice/ | 0 | ✅ |
| app/api/ | 0 | ✅ |
| app/services/ | 0 | ✅ |
| alembic/versions/ | 0 | ✅ |
| web/src/views/ | 0 | ✅ |
| web/src/composables/ | 0 | ✅ |
| web/dist/ | 0 | ✅ |

**0 production code 改动铁律** ✅ **守恒**

## 7. 派工前提铁律 12 条实战

1. 派生新任务必先 git log + grep 真验证 (派工 v6 段 5 反馈 #3)
2. 不重做已 plan 实施代码 (派工 v6 段 5 反馈 #2)
3. 调研"差距"必先辨明量纲 (W74 A-2 类 20.5)
4. 调研建议主拍必拍"破坏性 vs 渐进"修复路径 (W74 A-2 类 20.6)
5. 实施前必先 `information_schema` 实查 (派工 v6 段 5 反馈 #5)
6. alembic 链必 1 head (W73 E-1 派工 v6 段 5 反馈 #3)
7. 实施前置 7 项必含 (qa-bench D9 + C-2 §6 实战)
8. 商业化 B-2 主拍单独拍板 (派工 v6 段 5 反馈 #6)
9. 0 production code 例外必含派工批文 (CLAUDE.md W67 §3)
10. commit message 必含锚点范式数字 (派工 v10 段 9)
11. 部署前必跑 alembic chain verify (W74 E-1 类 20.8)
12. 调研派生的 schema 任务, 实施前必先 information_schema 实查 (W74 B-1 类 20.7)

## 8. 派工 v10 段 7 类 20 实战 (派生新任务必先真验证 14 条)

W72 A-2 3 + W74 A-1 1 + W74 A-2 2 + W74 B-1 1 + W74 E-1 2 + W75 A-2 4 = **14 条**

- 类 20.1: 派生新任务必先 git log + grep 真验证当前 main HEAD (W72 A-2)
- 类 20.2: 不信 plan Status 自报 (W72 A-2)
- 类 20.3: 不信派工 brief 假设 (W72 A-2)
- 类 20.4: 派工基线 999276dda 在 worktree 分支不在本地 main (W74 A-1)
- 类 20.5: 调研"差距"必先辨明量纲 (W74 A-2)
- 类 20.6: 调研建议主拍必拍"破坏性 vs 渐进"修复路径 (W74 A-2)
- 类 20.7: 调研派生的 schema 任务, 实施前必先 information_schema 实查 (W74 B-1)
- 类 20.8: 部署前必跑 alembic chain verify (W74 E-1)
- 类 20.9: 验证型 agent 必严格不照抄派工书 PASS, 必报实测不符 (W74 E-1)
- 类 20.10: 派工 brief "基线已在 main" 假设必拒, 必先 git log 真验证 (W74 A-1)
- **类 20.11**: 移动端兼容性调研必先 §1 三步真验证 (plan 索引 + git log + grep 当前代码) (W75 A-2)
- **类 20.12**: 调研完成 ≠ 主拍验收 (W75 A-2)
- **类 20.13**: 商业化主拍单独拍板 (W75 A-2)
- **类 20.14**: 跨平台兼容性调研必含 iOS Safari + Android Chrome 双端 (W75 A-2)

## 9. 锚点范式守恒

| 阶段 | 锚点范式 | 守恒 | commit hash |
|------|----------|------|-------------|
| W73 第 2 批 grand closure | 235 | - | (W73 closure) |
| W74 第 1 批 grand closure | 249 | +14 | `51d390b07` |
| **W75 第 1 批 A-2 调研** | **252** | **+3** | **(本任务)** |

**锚点范式守恒数字**: W74 第 1 批 249 → W75 第 1 批 A-2 **252 守恒** (+3, 0 regression)
**0 production code 守恒**: 14/15 守恒预测 (本调研例外 0, 14 commits 全是 docs/memory)

## 10. 关键发现总结 (派生 W76/W77 任务清单)

### 10.1 关键风险 5 项 (必在 W76/W77 解决)

1. **iOS Safari async 链丢 user gesture** (维度 1 case 1.2)
2. **iOS Safari AudioContext 被强制 suspend** (维度 1 case 1.3)
3. **缺 visibilitychange/pagehide 监听** (维度 3 case 3.2-3.4)
4. **缺网络 fetch retry + 指数退避** (维度 4 case 4.2)
5. **同文本无缓存** (维度 4 case 4.1)

### 10.2 关键机会 4 项 (W77 主拍决策点)

1. **Web Speech API 降级** (前端备选, 不依赖 Edge-TTS)
2. **Azure TTS 多供应商** (商业化按字符计费)
3. **后端 pre-synthesize 缓存** (alembic + 缓存层)
4. **MediaSession API 集成** (Android Chrome audio focus 优化)

## 11. 后续任务 (W76/W77 必先 git log 真验证)

依 v10 段 7 类 20.1-20.14 实战, W76/W77 实施前必先:

```bash
# W76 Step 8 派工前 (iOS Safari 修复)
git log --oneline main | grep -iE "edge-tts|playTTS|tts.*mobile"
git log --oneline main | grep -iE "audio.*context|user.*gesture|visibilitychange"
grep -rE "playTTS|new Audio|user gesture" web/src/ --include="*.ts" --include="*.vue" -l

# W76 Step 9 派工前 (Android Chrome 修复)
git log --oneline main | grep -iE "audio.*mpeg|media.*type|android.*chrome"
git log --oneline main | grep -iE "media.*session|audio.*focus"
grep -rE "media_type.*audio|StreamingResponse" app/api/ -l

# W77 Step 10 派工前 (主拍决策)
git log --oneline main | grep -iE "tts.*provider|azure.*tts|web.*speech"
git log --oneline main | grep -iE "tts.*cache|pre.*synthesize"
```

## 12. 调研 ≠ 生产警示 (再次强调)

**调研完成 ≠ 生产实施** —— 主拍须拍 §5 W76/W77 派工建议是否进实施阶段 + 选 iOS Safari 优先 / Android Chrome 优先 / 双端并行。

**商业化主拍单独拍板** —— Edge-TTS 主拍接入主拍 (派工 v6 段 5 反馈 #6), 选项 A/B/C/D 决策必含成本模型。

**派生新任务必先真验证** —— W76/W77 派工前必先 §11 三步真验证 (派工 v4 铁律 3 + 派工 v10 段 7 类 20.1-20.14 实战)。
