# 派工 Brief 模板 v4.1 (W92 升级)

> **定位**: v4.1 是增量模板，不复制 v3 正文，也不复制 v4 的 9 段全文。实际派工按
> `v3 头部与双锚定` → `v4 9 段` → `v4.1 6 必读段` 的顺序执行。
>
> **2026-07-30 实测基线**: `main` / `origin/main` / 本任务 base 均为 `3d908acb4`。
> v3 已在 main: `docs/dispatch-template-v3.md`；v4 提案尚未进 main，实测位于
> `origin/claude/w89-x27-brief-v4` commit `e59b501d5` 的 `docs/dispatch-template-v4.md`。

## 0. 证据状态与 fail-loud 原则

派工 brief 中的周次、分支、hash、路径、测试数和结论均是**待验证输入**，不是事实。
以下命令必须在写 brief 和 agent 开工时各跑一次：

```bash
git fetch origin --no-tags
git log -1 --format='%H %s' main
git log -1 --format='%H %s' origin/main
git branch --show-current
git status --short --branch
```

任一输入无法从 ref、文件或真跑结果中复现时，必须标为 `UNVERIFIED` / `MISSING`，
立即据实上报并按 stop condition 暂停；禁止为满足台账而补写不存在的历史。

### 本次 ref 校核勘误

- `W89-X-27` **存在**: `origin/claude/w89-x27-brief-v4` → `e59b501d5`，内容是 v4 提案。
- 可验证的“派工 brief 6 处错配”来源是
  `memory/w87-1st-batch-g1-a11y-2026-07-29.md`，不是 W89-X-27。
- `W91` **在项目历史中存在**：远端实存 WR-1、X-15～X-31 的多条分支和 commit。
- `W91-X-27`、`W91-X-32`、`W91-X-33` 的本地/远端 ref 本次实测均 `MISSING`；
  因此“X-27 6 处错配”“X-32 9 项致命错配”“X-33 证明 W91 不存在”不能当作已验证事实。
  正确结论是：**具体台账项不可证，必须拦截；不能扩大成整个 W91 不存在。**

## 1. 沿用 v4 9 段（类 20.60-68）

v4.1 沿用 `e59b501d5:docs/dispatch-template-v4.md` 的 9 段；这里只保留索引，不重写正文：

| 类 20 | v4 必读主题 | 派工硬门禁摘要 |
|---|---|---|
| 20.60 | axe SOP | ≥5 规则、每规则 ≥3 段、CI、后续留口、e2e 门禁 |
| 20.61 | Playwright 集成 | 真跑 build:a11y + pre-commit + lint/type-check 联动 |
| 20.62 | visual baseline | 逐 spec、统一 canonical project、数量拍板 |
| 20.63 | 测试硬门禁 | `TEST_TOKEN` 真注入；必填输入缺失必须 fail-loud |
| 20.64 | 真 CI 触发 | `gh auth status`、本地模拟、run 物证 |
| 20.65 | vitest 调研 | 根因分类、修法优先级、调研不擅自修 |
| 20.66 | runner 边界 | Vitest 与 Playwright API/路径不得混放 |
| 20.67 | 长连接等待 | WS/SSE/long-polling 禁用 `networkidle` |
| 20.68 | 真环境验证 v2 | 服务状态、a11y、visual、e2e、真功能、依赖前置 |

同时沿用 **类 20.82**：模板升级必须包含纪律、实战证据和 CLAUDE.md 永久引用。
这里的可验证范围是 `20.60-68 + 20.82`，不得凭“20.60-82”字面量虚构 20.69-81。

## 2. W92 升级 6 必读段（类 20.46 / 20.47 / 20.97 / 20.98 / 20.108 / 20.109）

### 段 0.1 — base ref 实测字段（类 20.46，类 20.32 加固）

派工 brief 必含实际命令取得的 hash 和 commit message，不写“按历史预计的 main”：

```yaml
base_ref:
  local_main: "<git log -1 --format='%H %s' main 的实测输出>"
  origin_main: "<git log -1 --format='%H %s' origin/main 的实测输出>"
  measured_at: "<ISO-8601 时间>"
  drift_policy: "执行超过 10 分钟时结束前重测；报告永远锚定开始 hash"
```

实战：W89-X-14 的 brief base 锚点 338 与 main 实测锚点 444 冲突；W90-X-14、
W91-X-31 执行期间 main 继续漂移。实测优先，不能以 CLAUDE.md 历史覆盖 Git 事实。

### 段 0.2 — 分支与 commit hash 实测（类 20.47，不照抄台账）

brief 提及任一 `Wxx-X-n hash` 时，必须同时验证 ref 存在、tip hash 和 commit message：

```yaml
required_refs:
  - logical_name: "W91-WR-1"
    branch: "origin/claude/w91-wr1-play-icon"
    measured_tip: "<git log origin/claude/w91-wr1-play-icon -1 --format='%H %s'>"
  - logical_name: "W91-X-16"
    branch: "origin/claude/w91-x16-alembic-091"
    measured_tip: "<git log origin/claude/w91-x16-alembic-091 -1 --format='%H %s'>"
missing_ref_policy: "标 MISSING，报告并暂停；禁止按 brief 数字补 hash"
```

