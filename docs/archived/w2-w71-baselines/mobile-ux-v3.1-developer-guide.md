# Mobile UX v3.1 开发者指南 — Composable API + 集成范式

> **版本**: v3.1
> **日期**: 2026-07-24
> **作者**: W68 路线 H-2 Agent
> **基线**: `37e0de62a` (W68 路线 B/E 收官后 main HEAD)
> **范围**: 仅 docs — 0 production code 改动 (主指挥来 merge 后, composable 由其他 PR 收官)
> **前置**: [Mobile UX v3.0 开发者指南](./mobile-ux-v3.md) + [v3.1 用户指南](./mobile-ux-v3.1-user-guide.md)

---

## 目录

1. [架构概览](#1-架构概览)
2. [`useMobileVoiceInput` API](#2-usemobilevoiceinput-api)
3. [`useSwipeGesture` / `useSwipeNavigation` API](#3-useswipegesture--useswipenavigation-api)
4. [`usePullToRefresh` API](#4-usepulltorefresh-api)
5. [`useHaptic` 触觉反馈最佳实践](#5-usehaptic-触觉反馈最佳实践)
6. [组件集成范式](#6-组件集成范式)
7. [iOS Safari / Android Chrome 兼容性矩阵](#7-ios-safari--android-chrome-兼容性矩阵)
8. [测试与可观测性](#8-测试与可观测性)
9. [性能与内存](#9-性能与内存)

---

## 1. 架构概览

v3.1 新增 5 个 composable + 3 个 component + 2 个 view 集成点, 全部围绕 "**单手操作**" + "**离线优先**" 两条主线展开。

```
┌─────────────────────────────────────────────────────────────┐
│  MobileChatView (G-1 + G-2 集成点)                          │
│  ├─ useMobileVoiceInput() ──→ MediaRecorder → ASR → text    │
│  ├─ useSwipeGesture(messageList) ──→ left/right → nav        │
│  └─ usePullToRefresh(messageList) ──→ server fetch + cache  │
│                                                              │
│  MobileCommandPalette (G-1 集成点)                           │
│  └─ useMobileVoiceInput() ──→ command ASR → fuzzy match     │
│                                                              │
│  MobileSearchSheet (G-1 集成点)                              │
│  └─ useMobileVoiceInput() ──→ query ASR → search results    │
│                                                              │
│  4 个主页面 (Dashboard / Task / Knowledge / Workspace)       │
│  └─ useSwipeNavigation() ──→ left/right → tab switch        │
│  └─ usePullToRefresh(scrollArea) ──→ server refetch         │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 设计原则 (CLAUDE.md v60+ 教训复用)

| 原则 | 说明 | 教训来源 |
|------|------|---------|
| **跨 event loop 安全** | 所有外部 IO (MediaRecorder / ASR client) 通过 `ctx` 注入, 禁止模块顶部 import 阶段创建 | CLAUDE.md 方案 C 铁律 1 |
| **触觉必带 `navigator.vibrate(10)`** | 所有移动端交互默认带 10ms 短震, iOS Safari 静默 try/catch | CLAUDE.md 2026-06-27 教训 |
| **dark mode 跨组件必须非 scoped 块** | 任何 v-html / inline style 都不能写 `<style scoped>`, 用全局 CSS 变量 | CLAUDE.md v60-v67 第 5 次强化 |
| **JSONB mutate 必 `flag_modified`** | (不适用本次, 防止新组件违反) | CLAUDE.md 2026-06-28 教训 |
| **失败 best-effort** | 所有触觉 / 录音 / 滑动回调都 try/catch, 不阻塞主流程 | CLAUDE.md Phase 3 铁律 5 |

### 1.2 文件清单 (v3.1 新增)

| 路径 | 类型 | 行数 (估) | 状态 |
|------|------|----------|------|
| `web/src/composables/useMobileVoiceInput.js` | composable | ~280 | 待合并 (主指挥来 merge) |
| `web/src/composables/useSwipeNavigation.js` | composable | ~120 | 待合并 |
| `web/src/composables/usePullToRefresh.js` | composable | ~200 | 待合并 |
| `web/src/composables/chat/useHaptic.js` | composable | 47 | 已存在 (复用, 仅文档) |
| `web/src/composables/useSwipeGesture.js` | composable | ~120 | 已存在 (v2.28+, 复用) |
| `web/src/components/mobile/VoiceInputButton.vue` | component | ~180 | 待合并 |
| `web/src/components/mobile/PullToRefreshIndicator.vue` | component | ~150 | 待合并 |
| `web/src/components/mobile/SwipePageIndicator.vue` | component | ~80 | 待合并 |
| `web/src/views/mobile/chat/MobileChatView.vue` | view (集成) | +60 行增量 | 待合并 |
| `web/src/views/mobile/MobileCommandPalette.vue` | view (集成) | +30 行增量 | 待合并 |

> **0 production code 改动铁律**: 本 PR **不包含**任何上述文件 — 全部是文档先行, 主指挥拍板后由其他 PR 收官。

---

## 2. `useMobileVoiceInput` API

### 2.1 签名

```typescript
interface UseMobileVoiceInputOptions {
  /** 录音最大时长 (ms), 默认 60000 */
  maxDuration?: number
  /** 最短录音时长 (ms), 低于则视为误触, 默认 500 */
  minDuration?: number
  /** 取消阈值 (px), 向上滑超过此值算取消, 默认 80 */
  cancelThreshold?: number
  /** ASR 服务地址, 默认走 /api/asr */
  asrEndpoint?: string
  /** ASR 引擎: 'sensevoice' | 'faster-whisper' | 'auto' */
  asrEngine?: 'sensevoice' | 'faster-whisper' | 'auto'
  /** 录音结束的回调 (传入 ASR 转写后的文字) */
  onResult?: (text: string) => void
  /** 录音被取消的回调 (用户上滑松手) */
  onCancel?: () => void
  /** 录音错误的回调 */
  onError?: (error: Error) => void
  /** 是否触发触觉反馈, 默认 true */
  haptic?: boolean
}

interface UseMobileVoiceInputReturn {
  /** 当前状态 */
  state: Ref<'idle' | 'requesting-permission' | 'recording' | 'processing' | 'cancelling'>
  /** 当前已录时长 (ms) */
  duration: Ref<number>
  /** 实时音量 (0-1) */
  volume: Ref<number>
  /** 错误对象 (如果有) */
  error: Ref<Error | null>
  /** 开始录音 (用于 @touchstart 绑定) */
  start: (event: TouchEvent) => void
  /** 移动 (用于 @touchmove 绑定, 检测上滑取消) */
  move: (event: TouchEvent) => void
  /** 结束 (用于 @touchend 绑定) */
  end: (event: TouchEvent) => void
  /** 强制停止 (组件卸载时调用) */
  stop: () => Promise<void>
}

export function useMobileVoiceInput(
  options?: UseMobileVoiceInputOptions
): UseMobileVoiceInputReturn
```

### 2.2 用例 1: MobileChatView 长按录音

```vue
<template>
  <div class="chat-input-bar">
    <textarea v-model="text" placeholder="输入消息或长按 🎤 说话" />
    <button
      class="mic-btn"
      :class="{ 'is-recording': state === 'recording' }"
      aria-label="长按开始录音"
      @touchstart="start"
      @touchmove="move"
      @touchend="end"
      @mousedown="start"
      @mouseup="end"
    >
      <MicIcon />
      <span v-if="state === 'recording'" class="recording-indicator">
        {{ formatDuration(duration) }}
      </span>
    </button>
    <button class="send-btn" @click="sendText">➤</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useMobileVoiceInput } from '@/composables/useMobileVoiceInput'
import { useHaptic } from '@/composables/chat/useHaptic'

const text = ref('')
const haptic = useHaptic()

const { state, duration, start, move, end } = useMobileVoiceInput({
  maxDuration: 60_000,
  cancelThreshold: 80,
  asrEngine: 'auto',
  onResult: (recognizedText) => {
    text.value = recognizedText
    haptic.success()
  },
  onCancel: () => {
    haptic.warning()
  },
  onError: (err) => {
    console.error('[voice-input] failed:', err)
    haptic.error()
  },
})

function sendText() {
  if (!text.value.trim()) return
  // 走 sendMessage 逻辑
  chatStore.send(text.value)
  text.value = ''
}

function formatDuration(ms) {
  const s = Math.floor(ms / 1000)
  return `00:${String(s).padStart(2, '0')}`
}
</script>

<style scoped>
.mic-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 200ms;
  /* 触觉反馈: 长按 0.3s 触发, 不需要额外 delay */
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}
.mic-btn.is-recording {
  background: var(--color-danger);
  color: white;
  /* 录音中脉冲动画 */
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}
</style>
```

### 2.3 用例 2: 错误处理与降级

```vue
<script setup>
import { useMobileVoiceInput } from '@/composables/useMobileVoiceInput'

const { state, error, start } = useMobileVoiceInput({
  onError: (err) => {
    // 错误分类处理
    if (err.name === 'NotAllowedError') {
      showPermissionDialog()
    } else if (err.name === 'NotSupportedError') {
      showUnsupportedDialog()
    } else if (err.message.includes('timeout')) {
      showTimeoutDialog()
    } else {
      showGenericError(err)
    }
  },
})

function showPermissionDialog() {
  // 引导去 iOS 设置: 设置 → Safari → 网站设置 → 麦克风
  // 引导去 Android Chrome: 地址栏锁形图标 → 权限 → 麦克风
  ElMessageBox.confirm(
    '请在浏览器设置中允许麦克风权限, 然后刷新页面',
    '需要麦克风权限',
    { confirmButtonText: '查看教程', cancelButtonText: '取消' }
  ).then(() => {
    window.open('/docs/mobile-ux-v3.1-user-guide.html#13-ios-safari-权限流程', '_blank')
  })
}
</script>
```

### 2.4 关键设计决策

| 决策 | 原因 | 替代方案 |
|------|------|---------|
| **不直接发送, 只填入输入框** | 给用户编辑机会 (ASR 5-10% 错误率) | 直接发送 (用户反馈差) |
| **长按 0.3s 触发** | 区分 "点击" 和 "按住" | 点击触发 (太敏感) |
| **向上滑取消, 下滑不响应** | iOS 习惯 + 避免与系统级下拉冲突 | 左右滑 / 下滑都取消 |
| **MIME 探测链 webm→ogg→mp4** | iOS Safari 只支持 mp4 | 硬编码 webm (iOS 必坏) |
| **5s getUserMedia timeout** | HarmonyOS ArkWeb / 企业微信 X5 已知 bug | 无 timeout (UI 永久卡死) |
| **ASR 走 /api/asr 异步** | 不阻塞 UI, 排队到 Celery | 同步请求 (ANR 风险) |

### 2.5 与 v3.0 录音机的区别

| 维度 | v3.0 录音机 | v3.1 语音输入 |
|------|------------|---------------|
| 入口 | 顶部导航 → 会议 → 录音机 | 任意页面的 🎤 按钮 |
| 时长 | 理论无上限 (分段 60s) | 单次 60s 硬上限 |
| 触发 | 显式开始/停止 | 长按 0.3s + 松开 |
| 用途 | 会议录音 / 长内容 | 聊天消息 / 搜索 / 命令 |
| 后处理 | 走会议 AI 分析 (发言人 + 转录) | 走 ASR 单次转写 |
| 存储 | MinIO + 会议表 | 不存储, 仅文字 |

---

## 3. `useSwipeGesture` / `useSwipeNavigation` API

`useSwipeGesture` (v2.28+ 已存在) 是基础手势识别, `useSwipeNavigation` (v3.1 新增) 是基于它的"页面级封装"。

### 3.1 `useSwipeGesture` (基础, 已存在)

```javascript
// 用法 (来自 web/src/composables/useSwipeGesture.js 注释)
const { onSwipeLeft, onSwipeRight, currentSwipe } = useSwipeGesture(elementRef, {
  threshold: 50,   // 距离阈值 (px)
  timeout: 300,    // 时间阈值 (ms)
})

onSwipeLeft(() => goNext())
onSwipeRight(() => goPrev())
```

### 3.2 `useSwipeNavigation` (高级封装, 待合并)

```typescript
interface UseSwipeNavigationOptions {
  /** 路由实例 (来自 useRouter()) */
  router: Router
  /** Tab 顺序, 例如 ['dashboard', 'task', 'knowledge', 'workspace'] */
  tabOrder: string[]
  /** 当前 tab name (用于计算 prev/next) */
  currentTab: string
  /** 是否启用 (例如在子页面禁用), 默认 () => route.path === '/'  */
  enabled?: () => boolean
  /** 触觉反馈开关, 默认 true */
  haptic?: boolean
}

interface UseSwipeNavigationReturn {
  /** 当前 swipe 方向 (用于 UI 跟随) */
  currentSwipe: Ref<'left' | 'right' | null>
  /** 上一页是否存在 */
  hasPrev: ComputedRef<boolean>
  /** 下一页是否存在 */
  hasNext: ComputedRef<boolean>
  /** 手动跳到上一页 (按钮替代) */
  goPrev: () => void
  /** 手动跳到下一页 */
  goNext: () => void
}

export function useSwipeNavigation(
  options: UseSwipeNavigationOptions
): UseSwipeNavigationReturn
```

### 3.3 用例: 4 个主页面集成

```vue
<!-- MobileDashboard.vue (其他 3 个主页面类似) -->
<template>
  <div ref="rootEl" class="mobile-dashboard">
    <SwipePageIndicator
      v-if="currentSwipe"
      :direction="currentSwipe"
      :has-next="hasNext"
      :has-prev="hasPrev"
    />
    <PageHeader title="Dashboard" />
    <div class="content">
      <!-- 卡片内容 -->
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSwipeNavigation } from '@/composables/useSwipeNavigation'

const rootEl = ref(null)
const route = useRoute()
const router = useRouter()

const { currentSwipe, hasPrev, hasNext, goPrev, goNext } = useSwipeNavigation({
  router,
  tabOrder: ['dashboard', 'task', 'knowledge', 'workspace'],
  currentTab: 'dashboard',
  enabled: () => route.path === '/mobile/dashboard',  // 仅根页面启用
})

// 同时挂载到原生 touch 事件 (composition API 模式)
// 注意: useSwipeNavigation 内部已自动绑 rootEl, 这里仅示意
</script>
```

### 3.4 与 Tab 栏的协同

| 触发 | 行为 | 备注 |
|------|------|------|
| 点击 Tab 栏 | 切换页面 (无 swipe 动画) | 正常点击 |
| 左/右滑 | 切换页面 (有 swipe 动画) | 平滑过渡 |
| 滑动未达阈值 | 回弹 (200ms 弹性动画) | UI 反馈 |
| 子页面 (Task 详情) | 滑动**不响应** (enabled 守卫) | 避免误触 |

> **设计取舍**: 子页面**禁用**滑动, 避免与系统级右滑返回冲突。如需要 "子页面间滑动", 建议用 **stack-based 路由** (router.replace + transition) 而不是 swipe。

### 3.5 触觉反馈集成

`useSwipeNavigation` 默认在 `start` / `success` 时调用 `useHaptic().tap()` / `useHaptic().success()`, 详见 [§5](#5-usehaptic-触觉反馈最佳实践)。

---

## 4. `usePullToRefresh` API

### 4.1 签名

```typescript
interface UsePullToRefreshOptions {
  /** 触发刷新的回调 */
  onRefresh: () => Promise<void>
  /** 触发阈值 (px), 默认 80 */
  threshold?: number
  /** 最大下拉距离 (px), 防止过度拉伸, 默认 120 */
  maxDistance?: number
  /** 顶部容差 (px), 在这个距离内不算下拉, 默认 8 (避免与 tab 栏点击冲突) */
  topTolerance?: number
  /** 是否启用, 默认 () => true */
  enabled?: () => boolean
  /** 触觉反馈开关, 默认 true */
  haptic?: boolean
  /** 距离边缘多少 px 内触发, 默认 20 (避免与系统级下拉冲突) */
  edgeTolerance?: number
}

interface UsePullToRefreshReturn {
  /** 当前下拉距离 (px) */
  distance: Ref<number>
  /** 是否在刷新中 */
  isRefreshing: Ref<boolean>
  /** 当前阶段: idle / pulling / ready / refreshing */
  phase: Ref<'idle' | 'pulling' | 'ready' | 'refreshing'>
  /** 主动触发刷新 (例如按钮) */
  trigger: () => Promise<void>
  /** 用于 ref 绑定 */
  bind: (el: HTMLElement | null) => void
}

export function usePullToRefresh(
  options: UsePullToRefreshOptions
): UsePullToRefreshReturn
```

### 4.2 用例: 4 个主页面集成

```vue
<!-- MobileTaskView.vue -->
<template>
  <div ref="scrollEl" class="mobile-task-view">
    <PullToRefreshIndicator
      :distance="distance"
      :phase="phase"
      :threshold="80"
    />
    <TaskList :tasks="tasks" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useTaskStore } from '@/stores/task'
import { usePullToRefresh } from '@/composables/usePullToRefresh'

const scrollEl = ref(null)
const taskStore = useTaskStore()

const { distance, phase, isRefreshing, bind } = usePullToRefresh({
  onRefresh: async () => {
    await taskStore.fetchTasks({ force: true })
    await taskStore.checkTrash()  // 软删除清理检查
  },
  threshold: 80,
  maxDistance: 120,
})

// bind 会在 onMounted 自动调, 也可以手动:
onMounted(() => bind(scrollEl.value))
</script>
```

### 4.3 三段式视觉状态

| 距离 | phase | UI |
|------|-------|-----|
| 0~40px | `pulling` | 🔄 灰色图标 + "下拉刷新" |
| 40~80px | `pulling` | 🔄 180° 旋转 + "松手刷新" |
| ≥80px (松手) | `refreshing` | ⏳ spinner + "正在刷新" |
| 刷新完成 | `idle` | 自动收起 (transition 250ms) |

### 4.4 关键设计决策

| 决策 | 原因 | 替代方案 |
|------|------|---------|
| **顶部容差 8px** | 区分 "下拉" 和 "点击 tab 栏" | 0 容差 (太敏感) |
| **边缘容差 20px** | 区分 "页面下拉" 和 "系统级右滑返回" | 0 容差 (与 iOS 冲突) |
| **最大距离 120px** | 防止过度拉伸 (overscroll bounce) | 无上限 (视觉不优雅) |
| **async onRefresh** | 支持 API 异步, 内部 await + finally 收起 | 同步 (阻塞 UI) |
| **不依赖 scroll 事件** | 用 touchstart/move/end 精确控制, 避免与 fastclick 冲突 | 监听 scroll (Chrome 桌面端可行, 移动端不可靠) |

### 4.5 与 iOS Safari 原生下拉刷新的冲突

iOS Safari tab 模式下, 顶部下拉会触发**原生刷新页面**行为。处理策略:

1. **PWA 模式**: 无冲突 (standalone 模式无浏览器 chrome)
2. **Browser tab 模式**:
   - `usePullToRefresh` **优先**触发 (touchstart 后立即 `e.preventDefault()`)
   - 触发后, iOS 原生下拉**不会**再次触发 (因为事件已被 preventDefault)
   - 在 PWA install banner (v3.0) 中引导用户 "添加到主屏" 以获得完整体验

> **注意**: iOS Safari < 14 的 `e.preventDefault()` 不能阻止原生下拉刷新, 已被 v3.0 PWA install banner 兜底。

---

## 5. `useHaptic` 触觉反馈最佳实践

`useHaptic` (位于 `web/src/composables/chat/useHaptic.js`) 是 v3.1 触觉反馈的**唯一入口**, 全部移动端组件必须通过它调用, 禁止直接 `navigator.vibrate(...)`。

### 5.1 现有 API (已存在, 复用)

```javascript
import { useHaptic } from '@/composables/chat/useHaptic'

const haptic = useHaptic()
haptic.tap()      // 10ms 单震 — 按钮点击
haptic.success()  // [10, 50, 10] — 成功反馈
haptic.warning()  // [30, 50, 30] — 警告
haptic.error()    // [50, 100, 50] — 错误
haptic.vibrate(pattern)  // 自定义
```

### 5.2 触觉反馈设计原则 (CLAUDE.md v60+ 教训)

| 原则 | 说明 | 反例 |
|------|------|------|
| **必须有视觉替代** | iOS Safari 无震动, 必须有颜色/动画 | 只震动, 无视觉 |
| **不要过频** | 单次操作最多 1 次震动 | 每次 scroll 都震 |
| **错误必震** | 失败时给 `error` 反馈, 让用户感知 | 静默失败 |
| **success 必震** | 完成时给 `success` 反馈, 让用户确认 | 静默成功 |
| **不阻塞主流程** | try/catch 包住, 失败静默 | throw 阻塞 UI |
| **统一入口** | 必须用 `useHaptic()`, 不要直接 `navigator.vibrate` | 散落各组件直接调 |

### 5.3 触觉 vs 视觉反馈映射表

| 场景 | 触觉 | 视觉 |
|------|------|------|
| 按钮点击 | `tap` (10ms) | 按钮 :active 变色 |
| 长按开始录音 | `tap` (10ms) | 🎤 变红 + 脉冲 |
| ASR 转写完成 | `success` | 输入框出现文字 + 短暂高亮 |
| 上滑取消录音 | `warning` | "松手取消" 气泡 + 图标淡灰 |
| 录音失败 | `error` | 红色 toast + 重试按钮 |
| 任务创建成功 | `success` | 卡片飞入动画 + ✓ 勾选图标 |
| 触觉反馈关闭 | 无 | 设置页显示 "触觉反馈已关闭" |

### 5.4 触觉反馈性能注意事项

| 问题 | 解决 |
|------|------|
| `navigator.vibrate` 在 iOS Safari 抛错 | useHaptic 内部 try/catch |
| 短时间内多次震动 (e.g. fast click) | 内部 100ms debounce |
| 后台调用震动 (无意义) | `document.visibilityState === 'visible'` 检查 |
| 用户偏好 `prefers-reduced-motion: reduce` | 同时禁用震动 + 动画 (a11y) |

### 5.5 用户开关实现

```typescript
// stores/userPreferences.ts (示意)
import { defineStore } from 'pinia'

export const useUserPreferences = defineStore('userPrefs', {
  state: () => ({
    hapticEnabled: localStorage.getItem('haptic-enabled') !== 'false',  // 默认开
  }),
  actions: {
    setHaptic(enabled: boolean) {
      this.hapticEnabled = enabled
      localStorage.setItem('haptic-enabled', String(enabled))
    },
  },
})
```

```javascript
// composables/chat/useHaptic.js (改造示意, 实际合并时改)
import { useUserPreferences } from '@/stores/userPreferences'

export function useHaptic() {
  const prefs = useUserPreferences()

  function vibrate(pattern) {
    if (!prefs.hapticEnabled) return
    if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
    if (typeof navigator === 'undefined' || !navigator.vibrate) return
    try {
      navigator.vibrate(pattern)
    } catch {
      // iOS Safari / 企业微信 X5 等老内核
    }
  }

  return { tap: () => vibrate(10), /* ... */ }
}
```

> **注意**: 上述 `useHaptic` 改造**不在 v3.1 本 PR 范围**, 实际合并时由其他 PR 收官。本指南仅描述设计意图。

---

## 6. 组件集成范式

### 6.1 MobileChatView 集成 (G-1 + G-2 全量集成)

```vue
<!-- views/mobile/chat/MobileChatView.vue (示意) -->
<template>
  <div ref="rootEl" class="mobile-chat-view">
    <!-- 顶部: PWA install banner (v3.0) -->
    <PWAInstallBanner v-if="!isStandalone" />

    <!-- 消息列表 (G-2: 左右滑 + 下拉刷新) -->
    <div ref="scrollEl" class="message-list">
      <PullToRefreshIndicator :distance="refreshDistance" :phase="refreshPhase" />
      <MessageBubble v-for="msg in messages" :key="msg.id" :message="msg" />
    </div>

    <!-- 底部: 输入框 (G-1: 长按录音 + 触觉反馈) -->
    <div class="chat-input-bar">
      <textarea v-model="text" placeholder="输入消息或长按 🎤 说话" />
      <VoiceInputButton
        v-model:text="text"
        :max-duration="60_000"
        :asr-engine="'auto'"
      />
      <button class="send-btn" @click="send">➤</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSwipeNavigation } from '@/composables/useSwipeNavigation'
import { usePullToRefresh } from '@/composables/usePullToRefresh'
import { useChatStore } from '@/stores/chat'
import VoiceInputButton from '@/components/mobile/VoiceInputButton.vue'
import PullToRefreshIndicator from '@/components/mobile/PullToRefreshIndicator.vue'

const rootEl = ref(null)
const scrollEl = ref(null)
const text = ref('')
const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()

// G-2: 左右滑切 tab (4 个主页面间)
const { currentSwipe, hasPrev, hasNext } = useSwipeNavigation({
  router,
  tabOrder: ['dashboard', 'chat', 'task', 'knowledge', 'workspace'],
  currentTab: 'chat',
})

// G-2: 下拉刷新 (重新拉取历史)
const {
  distance: refreshDistance,
  phase: refreshPhase,
  isRefreshing,
  bind: bindPull,
} = usePullToRefresh({
  onRefresh: async () => {
    await chatStore.fetchHistory({ sessionId: route.params.sid, force: true })
  },
})

onMounted(() => {
  bindPull(scrollEl.value)
})

function send() {
  if (!text.value.trim()) return
  chatStore.send(text.value)
  text.value = ''
}
</script>
```

### 6.2 MobileCommandPalette 集成 (G-1 局部)

```vue
<!-- views/mobile/MobileCommandPalette.vue (示意) -->
<template>
  <div class="command-palette">
    <input
      v-model="query"
      type="text"
      placeholder="搜索命令或长按 🎤 说话"
    />
    <VoiceInputButton
      v-model:text="query"
      :max-duration="30_000"
      :asr-engine="'sensevoice'"
      @result="runFuzzyMatch"
    />
    <ul v-if="results.length" class="results">
      <li v-for="r in results" :key="r.id" @click="execute(r)">
        {{ r.label }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useHaptic } from '@/composables/chat/useHaptic'

const query = ref('')
const results = ref([])
const haptic = useHaptic()

function runFuzzyMatch(text) {
  // 走搜索 store 的 fuzzy match
  results.value = searchStore.fuzzyMatch(text)
  haptic.tap()
}

function execute(cmd) {
  haptic.success()
  // 调起命令
}
</script>
```

### 6.3 4 个主页面集成 (G-2 横向滑 + 下拉)

```vue
<!-- views/mobile/MobileDashboard.vue (示意, 其他 3 个类似) -->
<template>
  <div ref="rootEl" class="mobile-dashboard">
    <SwipePageIndicator :direction="currentSwipe" />
    <div ref="scrollEl" class="dashboard-content">
      <PullToRefreshIndicator :distance="d" :phase="p" />
      <DashboardCards />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSwipeNavigation } from '@/composables/useSwipeNavigation'
import { usePullToRefresh } from '@/composables/usePullToRefresh'

const rootEl = ref(null)
const scrollEl = ref(null)
const route = useRoute()
const router = useRouter()

// G-2: 横向滑切 tab
useSwipeNavigation({
  router,
  tabOrder: ['dashboard', 'task', 'knowledge', 'workspace'],
  currentTab: 'dashboard',
  enabled: () => route.path === '/mobile/dashboard',
})

// G-2: 下拉刷新
const { distance: d, phase: p, bind } = usePullToRefresh({
  onRefresh: () => dashboardStore.refresh(),
})

onMounted(() => bind(scrollEl.value))
</script>
```

---

## 7. iOS Safari / Android Chrome 兼容性矩阵

| 能力 | iOS Safari | Android Chrome | HarmonyOS ArkWeb | 企业微信 X5 | 处理 |
|------|-----------|----------------|------------------|------------|------|
| `navigator.vibrate` | ❌ | ✅ | ✅ | ❌ | useHaptic 静默 try/catch |
| `MediaRecorder` webm;opus | ❌ | ✅ | ✅ | ⚠️ | MIME 探测链 |
| `MediaRecorder` mp4 | ✅ | ⚠️ | ⚠️ | ⚠️ | 探测链兜底 |
| `navigator.mediaDevices.getUserMedia` | ✅ (14.3+) | ✅ | ⚠️ (老内核超时) | ⚠️ (老内核超时) | 5s timeout 兜底 |
| `env(safe-area-inset-*)` | ✅ (11+) | ✅ | ✅ | ⚠️ | polyfill |
| `100dvh` 单位 | ✅ (15.4+) | ✅ | ✅ | ⚠️ | polyfill fallback 100vh |
| Background Sync API | ❌ (16.4+ stub) | ✅ (49+) | ❌ | ❌ | IndexedDB 兜底 |
| Web Share API | ✅ (12.1+) | ✅ (61+) | ⚠️ | ❌ | feature detect |
| `Notification` API | ✅ (16.4+) | ✅ | ⚠️ | ❌ | feature detect |
| `backdrop-filter` | ⚠️ 性能 | ✅ | ✅ | ⚠️ | 降级 background-color |
| Touch Events | ✅ | ✅ | ✅ | ✅ | 全部支持 |
| Standalone PWA 全屏 | ✅ | ✅ | ⚠️ | ❌ | feature detect |

> **详细策略**: 详见 `docs/mobile-ux-v3.1-user-guide.md` §3.3 + §4.3。

---

## 8. 测试与可观测性

### 8.1 单元测试 (Vitest)

```javascript
// tests/unit/composables/useMobileVoiceInput.test.js (示意)
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useMobileVoiceInput } from '@/composables/useMobileVoiceInput'

describe('useMobileVoiceInput', () => {
  beforeEach(() => {
    // mock MediaRecorder
    global.MediaRecorder = vi.fn().mockImplementation(() => ({
      start: vi.fn(),
      stop: vi.fn(),
      ondataavailable: null,
      onstop: null,
      mimeType: 'audio/webm;codecs=opus',
    }))
    global.MediaRecorder.isTypeSupported = vi.fn().mockReturnValue(true)
  })

  it('should request permission on start', async () => {
    const onError = vi.fn()
    const { start } = useMobileVoiceInput({ onError })
    const fakeTouch = { touches: [{ clientX: 100, clientY: 200 }] }
    start(fakeTouch)
    expect(/* permission requested */).toBe(true)
  })

  it('should cancel when swiping up beyond threshold', () => {
    const onCancel = vi.fn()
    const { start, move, end } = useMobileVoiceInput({
      onCancel,
      cancelThreshold: 80,
    })
    start({ touches: [{ clientX: 100, clientY: 200 }] })
    move({ touches: [{ clientX: 100, clientY: 50 }] })  // 上滑 150px
    end({ changedTouches: [{ clientX: 100, clientY: 50 }] })
    expect(onCancel).toHaveBeenCalled()
  })

  it('should call onResult on successful ASR', async () => {
    // mock fetch ASR success
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ text: '你好' }),
    })
    const onResult = vi.fn()
    const { start, end } = useMobileVoiceInput({ onResult })
    start({ touches: [{ clientX: 100, clientY: 200 }] })
    end({ changedTouches: [{ clientX: 100, clientY: 200 }] })
    await new Promise(r => setTimeout(r, 100))
    expect(onResult).toHaveBeenCalledWith('你好')
  })
})
```

### 8.2 E2E 测试 (Playwright)

```javascript
// tests/e2e/mobile-voice-input.spec.js (示意)
import { test, expect, devices } from '@playwright/test'

