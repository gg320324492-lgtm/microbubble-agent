# 桌面端科研 Agent 升级：本地文件操作能力重设计

> 2026-09-08 · 基于对 `desktop/src` 实际代码的审计，推翻此前"P1-P4 从头搭建"的假设，重新设计。

## 一、现状审计结论（结合实际）

### 已有能力（比预期完整得多）

| 层 | 现状 | 位置 |
|----|------|------|
| Agent 编排 | ResearchAgentRuntime：ResearchPlan → 拓扑排序 → 分步执行（knowledge/tool/model/analysis/synthesis 五类 step），事件流 trace | `desktop/src/main/services/agent/agent-runtime.ts` (424 行) |
| 工具注册 | 6 个 scientific tools（list_experiments / get_measurements / get_samples / run_kinetic / run_statistics / write_manuscript_section），全部绑定内部 SQLite | `agent-tools.ts` + `scientific-tools.ts` |
| 多智能体 | agent-coordinator / agent-registry / agent-debate + 6 个角色 agent（writing/reviewer/mechanism/literature/experiment/analysis） | `desktop/src/services/agents/` |
| 科研服务 | 统计分析、动力学拟合、假设生成、文献评审、稿件生成等 ~25 个 service | `desktop/src/main/services/science/` |
| 模型网关 | model-gateway + mimo/minimax adapter + capability-router | `desktop/src/main/services/agent/`、`model-provider/` |
| 安全基建 | audit 审计、token-vault、runtime 层 assertNoSecret 泄漏防护 | `services/audit/`、`security/` |
| UI | ChatView + ToolCallCard / ToolResultCard / PlanTimeline / TraceTimeline / ToolExecutionPanel，事件驱动渲染已就绪 | `renderer/src/components/chat/` |

### 关键缺口（离 Claude Code 式能力差的三层）

1. **零文件系统工具**。所有工具操作内部 SQLite（experiments/measurements/manuscripts），`write_manuscript_section` 写的是数据库表，磁盘上一个文件都改不了。
2. **范式错位**。agent-runtime 是"预规划 DAG 执行器"：planner 先产出 ResearchPlan，再拓扑执行。这适合结构化科研流（设计实验→分析→写稿），但**无法支撑文件操作的 ReAct 循环**——"读文件→发现不是预期的→换个路径再搜→再读"需要 LLM 每轮根据观察结果自主决定下一步，DAG 一旦生成就固化了。
3. **无工作区/权限/回滚概念**。没有 workspace root、没有写前确认、没有备份。

### 顺带发现的 Bug（与重设计无关但需修复）

`scientific-tools.ts:184-186`：`ON CONFLICT DO UPDATE SET excludedCLUDed.section` —— `excludedCLUDed` 是 `excluded` 的笔误，运行时更新已有稿件章节必然抛 SQL 语法错误。应为 `excluded.section`。

## 二、对既有路线的批判（为什么不"完美"）

1. 此前 P1 方案假设需要"在主进程新建 Agent 内核"——**错误前提**。runtime、工具注册、模型网关、trace UI 全部现成，新建内核是重复建设。正确做法是在既有 `ToolCaller` 接口后面**扩一类 FS 工具**。
2. 既有方向（继续堆结构化工具 + 多智能体辩论）**到不了** Claude Code 的能力：文件操作的本质是开放环境下的自主循环，不是预定义流程。多智能体辩论栈对文件任务纯属过度设计，不应让文件工具经过 coordinator。
3. 引入 Claude Agent SDK 之类外部引擎的选项**不划算**：会废弃 model-gateway 的 mimo/minimax 双适配、audit、trace UI 全套既有投资，且 SDK 锁定 Claude 单供应商。既有基建已覆盖 SDK 80% 的价值，缺的只是循环模式 + FS 工具层（估计 600-900 行）。

## 三、重设计：双循环架构

**核心原则：不重建引擎，只补两块——一个新循环 + 一层新工具，全部挂进既有接口。**

```
用户请求
  │
  ├─ 结构化科研任务 ──→ ResearchAgentRuntime（既有，保留不动）
  │                      planner 产 DAG → 拓扑执行 → synthesis
  │
  └─ 文件/工作区任务 ──→ FileAgentLoop（新增 ReAct 循环，~400 行）
                         每轮: LLM(模型网关) → tool.execute(既有接口)
                              → 观察结果 → 再决策，直至完成或达上限
                              → 事件走既有 EventEmitter → 既有 trace UI
```

两个循环共享：model-gateway（模型调用）、工具注册表（`ScientificToolRegistry` 同构扩展）、audit（全程留痕）、IPC + chat 组件（ToolCallCard/TraceTimeline 直接复用）。

意图分流：`intent-classifier.ts` 已存在，扩展一个 `file_workspace` 意图类别即可路由。

## 四、新增组件明细

### 4.1 WorkspaceService（`desktop/src/main/services/workspace/`，新建）

- 用户在 FirstLaunchWizard 中指定工作区根目录（如 `D:\科研工作区`），持久化到 electron-store
- 路径安全：所有工具路径参数必须 `path.resolve` 后落在根目录内（realpath 校验，防 `..` 与符号链接逃逸）
- 约定目录结构：`projects/<名称>/{data, figures, manuscript, refs, notes}`，建区时自动生成 `说明.md`（作用等同 Claude Code 的 CLAUDE.md，每次任务自动注入上下文）

