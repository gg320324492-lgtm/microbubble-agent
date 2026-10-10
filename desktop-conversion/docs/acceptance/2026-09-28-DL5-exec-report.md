# DL-5 执行报告：对话页整页滚动回归修复（2026-09-28）

## 结论

按工单三处约束修复完成，真实 Electron 渲染验收通过（截图 + 数值断言），`pnpm gate` 788/788 全绿。截图与数值存档于 `assets/2026-09-28-DL5/`。待总指挥复核。

## 基本信息

- **执行时父仓库 HEAD**：`d4bdf65ce`（工单基线 `c868898e2` 之后总指挥轨又推进 2 个 commit：`2b7745a76` ollama 原生 /api/chat 修复、`d4bdf65ce` 会议页 TabStrip 移除——均不触及本工单三组件，根因定位不受影响）
- **改动文件**（4 个，+11/−1）：
  1. `apps/desktop/src/renderer/src/views/AssistantView.vue` —— `.workbench` 加 `grid-template-rows: minmax(0, 1fr)`。理由：只定义列未定义行，唯一一行是隐式 auto 行，随 `.chat` 内容撑高（根因①）
  2. `apps/desktop/src/renderer/src/components/chat/ChatPanel.vue` —— `.chat` 加 `min-height: 0` 且 `1fr` → `minmax(0, 1fr)`。理由：grid item 的 `min-height: auto` 不可收缩到内容以下；且 `1fr` = `minmax(auto, 1fr)` 同样可被内容撑破（根因②）
  3. `apps/desktop/src/renderer/src/components/chat/SessionList.vue` —— `.sessions` 加 `min-height: 0`。理由：工单指定的防御性约束（已有 `overflow: hidden`）
  4. `apps/desktop/tests/unit/ui13-chat-follow.test.ts` —— 布局断言随新值更新（见下方「断言更新说明」）
- `.shell-main` **零改动**（红线遵守）；ChatPanel 滚动跟随 JS（`scrollToBottom`/`followOnNewMessage`）零改动；无新增依赖；工单三点之外**未加**任何额外 min-height/overflow 约束——三点已闭环（数值断言为证）

## 验收证据（assets/2026-09-28-DL5/）

**方法**：Playwright `_electron` 驱动真实 Electron 加载 `out/` 构建产物；`MNB_USER_DATA` 隔离档案（用户安装版数据零接触）；IPC 首启注册管理员（本地建号 UI 已退役但通道保留，断网可走）→ 新建会话 → 4 条长消息经本地回声灌出长对话（8 条消息）。先对修复前构建复现，再对修复后构建验收。

- **before-\***：修复前对用户安装版同源构建（c868898e2 产物）复现——滚到顶时 composer 在 y≈6806（900 视口之外约 6.8 屏）；`.shell-main` scrollHeight 6914 vs clientHeight 834（整页滚动）；`.chat-body` scrollHeight == clientHeight 6717（消息区不是滚动容器）；b-bottom 中 sessions top=-6040（被顶出视野成白板）——与用户真机截图现象一致
- **after-\***：修复后同 harness 三场景数值断言全过：
  - **a-top（滚到最顶）**：shellMain scrollHeight 834 == clientHeight 834（整页不滚）；chatBody 6717 > 637 内滚；composer top 726 / bottom 874 恒在视口；sessions 40–874 完整可见
  - **b-bottom（滚到最底）**：chatBody scrollTop 6080（消息区内滚到底），composer/sessions 位置不动
  - **c-chat-640（1100×640 矮窗口）**：shellMain 574==574 不外滚；chatBody 7893 > 377 内滚；composer 466–614 在视口内；sessions 完整。注：应用 `WINDOW_MIN_HEIGHT=640` 为强制下限，工单 ~600px 取可达的 640
  - **c-settings-640（M7 无回归）**：设置页 `.shell-main` scrollHeight 2386 > clientHeight 574，外滚正常
- **before-report.json / after-report.json**：完整数值断言

## 断言更新说明（透明度）

工单「修复要求 2」强制把 `.chat` 的 `grid-template-rows` 从 `auto 1fr auto` 改为 `auto minmax(0, 1fr) auto`，而 `ui13-chat-follow.test.ts:68` 的源码正则断言固化旧字面量 `/grid-template-rows:\s*auto\s+1fr\s+auto/`（该断言注释写明意图：三行网格 = 头部/可滚主体/输入区，输入区不随内容滚走）。两者字面冲突。处理：断言正则更新为 `/auto\s+minmax\(0,\s*1fr\)\s+auto/` + 注释同步，**意图零变化**，测试总数 788 守恒（该文件 7/7 独立复跑绿）。

## 附带观察（不构成顺手修复，仅报备）

- `ShellLayout.vue` 的 M7 注释「对话页 .workbench 显式 min-height:0 恰好填满，仍走内部独立滚动，不会出现双滚动条」在本次修复后**成为真命题**，注释无需改动（且红线禁止动 `.shell-main`）
- 无其它发现
