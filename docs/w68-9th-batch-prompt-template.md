# W68 第 9 批派工 Prompt 模板

> 适用范围：仅用于研究、文档、计划闭环和已批准的小修派工。生产代码默认冻结；任何例外必须由主指挥明确批准。
>
> 本模板基于 W68 第 9 批 15 agents 的真实复盘，目标是把“派工意图”转换为可验收、可追溯、可回滚的执行合同。

## §1 派工 Prompt 模板（W68 第 9 批 15 agents 实战总结）

### §1.1 五段结构

每一个派工 prompt 固定由五段组成。顺序不可调换，因为它对应 agent 的理解顺序：先知道为什么做，再知道在哪做，然后知道做什么，接着知道何时算完成，最后知道边界在哪里。

#### 1. 背景：含 commit 与真实引用

背景必须引用仓库中可以复核的事实，而不是 agent 的假设。至少包含：

- 当前主分支 commit 或相关 merge commit；
- 真实文件路径、行号、测试结果或现有文档链接；
- 已知约束（例如 alembic 链、0 production code 改动铁律）；
- 本任务属于哪个 batch、路线和编号。

推荐写法：

```text
## 背景
- W68 第 9 批当前基线：main HEAD <commit>（请先 git log -5 核对）。
- 事实引用：<path>:<line>、<test path>、<docs path>。
- 本任务编号：C-1；来源：已存在 plan <path>，不是 agent 自行提出的需求。
- 约束：仅修改 docs/memory；不得触碰 app/、web/、scripts/。
```

禁止写法：

```text
项目可能存在某问题，请你顺便修复。
```

“可能”“应该”“大概”都不是验收依据。若尚未验证，应先派调研任务，不得把猜测伪装成背景事实。

#### 2. 当前分支：含 worktree 路径

agent 必须知道自己在哪个隔离目录工作。prompt 应明确：

- 分支完整名称；
- worktree 的绝对路径；
- 开始前运行 `git status --short --branch`；
- 不得在其他 worktree 或 main 工作目录写文件。

推荐写法：

```text
## 当前分支
- branch: docs/w68-10th-batch-d1-prompt-template-2026-07-24
- worktree: E:/microbubble-agent/.claude/worktrees/<name>
- 开始前核对 branch/path/status；所有读写均在该 worktree 完成。
```

路径不清会导致跨 agent 串改、误删未提交文件，或把提交落到错误分支。绝对路径优先，Windows 与 Git Bash 的路径形式要同时可识别。

#### 3. 任务：含验收标准与真实测试

任务段必须拆成可执行步骤，并把“真跑测试”写进 prompt，而不是事后口头要求。至少包括：

1. 需要新增、修改或审计的文件；
2. 不可改变的文件范围；
3. 验收条件（数量、章节、字段、链路或输出）；
4. 要执行的真实命令；
5. 失败时的处理方式（停止、记录、回滚，不要静默绕过）。

示例：

```text
## 任务
1. 阅读 plan 与对应 commit，确认状态为 completed/partial/not_started。
2. 新建一份 docs 记录，引用真实路径和命令输出。
3. 运行 bash scripts/check_typing_imports.sh（若不涉及 Python，说明为何跳过）。
4. 运行 git diff --check 与文档结构检查。
5. 验收：3 个实战案例、5 条纪律、无生产代码 diff。
```

“测试通过”必须指向真实命令和真实结果。不能只写“自行验证”或“看起来没问题”。

#### 4. 完成定义：含 commit 格式与 push 目标

完成定义要让主指挥可以只看 commit 和状态就完成合并前审计。必须规定：

- commit subject 的格式（含 batch、编号、主题）；
- commit body 是否需要事实、测试和文件清单；
- commit 末尾固定的 Co-Authored-By；
- push 的远端和分支；
- 不得 merge，由主指挥负责。

标准格式：

```text
## 完成定义
- 仅允许预期文件发生变化；git diff --stat 与 git status 必须可解释。
- commit: docs: W68 route-10 D-1 prompt template
- 末尾必须包含：Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
- push: origin docs/w68-10th-batch-d1-prompt-template-2026-07-24
- 不 merge；回报 commit hash、push 输出、测试结果和未解决项。
```

#### 5. 不要做的事：避免跨路径与越权实现

最后一段必须显式写出禁区，而不是期待 agent 自己推断。常见禁区包括：

