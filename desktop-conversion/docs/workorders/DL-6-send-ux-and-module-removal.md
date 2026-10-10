# 工单 DL-6：发送 UX 修复（乐观上屏）+ 下架「实验 ELN」「稿件」两模块

> 签发：总指挥 · 2026-09-29 ｜ 优先级：**高（A 为真实模型时代主路径体验缺陷；B 为用户产品裁决）**
> 基线：`v1.3.0`（74140c7bb 已发布）/ 本单交付后走 v1.3.1 小列车——接单时以 `git log -1 -- apps/desktop` 实测 HEAD 为准，报告注明
> 用户真机：v1.3.0 安装版（D 盘），**真实 MiMo 模型已接通**（截图实证，非回声）

## 项目背景

「小气科研工作台」桌面端（Electron + electron-vite + Vue3 + TS strict，工作区 `E:\microbubble-agent\apps\desktop`）。测试基线 788 条全绿（`pnpm gate` = test && typecheck && build 串联，失败即停，绝不带失败提交）。

**本机环境陷阱（必读，历代踩过）**：
- `AppData\Local` 实际在 **D 盘**（`D:\Users\pc\AppData\Local`），C 盘同名路径是空壳
- 本机沙箱 vitest SSR 临时文件间歇 EPERM → 本地测试计数会波动；跑到的全过即可提交，全绿结论以 CI 为准
- `node -e` 内嵌探测会静默失败——探测用临时脚本文件
- 改仓库文件一律用 **Edit 工具**（Python replace 曾静默不生效）；提交链用 `&&` 串联
- 仓库有 post-commit 自动 push 钩子（commit 即推 origin）

---

## Part A：发消息后草稿滞留 + 用户消息不上屏（真实模型时代体验缺陷）

### 现象（用户真机截图 2026-09-29）

发送「你好」后：输入框里的「你好」**停留到整轮生成结束**；消息列表里**看不到刚发的用户消息**（只剩 AI 的流式气泡）；发送按钮一直「发送中…」。模型回完才一切就位。

### 根因（总指挥已定位于源码级）

- `ChatPanel.vue` `onSend()`：`draft.value = ''` 在 `await store.send(text)` **之后**
- `stores/chat.ts` `send()`：`await window.api.chat.send(...)` 即主进程 `CHAT_SEND`——该 IPC **要等 agent 循环+模型生成全部完成**才 resolve（返回 userMessage+assistantMessage），之后才 `messages.value.push(...)` 上屏
- 本地回声时代整链路毫秒级，缺陷不可见；接真实模型后 IPC 悬置数秒~数分钟，全部滞后暴露

### 修复要求（渲染层最小修复，**不改 IPC 契约**）

1. `onSend()`：校验通过后**立即** `draft.value = ''`（在 `await store.send` 之前）；`catch` 里恢复草稿（仅当失败时输入框仍为空才回填 `draft.value = text`，避免覆盖生成期间用户的新输入），并保留现有 ElMessage.error
2. `stores/chat.ts` `send()`：await 之前**乐观上屏**用户消息（`{id: 'temp-' + Date.now(), sessionId: activeId.value, role: 'user', content, meta: null, createdAt: Date.now()}`；以 ChatMessage 类型为准）；真实结果返回后**用 result.userMessage 原位替换**临时条目（按索引查找），再 push assistantMessage；**失败路径移除临时条目**再抛错
3. 若 ChatMessage 的 id 有格式断言/校验（`m-` 前缀等），用与其不冲突的临时前缀并在替换时保证最终列表里无 temp 残留
4. CU2 滚动跟随不受影响：乐观上屏后照常触发跟随（现有 `following`/`scrollToBottom` 逻辑不动）
5. `sending.value` 门控（生成期间禁二次发送+可停止）**保持现状**，本单不改

### Part A 验收

- 新增/更新单测：草稿立即清空、乐观条目出现→替换、失败回滚（mock `window.api.chat.send` 挂起/拒绝两种）
- `pnpm gate` 全绿；报告注明测试计数

---

## Part B：下架「实验 ELN」与「稿件」两模块（用户产品裁决 2026-09-29：不需要了）

### 要求

**用户可见面全部移除**，数据零破坏：

1. **渲染层**（已盘点）：
   - `router/index.ts`：删 `eln`、`manuscripts` 两条路由
   - `SideNav.vue`：删对应两个导航项
   - `App.vue` 命令面板注册表：删 `nav-eln`、`nav-manuscripts`、`new-experiment`、`new-manuscript` 四条命令
   - 删视图文件 `views/ExperimentView.vue`、`views/ManuscriptsView.vue`（及**仅**被这两视图引用的组件——执行端以 grep 反向依赖确认，被共享的组件不动）
2. **主进程**（已盘点，执行端逐个核实后删）：
   - `ipc.ts`：ManuscriptService 装配与相关 IPC handler；实验服务同查同删
   - `services/manuscript/manuscript.service.ts` 及实验服务文件
   - `services/cloud-identity.ts`：若认领逻辑引用两模块的表，**只摘模块相关行，认领主流程与安全网机制不动**，报告中说明摘除点
   - `shared/`：ipc-channels.ts、types.ts、preload-api.ts 中两模块的 channel/类型/API 声明
3. **数据库：表结构零改动**——migrations 不删表不删列（历史数据原样保留在 SQLite 里，日后想恢复随时可行）；报告列明保留的表名
4. **测试**（已盘点涉及 8 文件）：`manuscript.service.test.ts`、`experiment.service.test.ts` 整删；其余（backup-core / command-registry / command-palette / knowledge / layout-scroll / zb-cloud-attachments）中涉及两模块的断言随删，**与两模块无关的断言一根手指都不许碰**；layout-scroll 若依赖被删视图需换页面载体，说明理由
5. 全文兜底扫：`grep -rn "experiment\|Experiment\|manuscript\|Manuscript\|实验\b\|稿件" src/ tests/`（排除无关词命中）清零或逐处说明保留理由

### 范围红线（B 部分）

- 不动 knowledge / drive / meetings / assistant / settings / backup 任何行为
- 不动数据库 schema；不动云备份容器格式（backup 全库打包自然反映）
- 系统提示词/Agent 工具与两模块无关，不动

---

## 验收证据（整单，缺一退回）

1. **Part A**：单测三件套（清空/替换/回滚）+ 真实渲染截图（Playwright 或 gate 浏览器渲染：发送后瞬间——草稿已空、用户气泡已上屏、流式气泡进行中）
2. **Part B**：启动产物截图——侧栏只剩 AI 助手/知识库/网盘/会议/设置五项；Ctrl+K 命令面板无两模块条目
3. `pnpm gate` 全绿，报告注明实际 HEAD、测试计数（788 − 删除数 ± 新增数）、每处摘除理由
4. **透明度说明**：任何「顺手改动」一律禁止；发现必须做的额外摘除点，单列并说明

## 交付

- 提交链干净（post-commit hook 自动推 origin）；报告贴出后总指挥独立复测
- 本单交付验收后走 **v1.3.1** 小列车（CHANGELOG 随单起草段落，发布时定稿）
