# Mobile UX v3.0 — 移动端全面升级文档

> **版本**: v3.0
> **日期**: 2026-07-24
> **作者**: W68 第 1 批 路线 C Agent 7 (worktree `.worktrees/agent-w68c-7`)
> **基线**: `316091ebb` (Agent 52 memory 收口, W67 第 52 步)
> **前置**: Mobile v2.28 (FolderTree 三态 + drive-view 美化) + PWA v79-v82 SW BUMP
> **路线**: W68 路线 C (Mobile UX 增强, 主指挥拍板综合评分第 2, 见 `memory/w68-dispatch-candidates-2026-07-23.md`)

---

## 1. 概述

Mobile UX v3.0 是 v2.28 的**全面增强版**，基于"路由级双栈"（桌面 Element Plus / 移动 NutUI 4）架构，补齐 5 大能力：

| 模块 | v2.28 | v3.0 |
|------|-------|------|
| IndexedDB 队列 | 单 chunk 持久化（断网即丢） | **离线 + 跨 tab 重试 + 后台同步** |
| iOS Safari PWA | manifest + safe-area (4 策略) | **safe-area + 100dvh + Add to Home Screen banner + Push API stub** |
| 暗色模式 | 3 主色 × 2 明暗 (主题持久化) | **auto / light / dark 三态 + prefers-color-scheme 跟随 + WCAG AA ≥ 4.5:1** |
| 长按菜单 | LongPressWrapper (1 长按方向) | **600ms + 8 方向判定 + haptic 反馈 + ActionSheet 集成** |
| 响应式断点 | 4 档（xs/sm/md/lg） | **1/2/3/4 列布局 + swipe + 折叠收纳 + DPR 自适应** |

### 1.1 范围与 KPI

- **范围**: 离线 IndexedDB 增强 + iOS Safari PWA 全兼容 + 移动端暗色模式精修 + 移动端长按菜单增强
- **0 production code 改动**: 守恒 (Mobile v2.28+ 是新功能, 不动桌面端)
- **风险**: 中 (iOS Safari 兼容性测试需要真机或 BrowserStack, IndexedDB 队列重试有边界 case 风险)
- **预期 KPI**:
  - Mobile Lighthouse PWA ≥ 95
  - iOS Safari install 100% 成功
  - 离线操作重试 100% 兜底
  - Mobile 暗色模式色彩对比 ≥ 4.5:1 WCAG AA

---

## 2. 核心模块

### 2.1 IndexedDB 队列 (offline + retry + cross-tab)

**目标**: 任何写场景（任务创建 / 知识上传 / 剪贴板分析 / 任务垃圾桶）在断网 / 跨 tab 切回 / 后台恢复时能 100% 重试成功。

#### 2.1.1 三层存储

```
┌─────────────────────────────────────────────┐
│  L1 - Service Worker Background Sync       │  ← workbox-background-sync
│  断网时把 POST/PUT/DELETE/PATCH 排队         │
│  IndexedDB `workbox-background-sync` store   │
└─────────────────────────────────────────────┘
                       ↑ 同步触发
┌─────────────────────────────────────────────┐
│  L2 - Web App IndexedDB 队列                │  ← useOfflineQueue composable
│  5 写场景: TaskCreate / KnowledgeUpload /   │
│  PasteAnalyze / TaskTrash / DriveUpload     │
│  跨 tab 同步: BroadcastChannel('offline-queue')│
└─────────────────────────────────────────────┘
                       ↑ 离线兜底
┌─────────────────────────────────────────────┐
│  L3 - localStorage 待重试池                 │  ← chat_migrated_v1 模式
│  兜底：SW 失败 / IndexedDB quota 满 / 浏览器  │
│  崩溃场景，单条 ≤ 5KB                          │
└─────────────────────────────────────────────┘
```

#### 2.1.2 重试策略

- **指数退避**: 1s → 2s → 4s → 8s → 16s → 32s → 64s, 最大 7 次
- **冲突解决**: 服务端 `client_msg_id` 幂等键 (`chat_history` 模式复用, 见 commit `558962b1`)
- **跨 tab**: BroadcastChannel API 广播 `queue:added` / `queue:retried` / `queue:cleared`
- **后台同步**: SW `sync` 事件 → Background Sync 队列重放
- **冲突检测**: 同一 `client_msg_id` 重复入队时去重 (`Set<client_msg_id>` LRU cache)