```bash
git show-ref --verify refs/remotes/origin/<branch>
git log origin/<branch> -1 --format='%H %s'
git show --stat --oneline origin/<branch>
```

本模板将“分支/hash 不照抄台账”归口为类 20.47；其证据要求与类 20.46 的
base 实测相同。若历史类号台账有不同定义，以具体命令和证据文本为准，不以类号代替事实。

### 段 0.3 — 套件路径存在性探测（类 20.97 加固）

任何验证 agent 开工第一步先对表；全 MISS 时不把不存在的路径交给 pytest：

```bash
ls -d tests/<suite>/* 2>/dev/null

for suite in tests/<suite-a> tests/<suite-b>; do
  if [ -e "$suite" ]; then
    printf 'EXIST %s\n' "$suite"
  else
    printf 'MISSING %s\n' "$suite"
  fi
done
```

- 全 MISS → 立即上报并暂停，不空跑。
- 部分 MISS → 输出 EXIST/MISSING 对表，只跑实存套件；报告不得把 MISSING 计为 FAIL。
- 实战：W90-X-14 的 27 个新套件路径全部 MISS；W91-X-31 的 43 项中 33 项不存在。

### 段 0.4 — merge-base 假阳性拦截（类 20.98 加固）

`merge-base --is-ancestor` 为真不能证明“任务内容已合 main”；空分支也会满足祖先关系。

```bash
ahead=$(git rev-list --count origin/main..origin/<branch>)
behind=$(git rev-list --count origin/<branch>..origin/main)
printf 'ahead=%s behind=%s\n' "$ahead" "$behind"
git diff --stat origin/main...origin/<branch>
git log -1 --format='%H %s' origin/<branch>
```

判定规则：

- `ahead > 0`：分支有 main 未含的 commit，不能宣告已合。
- `ahead == 0`：**仍不能单独宣告已合**；可能是真已合，也可能是从未产出的空分支。
- 必须再核对 `commit_hash_预期` 和修后代码事实；没有预期 commit 或产物证据时标 `EMPTY_OR_UNVERIFIED`。

### 段 0.5 — 收官验证 6 步与 tail 禁读（类 20.108 加固）

```yaml
closure_verification:
  1_suite_probe: "先列 brief 套件 EXIST/MISSING"
  2_ref_probe: "逐分支实测 ahead/behind + 预期 commit/产物"
  3_summary_integrity: "核对 Running N tests 与完整 passed/failed/skipped；禁用 tail -N 下结论"
  4_server_prerequisite: "写明 baseURL、端口、谁启动 dev server，并先探测监听"
  5_base_anchor: "报告固定开始 hash；结束时记录 main 漂移量"
  6_side_effect_check: "测试后 git status + git diff，清理测试写脏文件"
```

Playwright/pytest 结果必须保留完整摘要：

```bash
# 不可只用 tail -N
rg -a "Running [0-9]+ tests|passed|failed|skipped|error" <完整日志>
```

实战：W91-X-31 的 a11y 实际 `25 failed + 25 passed`；只读尾部会只看到
`25 passed`，制造假全绿。main 漂移 11 commits 不会让已锚定的报告失效，但必须明确口径。

### 段 0.6 — 调研标“推断”必须先实测（类 20.109 沉淀）

调研里出现“推断 / NOT EXECUTED / 可能 / 待深查”时，下一单只能是**验证单**，不能是真修单：

1. grep 验证 brief 中给出的 API、symbol、路径确实存在且可调用。
2. 写一次性 Vitest/pytest/Playwright probe 或埋点，先让假设复现为红灯。
3. probe 反而为绿 → 假设被证伪，立即撤回真修，不修改业务代码。
4. 只有红灯可稳定复现并取得修前证据，才允许派生真修。

实战：W91-X-22 用 Vitest probe 证明 viewport 冷启动读到真实 `window.innerWidth=390`，
推翻“默认 1280 导致 desktop fallback”的推断；brief 建议的 `viewport.attach()` 也未 export。
该历史报告原归类为 20.102；v4.1 按 W92 台账统一沉淀为类 20.109，保留来源以避免类号覆盖事实。

## 3. 派工 v3 双锚定（v4.1 实战升级）

每个 brief 必填以下 8 项；占位符未替换即不得派出：

