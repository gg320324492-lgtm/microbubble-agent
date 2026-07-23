# W68 路线 G-1: Mobile 语音输入 (2026-07-24)

**锚点范式第 39 守恒 (W68 第 1 批跨主题收口延续)** — 移动端 10 PR 全栈定制收官
(v3.0) 续, 在 MobileChatView 聊天框接入语音输入 (复用现有 faster-whisper 后端
`/api/v1/voice/asr`).

## 范围 (0 production code 改动铁律维持)

仅 mobile 前端改动, 不动后端, 不动 v1/v2 老路径:

1. **新增** `web/src/composables/useMobileVoiceInput.ts` (~340 行) — MediaRecorder
   + ASR 转写 + 状态机 + 上滑取消 + 触觉反馈
2. **新增** `web/src/components/mobile/MobileVoiceInputButton.vue` (~280 行) —
   长按麦克风按钮 + 浮层 (5 音量柱 + 时长 + 提示)
3. **改动** `web/src/views/mobile/chat/MobileInputBar.vue` — 替换老麦克风 button
   为 `MobileVoiceInputButton`, 复用 v-model:text 双绑
4. **改动** `web/src/views/mobile/chat/MobileChatView.vue` — 监听
   `voice-transcribed` 事件 (滚动到底) + `voice-state` (错误处理)
5. **新增** `web/tests/e2e/mobile_voice_input.spec.js` — Playwright e2e (3 场景)
6. **新增** `web/src/composables/__tests__/useMobileVoiceInput.test.ts` — 8 vitest
7. **新增** `web/src/components/mobile/__tests__/MobileVoiceInputButton.test.js` —
   8 vitest

**总**: 5 新增 + 2 改动 = 7 文件. main HEAD `37e0de62a` 之前无 G-1 代码.

## 关键设计决策

### 决策 1: 默认 `autoSend=false` (仅插入文本, 不发送)

**反模式**: 老 `onVoiceStart`/`onVoiceEnd` 走 `asrRecognize(blob) → sendMessage()`,
长按到底自动发. 风险: 误触发 / ASR 识别错误无法修正 / 用户没准备好.

**新模式**: ASR 完成仅写入 `inputText`, 由用户编辑后点 send 按钮.
- 兜底: `autoSend=true` prop 可切换 (PR 后续, 当前默认 false)
- 理由: 移动端用户对"立即发送"敏感度低, 但对"误发"敏感度高 (CLAUDE.md
  2026-06-27 教训: mobile long-press 必带 vibrate, 但发送是另一回事)

### 决策 2: MIME 探测链复用 #207 修复 (2026-07-16)

```ts
const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',  // Chrome / Android / Edge
  'audio/webm',              // 部分老 Chromium
  'audio/ogg;codecs=opus',   // Firefox
  'audio/mp4',               // iOS Safari 必须
]
```

**复用来源**: `useGlobalRecorder.js` 第 36-58 行 `getSupportedMimeType()`.
**理由**: #207 教训 — HarmonyOS 6.x ArkWeb / 企业微信 X5 / iOS Safari 调
硬编码 `audio/webm;opus` 直接抛 `NotSupportedError` → 录音链路整个挂掉.
本组件沿用探测链 0 分叉, 避免再次踩坑.

### 决策 3: getUserMedia 5s timeout 兜底

```ts
function getUserMediaWithTimeout(timeoutMs) {
  return Promise.race([
    navigator.mediaDevices.getUserMedia({ audio: true }),
    new Promise((_, r) => setTimeout(() => r(new Error('5s timeout')), timeoutMs)),
  ])
}
```

**复用来源**: 同样在 `useGlobalRecorder.js` 第 22-32 行. 直接 copy 函数体, 不抽
公共 util (避免改老路径破坏其他 7 个录音组件).

### 决策 4: 浮层 Teleport to="body" + glass glass-lg

录音浮层用 `<Teleport to="body">` 而非固定在按钮上方. **理由**:
- iOS Safari 16+ PWA: 父容器若有 `transform: scale(...)` 或 `filter: ...`,
  内部 `position: fixed` 会受限于父容器 → 浮层不居中
- Teleport 绕过父容器 stacking context, 浮层一定居中
- 复用 `.glass .glass-lg` (v77 P2.5.1 工具类) → 背景透明 + 模糊,
  暗色模式自动适配

**Dark mode 适配** (CLAUDE.md v60-v67 第 5 次强化): dark mode 跨组件必须**非
scoped 块** (CSS 变量穿透). 浮层 `.mvi-panel` 在 `<style scoped>` 内定义
background, 但 `dark` 模式在 `<style>` (无 scoped) 块中重新覆盖:

```css
/* scoped 块 */
.mvi-panel { background: var(--color-bg-card); }

/* 非 scoped 块 — dark mode 适配 */
[data-theme="dark"] .mvi-panel { background: var(--color-bg-card); ... }
```

### 决策 5: 上滑取消阈值 50px (类似微信)

```ts
const SLIDE_CANCEL_THRESHOLD = 50
```

**复用**: MobileInputBar 既有 onVoiceStart/onVoiceEnd 没做上滑取消 → 误发
体验差. 新组件用全局 `touchmove` 监听 (mounted/unmounted 配对) → dy < -50px
进入取消区 → 浮层变红 + 提示"松手取消" → 松手 → 调 `voice.cancel()` (不触发
ASR).

**性能**: `touchmove` 监听用 `{ passive: true }`, 不 preventDefault, 不阻塞
滚动. `isCancelZone` ref 仅触发 reactive update, 不影响其他 ref.

