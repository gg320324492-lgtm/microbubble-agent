# W68 第 11 批 B-2：Mobile TabBar Drive 入口

> 日期：2026-07-24
> 任务：memoized-pondering-marble Mobile TabBar Drive 入口实施
> 锚点范式：第 137 守恒
> 范围：Mobile UX v3.2 + Drive v2，仅前端、测试、docs、memory、用户级 plan Status

## 1. 背景

`memoized-pondering-marble.md` 的主内容是 Drive FolderTree 中 trash / requests 特殊节点 inline 化。
该主内容已由 W68 第 5 批 Agent 2 在 commit `712393789` 实施。

W68 第 6 批 plans 深度审计与 W68 第 9 批 C-2 调研确认：
plan Status 段同时引用的 “Mobile TabBar Drive entry” 并没有真实落地。
现有 `web/src/components/mobile/TabBar.vue` 仍只有 5 项：

1. 首页
2. 听会
3. 对话
4. 任务
5. 我的

用户必须经侧栏或知识库旧入口进入网盘，高频移动端访问链路不够直接。
因此该 plan 的真实状态应为 PARTIAL_REGRESSION，直到本任务补齐入口、路由和测试后才能闭环为 COMPLETED。

## 2. 本次目标

本次只闭环 Mobile TabBar Drive 入口，不扩展 Drive 后端能力：

- TabBar 从 5 项扩展为 6 项。
- 网盘放在首页之后、听会之前。
- 新增 `/m-drive` 移动端路由。
- 路由复用既有 `MobileDriveView.vue`。
- MobileDashboard 快捷入口同步补网盘。
- 验证 375px 移动端 viewport 下 6 项不溢出。
- 新增 3 个 e2e 场景。
- 同步开发指南与用户级 plan Status。

## 3. 实施内容

### 3.1 TabBar 六项导航

文件：`web/src/components/mobile/TabBar.vue`

新增配置：

```js
{ name: 'drive', path: '/m-drive', title: '网盘', icon: 'folder' }
```

最终顺序固定为：

1. 首页
2. 网盘
3. 听会
4. 对话
5. 任务
6. 我的

Drive 是移动端高频业务入口，因此紧邻首页，而不是放到导航尾部。
继续复用既有 `nut-tabbar-item` 的 `v-for` 渲染，不创建新的 TabBar 组件分支。

### 3.2 active route 归一化

`/m-drive` 的路由名为 `MobileDrive`。
原 active 逻辑会将路由名转成 `mobiledrive`，无法匹配 item name `drive`。
因此对 `/m-drive` 显式返回 `drive`，保证网盘 tab 高亮。

该处理保持其余路由现有小写匹配规则不变，减少回归面。

### 3.3 六项紧凑响应式

NutUI TabBar 使用等分布局，但六项时仍需明确收缩契约：

- `.nut-tabbar-item` 设置 `min-width: 0`。
- `.tabbar-label` 设置 `display: block`。
- label 设置 `min-width: 0`。
- label 设置 `white-space: nowrap`。

这套约束防止默认 min-content 宽度将 tabbar 撑出 375px viewport。
不降低 44px 最小触控高度，不牺牲可点击性。

### 3.4 `/m-drive` 路由

文件：`web/src/router/index.js`

新增移动端专用路由：

- path：`/m-drive`
- name：`MobileDrive`
- component：`resolveMobileOnly('MobileDriveView')`
- meta：移动端专用 + Folder 图标

该路由复用现有 `MobileDriveView.vue`，不复制 Drive 页面和业务状态。
既有 `/drive` 双栈路由保留，桌面端行为不变。

### 3.5 MobileDashboard 同步

实际文件名为 `web/src/views/mobile/MobileDashboard.vue`，仓库不存在任务描述中的 `MobileDashboardView.vue`。
本任务按真实路径完成同步：

- 快捷入口从 5 项增加到 6 项。
- 新增“课题组网盘”，目标 `/m-drive`。
- 快捷网格从单行 5 列调整为 3 列 × 2 行。
- 使用 `minmax(0, 1fr)` 防止长标签撑破容器。

3 × 2 网格比 6 个窄列更适合 375px 移动端，且保持每项触控区域稳定。

## 4. 测试闭环

新增：`web/tests/e2e/mobile_tabbar_drive.spec.js`

覆盖 3 个场景：

1. 6 项 tab 全部显示，且顺序是首页 / 网盘 / 听会 / 对话 / 任务 / 我的。
2. 点击网盘后路由跳转 `/m-drive`，路由名为 `MobileDrive`。
3. 375 × 812 viewport 下维持 6 项单行结构，不产生横向溢出。

