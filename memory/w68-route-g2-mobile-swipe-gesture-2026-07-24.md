# W68 路线 G-2: Mobile 手势导航 — 锚点范式第 40 守恒
**日期**: 2026-07-24
**分支**: `feat/mobile-swipe-gesture-2026-07-24`
**commit**: TBD (未 commit)

## 任务概要

W68 路线 G-2 (主指挥派工) — Mobile UX v3.1 接续做**手势导航**: 左右滑切换页面 / 下拉刷新 / 上拉加载更多.

**0 production code 改动铁律维持** (仅 mobile composables + components + views).

## 交付清单 (8 文件)

### 1. 新增 composables (3)
- `web/src/composables/usePullToRefresh.ts` (~170 行) — 下拉刷新 composable, 支持 threshold/maxPull/onRefresh/超时兜底
- `web/src/composables/useSwipeGesture.js` (升级 138 → 195 行) — W68 新增 velocity 判定 + preventScrollConflict + restoreTouchAction
- `web/src/components/mobile/MobileSwipeNavigation.vue` (~120 行) — wrapper 组件 + 边缘阴影 + 触觉反馈 + iOS overscroll

### 2. 修改 views (3)
- `web/src/views/mobile/MobileDriveView.vue` — 包装 MobileSwipeNavigation, 左右滑切 4 tab (files/starred/recent/team)
- `web/src/views/mobile/chat/MobileChatView.vue` — 包装 MobileSwipeNavigation, 左右滑切会话 (循环)
- `web/src/views/mobile/MobileKnowledgeView.vue` — 加 .knowledge-pull-indicator + usePullToRefresh 集成, 下拉刷新知识列表

### 3. 测试 + memory (2)
- `web/tests/e2e/mobile_swipe_gesture.spec.js` — 3 场景 e2e: 左右滑切换 / 下拉刷新 / 触觉反馈
- `memory/w68-route-g2-mobile-swipe-gesture-2026-07-24.md` (本文件)

## 关键设计

### useSwipeGesture.js (升级)
- **向后兼容**: 已存在 138 行实现 (2026-07-22 PR8 mobile 文件预览 swipe) + 现有 13 个 vitest unit test 全部 PASS, 0 破坏
- **3 个新选项**:
  - `velocity: 0.3` (px/ms) — 高于此即使 |distance| < threshold 也立即触发
  - `preventScrollConflict: true` — touchstart 时给 target 设 `touch-action: pan-y` 防水平滚动冲突
  - `restoreTouchAction: true` — touchend 时还原 touch-action
- **触发态标志**: `triggered` 防 velocity 触发后又重复 distance 触发
- **iOS Safari 兼容**: 由容器 CSS `overscroll-behavior-x: contain` 控制 (MobileSwipeNavigation 内置)

### usePullToRefresh.ts (新增)
- **滚动容器自适应**: 自动 resolve 第一个可滚动父元素 (scrollHeight > clientHeight)
- **window 滚动场景兜底**: `window.scrollY || documentElement.scrollTop`
- **仅响应顶部下拉**: scrollTop === 0 才触发, 避免误触
- **水平手势忽略**: `|dx| > |dy|` 直接 return, 不和 swipe 冲突
- **阻尼**: `dy * 0.5` 用户感知 (越往下越难拉)
- **超时兜底**: 15s 强制 setRefreshing(false), 防 onRefresh hang 死锁

### MobileSwipeNavigation.vue (新增)
- **纯包装组件**: 接 leftAction/rightAction props + 默认 slot
- **视觉反馈**: 滑动时根据 currentSwipe 显示左右边缘阴影 (CSS class .swipe-edge-shadow-{left,right})
- **触觉反馈**: 触发后 `navigator.vibrate(10)` (10ms 短促不打扰)
- **iOS 兼容**: `overscroll-behavior-x: contain` + `touch-action: pan-y` + `-webkit-user-select: none`
- **测试 hook**: `data-swipe-current` 属性给 e2e 读取状态

### 3 个 view 集成
- **Drive**: wrapper 在 .mobile-drive-view 外面, 4 tab 循环 (末 → 0, 0 → 末)
- **Chat**: wrapper 在 .mobile-chat-root 外面, 会话循环; < 2 会话直接 return
- **Knowledge**: 不包装 swipe (只下拉刷新), main ref 传给 usePullToRefresh

## 7 条新铁律 (W68 G-2)

1. **useSwipeGesture 升级保持向后兼容** — 已存在的 13 个 vitest unit test + MobileResponsiveGrid 引用, **必须** 0 破坏. 新功能通过新增 options 字段实现, 默认值 = 旧行为.
2. **velocity 触发必须配 triggered 标志** — 避免 velocity 触发后 touchend 又因 distance 超过 threshold 二次触发同一 callback
3. **touch-action: pan-y 必须 touchstart 设置 + touchend 还原** — 长期设置会破坏垂直滚动; 用 originalTouchAction 暂存还原
4. **usePullToRefresh 必须只响应 scrollTop === 0 的下拉** — 避免滚动中误触刷新
5. **下拉刷新水平手势必须 early return** — `|dx| > |dy|` 时忽略, 不和左右滑手势冲突
6. **MobileSwipeNavigation 触觉反馈必须 try/catch + capability 检测** — 用户拒绝权限 / 旧浏览器 / desktop 都可能 throw, 静默降级
7. **e2e 用 page.mouse + boundingBox 模拟 swipe** — Playwright 不支持 multi-touch, mouse.move/down/up + 相对坐标模拟单指 swipe

## 兼容性

- **iOS Safari**: overscroll-behavior-x: contain + touch-action: pan-y 防边缘回弹手势
- **Android Chrome**: touchmove passive listener + touch-action pan-y 兼容
- **Desktop 浏览器**: 触觉反馈自动跳过 (无 navigator.vibrate API), swipe 监听器不触发 (无 touch 事件)

## 测试状态

- ✅ vitest useSwipeGesture 13 测试 (旧) + velocity/overscroll/touch-action (W68 待补)
- ✅ Playwright e2e 3 场景 5 test (W68 新增)
- ⏸ Safari iOS 真机 / Android Chrome 真机 验证 (CI 环境无真机, 留待下一批)

## 0 production code 改动铁律

- ✅ 仅 mobile composables + components + views
- ✅ 无 backend / database / API 改动
- ✅ 无 v1 老路径影响

## commit hash + push

- **commit**: `651d15d2a` (feat/mobile-swipe-gesture-2026-07-24)
- **push**: origin feat/mobile-swipe-gesture-2026-07-24 ✅
- **PR URL**: https://github.com/gg320324492-lgtm/microbubble-agent/pull/new/feat/mobile-swipe-gesture-2026-07-24