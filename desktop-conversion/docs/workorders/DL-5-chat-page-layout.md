# 工单 DL-5：对话页整页滚动回归——输入框不常驻 + 侧栏被顶出视野

> 签发：总指挥 · 2026-09-28 ｜ 优先级：**高（主战场对话页可用性缺陷，用户真机截图实锤）**
> 基线：HEAD `c868898e2` / **788 条测试**（typecheck 0 / build 0 / `pnpm gate` 全绿）——以接单时实测为准，报告注明实际 HEAD
> 用户真机：安装版 v1.3.0（`D:\Users\pc\AppData\Local\Programs\MicroBubbleWorkbench`，构建自 c868898e2）

## 项目背景

你在「小气科研工作台」桌面端项目（Electron + electron-vite + Vue3 + TS strict，工作区 `E:\microbubble-agent\apps\desktop`）。测试基线 788 条全绿（`pnpm gate` = test && typecheck && build 串联，**失败即停，绝不带失败提交**）。

**本机环境陷阱（必读，历代踩过）**：
- 这台机器 `AppData\Local` 实际在 **D 盘**（`D:\Users\pc\AppData\Local`），C 盘同名路径是空壳
- 本机沙箱会让 vitest 的 SSR 临时文件间歇性 EPERM → 本地测试计数会波动；跑到的全过即可提交，「全绿」结论以 CI 为准
- `node -e` 内嵌探测会静默失败——需要探测时用**临时脚本文件**
- 改仓库文件一律用 **Edit 工具**（Python replace 曾静默不生效三次）；提交链用 `&&` 串联（曾两次因 `;` 绕过门禁）

## 缺陷现象（用户真机截图）

AI 助手对话页，会话消息一长：
1. **输入框（composer）不常驻底部**——往上翻历史时输入框跟着内容滚出视野
2. **左侧会话列表也被顶出视野**——滚动后侧栏区域只剩一片空白（grid 拉伸出的空壳）
3. 即整个 `.shell-main` 变成了一个**大滚动文档**，而不是「侧栏固定 + 消息流内滚 + 输入框常驻」

## 根因（总指挥已定位于源码级，接单后核对并修复）

高度约束链在 `.workbench` 处断裂：

- `ShellLayout.vue` 的 `.shell-main`：`display:flex; flex-direction:column; overflow-y:auto`（M7 随车必办①，为列表型视图设——**不得改动**，设置页外滚依赖它）
- `AssistantView.vue` 的 `.workbench`：`flex:1; display:grid; grid-template-columns: 248px 1fr; min-height:0` ——**只定义了列，没有 `grid-template-rows`**，唯一一行是隐式 `auto` 行 → 行高随内容撑高
- `ChatPanel.vue` 的 `.chat`：`.workbench` 里的 grid item，`min-width:0` 但**没有 `min-height:0`**（min-height:auto → 不可收缩到内容以下），且自身 `grid-template-rows: auto 1fr auto` 的 `1fr` = `minmax(auto,1fr)` 同样可被内容撑破
- 链式结果：消息一长 → `.chat` 内容高 → 隐式行撑高 → `.workbench` 内容超出视口 → 外层 `.shell-main` 整页滚动。侧栏 `.sessions` 被 grid 拉伸到同样高，内容只在顶部，滚下去就是白板

M7 注释里「对话页 .workbench 显式 min-height:0 恰好填满，仍走内部独立滚动」是**从未成立的假设**——当时验收只看了设置页。

## 修复要求

1. `AssistantView.vue` `.workbench`：加 `grid-template-rows: minmax(0, 1fr);`
2. `ChatPanel.vue` `.chat`：加 `min-height: 0;`，并把 `grid-template-rows: auto 1fr auto` 改为 `auto minmax(0, 1fr) auto`
3. `SessionList.vue` `.sessions`：加 `min-height: 0;`（防御性；它已有 `overflow:hidden`）
4. **禁止改动 `.shell-main`**（M7 行为不许回归）；若核对中发现还需其它 min-height/overflow 约束才能闭环，可以加，但每处在报告里说明理由
5. 修完确认：消息区唯一滚动容器是 `.chat-body`；composer 恒在视口底部；会话列表内滚不受消息量影响

## 验收证据（缺一退回）

1. **真实渲染截图**（Electron 窗口或 gate 浏览器渲染均可，禁止手工拼图）：长对话状态下 (a) 滚到最顶——输入框仍在底部、会话列表仍可见；(b) 滚到最底；(c) 矮窗口（高度 ~600px）——设置页仍可外滚（M7 无回归）、对话页仅消息区内滚
2. `pnpm gate` 全绿；测试计数与基线一致或增加（jsdom 无法断言布局，不强求新增布局断言，但既有断言不许掉）
3. 报告注明实际 HEAD、改动文件清单、每处约束的理由

## 范围红线

- 只动上述三个组件的布局 CSS 与必要约束；**不碰** ChatPanel 的滚动跟随 JS（`scrollToBottom`/`followOnNewMessage`）、不碰业务逻辑、不碰 `.shell-main`
- 发现任何「顺手修复」的诱惑（无关样式、重构）一律不做，另报总指挥