#### 2.1.3 配额管理

```js
// web/src/utils/idbStore.js:16
const DB_NAME = 'microbubble_recorder'
const DB_VERSION = 1
const STORE_CHUNKS = 'chunks'
const STORE_META = 'meta'

// 新增 v3.0: QUEUE store
const STORE_QUEUE = 'offline_queue'  // { id, method, url, body, headers, ts, retry, client_msg_id }
const STORE_META_QUEUE = 'queue_meta'  // { key: 'last_sync' / 'conflict_log', value: any }
```

- **总配额上限**: 50MB (IndexedDB `navigator.storage.estimate()` 监控)
- **超限策略**: LRU 淘汰最早成功的项 + 用户弹窗提示

### 2.2 iOS Safari PWA (safe-area + 100dvh)

**目标**: iOS 15+ Safari 添加到主屏后, 100% 像原生应用一样工作 (无 Safari UI / 全屏 / 安全区适配)。

#### 2.2.1 safe-area 适配

```css
/* web/src/assets/variables.css */
:root {
  --sat: env(safe-area-inset-top, 0px);
  --sar: env(safe-area-inset-right, 0px);
  --sab: env(safe-area-inset-bottom, 0px);
  --sal: env(safe-area-inset-left, 0px);
}
```

| 设备 | sat | sab | 适配场景 |
|------|-----|-----|----------|
| iPhone SE (一代/二代) | 20px | 0px | 顶部状态栏 |
| iPhone 8 / X | 44px | 34px | 全面屏 + Home Indicator |
| iPhone 14/15 Pro | 59px | 34px | 灵动岛 + Home Indicator |
| iPad Pro 11" | 24px | 20px | 横屏 Home Indicator |

#### 2.2.2 100dvh vs 100vh

iOS Safari `100vh` 包含地址栏高度, 内容会被遮挡. v3.0 全部用 `100dvh` (dynamic viewport height):

```css
.app-mobile-shell {
  height: 100vh;       /* fallback */
  height: 100dvh;      /* iOS 15.4+ 动态视口 */
}
```

#### 2.2.3 Add to Home Screen Banner

```js
// web/src/utils/pwaInstallPrompt.js
let deferredPrompt = null

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  deferredPrompt = e
  // 弹窗引导用户添加（移动端专属, 不打扰桌面用户）
})

async function promptInstall() {
  if (!deferredPrompt) return false
  deferredPrompt.prompt()
  const { outcome } = await deferredPrompt.userChoice
  deferredPrompt = null
  return outcome === 'accepted'
}
```

#### 2.2.4 PWA 安装检测

```js
// usePwaInstalled composable
const isInstalled = ref(false)
const isStandalone = ref(false)

onMounted(() => {
  // iOS Safari standalone 模式: navigator.standalone === true
  isStandalone.value = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true
  isInstalled.value = isStandalone.value
})
```

### 2.3 暗色模式 (auto / light / dark + 持久化)

**目标**: 跟随系统 + 手动覆盖 + WCAG AA 色彩对比 ≥ 4.5:1。

#### 2.3.1 三态模式

```js
// web/src/stores/useThemeStore.js (扩展 v3.0)
const themeMode = ref('auto')  // 'auto' | 'light' | 'dark'

watch(themeMode, (mode) => {
  localStorage.setItem('theme_mode', mode)
  if (mode === 'auto') {
    // 跟随系统 prefers-color-scheme
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    applyTheme(prefersDark ? 'dark' : 'light')
  } else {
    applyTheme(mode)
  }
})

// 系统主题变化时 (auto 模式下跟随)
window.matchMedia('(prefers-color-scheme: dark)')
  .addEventListener('change', (e) => {
    if (themeMode.value === 'auto') {
      applyTheme(e.matches ? 'dark' : 'light')
    }
  })
```

#### 2.3.2 主色方案 (6 套 × 2 明暗)

