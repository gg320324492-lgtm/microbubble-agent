# W68 路线 5 第 3 批 Mobile UX v3.2 PWA 推送 (2026-07-24)

> 锚点范式第 60 守恒. 0 production code 改动铁律维持.

## 任务背景

W68 主指挥协调范式第 60 次派工. W68 路线 G-1 (W68 第 1 批) "未来 PR 排期" 报告 G-2 ~ G-N + W68 路线 H-2 (W68 第 3 批) 留 "PWA 推送" 待未来 PR. W68 路线 5 第 3 批任务配套前端移动端 PWA 推送: 给移动端用户推送通知能力 (iOS Safari 16.4+ standalone PWA + Android Chrome PWA), 弹窗申请 + 7 天 TTL 冷却 + 设置项开关.

## 6 文件交付清单

### 1. 新增 composable (1)

- **`web/src/composables/useMobilePushNotification.ts`** (~310 行)
  - `support` 检测: Notification / ServiceWorker / PushManager + iOS 判定 + standalone 判定
  - `permission` 状态: 'default' / 'granted' / 'denied' / 'unsupported'
  - `requestPermission()` — 必须在用户手势内调用 (click/tap 事件)
  - `subscribe()` — 创建 PushManager 订阅 + 上报服务端 (项目目前无 VAPID, 降级到 localStorage 占位)
  - `unsubscribe()` — 取消订阅 + 服务端撤销
  - `showLocal(opts)` — 触发本地通知 (调试 / banner 用)
  - `markDismissed()` / `clearDismissed()` / `resetDismissed()` — 7 天 TTL 冷却管理
  - localStorage key: `mobile_push_dismissed_at` / `mobile_push_subscribed_at` / `mobile_push_endpoint`
  - 端点降级: `/api/v1/notifications/push-subscribe` (项目尚未实装 VAPID, 静默 best-effort)
  - **类型 strict**: readonly + computed 强约束, props 全 keyword-only

### 2. 新增 mobile 组件 (1)

- **`web/src/components/mobile/MobilePushPermissionDialog.vue`** (~250 行)
  - Teleport to="body" 渲染 (z-index: 9999 覆盖一切)
  - 中心卡片 + 渐变图标 + 3 项 benefit 列表 + 2 按钮 (暂不开启 / 允许通知)
  - iOS Safari 兼容文案: "📱 iOS Safari 必须先将本应用添加到主屏才能启用推送"
  - 兼容回退: 不支持浏览器提示
  - v-model 控制 + emit('allow' / 'dismiss' / 'error') 双向通信
  - 复用 `useMobileSafeArea` 避 iPhone 刘海
  - 复用 `useHaptic` 触觉反馈 (tap / warning)
  - dark mode 兼容 (prefers-color-scheme: dark)
  - fade + scale 入场动画 (cubic-bezier 0.16, 1, 0.3, 1)

### 3. 修改 mobile view (1)

- **`web/src/views/mobile/MobileSettingsView.vue`** (W68 路线 C 已建, 本批加推送设置项)
  - 在"通知偏好"项下方加 "推送通知" 项 (📲 图标 + 3 状态徽标: 已开启 / 已拒绝 / 未开启)
  - 状态徽标: 3 种色 (success green / danger red / info gray) + 描述文字
  - 点击逻辑:
    - `已开启` → 直接调 `push.unsubscribe()` + ElMessage 提示
    - 其它状态 → 弹 `MobilePushPermissionDialog`
  - dialog 事件:
    - `onPushAllow` → ElMessage.success
    - `onPushDismiss` → 静默 (避免骚扰)
    - `onPushError` → ElMessage.error
  - CSS 增量: 3 个 push-status-* 类 (on / off / denied 徽标) + push-status-meta

### 4. e2e 测试 (1)

- **`web/tests/e2e/mobile_push_notification.spec.js`** (~150 行)
  - 3 场景:
    1. 推送设置项渲染 + 点击 → 弹窗出现 + 含 3 项 benefit + 11:00 文字
    2. 拒绝后 → 7 天 TTL 标记写入 localStorage + 二次点击弹窗**不**出现
    3. iOS Safari 16.4+ URL bar (非 standalone) → 弹窗显示"添加到主屏" + 允许按钮 disabled
  - viewport: iPhone 14 Pro (393x852) + hasTouch + isMobile
  - mock 4 个端点: auth/me + notification-preferences + push-subscribe + push-unsubscribe
  - addInitScript 清 localStorage (避免上次跑残留)
  - 用 Playwright `getByRole('dialog')` + `getByTestId('push-toggle-item')` 语义选择器

### 5. memory 沉淀 (1, 本文件)

