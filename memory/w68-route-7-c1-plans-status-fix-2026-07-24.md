# W68 第 7 批 C-1: 14 个 plans Status 段 commit hash 修正

**任务编号**: W68 第 7 批 C 路线
**锚点范式**: 第 83 守恒
**主指挥**: 主指挥
**执行 Agent**: Agent (claude-fable-5[1m]) on 2026-07-24
**分支**: `chore/w68-7th-batch-c1-plans-status-fix-2026-07-24`

---

## 上下文

W68 第 6 批的 5 个 Plan 深度审计 Agent 系统性发现: **14 个 plans 的 Status 段 commit hash 与 plan body 描述不对应**。这是 W66 主指挥批量状态化 67 个 plans 时"挂错标签"的系统性事故。

**根因**: W66 主指挥按 wave 派工时, 把"完成 wave"和"plan 内容真实施"绑在一起, 实际上 wave 完成 ≠ plan 完成。一个 wave 内可能有多个 plan 同时开工, 但主指挥拍板时只看过每 wave 提交的 commit hash, 没用 `git log --grep` 验证该 plan 文件名对应的功能 commit 是否真的存在。

**审计发现 (W68 第 6 批)**:

| # | plan 文件 | 原错 Status | 应改 Status |
|---|---|---|---|
| 1 | ai-reactive-candy.md | "4th-wave Agent 7: drive 模型 + auto-migration" | Knowledge 卡 stuck 'analyzing' 修复 (commit 3653890b4) |
| 2 | ai-sorted-shannon.md | "5th-wave Agent 1: Agent 6 runner 集成 grayscale=100" | ProcessingDialog 4 状态文案 (commit c741de9d4) |
| 3 | ancient-sauteeing-sunrise.md | "2nd-wave Agent 5: drive 测试" | voice_sample_count 重置为 1 (commit d13a17e7d alembic 034) |
| 4 | cam-agile-muffin.md | "6th-wave Agent 3: drive v2 retry 装饰器 (commit abbca9930)" | CAM++ 清理 (commit 7f838596a) |
| 5 | cheerful-questing-kite.md | "4th-wave Agent 6: drive feed 整合" | 声纹 anchor chain 实施 (commit b4123d304), 3 个新脚本留未来 PR |
| 6 | breezy-discovering-ripple.md | "3rd-wave Agent 6: 移动端 mobile views" | v31 + v31.2 完整 (commits 9110c32bc + 0c2b1e98b) |
| 7 | v77-p2-75-rustling-avalanche.md | "7th-wave Agent 6: rate limit 8 场景 spec (commit 7adb4e8eb)" | **SUPERSEDED** (templates admin page 已删 commit f66a21207) |
| 8 | qa-bench-isolation-a1.md | "qa-bench 700 题库 + 3-tier 阈值完成" | D4 题库子集完成. A1 物理隔离栈 0% (留 W68 第 7 批 A-3 实施) |
| 9 | qa-bench-v3.1-decisions.md | "7th + 6th wave qa-bench 完整收尾" | D1-D8 7/8 完成 (D5 留 W68 第 7 批 A-4) |
| 10 | silly-gliding-dahl.md | "knowledge pending Celery processor (commit 4085eeb80)" | fast mode + team_overview 留 W68 第 7 批 A-5 |
| 11 | delegated-orbiting-curry.md | "3rd-wave Agent 3: voiceprint batch" | Drive MIME 修复 (待 git log 找真 commit) |
| 12 | distributed-coalescing-stallman.md | "3rd-wave Agent 5: 项目综合" | MeetingRoom.vue 3 处硬编码浅色 → token 修复 (待 git log 找真 commit) |
| 13 | fizzy-cooking-puzzle.md | "7th-wave Agent 4: PWA InstallPrompt UI (commit 4f27118c0)" | Status 错 (commit 是 PWA, plan body 是 dedup toggle) |
| 14 | read-meetingdetailview-vue-lines-131-15-noble-lemon.md | "5th-wave Agent 3: ActivityFeedView 删除" | **SUPERSEDED** (plan body 自标废弃, ActivityFeedView 删除是独立 plan 工作) |

## 14 个 plans Status 修正详情

### 实施路径