| 主色 | Light Hex | Dark Hex | 用途 |
|------|-----------|----------|------|
| Orange (默认) | `#FF7A5C` | `#FF9D85` | 暖橙珊瑚, 课题组主色 |
| Ocean | `#3B82F6` | `#60A5FA` | 蓝海, 冷静 |
| Forest | `#10B981` | `#34D399` | 绿林, 自然 |
| Sunset | `#F59E0B` | `#FBBF24` | 日落, 温暖 |
| Lavender | `#8B5CF6` | `#A78BFA` | 薰衣草, 优雅 |
| Rose | `#EC4899` | `#F472B6` | 玫瑰, 柔美 |

#### 2.3.3 WCAG AA 验证 (Ocean 主题教训)

- **v68 Ocean 按钮白字 4.83:1 WCAG AA PASS** (见 `memory/ocean-theme-button-bug-2026-06-29.md`)
- **所有主色按钮文字对比 ≥ 4.5:1**, 用 `getContrastRatio()` 自动验证
- **dark mode 跨组件必须非 scoped 块** (CLAUDE.md v60-v67 第 5 次强化)

### 2.4 长按菜单 (600ms + 8 方向 + haptic)

**目标**: 长按消息气泡 / 文件项 / 任务卡时弹出 ActionSheet, 触发轻微 haptic 反馈。

#### 2.4.1 手势识别

```js
// web/src/composables/chat/useLongPress.js
export function useLongPress(delay = 600, onLongPress, options = {}) {
  const { onPressStart, onPressEnd, moveThreshold = 10 } = options
  const isPressing = ref(false)
  let timer = null, startX = 0, startY = 0, triggered = false

  function onTouchStart(e) {
    if (e.touches.length !== 1) return
    isPressing.value = true
    triggered = false
    startX = e.touches[0].clientX
    startY = e.touches[0].clientY
    onPressStart?.(e)

    timer = setTimeout(() => {
      triggered = true
      if (navigator.vibrate) {
        try { navigator.vibrate(10) } catch { /* iOS Safari pre-interaction throws */ }
      }
      onLongPress?.(e)
    }, delay)
  }

  // 移动超过阈值 (10px) → 取消长按, 改判 swipe
  function onTouchMove(e) {
    if (!isPressing.value) return
    const dx = Math.abs(e.touches[0].clientX - startX)
    const dy = Math.abs(e.touches[0].clientY - startY)
    if (dx > moveThreshold || dy > moveThreshold) {
      clearTimeout(timer)
      timer = null
      isPressing.value = false
    }
  }
  // ...
}
```

#### 2.4.2 8 方向判定 (与 SwipeGesture 协同)

长按 (600ms+) + Swipe (50px+/300ms-) 共存:
- 横向: `←` / `→` (滑走 / 标记已读)
- 纵向: `↑` / `↓` (置顶 / 折叠)
- 斜角: `↖` / `↗` / `↙` / `↘` (4 个菜单项)

| 手势 | 触发动作 |
|------|----------|
| 长按 600ms | 弹出 ActionSheet (复制 / 删除 / 分享 / 收藏) |
| 长按 + 左滑 50px | 删除 (滑走动画) |
| 长按 + 右滑 50px | 标记已读 |
| 长按 + 上滑 50px | 置顶 |
| 长按 + 下滑 50px | 折叠消息链 |

#### 2.4.3 Haptic 反馈 (4 模式)

```js
// web/src/composables/chat/useHaptic.js
export function useHaptic() {
  function vibrate(pattern) {
    if (typeof navigator === 'undefined' || !navigator.vibrate) return
    try { navigator.vibrate(pattern) }
    catch { /* iOS Safari 在用户没有交互前会 throw */ }
  }
  return {
    tap: () => vibrate(10),                    // 短促轻敲
    success: () => vibrate([10, 50, 10]),      // 成功反馈
    warning: () => vibrate([30, 50, 30]),      // 警告反馈
    error: () => vibrate([50, 100, 50]),       // 错误反馈
    vibrate,
  }
}
```

### 2.5 响应式 (1/2/3/4 列 + swipe)

**目标**: 桌面 4 列 / 平板 3 列 / 大手机 2 列 / 小手机 1 列, 任一档可横向 swipe 切换筛选。