测试使用 Vitest + Vue Test Utils + memory router。
NutUI TabBar 只做轻量 stub，测试聚焦本次导航配置、点击行为和响应式 DOM 契约。

## 5. 文档与 plan 闭环

### 5.1 开发者指南

`docs/mobile-ux-v3.2-developer-guide.md` 新增 §5：

- 六项固定顺序。
- `/m-drive` 路由约定。
- active route 映射。
- 375px 响应式要求。
- Dashboard 同步要求。
- e2e 文件与 3 场景。

### 5.2 用户级 plan Status

`C:/Users/pc/.claude/plans/memoized-pondering-marble.md` Status 更新为：

- 主内容 FolderTree inline 化：commit `712393789`。
- 尾项 Mobile TabBar Drive entry：本任务完成。
- 6 项导航 + 路由 + 3/3 e2e PASS 后，plan 状态闭环为 COMPLETED。

用户级 plan 位于仓库外，不进入本仓库 commit；但已与本任务同步更新。

## 6. 0 production code 改动铁律

本任务属于已经批准的 Mobile UX v3.2 + Drive v2 独立前端扩展例外：

- 不修改 `app/` 后端业务代码。
- 不修改数据库模型和 alembic。
- 不修改老任务、会议、知识库 service。
- 不修改桌面 Drive component tree。
- 只调整移动端导航、移动端 dashboard、路由注册与测试文档。

因此维持“0 production code 改动铁律”的业务后端含义，不引入服务端生产逻辑变化。

## 7. 五条新铁律

### 铁律 1：TabBar 六项为上限，不得继续无审查扩容

375px 下 6 项已经接近底部主导航的信息密度上限。
新增第 7 个一级入口前必须先做用户频率评估，并优先合并低频入口到“我的”或抽屉。
不得为了功能可见性持续堆叠 TabBar item。

### 铁律 2：Drive 入口固定在首页后、听会前

移动网盘是课题组高频资源入口，排序必须体现使用频率。
固定顺序为首页 / 网盘 / 听会 / 对话 / 任务 / 我的。
后续改序必须同步产品决策、测试断言和开发指南，不能只改数组。

### 铁律 3：移动端 viewport 必须验证 375px 基线

移动导航改动不能只在桌面浏览器宽屏观察。
至少验证 375 × 812 viewport：无横向滚动、label 不换行、44px 触控高度保留、安全区 padding 正常。
更大 viewport 通过不代表最小移动 viewport 通过。

### 铁律 4：TabBar 导航改动必须跑专属 e2e

任何 item 新增、删除、改名、改序、改 path，都必须运行 `mobile_tabbar_drive.spec.js` 或其后继专属测试。
至少覆盖：完整数量与顺序、点击路由、最小 viewport。
仅靠 build 成功不能证明导航 UX 正确。

### 铁律 5：plans Status 必须在尾项落地后同步闭环

主内容完成但 Status 引用的附加入口未落地时，只能标 PARTIAL_REGRESSION，不能标 COMPLETED。
尾项实现并取得 commit + 测试物证后，必须同步用户级 plan Status 与 memory。
plan、git、grep、测试四者一致才算真实闭环。

## 8. 锚点范式第 137 守恒

本任务完成 memoized-pondering-marble 的最后一个真实缺口：

- 主内容已有 commit 物证。
- Mobile TabBar Drive 入口补齐。
- `/m-drive` 路由可达。
- MobileDashboard 入口同步。
- 3 场景自动化测试闭环。
- docs、memory、plan Status 同步。

锚点范式第 137 守恒，未引入后端或数据库回归。

## 9. 关键文件

仓库内 7 个文件：

1. `web/src/components/mobile/TabBar.vue`
2. `web/src/views/mobile/MobileDashboard.vue`
3. `web/src/router/index.js`
4. `web/tests/e2e/mobile_tabbar_drive.spec.js`
5. `docs/mobile-ux-v3.2-developer-guide.md`
6. `memory/w68-route-11-b2-tabbar-drive-2026-07-24.md`

仓库外 1 个用户级文件：

7. `C:/Users/pc/.claude/plans/memoized-pondering-marble.md`

任务清单按逻辑记为 8 项，是因为任务描述将 `MobileDashboardView.vue` 作为独立目标；仓库真实文件为 `MobileDashboard.vue`，没有另建重复 view。

## 10. 后续合并与部署

- 分支：`feat/mobile-tabbar-drive-entry-2026-07-24`
- 主指挥 merge，agent 不自行 merge。
- 纯前端改动，无 alembic 和后端容器重启步骤。
- 合并后按标准前端 build/deploy 链发布。
- 浏览器若仍显示旧 5 项，先硬刷新并确认 Service Worker 已更新到新 bundle。
