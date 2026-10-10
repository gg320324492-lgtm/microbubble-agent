# 工单 C-1：工作区服务 + 工具注册表 + 只读工具（修订版 v2）

> 签发：总指挥 · 2026-09-14
> v2 修订：工作区 = GitHub 仓库根（本文件夹 desktop-conversion/）；新增 `.git` 禁区与 `.gitignore` 自动维护；说明文件定名 AGENT.md；Agent 不执行 git 命令。

## 你的任务背景

你在为"小气 · 科研工作台"（Electron 桌面端，代码在 `E:\microbubble-agent\apps\desktop`）实现 Agent 文件操作能力的地基。当前已完成：三栏工作台 UI、会话持久化（SQLite 迁移 001-003）、模型网关（Anthropic 协议流式已实测通）。

**工作区语义（已拍板）**：Agent 的工作区 = 一个 GitHub 仓库的本地根目录（首个工作区即 `E:\microbubble-agent\desktop-conversion\`，独立 git 仓库）。Agent 在仓库内自由读写，但：`.git/` 读写禁区、不执行任何 git 命令、删除走回收站（本单只读工具无删除）、备份机制 C-3 实现（本单只需维护 .gitignore）。

技术栈：Electron 32 + electron-vite + Vue3 + TS strict + better-sqlite3（主进程）/ vitest + node:sqlite（测试，参考 `tests/unit/chat.service.test.ts` 的 `openNodeSqlite` 模式，**测试绝不 import 依赖 Electron ABI 的模块**）。

## 常设红线（违反任一直接打回）

1. 保护路径零改动：`app/`、`web/`、`alembic/`、`nginx/`、`docker-compose*`、`.env`、`desktop-conversion/` 一律不碰（desktop-conversion 是总指挥独立仓库，执行 agent 无权写入）；交付时贴 `git status --short` 自证
2. 禁止 `git add -A`；只提交：`git commit -- apps/desktop`；遇 `.git/index.lock` 等待重试，禁止删锁
3. 禁止新增任何 npm 依赖
4. 完成门禁：`pnpm test` 全绿（当前基线 29 条，需新增 ≥14 条）、`pnpm typecheck` 0 错、`pnpm build` 成功
5. IPC 白名单三处同步（`src/shared/ipc-channels.ts` / `main/ipc.ts` / `preload`），一致性测试自动校验

## 交付物

### 1. WorkspaceService（`src/main/services/workspace/workspace.service.ts`）

```ts
export class WorkspaceService {
  constructor(storeDir: string)                      // JSON 持久化文件所在目录（userData）
  getRoot(): string | null                           // 未设置返回 null
  setRoot(dir: string): void                         // 必须已存在且为目录；AGENT.md 不存在时生成（已存在绝不覆盖）；确保 .gitignore 含 .agent-backups/（追加，不覆盖已有内容）
  resolveInWorkspace(inputPath: string): string      // 围栏：见下；越界抛 WorkspaceEscapeError
}
export class WorkspaceEscapeError extends Error
```

- 持久化用 `node:fs` 写 `<storeDir>/workspace.json`（**不引入 electron-store**）
- 围栏规则（安全核心，逐条实现）：
  a) `path.resolve(root, input)` 后必须仍以 root 为前缀
  b) 对路径上最近一个已存在祖先目录做 `fs.realpathSync` 再校验（防符号链接逃逸）
  c) **`.git` 禁区**：路径任何段落等于 `.git` → 直接拒绝（读/写都拒）
  d) 空路径 / 未设 root → 抛错
- 根目录的 `AGENT.md` 已由总指挥预置（内容=Agent 行为守则），服务**检测存在即跳过生成**

### 2. 工具注册表（`src/main/agent/tool-registry.ts`）

```ts
export type ToolPermissionLevel = 'auto' | 'confirm'   // 本单只实现 'auto'；'confirm' 留给 C-3
export interface ToolContext { userId: string; workspaceRoot: string }
export interface ToolResult { ok: boolean; summary: string; data?: unknown; error?: string }
export interface AgentTool {
  name: string
  description: string                                  // 给模型看的说明
  permission: ToolPermissionLevel
  parameters: { type: 'object'; properties: Record<string, unknown>; required: string[] }
  execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>
}
export class ToolRegistry {
  register(tool: AgentTool): void
  get(name: string): AgentTool | undefined
  list(): AgentTool[]
  async invoke(name: string, input: Record<string, unknown>, ctx: ToolContext): Promise<ToolResult>
  // invoke 统一入口：未注册报错 → 路径参数围栏校验 → 审计(前) → 执行 → 审计(后)
}
```

四个只读工具（`src/main/agent/tools/`，每工具一文件）：
- `list_dir`：列目录（名称/类型/大小/修改时间），非目录报错
- `read_file`：UTF-8 文本，上限 256KB 截断并在 summary 注明；NUL 字节探测判定二进制则拒读
- `glob`：模式匹配（`**/*` 语义，node:fs 自实现递归），上限 200 条
- `grep`：内容搜索（子串或正则+大小写开关），返回 文件:行号:行内容，上限 100 条
- 路径类参数一律相对工作区，拒绝绝对路径入参

### 3. 审计服务（`src/main/services/workspace/audit.service.ts` + 迁移 004）

- 迁移 004：`workspace_audit` 表（`id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, tool TEXT, input_summary TEXT, ok INTEGER, created_at INTEGER`），在 MIGRATIONS 数组追加，勿动 001-003
- `AuditService.record()` / `list(limit)`；invoke 前后各一条

### 4. IPC + 设置页

- 新通道：`workspace:get`、`workspace:set`（main 弹 `dialog.showOpenDialog({ properties: ['openDirectory','createDirectory'] })` 选目录后 setRoot）、`workspace:audit-list`
- preload 白名单同步暴露 `workspace.*`
- 设置页新增「工作区」区块（`components/settings/WorkspaceSection.vue`）：当前工作区/未设置态、选择目录按钮、最近 20 条审计记录（工具名+结果+时间）
- 设置页文案提示：建议将工作区设为 `E:\microbubble-agent\desktop-conversion`（GitHub 仓库根）

### 5. 测试（`tests/unit/`，node:sqlite / 真实临时目录）

- 围栏 ≥7 例：`../` 上跳、绝对路径出界、符号链接出界、空路径、未设 root、恰好等于根（放行）、`.git` 段落（拒绝）
- 四工具各 ≥2 例（正常+异常）
- WorkspaceService 持久化往返、AGENT.md 已存在不覆盖、.gitignore 追加不覆盖
- 审计写入与 list
- 现有 29 条测试零回归

## 定义完成（全部满足才算完）

- [ ] `pnpm test` 全绿且新增 ≥14 条
- [ ] `pnpm typecheck` 0 错、`pnpm build` 成功
- [ ] `git status --short` 无保护路径改动（含 desktop-conversion/）
- [ ] 断网自证：设置工作区 → 四工具 → 审计 全流程可用

## 交付报告格式

1. 变更/新增文件清单（路径+行数）
2. `pnpm test` / `typecheck` / `build` 输出尾部
3. commit hash + 提交信息
4. 自测记录：围栏 7 条逃逸用例结果表
5. 遗留问题 / 对 C-2、C-3 的接口建议