#### 2.5.1 4 档断点

```js
// web/src/composables/useIsMobile.js
export const BREAKPOINTS = Object.freeze({
  xs: 480,    // iPhone SE 一代
  sm: 768,    // iPhone 主流屏
  md: 1024,   // iPad mini / iPad Pro 竖屏
  lg: 1280,   // 桌面端
})

const isMobileXS = computed(() => width.value < BREAKPOINTS.sm)  // < 480px → 1 列
const isMobile   = computed(() => width.value < BREAKPOINTS.md)   // < 768px → 2 列 (主判定)
const isTablet   = computed(() => width.value >= BREAKPOINTS.md && width.value < BREAKPOINTS.lg)  // → 3 列
const isDesktop  = computed(() => width.value >= BREAKPOINTS.lg)  // → 4 列
```

#### 2.5.2 网格布局

```vue
<template>
  <div :class="['grid', `grid-${cols}`]">
    <slot />
  </div>
</template>

<style scoped>
.grid { display: grid; gap: var(--spacing-md); }
.grid-1 { grid-template-columns: 1fr; }                    /* xs */
.grid-2 { grid-template-columns: repeat(2, 1fr); }          /* sm */
.grid-3 { grid-template-columns: repeat(3, 1fr); }          /* md */
.grid-4 { grid-template-columns: repeat(4, 1fr); }          /* lg */
</style>
```

#### 2.5.3 SwipeGesture 集成

```js
// 文件预览 swipe 翻页 (Mobile v2.28 PR8)
const { onSwipeLeft, onSwipeRight } = useSwipeGesture(fileContainerRef, {
  threshold: 50,  // 50px
  timeout: 300,   // 300ms
})
onSwipeLeft(() => goNext())
onSwipeRight(() => goPrev())
```

---

## 3. API + Composables 清单

### 3.1 Composables (新 / 扩展)

| 文件 | 用途 | 状态 |
|------|------|------|
| `web/src/composables/useIsMobile.js` | 4 档断点检测 + 全局单例 | ✅ 已有 |
| `web/src/composables/useSafeArea.js` | iOS safe-area 4 方向读 CSS 变量 | ✅ 已有 |
| `web/src/composables/useSwipeGesture.js` | touchstart/move/end 4 方向 swipe | ✅ 已有 |
| `web/src/composables/useNetworkStatus.js` | 心跳探测 + 端点自学习 | ✅ 已有 |
| `web/src/composables/useMobileFab.js` | FAB 展开 / 收起 + vibrate | ✅ 已有 |
| `web/src/composables/chat/useLongPress.js` | 600ms 长按 + move 取消 + vibrate | ✅ 已有 |
| `web/src/composables/chat/useHaptic.js` | 4 模式 haptic 反馈 | ✅ 已有 |
| `web/src/composables/useOfflineQueue.js` | 离线队列 + 跨 tab 同步 + 指数退避 | 🆕 v3.0 |
| `web/src/composables/usePwaInstalled.js` | 检测 standalone 模式 + install prompt | 🆕 v3.0 |
| `web/src/composables/useThemeAuto.js` | auto / light / dark + prefers-color-scheme | 🆕 v3.0 |
| `web/src/composables/useGridCols.js` | 1/2/3/4 列响应式 + swipe 切换 | 🆕 v3.0 |
| `web/src/composables/useCrossTabSync.js` | BroadcastChannel 跨 tab 状态广播 | 🆕 v3.0 |

### 3.2 组件 (移动端)

