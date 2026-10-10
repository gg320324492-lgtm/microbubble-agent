# 工单 C-2：ReAct 原生 tool_use 循环 + 工具卡片 + thinking 折叠面板（v1）

> 签发：总指挥 · 2026-09-16
> 上游：C-1 已验收通过（commit `220f624e8`，测试基线 63 条全绿）

## 你的任务背景

你在为「小气 · 科研工作台」（Electron 桌面端，代码在 `E:\microbubble-agent\apps\desktop`）实现 M1-C 的核心一步：把 AI 助手从纯聊天升级为**真正的 Agent 循环**——模型可调用 C-1 交付的工作区只读工具（list_dir / read_file / glob / grep），多轮「思考→调工具→看结果→再回答」直至完成。

已就绪的地基：
- WorkspaceService（围栏）+ ToolRegistry（invoke 统一入口，含审计前后各一条）+ 4 个只读工具，全部 `permission: 'auto'`
- M1-B 模型网关：Anthropic 协议 SSE 流式实测通（含 thinking 块过滤，当前只取 text_delta）
- 三栏工作台 UI + 会话持久化（迁移 001-004）

**关键已验证事实（直接采用，勿重新探针）**：
1. MiMo（`mimo-v2.5`）走 Anthropic 协议，**原生支持 tool_use**：返回 `stop_reason:"tool_use"` + 结构化 `input`；一次响应可能含**多个** tool_use 块
2. MiMo 在正文前输出 thinking 块（`thinking_delta`）——思维链不得混入正文
3. 用 curl 实测中文请求时 JSON 写临时文件 `--data-binary @file`（Windows 控制台编码坑）

技术栈同前：Electron 32 + electron-vite + Vue3 + TS strict + better-sqlite3（主进程）；测试 vitest + jsdom + node:sqlite（`openNodeSqlite` 模式，**绝不 import 依赖 Electron ABI 的模块**）。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 完成门禁：`pnpm test` 全绿（当前基线 **63** 条，需新增 ≥12 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## 交付物

### 1. Agent 循环服务（主进程，`src/main/agent/` 下自行组织）

- 组装请求：`registry.list()` 转 Anthropic tools 格式（`name` / `description` / `input_schema` = 现有 `parameters`，已是 JSON Schema 形状）；system 提示词含工作区根路径与「路径一律相对工作区」约定（可选：注入 AGENT.md 内容，截断到合理长度）
- 循环：流式转发 `text_delta` → `stop_reason === 'tool_use'` 时解析全部 tool_use 块 → 逐个 `registry.invoke` → 全部 `tool_result` 回喂 → 继续请求；`stop_reason === 'end_turn'` 结束
- **健壮性**：
  - 未注册工具 invoke 会 throw——循环层 catch 后作为 `ok:false` ToolResult 回喂模型（C-1 报告建议，采纳）
  - **最大 15 轮**保护，超限优雅终止并向用户说明
  - 用户停止（Esc / 停止按钮）能中断流式与循环任意环节，已产生的部分内容不丢
  - 工具卡片需展示「运行中 → 成功 / 失败」状态流转，因此循环过程要以事件流形式推给渲染进程
- thinking 块：剥离不进正文；以独立事件/字段透传给 UI（折叠面板用），并存库供会话恢复

### 2. 会话持久化扩展

- assistant 消息中的工具调用轮次（tool_use / tool_result / thinking）须能存库并在重新打开会话时还原（工具卡片还原为已完成态）
- 需要新表/新列则追加**迁移 005**，勿动 001-004；能复用 003 现有结构（如 JSON content 字段）则不必新建迁移

### 3. UI（`components/chat/` 下自行组织）

- **工具卡片**：内嵌助手消息流——工具名 + 输入摘要 + 状态（运行中/成功/失败）+ 可展开查看结果详情（data/summary）
- **thinking 折叠面板**：默认折叠，标题显示「思考过程」，展开看全文；不参与正文渲染
- 循环进行中的轻量状态提示（如「第 N 轮 · 正在执行 list_dir…」）
- 无工作区时发起会话：模型仍可纯对话，但工具不可用要有清晰降级提示（不崩溃）

### 4. IPC

- 沿用 `chat:stream` 扩展或新增 agent 通道均可，但必须白名单三处同步 + 契约测试

### 5. 测试（全部离线，假网关驱动）

- 循环全链路 ≥1 条：tool_use 停止 → invoke → tool_result 回喂 → end_turn（用假网关脚本化返回）
- 多 tool_use 块一次响应、未注册工具回喂 ok:false、15 轮超限中断、用户停止中断
- 持久化往返：含工具轮次的会话存→取→还原
- 工具卡片 / thinking 面板组件测试（状态流转、折叠行为）
- 现有 **63** 条零回归

## 定义完成（全部满足才算完）

- [ ] `pnpm test` 全绿且新增 ≥12 条（63 → N）
- [ ] `pnpm typecheck` 0 错、`pnpm build` 成功
- [ ] `git status --short` 无保护路径改动（含 desktop-conversion/）
- [ ] 自测记录：假网关下「工具调用→结果→总结」全链路时序说明
- [ ] 真机联调指引：告知总指挥如何配 key 实测「列出工作区根目录并读 AGENT.md」全链路（此步由总指挥亲自验收）

## 交付报告格式

1. 变更/新增文件清单（路径+行数）
2. `pnpm test` / `typecheck` / `build` 输出尾部（注明测试条数：基线 63 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：假网关全链路时序 + 停止/超限/未注册工具三异常路径结果
5. 遗留问题 / 对 C-3 的接口建议