- 不修改 `app/`、`web/`、数据库 schema 或部署配置；
- 不顺手重构、不扩展需求、不创建未要求的 README；
- 不修改其他 agent 的文件；
- 不提交测试生成物、截图、dist 或临时日志；
- 不把未经批准的 production code 修复混入文档提交；
- 不 merge、不 force push、不删除主分支内容；
- 不用假想问题替代真实调研。

标准写法：

```text
## 不要做的事
- 0 production code 改动铁律：只改列出的 docs/ 与 memory/ 文件。
- 不跨 worktree，不改其他路径，不新增未授权脚本。
- 发现生产代码问题只记录路径和证据，另起任务，不在本任务修复。
```

### §1.2 可复制的完整模板

```text
你是 Agent “<batch>-<route>-<id>: <title>”。

## 背景
- 当前基线：main HEAD <commit>；开始前用 git log -5 核对。
- 真实引用：<path>:<line>、<docs path>、<test output>。
- 任务来源：<plan / issue / 调研报告>，不得自行扩展。
- 约束：<0 production code / migration chain / deployment rule>。

## 当前分支
- branch: <full branch name>
- worktree: <absolute path>
- 先运行 git status --short --branch；只在此 worktree 工作。

## 任务
1. <step 1>
2. <step 2>
3. <step 3>
- 验收标准：<具体数量/章节/行为>。
- 真跑测试：<exact commands>。
- 失败处理：停止并记录证据，不静默绕过。

## 完成定义
- 预期文件：<exact paths>。
- commit: <type>: <batch> <route> <topic>
- commit 末尾：Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
- push origin <branch>；不 merge。
- 回报 hash、push、测试与剩余风险。

## 不要做的事
- <forbidden paths>
- 不跨任务、不重构、不提交生成物。
- 0 production code 改动铁律；发现问题只留证据并上报。
```

## §2 三个真实派工示例解析

### §2.1 C-1：plans 闭环

**真实意图**：核对 W68 第 9 批 backlog 中的计划状态，补齐已完成但缺少证据的闭环记录。它不是让 agent 重新设计功能，也不是让 agent 直接修改业务代码。

**prompt 应有的五段信息**：

1. 背景引用 verified-plans 与 W68 第 8/9 批 closure 记录，明确计划名称、状态和对应 commit。
2. 当前分支明确使用独立 docs worktree，避免修改主指挥的 backlog 文件。
3. 任务要求逐项 `git log`、`git show`、`grep`，对 completed、partial、not_started 给出证据，并更新指定 memory/docs。
4. 完成定义要求文档中保留 plan ID、commit hash、实际验证命令，commit 只含文档文件并 push 分支。
5. 禁止自行“补实现”、禁止把 partial 写成 completed、禁止用 agent 名称或聊天记录替代仓库证据。

**验收重点**：每一个状态结论都能回链到 commit 或文件；没有生产代码 diff；报告中区分“计划声称完成”和“仓库实际完成”。这一步把 W68 第 7 批发现的状态错位转成可追踪资产。

### §2.2 A-3：cleanup

**真实意图**：清理已经确认属于 worktree、测试或临时产物的内容，降低仓库噪音；不是泛化式删除“看起来没用”的文件。

**prompt 应有的五段信息**：

1. 背景必须列出 `git status`、worktree 列表、文件来源和删除安全依据；引用 W68 第 9 批 cleanup 审计。
2. 当前分支和绝对 worktree 路径写清楚，先保存 status，再进行 dry-run。
3. 任务先盘点，再按白名单删除；必须运行 `git diff --stat`、`git status`，必要时跑对应测试。
4. 完成定义要求删除列表可复核、commit 主题带 cleanup、push 到 agent 分支，不 merge。
5. 禁止删除主分支文件、未确认的用户数据、生产资源、数据库迁移或其他 agent 未合并内容。

**验收重点**：cleanup 必须是证据驱动的白名单操作。对于疑似重要文件，宁可上报留待主指挥，也不能猜删。删除前后都要保留可复核的状态信息。

### §2.3 D-5：W69 + W70 排期

**真实意图**：基于 W68 第 9 批调研结果规划后续 batch，而不是凭空发明新路线。排期文档必须明确哪些事项已经有证据、哪些仍需调研、哪些不触发。

**prompt 应有的五段信息**：

1. 背景引用 W68 第 9 批各 route closure、ROADMAP、plans backlog 与真实 git log；注明预测与事实的区别。
2. 当前分支使用文档专用 worktree，避免和实现 agent 的 branch 混用。
3. 任务要求把候选项按 P0/P1/P2、来源、依赖、验证门槛、预计 agent 数量整理，并执行文档链接和 commit 核查。
4. 完成定义要求交付 W69/W70 排期、触发条件和不触发条件；commit/push 只改 docs/memory。
5. 禁止把预测写成承诺，禁止无证据增加生产任务，禁止跳过 plans backlog 或忽略既有 migration 依赖。