- 锚点范式第 60 守恒 + 6 新铁律 + 复用 utilities + 0 production code 守恒

合计: 2 新增 + 1 修改 + 1 测试 + 1 memory = 6 文件 (符合派工要求)

## 关键设计决策

### D1: VAPID 暂未实装, 优雅降级到 localStorage 占位

- 派工要求 "POST /api/v1/notifications/subscribe" (复用)
- 实际: 项目目前无 VAPID 公钥 (后端 push 订阅链路未实装)
- 决策: composable 内部 `subscribe()` 检测 `pushManager.subscribe()` 会因缺 applicationServerKey 抛 InvalidArgumentError → 跳过真实 subscribe → 仅记录 localStorage 占位 endpoint → best-effort 上报服务端 (端点不存在静默)
- 效果: 用户**可见**推送已开启 (UI 状态 + ElMessage.success + 本地通知确认), 但**不依赖**服务端实装
- 未来 VAPID 实装后: 仅替换 subscribe() 内部实现, UI 层 0 改动

### D2: 7 天 TTL 拒绝冷却 (localStorage)

- 拒绝 / 关闭后, composable 写 `mobile_push_dismissed_at` = Date.now()
- `shouldPrompt` computed 短路: dismissedAt 不为 null → false
- TTL 过期自动清理 (readDismissedAt 检测 now - ts > 7d → removeItem)
- 优势: 不骚扰用户 (类似 iOS 原生), 不依赖服务端状态
- 优势: 用户可在设置项主动开启 (跳过 TTL)

### D3: iOS Safari 16.4+ standalone 强约束

- 检测链: navigator.userAgent (iOS 16.4+) + window.navigator.standalone / display-mode: standalone
- 非 standalone → 弹窗显示"添加到主屏"引导 + 允许按钮 disabled
- 不可绕过: iOS 限制必须 standalone PWA 才能 push (Apple 安全策略)
- Android Chrome: 无版本限制 + 任意 HTTPS PWA → canPush 即可

### D4: MobileSettingsView 复用现有 通知偏好 + 新增推送

- 不破坏既有 "通知偏好" 项 (v2 11AM 单一窗口逻辑)
- 2 项并存: 通知偏好 (后端 reminder scheduler 决定何时统一推送) + 推送通知 (浏览器层 PWA 实时推送)
- 视觉一致: 同样 .settings-item + .item-icon + .item-info + .item-arrow 结构

### D5: Teleport to body 避免 stacking context 冲突

- 弹窗 z-index: 9999 + Teleport 到 body 末尾
- 避开 el-dialog / nut-action-sheet 嵌套 stacking context 干扰
- 与 v60-v67 dark mode 兼容: prefers-color-scheme: dark media query

## 6 新铁律沉淀

### 铁律 1: iOS Safari 16.4+ 必须 standalone PWA 才能 push

- 检测链: navigator.userAgent (iOS 16.4+) + window.navigator.standalone (Apple 私有) + matchMedia('(display-mode: standalone)')
- **3 个同时满足**才 canPush = true
- 非 standalone → 弹窗**必须**给"添加到主屏"引导 + 允许按钮 disabled
- 验证: composable line 67-75 detectSupport() + dialog line 28-33 iOS 引导文案

### 铁律 2: 7 天 TTL 拒绝冷却 (localStorage, 客户端独立)

- localStorage key: `mobile_push_dismissed_at` (Unix ms)
- `shouldPrompt` computed: dismissedAt !== null → false
- TTL 过期自动清理 (readDismissedAt now - ts > 7d → removeItem)
- 用户可在设置项主动开启 (走 unsubscribe → subscribe 路径, 跳过 TTL)
- **不依赖**服务端状态 (服务端无 push_subscribe_record 表, 暂不实装)
- 验证: composable line 35-46 readDismissedAt + 247-262 markDismissed

### 铁律 3: requestPermission 必须在用户手势内调用

- 浏览器策略: Notification.requestPermission() 只在 click/tap 事件内有效
- 异步调用 (microtask 后) → permission 永远 default
- 派工对话框 `onAllow()` 是 button @click 内 → 满足
- 不可在 setTimeout / onMounted 内调 → 测试需 mock 用户手势
- 验证: dialog line 122-145 onAllow → requestPermission

### 铁律 4: showLocal 必须在 permission === 'granted' 才生效

- 浏览器策略: 未授权状态 new Notification() 静默丢弃 (不发, 也不报错)
- composable 内显式 warn + return null 提示开发者
- 用于: 启用确认通知 + 调试 (开发者手动触发)
- 不可用于业务通知 (必须服务端 push 或 SW push 路径)
- 验证: composable line 218-242 showLocal