**步骤 1**: 主指挥 W68 第 6 批派 5 个 Plan 深度审计 Agent, 系统化输出 14 个 plans 错归类清单。
**步骤 2**: W68 第 7 批 C-1 Agent 逐一按上表修正 plan 头部 Status 段。
**步骤 3**: 2 个 SUPERSEDED plan (#7 + #14) 在 W68 第 7 批 C-2 阶段被归档到 `archived/` 子目录 (注意: 这是 C-2 阶段做的, C-1 Agent 编辑的是已经归档的副本, 不影响 C-2)。
**步骤 4**: 写 1 个 memory 文件沉淀 5 新铁律 (本文件) + commit + push。

### Status 修正模式 (新铁律 1 配套)

每条 Status 包含 4 部分:
- **日期**: `(2026-07-24 W68 第 7 批 C-1 修正)` 替换原 `(2026-07-23)`
- **状态锚定**: 真实施 commit hash + 简短描述 (或 PARTIAL / SUPERSEDED 标注)
- **修正说明段**: 解释原 Status 与 plan body 为什么不符, 真实施 commit 是哪个 / 待 git log 验证
- **删除**: 原 "Update by 主指挥 (W66)" 锚点范式罗列段 (W66 closure 总结) — 这些信息属于独立 memory, 不在 plan 头部 Status 段重复

---

## 5 新铁律

### 铁律 1: plans Status 段必须描述真实实施 commit, 不能借用同 wave 别的 plan commit

**W66 事故**: 主指挥批量状态化时, "完成某 wave" 用最后一个 agent 的 commit hash 作为所有该 wave 内 plans 的 Status 锚点。问题: wave 内 N 个 plans 共用同一个 wave commit hash, 但每个 plan 的真实施 commit 是不同的。

**新规范**:
- Status 段必须 `git log --oneline -- "**/<plan-body-关键词>"` 找到 plan body 描述对应的 commit
- 如找不到唯一对应 (多个相关 commit), 必须标 PARTIAL + 列候选 commit
- 如 plan body 描述的目标物已被删除 (e.g. templates admin page), 必须标 SUPERSEDED + 记录删除 commit
- 跨 wave 借 commit (比如把 drive v2 commit 用作声纹 plan Status) 是禁止的, 立即审计修正

### 铁律 2: W66 批量状态化时挂错标签是系统事故, W68 第 6 批审计修正

**根因**: W66 主指挥"plans 优先"任务模式下, 主指挥没时间逐 plan `git log --grep "<plan-name>"` 验证, 而是按 wave 完成度逐个水 Status 标签。**结果**: 67 个 plans 中 14 个 (21%) 错归类。

**新规范**:
- **批量状态化必须有验证步骤**: 不能拍脑袋 + 模板 Status 段循环改 14 个 plans 就提交
- **必须用 `git log --oneline` 或 `git log --grep` 验证**: 每个 plan 的真实施 commit 都对应 plan body 描述
- **系统事故必须 1 次性批量修正**: 不留半修正 (14 个全改或全不改), 防止后续派工读 Status 时再次被错归类误导

### 铁律 3: AGENT_STUB 必须真合并, 不能 11KB 错归类

**W66 事故背景**: 部分 agent (如 4th-wave + 5th-wave) 派工时, 多 agent 共用同一个 plan 文件 (叫做 "AGENT_STUB"), 各 agent 的 plan 内容由 agent-stub 拼接到主 plan 文件。**问题**: 某些 agent-stub 拼接到错误 plan (比如声纹 agent-stub 拼到了 drive plan), 主指挥又把 drive plan 拍板成 "drive 完成"。

**新规范**:
- AGENT_STUB 文件的 `agent-stub` tag 必须 100% 保留 (尤其在归档移动时)
- agent-stub 拼接时必须验证拼接目标 plan 的文件名 / 内容 / agent 派工的对应关系
- 任何"agent 完成 → Status 拍板"链条必须有 1:1 对应验证, 不能多个 agent 共享 1 个 plan Status
- 后续 plans 目录如果有 `<plan-name>-agent-<hash>.md` 后缀文件, 必须确认是 AGENT_STUB 还是独立 plan

### 铁律 4: plan 文件名应与实际内容一致, 60% 命名误导需整改

**W68 第 6 批审计发现**:
- `ai-sorted-shannon.md` 标题 "ProcessingDialog", 文件名 "ai-sorted-shannon" — **不一致**
- `breezy-discovering-ripple.md` 标题 "v31 检索质量监控", 文件名 "breezy-discovering-ripple" — **不一致**
- `cam-agile-muffin.md` 标题 "CAM++ 清理", 文件名 "cam-agile-muffin" — **不一致**
- `cheerful-questing-kite.md` 标题 "声纹循环净化 sub-project", 文件名 "cheerful-questing-kite" — **不一致**
- `cheerful-questing-kite-agent-*.md` 是 SUBPLAN 而非独立 plan — **命名误导**
- `fizzy-cooking-puzzle.md` 标题 "移除 dedup toggle", 文件名 "fizzy-cooking-puzzle" — **不一致**
- `delegated-orbiting-curry.md` 标题 "Drive 跨分支冲突解决", 文件名 "delegated-orbiting-curry" — **不一致**
- `distributed-coalescing-stallman.md` 标题 "MeetingRoom dark mode", 文件名 "distributed-coalescing-stallman" — **不一致**

**新规范**:
- Claude Code plan 文件名是 random adjective-noun-Verb-Pl了 全项目 50+ plan 文件, 60% 都是 random 名 (这是工具生成的, 没强约束)
- 但**对派工有意义**: agent 派工时常用 plan 标题定位, 不用 plan 文件名随机词定位
- **整改方案 (未来 PR)**: 给每个 plan 加 `slug:` frontmatter / 或每个 plan 加 README index / 或 plans 目录加 `INDEX.md` 表 — 让主指挥拍板能从标题反查派工内容
- **现行妥协**: W68 第 7 批 C-1 仍用 random 文件名, 但 Status 段必须包含**完整 plan 标题关键词**让 grep 找得到

### 铁律 5: plan body 自标 SUPERSEDED 的, Status 段必须更新, 不能仍标 COMPLETED

**W68 第 6 批审计发现**:
- `read-meetingdetailview-vue-lines-131-15-noble-lemon.md` plan body 第 15 行写 **"Plan 已废弃. 用户已决定不做 v73 P1 / P2, 此 plan 文件保留为空占位"**, 但 Status 段还标 **"COMPLETED: 5th-wave Agent 3: ActivityFeedView 桌面 + 移动 + 文档删除"** — 自相矛盾
- `v77-p2-75-rustling-avalanche.md` plan body 描述 templates admin page, 但 commit f66a21207 已删除该功能 — Status 段还能标"7th-wave Agent 6 rate limit"

**新规范**:
- 任何 plan body 自标 SUPERSEDED / 已废弃 / NOOP / CANCELLED, Status 段必须同步标注 SUPERSEDED
- 删除 commit (如 templates admin) 后, 该 plan 必须标 SUPERSEDED, 不能借别的 commit 标 COMPLETED
- SUPERSEDED plan 应该归档到 `archived/` 子目录 (W68 第 7 批 C-2 已实施), 但 Status 段必须先标 SUPERSEDED 再归档

---

## 与其他 W68 第 7 批的关系

- **C-1 (本任务)**: 14 个 plans Status 错归类修正 (本文件主任务)
- **C-2 (并行)**: SUPERSEDED plan 物理归档到 `archived/` 子目录 (`v77-p2-75-rustling-avalanche.md` + `read-meetingdetailview-vue-lines-131-15-noble-lemon.md` 已归档)
- **A-3**: qa-bench 物理隔离栈 (qa-bench-isolation-a1.md 真实施)
- **A-4**: KB Dashboard 监控 (qa-bench-v3.1-decisions.md D5 真实施)
- **A-5**: 智能对话 fast mode + team_overview 个性化 (silly-gliding-dahl.md 真实施)

---

## 流程纪律

1. **0 production code 改动铁律 13/15 守恒**: 本任务仅改 `C:/Users/pc/.claude/plans/` 14 个 plans Status 段 (plans 在仓库外, 不算 production code) + 写 memory 文件 (repository 内唯一变更)
2. **不动 plan body**: Status 段是顶部 `## Status (...)\n\n**COMPLETED**: ...` 块, 不下穿到 plan body
3. **保留 AGENT_STUB 标记**: 同时确保归档的 4 个 `-agent-*.md` files 不被本任务改动
4. **commit 末尾**: Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
5. **分支 + push**: push 到 origin, 不 merge (主指挥来 merge)

---

## 时间线

- **2026-07-24 主指挥 W68 第 6 批派工**: 5 个 Plan 深度审计 Agent 系统化报告 14 plans 错归类
- **2026-07-24 主指挥 W68 第 7 批派工 (本任务)**: Agent 接收 C-1 任务
- **2026-07-24 执行**: 14 个 plan Status 段逐一修正 + 1 memory 文件创建 + 1 commit + push
