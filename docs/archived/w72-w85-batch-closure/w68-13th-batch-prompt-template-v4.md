# W68 第 13 批派工纪要：Prompt Template v4

> 版本：v4（2026-07-24）  
> 适用：主指挥、并行 agent、文档/调研/迁移派工  
> 原则：先验证、再派工；先串链、再合并；完成必须有可复核证据。

## §1 W68 第 12 批 v3 升级到 v4

### §1.1 段 3：任务描述与 Alembic 双头防线

W68 第 12 批 B-1、B-2、C-2 均产生 070 migration 双头风险。v4 将迁移任务的前置检查写入 prompt，而不是依赖 agent 自觉：

**alembic 派工前必：**

1. 跑 `git fetch origin main && cd main && alembic heads`。
2. 如有 066/067/068/069 等 migration，在写新 migration 前 verify：
   - revision 不与任何已有 migration 重（包括 main 未合并分支）。
   - `down_revision` 指向最新 head，不是跳级。
3. 如发现双头，必报主指挥拍板，不自动改 `down_revision`，跟 W68 第 3 批纪律一致。
4. 主指挥合并后，必 rebase 重命名（例如 070→075/074/076）并串成单链。

Agent 必须在交付中附上 `alembic heads` 输出、revision/down_revision 对照和合并后的链路建议。发现冲突时状态写 `BLOCKED_ALEMBIC_HEAD_CONFLICT`，不得以“本地测试通过”替代拍板。

### §1.2 段 4：完成定义与 PS 5.1 参数 binding

W68 第 12 批 B-4 证明 PowerShell 的参数绑定错误会让派工脚本表面成功、实际走错分支。v4 的完成定义新增 PS 5.1 约束：

**PowerShell 派工脚本必：**

- 用 `--mode <value>` 空格分隔，不用 `--mode=<value>` 等号形式。
- 用 `[string]$Mode`，而非 `[switch]`。
- 验证 `$Mode -eq 'session'` 严格，不使用 `contains`。

脚本交付必须提供一个 session 模式实跑证据和一个非 session 模式拒绝/分流证据；参数缺失、大小写和额外字符均应由严格比较覆盖。不要把 PowerShell 7 的行为当作 Windows PowerShell 5.1 的兼容性证明。

### §1.3 段 3：plans/ 调研真验证

W68 第 12 批 A-1、D-1 暴露出 plans 状态段可能是自报，不能直接当作完成证据。v4 增加独立验证步骤：

**plans 派工前必：**

1. `grep -rn "<keyword>" C:/Users/pc/.claude/plans/`，验证 status 段不是自报。
2. 调研发现的 5 个真未实施 plans 必写 backlog docs，记录 plan、缺口、影响和后续路线。
3. 实施完成的 plans 必标 `COMPLETED`，并引真 commit（不能只写“已实现”）。

验证报告要区分 `COMPLETED`、`PARTIAL`、`NOT_STARTED`、`SUPERSEDED` 和 `AGENT_STUB`。每一项至少有路径、代码/文档证据、commit 或明确阻塞原因。若 plan 与仓库现状不一致，以 git、grep、测试和实际文件为准。

## §2 W68 第 13 批派工如何应用 v4

### A-1：plans 派工

A-1 已应用 §5.3 的真验证要求：先 grep plans，再审仓库与 git log；将自报完成和真实完成分开；对 5 个真未实施项写入 backlog docs。后续报告必须保留检索命令和证据路径。

### B-1：仓库模板

B-1 已应用 §5.1 的 PowerShell 参数约束：脚本按空格参数调用，`[string]$Mode` 严格比较 session，避免参数绑定落入默认模式。

### C-1：Alembic renumber

C-1 已应用 §5.1 的迁移安全流程：先确认 head 和 revision 唯一性，再由主指挥确定 070 系列重编号，最后串成单链；agent 不私自修正其他分支的 down_revision。

### 留 W71 派工

W71 新派工默认应用 v4。尤其是新增迁移、PowerShell 派工器和 plans 审计任务，prompt 必须逐条引用 §1 的前置门禁，并把证据列入完成定义。

## §3 W68 第 12 批派工错误案例：v3→v4 增量

### 案例一：B-1 Alembic 双头

B-1 与 B-2/C-2 三方在 070 附近并行，未在派工前统一检查最新 head 和 revision 唯一性，导致多个分支看似合理、合并后形成双头。v4 的修复不是“让每个 agent 自己改 down_revision”，而是：主指挥发现后拍板，按合并顺序 rebase、重命名并串单链，再验证唯一 head。

**复核命令：**

```bash
alembic heads
alembic history --verbose
```

### 案例二：B-4 PowerShell 5.1 参数 binding

B-4 的派工脚本将参数写成等号形式或使用 switch，PowerShell 5.1 解析后与预期不同，脚本进入错误路径。v4 强制空格分隔、`[string]` 类型和严格 `-eq`，并要求两条分支实跑证据。

### 案例三：A-1 plans 调研自报

A-1 早期依据 plan 的 status 文字判断完成，未先 grep 关键字核对实现，造成“完成率”与仓库事实偏差。v4 要求把 plan 状态当线索而非证据：必须交叉 git log、文件、测试及 backlog 文档。

## §4 v4 完整 5 段模板（供 W71 参考）

以下模板可直接复制到派工消息；尖括号内容必须替换。

### 段 1：角色、范围与不变量

