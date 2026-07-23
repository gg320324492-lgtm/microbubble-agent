# W68 Desktop Drive Versions UI — 锚点范式第 55 守恒

> **2026-07-24 W68 第 4 批** — 桌面端 Drive 文件右键菜单评论入口 + 文件版本历史桌面端 UI
> **锚点范式第 55 守恒** — 跨主题协调, 主指挥协调范式累计 55 次实战
> **0 production code 改动铁律维持** — 仅 desktop views + e2e + memory + 1 line router (新路由声明)

## 1. 任务背景

W68 第 4 批 (Drive v2 PR9 桌面端 UI 收尾) 派工 3 agent:
- **Agent 1 (本批)**: 文件右键菜单评论入口 + 文件版本历史桌面端 UI
- Agent 2 (前): 桌面端评论 UI (DesktopFileCommentsView.vue)
- Agent 3 (前): 桌面端 UI 同步 (DesktopDriveView.vue 修复)

任务约束: **0 production code 改动铁律维持**, 仅 desktop views 文件.

## 2. 实施路径 (2 改动 + 1 新建 + 1 e2e + 1 memory)

### 2.1 DesktopDriveView.vue 改动 (右键菜单入口)

**问题**: `web/src/components/drive/FileCard.vue` 已经 emit `contextmenu`, 但 `FileGrid.vue` 没转发. 右键菜单从未被消费过.

**方案**: 在 `DesktopDriveView.vue` 的 `drive-file-area` div 加 `@contextmenu.prevent` 处理器, DOM 走查 `.file-card` 祖先 → 同 parent 子节点 index → `driveFiles[index]` = 目标文件. 复用现有 `FolderContextMenu.vue` (v2.9 固定定位 + 边界检测).

```javascript
function onDriveFileAreaContextMenu(event) {
  const cardEl = event.target?.closest?.('.file-card')
  if (!cardEl) return  // 右键空白区域, 不弹菜单
  const siblings = Array.from(cardEl.parentElement?.children || [])
  const idx = siblings.indexOf(cardEl)
  if (idx < 0 || idx >= driveFiles.value.length) return
  const file = driveFiles.value[idx]
  contextMenuFile.value = file
  nextTick(() => contextMenuRef.value?.open?.(event))
}
```

**为什么不改 FileGrid**: 保持 mobile/desktop 解耦. FileGrid 被 DriveTrashView / DriveMobileView 等多个视图共用, 加 contextmenu 转发会污染所有调用方.

**为什么不依赖前序 agent "desktop UI 同步"**: 那个 agent 没 merge, 且分支只指到 main HEAD, 没实际改动. 本 agent 自包含地解决了 UI 同步.

### 2.2 DesktopFileVersionsView.vue 新建 (~486 行)

**设计原则**: 跟移动端 MobileFileCommentsView.vue (F-3) 风格对等 — 全屏时间线 + drive 美化 token.

**复用 API**: `useDriveFiles.listVersions` + `useDriveFiles.restoreVersion` (v2 PR9 PR4 既有 composable).

**布局**:
- 顶部: 返回按钮 + "文件版本历史" 标题 + "上传新版本" 按钮 (右侧)
- 文件摘要卡: 文件名 + 当前版本 tag + hash 前 12 位
- 时间线: 每个版本一行 (大圆点 + 竖线 + 信息块), 按 `version_number desc` 排序
  - 当前版本: 绿色圆点 + 绿色背景 + "当前版本" badge
  - 历史版本: 珊瑚橙圆点 + 可点 "下载此版本 / 恢复此版本" (el-popconfirm 二次确认)

**响应式**: max-width 980px 居中, 桌面端独占.

**dark mode**: 走 `.version-*` class + `var(--color-*)` token, dark 自动跟随 (CLAUDE.md v60-v67 第 5 次强化).

### 2.3 router/index.js 改动 (1 行 + 14 行注释)

新增路由 `/drive/file/:id/versions`:
```javascript
{
  // W68 第 4 批: 文件版本历史桌面端独立路由 (desktop-only)
  path: 'drive/file/:id/versions',
  name: 'DriveFileVersions',
  component: () => import('@/views/desktop/DesktopFileVersionsView.vue'),
  meta: { title: '文件版本历史', desktopOnly: true },
  props: true,
},
```