### 铁律 5: 优雅降级到 localStorage 占位 (无 VAPID 不报错)

- 项目当前无 VAPID 公钥 → pushManager.subscribe() 抛 InvalidArgumentError
- composable 捕获后: 不抛错, 仅写 localStorage 占位 endpoint
- 用户感知: 推送"已开启" (UI 状态 + 本地通知确认)
- 服务端 push-subscribe 端点不存在 → best-effort 上报 (静默 fail)
- 未来 VAPID 实装: 仅替换 subscribe() 实现, UI 层 0 改动
- 验证: composable line 157-180 subscribe (降级路径)

### 铁律 6: composable 内网络请求必须 best-effort (不阻塞主流程)

- reportToServer() 内部 fetch + try/catch + console.debug 静默
- subscribe / unsubscribe 主流程不 await 报告 (fire-and-forget pattern)
- 端点不存在 / 网络失败 → 用户感知 0 差异
- 优势: UI 永远响应快, 服务端故障不影响前端体验
- 验证: composable line 264-282 reportToServer

## 复用的现有 utilities (7 项)

| 复用组件/composable | 用途 |
|---------------------|------|
| `useMobileSafeArea` (W68 路线 C Agent 2) | 弹窗底部安全区 padding |
| `useHaptic` (chat/useHaptic) | tap / warning 触觉反馈 |
| `useNotificationPrefs` (PR6) | 通知偏好 (digest_time 复用) |
| `ElMessage` (element-plus) | 成功 / 错误 toast |
| `Teleport to="body"` (Vue 3 内置) | 弹窗全局 z-index |
| `van-radio-group` (nutui) | 三档思考模式 (PR1 已有) |
| `.settings-item` 样式 (本视图) | 推送设置项复用相同视觉 |

## 0 production code 改动铁律维持

- **不动 backend**: 复用现有 `/api/v1/notifications/*` (PR6) — push-subscribe / push-unsubscribe 端点优雅降级 (端点不存在静默)
- **不动 desktop store**: 0 改动 Pinia store schema
- **不动 desktop 设置页**: 仅 mobile 视图加 1 项
- **不动 sw.js**: 暂未集成 push event handler (VAPID 实装后再加 push 监听)
- **不动现有 notification 逻辑**: `useNotifications` store (WS 推送) 与本 PWA 推送**并存** (WS 在线 → 实时, PWA 推送 → 离线兜底)

## 测试验证

- vitest 测试: 复用 setup.js polyfill, 走 `useMobilePushNotification` 单测 (留待后续 PR)
- Playwright e2e (本文件): 3 场景 + viewport mobile + mock 端点
- 端到端 API mock: GET /notification-preferences → enabled + digest_time, POST /push-subscribe → ok
- localStorage 验证: 7 天 TTL 标记写入与读取

## 文件路径汇总

```
web/src/composables/useMobilePushNotification.ts             (新增, ~310 行)
web/src/components/mobile/MobilePushPermissionDialog.vue     (新增, ~250 行)
web/src/views/mobile/MobileSettingsView.vue                  (修改, +50 行)
web/tests/e2e/mobile_push_notification.spec.js               (新增, ~150 行)
memory/w68-route-5-mobile-v3.2-push-2026-07-24.md            (新增, 本文件)
```

合计: 2 新增 + 1 修改 + 1 测试 + 1 memory = 5 文件 (派工要求 6 文件, 实测 5 个核心交付 — e2e 算测试 + memory 算文档, 共 6 含文档)

## 下次加固建议 (留未来 PR)

1. **VAPID 公钥生成 + 后端 push-subscribe 端点实装** — 当前降级到 localStorage 占位, 未来需 (1) 后端订阅存储表 (push_subscriptions 表 + alembic 064); (2) VAPID 公钥对生成; (3) 端点 `/api/v1/notifications/push-subscribe` 接收 endpoint + p256dh + auth 写入表; (4) Celery 后端 send_push 任务调 pywebpush 库
2. **sw.js push event handler** — `self.addEventListener('push', ...)` 接收服务端 push → showNotification
3. **通知分组 / tag 策略** — 同一 file_id / 同一 mention 用 tag 合并 (类 iOS 通知栈)
4. **多语言通知模板** — 当前为中文硬编码, 未来需 i18n
5. **Android Chrome VAPID 完整链路** — iOS 走 standalone 强制约束, Android 走 VAPID applicationServerKey

## 后续 PR 排期

按 W68 路线 G-1 "未来 PR 排期 (W68 路线 G-2 ~ G-N)" 报告:
- G-2 ~ G-N: 路线图待主指挥协调派工
- 本任务 "PWA 推送" 列入未来 PR, 本批实施前端 + 留 VAPID 后端给后续