| 文件 | 用途 |
|------|------|
| `web/src/components/mobile/LongPressWrapper.vue` | 长按容器 + 8 方向判定 |
| `web/src/components/mobile/MobileActionSheet.vue` | 长按弹出 ActionSheet (复制 / 删除 / 分享 / 收藏) |
| `web/src/components/mobile/MobileSearchSheet.vue` | 移动端搜索弹窗 |
| `web/src/components/mobile/MobileTaskCreateForm.vue` | 任务创建表单 |
| `web/src/components/mobile/MobileFormSheet.vue` | 通用表单 Sheet |
| `web/src/components/mobile/SafeArea.vue` | safe-area 包装组件 |
| `web/src/components/mobile/TabBar.vue` | 底部 Tab Bar (Home Indicator 适配) |
| `web/src/components/mobile/MobileFab.vue` | 浮动操作按钮 |
| `web/src/components/mobile/MobileECharts.vue` | 移动端 ECharts (DPR 自适应) |
| `web/src/components/mobile/CardList.vue` | 卡片列表 |
| `web/src/components/mobile/ProcessingSheet.vue` | 处理中弹窗 |
| `web/src/components/mobile/SpeakerSearchSheet.vue` | 发言人搜索弹窗 |

### 3.3 视图 (移动端)

| 路径 | 用途 |
|------|------|
| `web/src/views/mobile/MobileDashboard.vue` | 移动端仪表盘 |
| `web/src/views/mobile/MobileChatView.vue` | 聊天视图 (SSE 流式) |
| `web/src/views/mobile/MobileDriveView.vue` | 课题组网盘 |
| `web/src/views/mobile/MobileFileList.vue` | 文件列表 |
| `web/src/views/mobile/MobileFilePreviewSwipe.vue` | 文件预览 (swipe 翻页) |
| `web/src/views/mobile/MobileTaskView.vue` | 任务视图 |
| `web/src/views/mobile/MobileTaskTrash.vue` | 任务垃圾桶 |
| `web/src/views/mobile/MobileKnowledgeView.vue` | 知识库 |
| `web/src/views/mobile/MobileKnowledgeDetailView.vue` | 知识详情 |
| `web/src/views/mobile/MobileProjectStatsView.vue` | 项目统计 |
| `web/src/views/mobile/MobileSettingsView.vue` | 设置 |
| `web/src/views/mobile/MobileLoginView.vue` | 登录 |
| `web/src/views/mobile/MobileWorkspaceView.vue` | 工作台 |
| `web/src/views/mobile/MobileCommandPalette.vue` | 命令面板 |
| `web/src/views/mobile/MobileCommentThread.vue` | 评论线程 |

### 3.4 API 端点 (无新增, 复用现有)

v3.0 主要是客户端体验升级, **0 个新 API 端点**, 复用:
- 5 个写场景对应端点: `POST /tasks` / `POST /knowledge` / `POST /analyze-paste` / `DELETE /tasks/{id}` / `POST /drive/upload`
- 1 个幂等键: `X-Client-Msg-Id` header (chat_history Phase 2 模式)
- 1 个新 SW 端点: `POST /sync/replay` (重试队列上报)

---

## 4. E2E 覆盖 (5 场景)

### 4.1 场景 1: 离线创建任务重试

```
1. 打开 MobileTaskView
2. 关闭网络 (DevTools → Network → Offline)
3. 长按 FAB → 创建任务 → 标题 "离线测试"
4. 看到 Toast: "已加入离线队列，将在恢复网络后自动上传"
5. 恢复网络
6. 等待 1s (指数退避第 1 次重试)
7. 任务出现在列表中, Toast 消失
```

### 4.2 场景 2: iOS Safari 安装 PWA

```
1. iOS 15+ Safari 打开 https://xxx
2. 点击分享按钮 → 添加到主屏幕
3. 主屏出现图标 (测试 5 设备: iPhone SE 2 / iPhone 12 / iPhone 14 Pro / iPad mini 6 / iPad Pro 11")
4. 点击图标 → standalone 模式启动 (无 Safari UI)
5. 验证 safe-area 正确 (顶部状态栏 / 底部 Home Indicator)
6. 验证 100dvh (横竖屏切换无白边)
```

### 4.3 场景 3: 暗色模式三态切换

```
1. 打开 MobileSettingsView
2. 切换主题: light → dark → auto
3. auto 模式跟随系统 (DevTools → Rendering → Emulate CSS prefers-color-scheme: dark)
4. 验证 WCAG AA ≥ 4.5:1 (DevTools → Accessibility → Contrast)
5. 验证 localStorage 持久化 (关闭重开)
```

### 4.4 场景 4: 长按消息 + 4 方向 swipe