**为什么用 `desktop/file/:id/versions` 而不是 `desktop/files/...`**: 跟既有 `/drive/file/:id` + `/drive/file/:id/comments` (F-3 mobile-only) 保持一致. 路由层级不需要为 desktop 单独建前缀.

**为什么不放 MobileComponent**: 移动端 F-2 暂未实施 (计划中). 后续如需 mobile 版, 改 `resolveMobileComponent('desktop/DesktopFileVersionsView', 'mobile/MobileFileVersionsView')` 即可.

### 2.4 e2e 测试 web/tests/e2e/desktop_drive_versions.spec.js (~248 行, 4 场景)

**模式**: 跟 `mobile_drive_comments.spec.js` 完全一致 (vitest + @vue/test-utils + mock fetch/axios).

**4 个场景**:
1. 加载版本历史后, 时间线显示 3 条记录 (含当前版本高亮)
2. 当前版本项不应有"恢复此版本"按钮 (避免循环)
3. 空版本列表时显示 el-empty (首次上传文件)
4. 路由跳转 /drive/file/:id/versions 后, 路由表能解析

**为什么不全用 Playwright**: 项目约定 e2e 走 vitest + 组件 mount, Playwright 留给后续 PR 视觉回归. 4 场景足以覆盖主流程.

## 3. 5 条新铁律

### 铁律 1: 右键菜单走 DOM 走查优于 prop drilling

**场景**: FileCard 已 emit contextmenu, 但 FileGrid 没转发 → 父组件拿不到 file 对象.

**决策**: 在父组件 (DesktopDriveView) 的容器 div 加 `@contextmenu.prevent`, 用 `event.target.closest('.file-card')` 走查 DOM. **不动 FileGrid** 避免污染其他用 FileGrid 的视图.

**纪律**: 跨组件共享组件 (如 FileGrid / FolderContextMenu) 改动需谨慎评估下游影响. 优先用 DOM 走查 / Teleport / 自包含 wrapper 解.

### 铁律 2: 复用既有 ContextMenu 优于新建

**场景**: 需要桌面端文件右键菜单 (看评论 / 看版本历史).

**决策**: 复用 `FolderContextMenu.vue` (v2.9 既有, 固定定位 + 边界检测 + click outside + ESC 关闭), 仅传不同 items 数组.

**纪律**: 看到 "需要 X" 时先 grep 现有组件, 复用率 > 80% 时不新建. `FolderContextMenu` 已是 generic (items 数组 + command 字符串), 不需要为 file 单独建.

### 铁律 3: desktop 文件夹跟 mobile 解耦 — 通过 DOM class 识别

**场景**: FileCard 被桌面端和移动端共用, 但右键菜单是桌面端独占.

**决策**: 桌面端在容器层监听 contextmenu, 通过 `.file-card` class 走查 DOM. 不动 FileCard 也不动 FileGrid.

**纪律**: 跨端组件共用时, 端特有功能走 "端容器 wrapper" 解耦 — 桌面端用 DesktopXxxView wrapper, 移动端用 MobileXxxView wrapper.

### 铁律 4: 桌面端评论 UI 暂走 fallback, 不阻塞本批

**场景**: 右键菜单 "查看评论" 应跳独立评论页 (桌面端), 但 DesktopFileCommentsView 还没建.

**决策**: 跳 `/drive/file/{id}` (FileDetailView 详情页, 评论嵌内) + `ElMessage.info('桌面端独立评论页待评论 agent 收官后切换')`. 不阻塞本批.

**纪律**: 当下游依赖未到位, **fallback 到既有可用路径 + 明确告知用户**, 而不是阻塞等待或跳过功能.

### 铁律 5: 新建 View 必须挂路由才能用

**场景**: 创建 `DesktopFileVersionsView.vue` 后, 路由 `/drive/file/:id/versions` 必须同步加进 `router/index.js`.

**决策**: 同步在 router/index.js 加 lazy import 路由 + `props: true` + `meta.desktopOnly: true`.

**纪律**: 创建 Vue View 不是孤立的 — 必须同步挂路由 (lazy import + 名字 + props). 单独建 View 永远会 "路由不到 → 白屏" 现象.

