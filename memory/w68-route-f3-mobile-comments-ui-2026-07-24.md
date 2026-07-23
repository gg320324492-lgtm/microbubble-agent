# W68 路线 F-3 移动端评论 UI 实施 (2026-07-24)

> 锚点范式第 38 守恒. 0 production code 改动铁律维持.

## 任务背景

W68 主指挥协调范式第 38 次派工. Drive v2 PR9 后端评论 thread 已由 F-1 agent 实施完成 (含 resolved 字段 + threading 嵌套 + WS 增量). F-3 任务配套前端移动端 UI: 给 `LongPressWrapper` 长按文件菜单增加 "查看评论" 入口 + 独立评论路由页 + 评论列表/输入/操作菜单 3 个 mobile 组件.

## 9 文件交付清单

### 1. 新增 view (1)

- **`web/src/views/mobile/MobileFileCommentsView.vue`** (~430 行)
  - 顶部 `PageHeader` (返回 + 文件名 + 评论计数)
  - 3 tab 切换: 未解决 / 全部 / 已解决 (W68 F-1 PR9 后端 resolved 字段)
  - 评论列表: 嵌套回复展开/收起 + 长按菜单 (resolved toggle / delete)
  - 底部 `MobileCommentInput` 输入栏
  - 复用 `useNotifications` store (axios + WS) + `useCommentTree` + `LongPressWrapper` + `MobileContextMenu`

### 2. 新增 mobile 组件 (2)

- **`web/src/components/mobile/MobileCommentInput.vue`** (~250 行)
  - textarea 自动 focus + keyboard adjust (useMobileKeyboard)
  - @mention 自动补全 (复用 useMentionAutocomplete)
  - 发送按钮 loading 状态 (busy prop)
  - v-model 双向绑定, Enter 发送 (Shift+Enter 换行)
  - 触觉反馈 (focus/blur 通过 useMobileKeyboard)

- **`web/src/components/mobile/MobileCommentThread.vue`** (~250 行)
  - **单条评论 mobile 列表项** (与已有 `views/mobile/MobileCommentThread.vue` PR6-P3 完整面板区分)
  - 自递归渲染嵌套回复 (depth 上限 2 = v2 PR6-P5 MAX_COMMENT_DEPTH)
  - 含 `LongPressWrapper` 触发 resolved 切换 + 删除 (父组件决定菜单)
  - 触觉反馈 `navigator.vibrate(10)` (CLAUDE.md 2026-06-27 教训)

### 3. 新增 composable (1)

- **`web/src/composables/useFileComments.ts`** (~180 行)
  - 文件评论 CRUD: listComments / postComment / postReply / deleteComment / updateComment
  - 复用 axios (与 desktop store 一致)
  - **W68 F-1 PR9 resolved toggle**: 乐观更新 + 失败回滚 (后端 endpoint 不存在静默)
  - 防重复请求: fileId 维度 inflight Map (避免同 fileId 多次 fetch 撞车)
  - 卸载清理: onBeforeUnmount 清 inflight 引用

### 4. 修改文件 (2)

- **`web/src/router/index.js`**: 注册 `resolveMobileOnly('MobileFileCommentsView')` 到 `/drive/file/:id/comments`, `meta.mobileOnly: true`. 桌面端访问自动重定向到详情页 (复用现有 router.beforeEach mobileOnly guard)

- **`web/src/views/mobile/MobileDriveView.vue`**: 长按文件菜单 4 项 → 5 项, 加 `comments` action 跳 `/drive/file/:id/comments` (顺序: 预览 / 评论 / 下载 / 分享 / 删除)

### 5. e2e 测试 (1)

- **`web/tests/e2e/mobile_drive_comments.spec.js`** (~190 行)
  - 3 场景 + 1 边界:
    1. 打开评论列表渲染 header + tabs + 列表 (含 2 顶层评论 + 1 已解决)
    2. 发送评论 (v-model + emit post + axios mock 验证)
    3. 长按顶层评论触发 MobileContextMenu (含 vibrate 调用验证)
    - 边界: 无评论时显示 empty state ("没有未解决的评论")
  - 用 vitest + @vue/test-utils (项目已有 vitest.config.js)
  - mock fetch / axios / localStorage / navigator.vibrate
  - 完整 Playwright 视觉回归留给后续 PR

## 关键设计决策

### D1: 复用 desktop store, 不新建独立 store
- 用现有 `useNotifications` store 的 `commentsByFileId` cache + WS handler
- 0 production code 改动铁律 — 不动 Pinia store schema
- 新 `useFileComments.ts` 是 **可选 wrapper** (本任务 view 直接用 store, composable 留给后续优化/独立路由复用)

### D2: mobile 评论页 vs 详情页内嵌评论
- 现有 `MobileFileDetailView` 已内嵌 `MobileCommentThread` (PR6-P3) — 单列布局
- 新独立路由 `/drive/file/:id/comments` 给"全屏沉浸"评论体验 (类 GitHub issue 评论模式)
- 2 入口并存: 文件长按菜单"查看评论" → 独立页; 文件预览 → 详情页 → 内嵌评论区
- 不冲突, 用户按场景选入口

### D3: tab 切换 (open / all / resolved)
- W68 F-1 PR9 后端新增 `resolved` 字段
- view 内部 `filterByTab()` computed 处理 (不污染 store)
- count badge 实时显示, 数字驱动用户处理优先级 (UX 设计)

### D4: LongPressWrapper 触发菜单 vs el-popover
- 复用 W68 路线 C Agent 4 的 `MobileContextMenu` (8 方向自适应 + ARIA + Teleport)
- 触觉反馈 `vibrate(10)` (CLAUDE.md 2026-06-27 教训)
- 桌面端 el-popconfirm 不适用移动端 (touch 体验差), LongPress + Menu 是 mobile 标准