**验收重点**：排期应能回答“为什么现在做、证据是什么、谁依赖谁、何时停止”。未来 batch 的候选必须保留来源链接，避免下一批重新从猜测开始。

## §3 失败模式：W68 第 9 批 A-1 与跨 batch 教训

### 3.1 并行派 alembic 前先 verify 既有 head

任何涉及 migration 的派工，第一步不是写文件，而是读取当前脚本链并执行 head 检查：

```bash
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
```

若已有多个 head，先停止并上报；不能在分叉链上继续叠加 migration。若只有一个 head，prompt 必须把它写入背景和任务验收。merge 后立即重新执行同一检查。

### 3.2 prompt 必须写明“接 X”

并行 migration agent 不得只说“接最新迁移”。必须写明：

```text
本迁移的 down_revision 必须接 062_drive_comments；不得接 061 或自行选择其他 head。
```

W68 第 4 批已经证明，两个 agent 同时接同一上游会产生 Multiple heads。串单链是 merge 顺序和部署安全的前置条件，不是实现完成后的补救。

### 3.3 跨 batch 调研发现必须 document

只写进 memory 会让仓库里的下一位 agent 找不到证据，也无法在审计时区分事实和口头结论。凡是影响 W69/W70 排期、路线取舍、失败模式或部署操作的调研发现，必须同步写入指定 docs；memory 只承担索引、经验沉淀和跨会话提示。

最低记录项：来源 batch、真实 commit/path、结论、影响、待验证项、下一步触发条件。没有真实引用的“发现”只能标记为假设，不能直接变成派工任务。

## §4 五拍板纪律（W68 第 4 批拍板，W68 第 9 批 v2 升级）

### 1. plans 查 backlog 后再选派工

先读取 plans/backlog，核对状态和真实 commit，再决定派工。不得因为某个主题“看起来重要”就绕过已有计划。派工 prompt 需写明它对应哪一个 plan，或者明确记录“本任务是调研，不是实施”。

### 2. 小修来源 = 调研发现，不允许 agent 假想

小修必须来自已完成的 grep、测试、日志、git diff 或用户明确报告。agent 可以发现问题，但不能在没有证据时把猜测包装成缺陷，更不能借小修名义扩大范围。

### 3. 调研发现必写到 docs

影响后续决策的调研结果必须落仓库 docs，并在 memory 中建立索引。文档要包含路径、commit、命令和结论；只写聊天或 memory 不算跨 batch 闭环。

### 4. 跨 session 监控必须含本地 session + main session 双 git log

监控并行工作时，至少核对：

```bash
git -C <agent-worktree> log --oneline -5
git -C E:/microbubble-agent log --oneline -5
```

两处都要记录分支、HEAD、是否已 merge。单看 agent session 的聊天回报无法证明 commit 已进入 main；单看 main 又无法发现 agent 尚未 push 或落在错误分支。

### 5. 调研 agent 必 grep 真验证

调研不是“读几段文件后总结”。prompt 必须要求 `grep`/`rg`、`git show`、测试或脚本输出等可复核证据，并把命令写入交付报告。若搜索无结果，也要记录搜索范围和命令，防止“未发现”被误读为“肯定不存在”。

## §5 主指挥验收清单

- [ ] prompt 是否严格五段结构？
- [ ] 背景是否有 commit、路径和真实引用？
- [ ] branch 与 worktree 是否为绝对路径？
- [ ] 任务是否包含验收标准和真跑测试？
- [ ] 完成定义是否指定 commit、Co-Authored-By、push、禁止 merge？
- [ ] 禁区是否覆盖 0 production code 改动与跨路径风险？
- [ ] 若为 migration，是否先查 head、明确“接 X”、merge 后复查？
- [ ] 实战发现是否同步 docs 与 memory？
- [ ] 监控是否同时核对 agent worktree 与 main 的 git log？
- [ ] 最终 diff 是否只有授权文件？

## §6 结语

W68 第 9 批的核心升级不是更长的 prompt，而是把 prompt 变成可验证的执行契约：真实背景、隔离位置、明确任务、可审计完成定义和显式禁区五者缺一不可。配合 backlog 优先、证据驱动小修、跨 batch 文档化、双 session 监控和 grep 真验证，后续 batch 才能保持“plans 优先 + 小修搭配”的任务模式 v2，并持续满足 0 production code 改动铁律。