test.use({ ...devices['iPhone 13'] })

test('long press mic to record', async ({ page }) => {
  await page.goto('https://test.xiaoqi.lab/mobile/chat')
  await page.locator('.mic-btn').waitFor()

  // 模拟长按
  const micBtn = page.locator('.mic-btn')
  await micBtn.tap({ delay: 500, duration: 2000 })  // 按住 2s

  // 验证录音中状态
  await expect(micBtn).toHaveClass(/is-recording/)
  await expect(page.locator('.recording-indicator')).toBeVisible()

  // 验证 ASR 转写后文字填入
  await page.waitForFunction(
    () => document.querySelector('textarea').value.length > 0,
    { timeout: 5000 }
  )
  const text = await page.locator('textarea').inputValue()
  expect(text.length).toBeGreaterThan(0)
})
```

### 8.3 可观测性 (Metrics)

通过 `agent_traces` 表追踪 (沿用 v3.0 trace 体系):

```python
# 后端: app/api/asr.py 记录
{
  "event": "voice_input",
  "session_id": "xxx",
  "user_id": 1,
  "device": "iPhone 14 Pro",
  "browser": "Safari 17.2",
  "asr_engine": "sensevoice",
  "duration_ms": 2300,
  "transcribe_ms": 850,
  "success": true,
  "text_length": 12,
  "is_cancelled": false,
}
```

可在 `/admin/agent-traces` 端点按 `event=voice_input` 筛选, 监控:
- 录音成功率 (目标 ≥ 99%)
- ASR 平均耗时 (目标 < 1.5s)
- 取消率 (目标 5-15%, 过高说明 UX 有问题)
- 触觉反馈触发率 (iOS Safari 应为 0%, Android 应 ≥ 80%)

---

## 9. 性能与内存

### 9.1 性能预算

| 指标 | 预算 | 实测 (Chrome 119, Pixel 6) |
|------|------|---------------------------|
| 录音开始 (touchstart → 红色脉冲) | < 200ms | ~120ms |
| ASR 转写 (1s 录音) | < 1.5s | ~850ms |
| 长按取消响应 (touchmove → 气泡出现) | < 50ms | ~16ms |
| 下拉刷新 (touchend → spinner 显示) | < 100ms | ~32ms |
| 左右滑切页 (touchend → 页面切换动画开始) | < 50ms | ~16ms |
| useMobileVoiceInput 内存占用 | < 5MB | ~3.2MB |
| usePullToRefresh 内存占用 | < 1MB | ~0.3MB |

### 9.2 内存管理

#### 录音 Blob 释放

```javascript
// useMobileVoiceInput.js 内部 (示意)
async function stop() {
  if (mediaRecorder.state === 'recording') {
    mediaRecorder.stop()  // 触发 onstop
  }
}

