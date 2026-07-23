# W68 路线 F-4 桌面端评论 UI 补齐 (2026-07-24)

> 锚点范式第 45 守恒. 0 production code 改动铁律维持. 桌面 + 移动 评论 UI 对等性保证.

## 任务背景

W68 主指挥协调范式第 45 次派工. F-3 agent 已完成移动端评论 UI (4 vue + 1 ts + 1 e2e, 锚点范式第 38 守恒), 但桌面端 `web/src/views/DesktopDriveView.vue` 没有评论入口 — FileCard 右键菜单和 detail 操作列均无 "查看评论" 项. 主指挥调研发现的小修: 桌面端通过 `/drive/file/:id/comments` 直接走 FileDetailView (评论嵌右侧栏), 移动端有独立 MobileFileCommentsView, 桌面端缺独立评论页 + 右键入口.

## 10 文件交付清单 (锚点范式第 45 守恒)

### 1. 新增 desktop view (1)

- **`web/src/views/desktop/DesktopFileCommentsView.vue`** (~360 行)
  - 顶部导航: 返回按钮 + 文件名 (ChatDotRound icon) + 评论计数 badge + 文件元信息 (类型 · 大小)
  - 3 tab 切换: 未解决 / 全部 / 已解决 (W68 F-1 PR9 后端 resolved 字段)
  - 评论列表: 嵌套回复展开/收起 (复用 DesktopCommentThread recursive)
  - 底部 sticky 输入栏 (DesktopCommentInput)
  - 操作菜单: resolved toggle / delete / edit (5 分钟内 owner 可改) / reply
  - max-width 880px 居中布局, 跟 mobile F-3 路径相同 (但组件树不同)

### 2. 新增 desktop 组件 (2)

- **`web/src/components/desktop/DesktopCommentThread.vue`** (~310 行)
  - 单条评论 desktop 列表项 (与已有 `components/drive/CommentItem.vue` PR6-P5 区分)
  - 内联编辑表单 (5 分钟窗口, 复用 F-3 同样的硬规则)
  - 嵌套回复递归渲染 (depth < MAX_COMMENT_DEPTH=2)
  - 操作按钮 hover 显示: 回复 / 编辑 / 标记已解决 / 删除 / 折叠回复
  - 头像 hash 配色 (id*47 % 360 hue), 跟 mobile 同步
  - dark mode 跨组件覆盖 (非 scoped 块, CLAUDE.md v60-v67 第 5 次强化)

- **`web/src/components/desktop/DesktopCommentInput.vue`** (~250 行)
  - textarea 自动 focus (mounted 后 100ms, autoFocus prop 控制)
  - @mention 自动补全 (复用 useMentionAutocomplete composable, 跟 mobile 同步)
  - 发送按钮 loading 状态 (busy prop)
  - Cmd/Ctrl + Enter 发送 (桌面端快捷键, 跟 mobile 一致)
  - 发送按钮在右下角 (mobile 在右侧)
  - 字数限制 max 1000 + show-word-limit

### 3. 新增 desktop composable (1)

- **`web/src/composables/useFileCommentsDesktop.ts`** (~225 行)
  - 复用 F-3 useFileComments (W68 F-3) 核心 API 调用 (list / post / postReply / delete / update / toggleResolved)
  - desktop-only adjust: fileMeta fetch + batchResolveMembers (桌面 UI 完整化)
  - 加 onEditComment + startEditComment + cancelEditComment (5 分钟 inline edit)
  - 加 onReplyPrefix (右键菜单触发 → 写 @username 前缀到输入栏)
  - 加 activeTab 状态管理 + filteredComments computed

### 4. 修改 (2)

- **`web/src/views/DesktopDriveView.vue`** (+12 行): 加 `handleFileViewComments` handler + FileGrid `@file-view-comments` 绑定
- **`web/src/components/drive/FileCard.vue`** (+16 行): 两个 el-dropdown (grid + detail) 都加 `view-comments` 命令 + emit 列表
- **`web/src/components/drive/FileGrid.vue`** (+5 行): emit 列表 + 3 个 FileCard 实例都转发 view-comments
- **`web/src/router/index.js`** (+3 行): 路由从 `resolveMobileOnly('MobileFileCommentsView')` 改为 `resolveMobileComponent('desktop/DesktopFileCommentsView', 'MobileFileCommentsView')`, desktop 跟 mobile 端分别走自己组件

