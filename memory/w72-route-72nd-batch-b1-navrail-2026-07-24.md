# W72 第 1 批 B-1：NavRail 基础组件

日期：2026-07-24
分支：`feat/w72nd-batch-b1-navrail-2026-07-24`
锚点范式：第 211 守恒

## 任务定位

本任务是子 plan ③ 的 W72 第一件，也是 B 路线串单链最上游。
B-3 顶栏 3-zone、B-4 跨端点与六主题、B-5 桌面六主题回归均以本组件为基础。
本批仅交付独立 NavRail 组件及其状态契约，不提前修改 ChatViewSSE 集成路径。

## 派工前真验证

- 指定 worktree 与分支正确，HEAD 为 `9e21fbfcd`。
- `git status --short` 为空，没有 partial diff 需要抢救提交。
- 仓库已有 v78 `NavRail.vue`，并非派工描述中的“尚未存在”。
- 既有版本只有固定 64px 图标栏，缺少 `/drive`、折叠态、移动抽屉和 useUiStore 集成。
- `SessionSidebar.vue` 已存在，末尾有一整段重复 dark-mode CSS。
- `useUiStore.js` 已有 thinkingMode，但没有 NavRail 折叠状态。

## 实施内容

### NavRail.vue

- 在既有组件基础上重构为 213 行独立组件，低于 350 行预算。
- 六类路由固定为 `/chat`、`/knowledge`、`/drive`、`/tasks`、`/meetings`、`/workspace`。
- desktop 宽度为 200px，折叠后为 60px。
- mobile 断点为 `< 768px`，使用 fixed drawer、scrim 和关闭按钮。
- 当前路由通过精确路径或子路径前缀判断，设置 `active` 与 `aria-current="page"`。
- 保留 keyboard focus、aria-label、title，并支持 `prefers-reduced-motion`。
- 图标使用 Element Plus 图标，不使用 emoji，避免跨平台字形和性能漂移。
- MNB 仪器铭牌作为唯一视觉识别点，其余全部保持 token 驱动。

### useUiStore.js

- 新增 `navRailCollapsed` 响应式状态。
- 新增 `toggleNavRail()` 与 `setNavRailCollapsed(value)` action。
- 使用 `mnb:ui:navRailCollapsed` localStorage key 持久化。
- 既有 thinkingMode、showThinking 和兼容 API 均未改变。

### SessionSidebar.vue

- 将两个硬编码 border 色替换为既有主题 token。
- transition 改用既有 duration token。
- 删除末尾重复的 34 行 dark-mode 覆盖，保留功能更完整的第一段。
- 不修改会话筛选、切换、同步、右键菜单、长按和滚动锚点逻辑。

## 六主题契约

覆盖矩阵：

1. orange light
2. orange dark
3. ocean light
4. ocean dark
5. forest light
6. forest dark

组件颜色全部取自 `--color-bg-card`、`--color-text-*`、`--color-primary`、
`--color-primary-bg`、`--color-border-light` 与 `--color-bg-hover`。
dark mode 覆盖放在非 scoped style 中，符合 v60-v67 跨组件主题纪律。

## 测试与验证

新增 `web/tests/e2e/nav-rail.spec.js`，四个场景：

1. desktop 渲染六个路由项。
2. `/knowledge` 高亮“知识库”并设置 aria-current。
3. 200px 与 60px 折叠切换，并验证 localStorage 持久化。
4. orange/ocean/forest × light/dark 六组合与 token 边界。

真跑结果：Vitest `1 file passed, 4 tests passed`。
typing import 检查：扫描 173 文件，0 错误。
PWA 安全构建：`npm run build:pwa` 成功，postbuild 完成。
构建生成的 `web/dist` 变化已恢复，未扩大提交范围。

## 串单链边界

- B-1 先合并后，B-3 才能把 NavRail 接入 ChatViewSSE 顶栏 3-zone。
- B-4 在 B-1 基础上做真实跨端点与主题整体验证。
- B-5 在 B-1 + B-4 后做桌面六主题最终回归。
- 本任务不越权提前改动上述下游文件。

## 守恒结论

W72 B-1 是本批唯一获批的 production code 例外范围之一，修改限定于
`web/src/components/chat/` 与 `web/src/stores/useUiStore.js`，另增独立测试。
未改后端、数据库、agent、老路由或部署配置。
锚点范式第 211 守恒。