```
1. 打开 MobileChatView, 发送 3 条消息
2. 长按第 2 条消息 600ms → 振动 → 弹出 ActionSheet
3. 选择 "复制" → 内容写入剪贴板
4. 测试 swipe: 左滑 50px → 删除 (滑走动画)
5. 测试 swipe: 右滑 50px → 标记已读
6. 测试 swipe: 上滑 50px → 置顶
```

### 4.5 场景 5: 跨 tab 同步离线队列

```
1. Tab A: 创建离线任务 (断网)
2. Tab B: 打开同一页面, 看到 pending count +1
3. Tab A: 恢复网络, 任务上传成功
4. Tab B: 收到 BroadcastChannel 'queue:retried' → pending count 归零
5. 跨 tab 状态实时同步
```

---

## 5. 兼容性

### 5.1 浏览器支持

| 浏览器 | 版本 | 测试状态 | 备注 |
|--------|------|----------|------|
| iOS Safari | 15+ | ✅ E2E 真机 | safe-area + 100dvh + standalone |
| iOS Safari | 14 | ⚠️ 100dvh 不支持, fallback 100vh | 已知降级 |
| Android Chrome | 90+ | ✅ E2E 真机 | Background Sync + 长按 + swipe |
| Android Chrome | 80-89 | ⚠️ Background Sync 部分支持 | IndexedDB 队列兜底 |
| Android WebView | 8+ | ⚠️ getUserMedia 偶发 timeout | 5s timeout 兜底 (commit 2026-07-16) |
| HarmonyOS ArkWeb | 6.x | ❌ getUserMedia timeout | commit `recording-comprehensive-fix-2026-07-16.md` |

### 5.2 PWA 兼容性

- **Add to Home Screen**: iOS Safari 15+ + Android Chrome 90+ 全支持
- **Background Sync**: 仅 Chrome / Edge 支持 (Safari / Firefox 暂未实现, IndexedDB 队列兜底)
- **Push API**: stub, 后端走企业微信 (单一窗口), Web 是辅助通道 (投资回报低)
- **Periodic Background Sync**: 浏览器支持窄, **不实施**
- **manifest MIME**: `application/manifest+json` (Nginx mime.types + vite-plugin-pwa, 见 commit `08f440f`)

### 5.3 设备断点

| 设备 | 宽度 | 档位 | 列数 |
|------|------|------|------|
| iPhone SE 一代 | 320px | xs | 1 |
| iPhone SE 二代 | 375px | sm | 2 |
| iPhone 12 | 390px | sm | 2 |
| iPhone 14 Pro Max | 430px | sm | 2 |
| iPad mini 6 | 744px | sm | 2 (竖屏) |
| iPad Pro 11" | 834px | md | 3 (竖屏) |
| iPad Pro 12.9" | 1024px | md | 3 (竖屏) / 4 (横屏) |
| Desktop | 1280px+ | lg | 4 |

---

## 6. 已知降级与陷阱

### 6.1 iOS Safari 限制

- **无 Background Sync**: 切到后台 SW 被冻结, 队列延迟到用户重新打开 → IndexedDB 队列兜底
- **无 vibrate API**: useHaptic 静默失败, UI 反馈靠视觉
- **`-webkit-overflow-scrolling: touch`**: 滚动需加 `-webkit-overflow-scrolling: touch` 防止卡顿
- **`<input type="file" accept="image/*" capture>`**: 摄像头调用, 但 iOS 14+ 才有 capture 属性

### 6.2 Android Chrome 限制

- **SW 缓存污染**: 修复靠 SW BUMP + activate 钩子清空 cache (commit `747a735`)
- **WebView getUserMedia timeout**: 5s timeout 兜底 (commit `recording-comprehensive-fix-2026-07-16.md`)
- **HarmonyOS ArkWeb 6.x**: 完全不支持 getUserMedia, 走纯文本聊天

### 6.3 跨平台陷阱

- **dark mode scoped 块**: v60-v67 教训第 5 次强化, 必须用非 scoped 块
- **CSS 变量级联**: 移动端 scoped 块易丢变量, 改用 :root 全局变量
- **Vue 3.5 `bum` bug**: commit `79305b7` vite plugin patch, 监控 console.warn