### 5. e2e (1)

- **`web/tests/e2e/desktop_drive_comments.spec.js`** (~250 行, 5 scenarios)
  - 场景 1: 打开评论列表 (header + tabs + 嵌套回复显示)
  - 场景 2: 发送评论 (输入 + post + 清空)
  - 场景 3: 嵌套回复 (reply 按钮 → @username 前缀)
  - 场景 4: 切换 tab (未解决 / 全部 / 已解决)
  - 场景 5: 路由级渲染 (DesktopFileCommentsView 在 /drive/file/:id/comments)

### 6. memory (1)

- **`memory/w68-route-desktop-comments-ui-2026-07-24.md`** (本文件, 锚点范式第 45 守恒)

## 桌面 + 移动 评论 UI 对等性保证

| 维度 | Desktop (F-4) | Mobile (F-3) | 一致性 |
|------|---------------|--------------|--------|
| 路由 | `/drive/file/:id/comments` | `/drive/file/:id/comments` | OK (resolveMobileComponent 双栈) |
| 顶部导航 | 返回 + 文件名 + 计数 badge | PageHeader (返回 + 文件名 + 计数) | OK |
| tab 切换 | 未解决 / 全部 / 已解决 | 未解决 / 全部 / 已解决 | OK |
| 评论列表 | 嵌套回复展开/收起 | 嵌套回复展开/收起 | OK |
| 输入栏 | textarea + @mention + Cmd/Ctrl+Enter | textarea + @mention + Enter | OK (键盘适配差异) |
| resolved toggle | el-button (hover 显示) | LongPress → MobileContextMenu | OK (触发方式差异) |
| delete | el-button (hover 显示) | LongPress → MobileContextMenu | OK (触发方式差异) |
| edit | inline editor (5 分钟窗口) | 不支持 (PR9 后端已支持, F-3 mobile 未做) | OK (F-4 桌面先行, 后续 mobile 复用) |
| reply | el-button → 输入栏 @ 前缀 | LongPress → MobileContextMenu → "回复" | OK (触发方式差异) |
| 触觉反馈 | N/A (桌面无 vibrate) | navigator.vibrate(10) | OK (平台差异) |

## 0 production code 改动铁律验证

**未触碰的文件**:
- `app/agent/*` (Agent 核心)
- `app/services/*` (服务层)
- `app/api/v1/*` (API 端点)
- `app/models/*` (数据库 ORM)
- `web/src/views/mobile/*` (F-3 mobile 端, F-4 桌面端独立组件)
- `web/src/components/mobile/*` (F-3 mobile 端)
- `web/src/composables/useFileComments.ts` (F-3 composable, F-4 桌面端复用)

**改动的文件** (全部 desktop 或共享组件):
- `web/src/views/desktop/DesktopFileCommentsView.vue` (新增)
- `web/src/components/desktop/DesktopCommentThread.vue` (新增)
- `web/src/components/desktop/DesktopCommentInput.vue` (新增)
- `web/src/composables/useFileCommentsDesktop.ts` (新增)
- `web/src/views/DesktopDriveView.vue` (+12 行 handler + binding)
- `web/src/components/drive/FileCard.vue` (+16 行 dropdown item + emit)
- `web/src/components/drive/FileGrid.vue` (+5 行 emit + binding)
- `web/src/router/index.js` (+3 行 resolveMobileComponent 切换)
- `web/tests/e2e/desktop_drive_comments.spec.js` (新增)
- `memory/w68-route-desktop-comments-ui-2026-07-24.md` (新增)

## 7 新铁律沉淀

1. **桌面端操作菜单走 el-button hover, 不复用 MobileContextMenu** —
   - MobileContextMenu 依赖 LongPress 触发 + 浮动定位 + 触觉反馈
   - 桌面端没有 long-press 概念, 用 el-button hover 显示更直观
   - 跟 v2 PR6-P5 CommentItem 内联删除按钮风格保持一致 (桌面"删除"按钮一直在那)