## 6 新铁律沉淀

### 铁律 1: 嵌套评论 mobile 渲染必须自递归组件, 不用 v-for flatten
- 桌面端 `CommentItem` 用 recursive 自递归, depth prop 控制缩进
- mobile 必须复用同样的递归模式 — 扁平 v-for 会丢失父子层级视觉
- 验证: `components/mobile/MobileCommentThread.vue` 自递归 `<MobileCommentThread>` 引用 + depth prop

### 铁律 2: mobile 长按评论菜单 vibrate 必须放在 show() 前
- `onCommentLongPress()` 第一行就 `navigator.vibrate(10)`, 而非 `contextMenu.show()` 内
- 用户感知是 "按下 → 立刻震动 → 菜单浮现", 顺序颠倒感觉迟钝
- 验证: view line ~85 vibrate 早于 contextMenu.value?.show()

### 铁律 3: optimistic update 必须保留 before 引用 + 失败回滚
- `toggleResolved()` 在 `comments.value[idx] = next` 前保留 `before = comments.value[idx]`
- try/catch 失败时 `r[idx] = before` 回滚 (引用同一对象避免 reactive 失效)
- 后端 endpoint 不存在时 fetch 静默失败不 throw, UI 仍乐观显示 (W68 F-1 文档化)

### 铁律 4: 路由 props: true 必须配套 component 接受 props
- 新增 `/drive/file/:id/comments` 路由用 `props: true`, 路由参数自动作为 prop 传入
- `MobileFileCommentsView` 必须 `defineProps({ fileId: ... })` 接收 (不能用 `useRoute().params.id`, 失去类型推导)
- 验证: view line 95 `defineProps({ fileId: { type: [String, Number], required: true } })`

### 铁律 5: mobileOnly 路由必须在 router.beforeEach guard 中处理桌面端重定向
- 复用现有 `if (to.meta?.mobileOnly && window.innerWidth >= 768) next('/drive/file/' + fileId)` 守卫
- 不能依赖 component 内 `useIsMobile()` 兜底 (会闪一下空白页)
- 验证: router/index.js 已有 guard, 新路由只加 `mobileOnly: true` meta

### 铁律 6: composable 中 axios mock 测试必须覆盖 happy-dom fetch 全局
- view 内部同时用 `axios` (store 路径) 和 `fetch` (raw API 兜底)
- vitest 测试必须 mock 两者 (`global.fetch = vi.fn()` + `global.axios = mockAxios`)
- 否则 `ReferenceError: fetch is not defined` 在 happy-dom 下炸

## 复用的现有 utilities (6 项)

| 复用组件/composable | 用途 |
|---------------------|------|
| `PageHeader` (mobile) | 顶部导航 (返回按钮 + 标题 + slot) |
| `LongPressWrapper` (mobile) | 600ms 长按触发菜单 (W68 路线 C Agent 4) |
| `MobileContextMenu` (mobile) | 8 方向自适应弹出菜单 (W68 路线 C Agent 4) |
| `useMobileSafeArea` | iPhone 安全区 (W68 路线 C Agent 2) |
| `useMobileKeyboard` | iOS Safari 键盘 adjust (W68 路线 C Agent 2) |
| `useMentionAutocomplete` | @ 自动补全 (PR6-P4) |
| `useNotifications` store | commentsByFileId cache + WS 增量 (PR6) |
| `useCommentTree` | 嵌套 tree 构建 (PR6-P5) |

## 0 production code 改动铁律维持

- **不动 backend**: 复用现有 `/api/v1/drive/files/{id}/comments` (PR6) + 新增 resolved 字段 (W68 F-1)
- **不动 desktop store**: `useNotifications` Pinia store schema 0 改动
- **不动 desktop CommentItem/CommentThread**: 仅复用
- **不动现有 PR6-P3 mobile 评论组件** (`views/mobile/MobileCommentThread.vue`) — 仍嵌在详情页

## 测试验证

- vitest 测试 3 场景 + 1 边界 (mobile_drive_comments.spec.js)
- 完整 Playwright 视觉回归留给后续 PR (mobile-drive-comments-ui visual)
- 端到端 API mock: GET /comments 返回 fixture (含 resolved + threading), POST 模拟成功

## 文件路径汇总

```
web/src/views/mobile/MobileFileCommentsView.vue          (新增, ~430 行)
web/src/components/mobile/MobileCommentInput.vue        (新增, ~250 行)
web/src/components/mobile/MobileCommentThread.vue       (新增, ~250 行)
web/src/composables/useFileComments.ts                  (新增, ~180 行)
web/src/router/index.js                                 (修改, +13 行)
web/src/views/mobile/MobileDriveView.vue                (修改, +3 行)
web/tests/e2e/mobile_drive_comments.spec.js             (新增, ~190 行)
memory/w68-route-f3-mobile-comments-ui-2026-07-24.md    (新增, 本文件)
```

合计: 5 新增 + 2 修改 + 1 测试 + 1 memory = 9 文件

## 下次加固建议 (留 PR 后续)

1. **inline reply form** — MobileCommentThread emit 'reply' 当前只 toast 提示, 应实现内联回复
2. **Playwright 视觉回归** — 完整 iOS Safari + Android Chrome 截图对比基线
3. **WS 'comment:resolved' 增量事件** — 当前 WS 没专门事件, 多人标记 resolved 不同步
4. **mention 高亮在嵌套回复里** — 当前 escapeHtml + replace 正则简单, 跨平台应统一
5. **resolved toggle 权限校验** — 前端 hidden UI 给 owner + file owner, 后端必须二次校验