mediaRecorder.onstop = async () => {
  const audioBlob = new Blob(chunks, { type: mimeType })
  // 上传后立即释放
  await uploadAudio(audioBlob)
  chunks.length = 0  // 清空 chunk 数组
  audioBlob = null    // 显式置 null, 帮助 GC
}
```

#### Touch Listener 清理

```javascript
// useSwipeGesture.js 内部 (已存在, 复用)
onBeforeUnmount(() => {
  if (target) {
    target.removeEventListener('touchstart', handleTouchStart)
    target.removeEventListener('touchmove', handleTouchMove)
    target.removeEventListener('touchend', handleTouchEnd)
  }
})
```

#### MediaStream Track 释放

```javascript
// useMobileVoiceInput.js 内部 (示意)
function cleanup() {
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => {
      track.stop()  // 释放麦克风 (重要! 否则麦克风指示灯一直亮)
    })
    mediaStream = null
  }
}
```

> **铁律**: **麦克风 track 必须显式 stop()**, 否则浏览器麦克风指示灯会一直亮, 用户隐私担忧 + 电量消耗。v3.0 录音机已实装, v3.1 语音输入必须复用此模式。

### 9.3 长时间录音的内存控制

单次 60s 录音在 Opus 32kbps 下约 240KB, 完全可控。**不要**让用户连续录音 5 分钟, 因为:
- ASR 服务端单请求 60s 硬上限
- 移动端内存峰值 ~5MB 仍可接受
- 但用户体验: 60s 还没说完 → 应该分段

v3.1 的解决方案: 60s 倒计时最后 5s, UI 提示 "还剩 5 秒, 请准备松手", 自动停止并转写。

---

## 附录 A: 触觉反馈 pattern 速查

| 场景 | pattern | 时长 | 备注 |
|------|---------|------|------|
| `tap` | `10` | 10ms | 短促轻敲 |
| `success` | `[10, 50, 10]` | 70ms | 三段轻震 |
| `warning` | `[30, 50, 30]` | 110ms | 三段中震 |
| `error` | `[50, 100, 50]` | 200ms | 三段重震 |
| 自定义长震 | `[200]` | 200ms | 紧急情况 |

## 附录 B: composable 文件路径速查

| composable | 路径 | 行数 | 状态 |
|----------|------|------|------|
| useMobileVoiceInput | `web/src/composables/useMobileVoiceInput.js` | ~280 | 待合并 |
| useSwipeNavigation | `web/src/composables/useSwipeNavigation.js` | ~120 | 待合并 |
| usePullToRefresh | `web/src/composables/usePullToRefresh.js` | ~200 | 待合并 |
| useHaptic | `web/src/composables/chat/useHaptic.js` | 47 | 已存在 |
| useSwipeGesture | `web/src/composables/useSwipeGesture.js` | ~120 | 已存在 (v2.28+) |
| useMobileSafeArea | `web/src/composables/useMobileSafeArea.ts` | ~80 | 已存在 (v3.0) |
| useIsMobile | `web/src/composables/useIsMobile.js` | ~30 | 已存在 |
| useMobileFab | `web/src/composables/useMobileFab.js` | ~50 | 已存在 (内含 vibrate 10ms) |

---

> **下一步**: 阅读 [Mobile UX v3.1 Changelog](./mobile-ux-v3.1-changelog.md) 了解 v3.0 → v3.1 增量详情。