```text
你是 Agent <编号>：<标题>。目标是 <一句话目标>。
范围：<文件/目录>；不范围：<明确排除项>。
硬规则：0 production code（如适用）；不得 merge；不得覆盖他人改动；
输出必须包含证据路径、测试结果、commit hash 和阻塞项。
```

派工者还要写明当前分支、基线 commit、依赖 agent 和是否允许新增文件。文档任务明确“仅 docs + memory”，迁移任务明确上游 head。

### 段 2：交付物与操作边界

```text
交付物：
1. <文件一>：<内容和大致规模>
2. <文件二>：<内容和大致规模>
禁止：<代码/配置/数据库/部署等不应修改的对象>。
```

若需要脚本，列出运行时版本（Windows PowerShell 5.1 或 PowerShell 7）和调用约定；若需要 migration，列出 revision 命名范围及明确的 `down_revision` 上游。

### 段 3：任务描述、前置验证与风险门禁

```text
开始前：
- git status；确认基线没有未授权修改。
- plans 任务：grep -rn "<keyword>" C:/Users/pc/.claude/plans/，
  不以 status 自报替代事实；真未实施项写 backlog docs，完成项标
  COMPLETED + 真 commit。
- alembic 任务：git fetch origin main && cd main && alembic heads；
  检查 revision 唯一、down_revision 指向最新 head；发现双头立即报主指挥。
- 其他任务：<领域特定检查>。
```

迁移 agent 不得自动替换有争议的 down_revision；必须给出冲突矩阵。合并后由主指挥 rebase 重命名（如 070→075/074/076）、串单链并再跑 heads。

### 段 4：完成定义、测试与 PS 5.1 约束

```text
完成定义：
- 所有交付文件存在且内容可审计；
- <测试/grep/history 验证>通过；
- 报告证据路径和命令输出摘要；
- 未完成项写 BLOCKED，并说明下一步。
PowerShell 5.1：使用 --mode <value>（空格），[string]$Mode，
仅用 $Mode -eq 'session' 判断 session；附两种模式实跑证据。
```

完成定义不能只写“代码已写”或“测试通过”。测试需说明是单元、集成、静态检查还是人工检查，以及是否受环境限制。对于 docs-only 任务，至少做文件计数、关键词检查、git diff --check。

### 段 5：回传格式、提交与交接

```text
回传：
- 状态：COMPLETED / PARTIAL / BLOCKED / SUPERSEDED；
- 修改文件（绝对路径）；
- 验证命令与结果；
- 关键风险和待主指挥拍板项；
- commit hash（不 merge、不 push，除非明确授权）。
```

如任务明确要求 push，则 push 到指定分支并回传远端 ref；否则只提交本地 commit。commit message 末尾必须包含：

```text
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

交接时说明是否产生 migration head、是否有 backlog docs、是否需要主指挥重编号或部署步骤。任何“顺手修复”必须单列并取得授权。

## §5 v1/v2/v3/v4 兼容矩阵

| 版本 | 核心能力 | Alembic 门禁 | PS 绑定门禁 | plans 真验证 | 适用 |
|---|---|---|---|---|---|
| v1 | 基本角色、范围、交付物 | 未明确 | 未明确 | 未明确 | 历史单 agent 小任务 |
| v2 | 增加测试、证据、分支边界 | 有基本 heads 检查 | 有调用示例但不严格 | 以 status 为主 | 一般文档/前端任务 |
| v3 | 五段结构雏形、交接和回滚 | 强调串链但未覆盖 070 三方 | 未覆盖 PS 5.1 陷阱 | 未覆盖自报偏差 | W68 第 12 批 |
| v4 | 五段完整模板、前置门禁、证据闭环 | revision 唯一、最新 head、双头拍板、重编号串链 | 空格参数、`[string]`、严格 `-eq`、双模式实跑 | grep plans、5 项 backlog、COMPLETED+真 commit | W68 第 13 批及 W71 |

### 升级路径

- v1→v2：补测试命令、证据路径和分支边界。
- v2→v3：采用五段结构，增加交接、回滚和迁移串链提醒。
- v3→v4：把 W68 第 12 批三个错误案例转为硬门禁：Alembic 双头预防、PS 5.1 binding、plans 真验证。
- v4→未来版本：只增可验证门禁，不删除已有兼容项；每次升级须增加案例、矩阵行和迁移说明。

### v4 发布前自检清单

- [ ] 段 1 写清角色、范围、不变量。
- [ ] 段 2 列出文件、规模和禁止修改项。
- [ ] 段 3 含 plans grep 和 Alembic heads 前置检查。
- [ ] 段 3 写明双头必须报主指挥，不能私改。
- [ ] 段 4 含 PS 5.1 三项 binding 约束。
- [ ] 段 4 要求真 commit、测试结果和 BLOCKED 原因。
- [ ] 段 5 规定回传格式、push/merge 边界和 co-author。
- [ ] 文档任务完成 `git diff --check`。
- [ ] migration 合并完成后只有一个 head。
- [ ] plans 调研结果有 backlog docs 或 COMPLETED 真 commit。

## 结语

v4 的重点不是增加格式，而是把三类“看起来完成、合并才出错”的问题前置：迁移 head 冲突、PowerShell 参数误绑定、plans 状态自报。主指挥应把模板当作可执行门禁；agent 应把命令输出和路径当作交付物的一部分。这样 W71 及以后派工可以复用同一套证据标准，同时保持 v1/v2/v3 任务的兼容交接。