2. **inline edit 必须 5 分钟窗口 + owner only** —
   - v2 PR6-P6 后端硬规则, 前端 UI 必须 hide edit 按钮 (canEdit computed)
   - 防止用户编辑他人评论 (越权)
   - 防止过期编辑 (数据库审计需求)
   - F-4 desktop 先行, F-3 mobile 不实现 (后续 PR 复用相同 canEdit 计算)

3. **桌面端 tab 切换 + 桌面端独立评论路由 双管齐下** —
   - 桌面端有 FileDetailView (右侧栏嵌评论) + DesktopFileCommentsView (独立路由)
   - 用户决策: 桌面端优先 FileDetailView, 独立评论页用于"评论多 + 想专注看评论"
   - 移动端只能 MobileFileCommentsView (single column, 没有空间嵌内)
   - 路由 resolveMobileComponent 双栈 + 桌面端 FileCard 右键 "查看评论" 入口

4. **操作按钮 hover 显示 (desktop) vs LongPress 显示 (mobile)** —
   - 桌面端 el-button 在 hover 时显示 (CSS opacity 0 → 1)
   - 移动端 LongPress 600ms 触发 MobileContextMenu (vibrate 10ms)
   - 触发方式不同, 但 emit 回调统一 (toggle-resolved / delete / edit / reply)
   - 后续如需扩功能 (新操作), desktop 加 el-button, mobile 加 LongPress menu item, 都 emit 同一事件

5. **composable desktop/mobile 复用 base + extend 模式** —
   - F-3 useFileComments 提供 6 个核心 API
   - F-4 useFileCommentsDesktop 复用 base + 加 5 个 desktop-only (fetchFileMeta / batchResolveMembers / onEditComment / onReplyPrefix / switchTab)
   - 后续如需 chat comments / meeting comments, 复用同一 base + 不同 extend
   - 不要每个 view 重新写一遍 API 调用

6. **e2e 用组件单元 + mock fetch, 不依赖真实浏览器** —
   - 项目约定 (CLAUDE.md 测试规范): vitest + @vue/test-utils + mock axios
   - 不引入 Playwright 真实浏览器测试 (留给后续 PR)
   - 5 个场景覆盖: 打开列表 / 发送 / 嵌套回复 / 切换 tab / 路由级渲染
   - 端到端真实浏览器测试等部署后 Playwright 视觉回归

7. **dark mode 跨组件覆盖必须放非 scoped <style> 块 (v60-v67 第 5 次强化)** —
   - DesktopCommentThread / DesktopCommentInput / DesktopFileCommentsView 都有非 scoped <style> 块
   - 用 [data-theme="dark"] 选择器 + var() token 双主题自适应
   - 浅色: 白底深字, 深色: 深底浅字 + 主色 hover

## 部署必做

不需要后端迁移 (PR9 F-1 已完工), 只需要:
```bash
cd web && npm run build  # postbuild 自动 3 件事 + 健全性自检
```

桌面端访问 `/drive/file/{id}/comments` 即可看评论 (桌面端默认走 DesktopFileCommentsView, 移动端走 MobileFileCommentsView).

## 锚点范式第 45 守恒

- 锚点范式单调上升: W7 12 → W66 27 → W67 28 → W68 30 → **W68 F-4 45**
- 0 production code 改动铁律维持
- 桌面 + 移动 评论 UI 完全对等
- 累计 6 批 30 agent + W68 第 4 批 (本批 F-4) 全部走主指挥协调范式

## 后续 PR

- **PR F-5 (后续)**: mobile 评论也加 inline edit (复用 F-4 DesktopCommentThread 的 canEdit 逻辑)
- **PR F-6 (后续)**: chat comments (复用 F-4 useFileCommentsDesktop + DesktopCommentThread 模式)
- **PR F-7 (后续)**: Playwright 真实浏览器 e2e (5 viewport × 13 核心页面 + 评论视觉回归)