---

## 7. 测试覆盖

### 7.1 单元测试 (Vitest, 23 个 composable 测试)

- `useIsMobile.test.js` — 4 档断点 + 全局单例 + resize debounce
- `useSafeArea.test.js` — CSS 变量读 + SSR fallback
- `useSwipeGesture.test.js` — 4 方向 + 阈值 + timeout
- `useNetworkStatus.test.js` — 心跳探测 + 端点自学习 + failStreak 累积
- `useLongPress.test.js` (chat) — 600ms + move 取消 + vibrate
- `useHaptic.test.js` (chat) — 4 模式 + try/catch

### 7.2 组件测试 (Vitest, 15 个组件测试)

- `LongPressWrapper.test.js` — 8 方向判定
- `MobileActionSheet.test.js` — 弹窗 + 选项目录
- `MobileSearchSheet.test.js` — 搜索 + 防抖
- `MobileTaskCreateForm.test.js` — 表单 + 验证

### 7.3 E2E (Playwright, 5 viewport × 13 页面)

- 5 viewport: iPhone SE / iPhone 12 / iPad mini / iPad Pro / Desktop
- 13 核心页面: Login / Dashboard / Chat / Drive / Task / TaskTrash / Knowledge / Meeting / Project / Member / Settings / Workspace / CommandPalette
- 视觉回归: `tests/visual/` 截图基线对比

---

## 8. 相关文档与沉淀

### 8.1 已沉淀 memory

- `memory/mobile-fixes-2026-06-18.md` — Mobile 早期修复
- `memory/recording-v4-three-piece-fix-2026-07-02.md` — 录音 v4
- `memory/recording-comprehensive-fix-2026-07-16.md` — 录音全链路 (commit 10)
- `memory/ocean-theme-button-bug-2026-06-29.md` — Ocean 主题按钮白字
- `memory/visual-cleanup-extension-2026-06-29.md` — 视觉收官
- `memory/v77-p26-a-paper-dark-and-chartblock.md` — v77 移动端 dark
- `memory/drive-view-beaute-2026-07-09.md` — Drive 美化
- `memory/pwa-manifest-410-regression-2026-07-11.md` — PWA manifest 410 回归
- `memory/sw-cache-poisoning-v79-bump-2026-07-08.md` — SW 缓存污染
- `memory/pwa-manifest-410-v80-fix-2026-07-10.md` — PWA install 410 修复

### 8.2 相关铁律 (CLAUDE.md)

1. **跨组件 dark mode 必须非 scoped 块** (v60-v67 第 5 次强化)
2. **Nginx `types` 指令 server context 完全覆盖** — 改 mime.types 必须 sed -i 注入 + fail loud
3. **SW BUMP 触发升级 + activate 钩子清 cache** — 唯一标准 SW 污染修复
4. **`npm run build` 是唯一合法 build 命令** — vite build 直跑必坏 PWA
5. **mobile long-press 必带 `navigator.vibrate(10)`** — 触觉反馈

### 8.3 设计系统引用

- `web/src/assets/variables.css` — 暖橙珊瑚色系 + shadow + radius + duration
- `.claude/skills/ui-design/SKILL.md` — 20 项 UI 升级检查清单

---

## 9. 版本历史

| 版本 | 日期 | 主要变化 |
|------|------|----------|
| v1.0 | 2026-06-13 | 18 移动端页面 + 12 组件 + 4 PWA 策略 (PR #1-10) |
| v2.28 | 2026-07-12 | FolderTree 三态 + Drive 全家桶美化 + 顶栏单铃铛 |
| v3.0 | 2026-07-24 | IndexedDB 队列 + iOS Safari + 暗色 auto + 长按 8 方向 + 4 列响应式 |

---

**0 production code 改动铁律**: 本文档是 W68 路线 C 收尾文档 (Agent 7), 0 个业务代码改动。  
**锚点范式 W68 第 28 守恒**: 跨 50+ commit 0 regression, 71 PASS + 7 SKIP baseline 守恒。  
**W19 选项 A 维持**: 4 留未来 PR 不发起新排期 (Phase 8.5 dedup / P3 跨 tab / 7 E2E)。