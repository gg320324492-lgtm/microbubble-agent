# 工单 C-3：写工具 + Diff 确认 + 备份回滚（v1）

> 签发：总指挥 · 2026-09-17
> 上游：C-1（`220f624e8`）、C-2（`08184aa0f`）均已验收通过；测试基线 **80** 条全绿
> 这是 M1-C 的最后一步：完成后 Agent 具备完整「读 + 写」工作区能力，随后进入 R-1 发布

## 你的任务背景

你在为「小气 · 科研工作台」（Electron 桌面端，代码在 `E:\microbubble-agent\apps\desktop`）给 Agent 增加写能力。/workspace AGENT.md 守则里对用户的承诺必须逐条兑现：**覆写前自动备份到 `.agent-backups/`、删除走系统回收站、修改既有内容前征得用户确认**。真机已实测 C-2 循环/工具卡片/确认面板运转良好。

直接可用的地基（C-1/C-2 已验证）：
- `ToolRegistry.invoke`：参数名为 `path` 的输入自动过围栏换成绝对路径；invoke 语义保持「已授权即执行」，**confirm 拦截在循环层做**
- `AgentLoopService`：注入式 `streamTurn`（离线假网关可测）；`LoopEvent` 事件流推 renderer；`ToolCallRecord`（id/name/input/status/summary/data）已持久化到 `chat_messages.meta` 并可还原
- `.agent-backups/` 已由 WorkspaceService 自动维护进 `.gitignore`（追加幂等）
- `serializeToolResult` 8000 字符截断已内置

技术栈约束同前：**工具模块与单测绝不 import 依赖 Electron ABI 的模块**（vitest + jsdom + node:sqlite，`openNodeSqlite` 模式）。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰；交付时贴 `git status --short` 自证。**开发/测试期绝不向真实工作区写入**——测试全用临时目录夹具
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 完成门禁：`pnpm test` 全绿（当前基线 **80** 条，需新增 ≥15 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. 新增 IPC 通道须白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## 交付物

### 1. 三个写工具（`src/main/agent/tools/`，每工具一文件）

- **write_file**（`permission: 'confirm'`）：创建或覆写 UTF-8 文本文件；自动创建父目录；**覆写已存在文件前**把原内容备份到 `.agent-backups/<时间戳>/<相对路径>`；单文件上限 2MB，超出拒绝并说明；成功回喂只含 summary + 相对路径（**绝不回全文**，保护上下文窗口）
- **delete_file**（`permission: 'confirm'`）：删除单个文件，走系统回收站，**绝不物理删除**。Electron `shell.trashItem` 以**注入函数**传入（ipc.ts 装配时注入；工具与测试不 import Electron，测试注 fake 验证「调用了回收站而非 unlink」）
- **mkdir**（`permission: 'auto'`，无破坏性）：创建目录含父目录，幂等（已存在返回 ok）
- 路径参数统一相对工作区（围栏由 registry 自动强制，无需重复实现）

### 2. confirm 权限链路（循环层拦截）

- `AgentLoopService` 在调 `invoke` 前检查 `tool.permission === 'confirm'` → 拦截并 emit awaiting_confirm 事件（含 diff）→ 等待 renderer 用户决定
- **批准** → 继续 invoke（审计前后各一条照常）；**拒绝** → 不执行，直接 `audit.record` 一条「用户拒绝」留痕（ok:0），并回喂明确拒绝语义的 tool_result（模型可改道）；**用户停止** → 取消等待、按停止处理
- `ToolCallRecord.status` 扩展 `'awaiting_confirm'` 与 `'rejected'`；含未决确认的会话重开时，该卡片降级展示为「已取消/未完成」，不阻塞还原

### 3. Diff 生成

- write_file 对已存在文件生成行级 diff（新增/删除行），上限 200 行截断；新文件展示「新建文件 + 内容预览」
- diff 放 `ToolCallRecord.data.diff` 供卡片展示，**不进模型回喂**

### 4. UI（`components/chat/`）

- 工具卡片新状态：awaiting_confirm 显示 diff（新增绿/删除红，等宽字体）+「批准 / 拒绝」；rejected 标识
- write_file 完成态卡片有备份时显示「回滚此写入」：确认后从备份恢复原内容、再次审计留痕、卡片状态更新；新文件（无备份）不显示
- 新增 IPC：确认结果回传通道（如 `chat:confirm-resolve`），白名单三处同步 + 契约测试

### 5. 测试（全部离线，临时目录 + 假网关）

- write_file：新建 / 覆写（备份产生且内容正确）/ 父目录自动创建 / 2MB 拒绝 / 围栏与 `.git` 拒绝
- delete_file：fake 注入验证走回收站；拒绝不删
- mkdir：幂等
- confirm 链路：批准路径（执行+审计+备份）/ 拒绝路径（文件未动+拒绝留痕+回喂拒绝语义）/ 停止取消等待
- 回滚：覆写 → 回滚 → 原内容恢复且再次留痕
- meta 持久化往返：含 rejected/未决确认的消息重开降级展示
- 现有 **80** 条零回归

## 定义完成（全部满足才算完）

- [ ] `pnpm test` 全绿且新增 ≥15 条（80 → N）
- [ ] `pnpm typecheck` 0 错、`pnpm build` 成功
- [ ] `git status --short` 无保护路径改动（含 desktop-conversion/）
- [ ] 断网自证：写工具全流程（确认/拒绝/备份/回滚/回收站）离线可测
- [ ] **CHANGELOG 条目草稿**（新制度，见交付报告格式第 6 项；需把 C-2 的条目一并补上）

## 交付报告格式

1. 变更/新增文件清单（路径+行数）
2. `pnpm test` / `typecheck` / `build` 输出尾部（注明测试条数：基线 80 → 共 N 条）
3. commit hash + 提交信息
4. 自测记录：confirm 三条路径（批准/拒绝/停止）+ 备份回滚 + 回收站 注入验证结果表
5. 遗留问题 / 对 R-1 发布工单的接口建议
6. **版本迭代信息（CHANGELOG 条目草稿）**：C-2 一条 + C-3 一条（新功能/修复/已知问题格式）

注：真机写工作区验收（在指挥部工作区实际新建/覆写/删除文件）由总指挥在应用运行时执行，属产品运行行为，不在你开发范围内。