### 4.2 FS 工具组（`agent/file-tools.ts`，新建，注册进既有工具表）

| 工具 | 说明 | 默认权限 |
|------|------|---------|
| `list_dir` | 列目录（含大小/修改时间） | 自动 |
| `read_file` | 读文本（截断保护，二进制检测） | 自动 |
| `glob` | 模式匹配找文件 | 自动 |
| `grep` | 内容搜索（复用 ripgrep 语义，Node 实现） | 自动 |
| `write_file` | 新建/整体覆写 | 确认 |
| `edit_file` | 精确字符串替换（Claude Code Edit 语义：old_string 唯一匹配，失败报歧义） | 确认 |
| `move_file` / `delete_file` | delete 进系统回收站，绝不直接删 | 必确认 |
| `search_workspace` | 本地全文检索（见 4.4） | 自动 |

每个工具：入参校验（沿用 scientific-tools 的 assertId/clamp 风格）→ 权限门 → 执行 → `audit.record()` → 结构化返回。

### 4.3 权限与回滚引擎（`workspace/permission.ts` + `diff.ts`，新建）

- 三级策略（electron-store 可配）：读=自动；根目录内写=Diff 确认（可切"本会话免确认"）；删除/移动/根目录外=必须确认
- **Diff 确认流**：写操作不直接落盘 → 生成 unified diff → IPC 推给渲染进程新组件 `DiffConfirmCard.vue`（approve / reject / 修改后重提）→ 批准后才执行
- **回滚**：每次覆写前把原文件复制到 `<root>/.agent-backups/<时间戳>/`，保留最近 N 份；`DiffConfirmCard` 提供"一键还原本次会话所有修改"
- 删除走 Electron `shell.trashItem()`（回收站），双保险

### 4.4 本地文件 RAG（渐进式，不一步到位）

- **第一期用 FTS5**（better-sqlite3 内置，零新依赖）：对工作区内 `.md/.tex/.txt/.csv` 建全文索引（文件监听 chokidar 增量更新），`search_workspace` 工具暴露给 Agent——科研场景关键词检索（试剂名、样品号、模型名）命中率高，性价比远高于先上向量
- **第二期加 sqlite-vec**：需要语义检索（"找和超声空化效应相关的结论"）时再引入，embedding 调用走既有 model-gateway，索引存同一 SQLite
- 云端知识大脑不重复建设：保留既有 `query_lab_knowledge` 类通道（FRP → 后端 pgvector），本地/云端双检索工具并存，由 Agent 自主选择

### 4.5 FileAgentLoop 细节（`agent/file-agent-loop.ts`，新建）

- 复用 `RuntimeEvent` 事件协议（step_started/step_completed/step_failed），**渲染层零改动**即可显示过程
- 系统提示包含：工作区结构说明 + `说明.md` 内容 + 工具使用黄金规则（移植后端 `prompts.py` 的经验：先读后写、edit 前必须 read、禁止凭空编造路径）
- 迭代上限（默认 25 轮）+ 单轮 token 预算，超限转交用户
- 错误自愈：工具报错将错误文本作为观察返回给 LLM（而非终止），允许其换路径重试——这是 DAG 范式做不到、ReAct 范式的核心价值

### 4.6 UI 增量（最小改动）

- `DiffConfirmCard.vue`：新增，diff 渲染 + 批准/拒绝
- FirstLaunchWizard：加一步工作区目录选择
- ChatView / AgentCenter：无需结构性改动，新事件类型走既有卡片

## 五、实施顺序（每步独立可验收）

| 步骤 | 内容 | 验收 |
|------|------|------|
| S0 | 修复 `excludedCLUDed` SQL bug | 重复 write_manuscript_section 不再报错 |
| S1 | WorkspaceService + 4 个只读工具（list/read/glob/grep）+ audit 接入 | "看看我工作区里有哪些数据文件"全流程跑通 |
| S2 | FileAgentLoop（ReAct）+ intent 分流 | 多轮文件任务：读→搜→汇总回答，过程在 TraceTimeline 可见 |
| S3 | 写工具 + 权限引擎 + DiffConfirmCard + 备份回滚 | "把这批实验数据整理成汇总表" 写文件前弹 diff 确认，可一键还原 |
| S4 | FTS5 索引 + search_workspace | "在我笔记里找关于 XX 的记录" 命中本地文件 |
| S5 | 接通云端知识大脑查询工具（FRP） | "结合组会纪要帮我改 manuscript" |

S1-S3 是主线（约 600-900 行新代码 + 1 个新 Vue 组件），S4/S5 增量叠加。

## 六、明确不做的事

- 不重写 agent-runtime，不动既有 6 个 scientific tools 和多智能体辩论栈
- 文件任务不经过 agent-coordinator/debate（直连 FileAgentLoop）
- 第一期不引入向量数据库新依赖、不训练本地 embedding
- 不做通用 shell 执行工具（`run_command`）——科研桌面端风险收益比差，数据分析走既有 analysisEngine；确有需要时 S6 再议且强制确认