```yaml
dispatch_brief_v41:
  1_commit_hash_预期: "<实测 hash + commit message；ref 不存在则 MISSING>"
  2_branch_name_预期: "<git show-ref 实测存在的 claude/wxx-... 或明确待创建>"
  3_base_ref_实测: "<local main + origin/main hash、message、测量时间>"
  4_worktree_path: "<绝对路径；创建后用 git worktree list 复核>"
  5_boundary_allow_deny:
    allow: ["具体文件或目录", "必要时标行号/函数"]
    deny: ["app/", "web/src/", "alembic/versions/", "其它明确边界"]
  6_e2e_smoke_test: "<路径已探测存在的真跑命令 + 预期 case 总数>"
  7_cherry_pick_conflict:
    file: "<可能冲突文件>"
    decision: "<--theirs / --ours / 手工合并的明确选择及理由>"
  8_stop_condition:
    - "base/ref/path 与 brief 冲突"
    - "前置分支未合或预期 commit 不存在"
    - "推断无法复现为红灯"
    - "冲突无主拍选择"
    - "执行将越过 allow/deny 边界"
```

`commit_hash_预期` 与 `branch_name_预期` 是两个独立锚点：分支名可能 fallback，hash 也可能因
rebase/cherry-pick 改变；二者必须用 commit message、patch-id 或修后代码事实交叉验证。

## 4. 8 次拦截/核验实战教训

| # | 实战 | 实测教训 |
|---|---|---|
| 1 | W87-G-1 | brief 有 6 处错配：base、路径、testMatch、matcher、扩展名和覆盖结论；这是“6 处错配”的可验证来源。 |
| 2 | W89-X-27 | v4 提案存在于独立分支但未进 main；“agent 完成”不等于模板已可从 main 读取。 |
| 3 | W90-X-14 | 27 个 brief 套件路径全 MISS；前提“X-series 已合 main”不成立。 |
| 4 | W91-X-15 | brief 估 29 分支，实测 53；空分支让 merge-base 产生“已合”假阳性。 |
| 5 | W91-X-17 | WR-1 未合、build 红、orphan/missing 语义相反；宽泛 commit grep 也会假阳性。 |
| 6 | W91-X-22 | “viewport race”只是未执行推断，probe 将其证伪；具体修法 API 甚至未 export。 |
| 7 | W91-X-23 | brief 写 7 violations 实测 8，且路径大小写/目录错；承接调研仍须重测。 |
| 8 | W91-X-31 + ref 审计 | 33/43 路径不存在、5 分支未合、tail 可制造假绿；X-27/X-32/X-33 具体 ref 也不可证，但 W91 本身明确存在。 |

## 5. W92 实战沉淀类 20（8 条）

- **类 20.46** — brief 与 Git 实测冲突时，实测优先；立即据实上报并按 stop condition 暂停。
- **类 20.85** — test helper 缺必填输入时，静默 `false/null/skip` 是假绿制造机；必须 throw fail-loud，并有负向对照。
- **类 20.86** — alembic test 锚点必须随 migration PR 同步；改前实测当前 head、grep 全部 tests 引用、冷缓存真跑，不凭 CLAUDE.md 历史。历史中 20.86 曾被另一报告用于“前提 grep 要验证修后事实”，类号冲突时两项纪律都保留。
- **类 20.97** — 收官验证 agent 开工第一步探测 brief 套件路径；全 MISS 立即上报，不空跑。
- **类 20.98** — 判定分支已合必须查 ahead/behind、预期 commit 和修后产物；`merge-base --is-ancestor` 不能区分空分支。
- **类 20.108** — 收官验证执行套件探测、ref 实测、完整摘要、server/端口、base 锚定、副作用复检 6 步。
- **类 20.109** — 调研结论若标“推断”，不得直接派生真修；先用 probe/埋点取得稳定红灯。
- **类 20.110** — 错配率必须由派工台账逐单实测：`blocked / dispatched`。W92 brief 给出的 W91 `9/20 = 45%` 只能标为待复核口径；因 X-27/X-32/X-33 ref 不可证，未取得台账物证前不得把 45% 写成已验证项目事实。

> 派工 v6 §5 反馈类 20 按现有台账采用“累计 113+”口径，但 `113+` 是历史聚合值，
> 不能由类号最大值推算。每批必须附本批实例清单和可验证来源，禁止为了达到累计数虚构实例。

## 6. v4.1 开工与报告最小模板

```markdown
## 前提校核
- base: <hash + subject + measured_at>
- branch/ref: <EXIST/MISSING + tip>
- suite paths: <EXIST/MISSING 对表>
- assumptions: <VERIFIED / INFERRED / DISPROVED>

## 真跑结果
- command: <完整命令>
- discovered/running: <N>
- pass/skip/fail/error: <完整四元组>
- log evidence: <不可只取 tail>

## 边界
- allow diff: <文件清单>
- unexpected side effects: <无 / 已还原清单>

## stop condition
- <未触发 / 触发项 + 暂停原因>

## commit
- <真实 hash 7+ 位；未 commit 就写 pending，不伪造>
```

## 7. 模板历史

- **v3**: main `docs/dispatch-template-v3.md`，双锚定、worktree fallback、base 实测、集成 e2e。
- **v4 提案**: `e59b501d5:docs/dispatch-template-v4.md`，类 20.60-68 九段 + 类 20.82。
- **v4.1**: 本文，增加 6 必读段、8 类 20 和“不可证 ref fail-loud”纪律。

详见 `memory/w92-x6-brief-v41-2026-07-30.md`。