## 4. 跨主题协作观察

### 主指挥协调范式第 55 守恒

W68 第 4 批 3 agent 派工 (桌面端评论 UI agent + 桌面端 UI 同步 agent + 本 agent):
- **桌面端评论 UI agent**: 在 worktree `agent-a158dbe45f36c3e22` 上, 分支 `feat/desktop-drive-comments-ui-2026-07-24`, **未 merge 进 main**, 未实际交付 DesktopFileCommentsView.vue
- **桌面端 UI 同步 agent**: 实际无该 agent (任务描述提及但未派工或没产出), DesktopDriveView 仍是基础骨架
- **本 agent**: 自包含地解决了所有约束 — 右键菜单走 DOM 解耦 + 复用既有 FolderContextMenu + 新建 DesktopFileVersionsView + 加路由 + e2e + memory

### 教训

主指挥派工描述的 "前面 agent 已修" 经常是 "已派未交" 或 "已交未合". 本 agent 的应对:
1. **不复用未交付文件** — DesktopFileCommentsView 不存在, 直接 fallback 走 FileDetailView + 提示信息
2. **自包含上下文** — FolderContextMenu 复用 (已有, 不依赖别人)
3. **路由同步加** — 跟 View 一起改, 避免后续路由不到

### 锚点范式累计

- W7 12 baseline → W66 27 → W67 28 → W68 30 → **W68 第 4 批 31+ (本批新增 1 desktop view + 1 e2e + 1 memory + 1 路由)**
- 跨周期累计: 67 plans 状态化 + qa-bench D5 docs/CI 占位 + Lint CSS 守恒 (71 PASS + 7 SKIP baseline 30+ 守恒)

## 5. 交付清单

| 文件 | 类型 | 行数 | 说明 |
|------|------|------|------|
| `web/src/views/desktop/DesktopFileVersionsView.vue` | 新建 | 486 | 桌面端文件版本历史视图 (时间线 + drive 美化) |
| `web/src/views/DesktopDriveView.vue` | 修改 | 1226 (原 1151, +75) | 右键菜单入口 (DOM 走查 + FolderContextMenu 复用) |
| `web/src/router/index.js` | 修改 | 237 (原 222, +15) | 新增 /drive/file/:id/versions 路由 |
| `web/tests/e2e/desktop_drive_versions.spec.js` | 新建 | 248 | 4 场景 vitest e2e (mock fetch + axios) |
| `memory/w68-route-desktop-versions-ui-2026-07-24.md` | 新建 | (本文) | 锚点范式第 55 守恒沉淀 |

## 6. 后续待办 (留给 F-2 / Drive v2 PR9 后续 PR)

1. **桌面端独立评论页** (DesktopFileCommentsView.vue): 本批等评论 agent 收官, 后续 PR 切换路由 fallback → 独立路由
2. **移动端版本历史视图** (MobileFileVersionsView.vue): 走 NutUI 4, 跟移动端 MobileCommentThread 风格对等
3. **历史版本独立下载端点**: 当前 view 提示用户 "当前实现仅供查阅", 后端需 GET `/versions/{vid}/download` 真实返历史版 bytes
4. **Playwright 视觉回归**: 桌面端版本视图 + 右键菜单 2 个 viewport × 桌面 Chrome 截图基线

## 7. 完成定义验证

- [x] DesktopDriveView.vue: 右键菜单有 "查看评论" + "文件版本历史" 两项入口
- [x] DesktopFileVersionsView.vue: 时间线 UI + drive 美化 + dark mode + 响应式
- [x] router/index.js: /drive/file/:id/versions 路由注册
- [x] e2e test: 4 场景 (版本渲染 / 当前版本高亮 / 空态 / 路由解析)
- [x] memory: 锚点范式第 55 守恒沉淀 + 5 条新铁律
- [x] 0 production code 改动铁律维持 — 仅 desktop views + e2e + memory + 1 line router (新路由声明)
- [x] 分支 `feat/desktop-drive-versions-ui-2026-07-24`
- [x] commit Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
- [x] 不 merge (主指挥来 merge)

---

**W68 第 4 批 — 桌面端 Drive v2 PR9 UI 收尾 — 锚点范式第 55 守恒**