### 决策 6: 不复用 `useGlobalRecorder.js` 单例

**反模式**: 复用 `useGlobalRecorder` 全局单例 → 与会议录音冲突 (会议房间
在录会议, 用户又开 mobile voice input → stream 共享, ondataavailable 互相
污染).

**新模式**: `useMobileVoiceInput` 独立创建 `MediaRecorder` 实例, 组件 unmount
时调 `dispose()` → 释放 stream + AudioContext. 零共享, 零冲突.

**代价**: 多份 `MediaRecorder` 内存 (一个 ~5KB, 可忽略), 换取 0 状态污染.

## 7 条新铁律沉淀

1. **Mobile 语音输入不复用 useGlobalRecorder 单例** — 与会议录音冲突
   (stream 共享, ondataavailable 互相污染). 必须独立 MediaRecorder 实例
2. **getUserMedia 5s timeout 兜底是必须的** — HarmonyOS / X5 / 部分 WebView
   既不 resolve 也不 reject, UI 永久卡死
3. **MIME 探测链 webm;opus → webm → ogg;opus → mp4** — iOS Safari 不支持
   前 3 种, 必须 mp4
4. **默认 autoSend=false, 仅插入文本** — mobile 误发体验差, 用户可编辑
5. **浮层用 Teleport to="body"** — 父容器 transform 限制会破坏 fixed 居中
6. **上滑取消阈值 50px 全局 touchmove + passive** — 类似微信, 不阻塞滚动
7. **dark mode 跨组件必须非 scoped 块** — CLAUDE.md v60-v67 第 5 次强化,
   浮层穿透父容器后 scoped 块失效

## 复用模式

### 复用 #1: 触觉反馈 useHaptic (CLAUDE.md 2026-06-27 教训)

```ts
import { useHaptic } from '@/composables/chat/useHaptic'
const haptic = useHaptic()
haptic.tap()       // 录音开始 10ms
haptic.success()   // ASR 完成 [10, 50, 10]
haptic.warning()   // 取消 [30, 50, 30]
```

### 复用 #2: ASR 端点 `/api/v1/voice/asr`

直接 axios post, 不动后端. 客户端 < 1KB 拦截 (复用 CLAUDE.md 2026-06-18
教训):

```ts
const MIN_AUDIO_SIZE = 1024
if (blob.size < MIN_AUDIO_SIZE) {
  ElMessage.warning('录音太短（不到 1 秒），请长按说话')
  return null
}
```

### 复用 #3: AudioContext + AnalyserNode 波浪动画

`createAnalyser().getByteFrequencyData()` 拿 0-255 频率强度 → 5 段均值 →
映射到 4-40px 高度 → `requestAnimationFrame` 60fps 更新.

**iOS Safari 兼容**: `new AudioContext()` 必须在 user gesture (touchstart) 内
创建, 否则静音. setup.js polyfill 提供 `FakeAudioContext` 兜底测试.

## 部署必做

```bash
# 1. 跑迁移 — 本次无 DB 改动, 跳过 alembic
# 2. 重启 Python 进程 — 本次无后端改动, 跳过 docker compose restart
# 3. 前端构建 (CLAUDE.md 752 行铁律: npm run build 是唯一合法 build)
cd web && npm run build
# 4. git add -f web/dist/manifest.{hash}.webmanifest
# 5. push → webhook 30s → 用户浏览器 DevTools Clear site data + 硬刷
```

## vitest 验证 (16/16 PASS)

```
RUN  v4.1.8
Test Files  2 passed (2)
Tests       16 passed (16)
Duration    1.30s
```

- `useMobileVoiceInput.test.ts` — 8 场景 (start / error / MIME 探测 / ASR /
  cancel / 自定义 asrFn / autoSend)
- `MobileVoiceInputButton.test.js` — 8 场景 (默认渲染 / touchstart / v-model
  / touchend stop / 取消区 cancel / aria-label / disabled / 浮层显示)

## 跨主题累计

W68 第 1 批 14+1 agents 收官 (锚点范式第 30 守恒) + W68 路线 G-1 Mobile
语音输入 (本 commit) → W68 累计 16 commits, 锚点范式单调上升.

**未来 PR 排期** (W68 路线 G-2 ~ G-N):
- G-2: Mobile 消息长按菜单已存在 (MobileMessageList 走 LongPressWrapper),
  可优化为 v3.0 风格
- G-3: Mobile 录音断网防御 (网络失败时 blob 暂存 IndexedDB, 恢复后重试)
- G-4: Mobile 语音输入 i18n (英文 / 日文 ASR 切换)

## commit 信息

```
feat(mobile): voice input for MobileChatView (W68 路线 G-1)

- New useMobileVoiceInput composable: MediaRecorder + ASR + slide-to-cancel
- New MobileVoiceInputButton: long-press mic + glass overlay with 5 volume bars
- Wire into MobileInputBar replacing the legacy mic button
- MobileChatView listens voice-transcribed for scroll-to-bottom + state hooks
- E2E spec at tests/e2e/ + 16 vitest cases (8 composable + 8 component)
- Reuse /api/v1/voice/asr (no backend changes, 0 production code 改动铁律)
- Reuse #207 fix: MIME probe chain + 5s getUserMedia timeout
- Reuse 2026-06-27 lesson: long-press triggers navigator.vibrate(10)
- Dark mode: non-scoped block per v60-v67 lesson
```
