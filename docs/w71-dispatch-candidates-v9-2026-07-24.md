# W72 派工纪要：Prompt Template v9

> 版本：v9（2026-07-24/27）
> 适用：主指挥、并行 agent、文档/调研/迁移派工
> 沿用：v8 12 段全部 + 段 5 升级 12 → **15 项**必填 + 段 7 升级 13 → **16 类**派工前提错误 + **新增段 8 v9 升级实战反馈**（W72 batch 派工实战暴露的 B 路线接口协调 / SubAgent 编排 / 派生新任务 3 类新缺口显式沉淀）
> 原则：先验证、再派工；先串链、再合并；先反馈、再升级；合并顺序可见；派工前提错误必沉淀；**W72 batch 派工实战反馈强制入模板**，W73+ 派工必须用 v9。

## TL;DR（v8 → v9 升级理由）

W72 batch 派工实战（锚点范式 W71 206 → W72 预期 ~214，~8 守恒）暴露 v8 三层缺口，v9 必含：

1. **W72 派工调研"派生新任务"真验证缺口**：v8 段 5 第 11 项已含"派生新任务真验证"原则，但 W72 batch C-1（容器 rebuild 调研）+ C-2（商业化调研）+ C-3（ppt/word 5 缺口调研）三个 agent 派工时主指挥口头追加"派生新任务清单"作为后续 W73 派工基础，agent 自报完成但 `git log` 显示派生任务清单实际**只在 plan 文件内**未派工到独立 worktree。v9 必须显式要求"派生新任务真验证 = 必含 git log + grep + commit 引用 3 段 + 派生任务清单逐项 git log 验证"。
2. **W72 派工调研"git log 真验证状态"缺口**：v8 段 1.2 含"branch-pushed ≠ merged"原则但缺"派工调研文档必含 git log 真验证状态"实战类。W72 batch D-2 partial 守恒实战发现 D-2 文档同步 agent 报告"W71 15 agents 全部合并 main"但 `git log main | grep` 仅 3 commit 落地，12 agent 仍 base HEAD `0ae74f477` 0 commit 状态。v9 必须显式要求"派工调研文档必含 git log 真验证状态"。
3. **W72 派工 B 路线 5 agents 串单链"Celery 串行约束"缺口**：v8 段 6 含"B 路线 Celery 串行约束"原则但缺"W72 派生 B 路线新任务必含 Celery 串行约束"实战类。W72 batch B-1..B-5 五个新派生 agent（NavRail.vue + ThinkingModeSwitch.vue + ChatBreadcrumb.vue + 商业化分析脚本 + 容器 rebuild 脚本）之间 Celery 串行约束未在派工 prompt 显式声明，导致 agent 默认并行开发。v9 必须显式要求"B 路线新派生任务必含 Celery 串行约束 + 数据流向图"。

**v9 增量**：
- 段 5：升级 12 → **15 项**必填（+ W72 batch 派生新任务真验证 / W72 起步纪律必读 / git log 真验证状态 3 项实战信号）
- 段 7：升级 13 → **16 类**派工前提错误（+ W72 起步纪律必读 / 派生调研 git log 真验证 / B 路线新派生 Celery 串行 3 类）
- **新增段 8：v9 升级实战反馈**（W72 batch 派工调研实战暴露的 3 类新缺口显式沉淀）

v9 默认应用从 W73 batch 开始；W74+ 调研任务**必须**用 v9。

## §1 角色、范围与不变量（沿用 v8 + 派工 v9 升级）

```text
你是 Agent <编号>：<标题>。目标是 <一句话目标>。
范围：<文件/目录>；不范围：<明确排除项>。
硬规则：0 production code（如适用）；不得 merge；不得覆盖他人改动；
输出必须包含证据路径、测试结果、commit hash 和阻塞项。
当前分支：<worktree 分支名>；基线 commit：<hash>；
依赖 agent：<agent-id>（说明是否等待其 commit）。

【v9 升级】若本 agent 是 B 路线 5 agents 之一，必须在 prompt 里同时列出
<B-1/B-2/B-3/B-4/B-5> 接口契约文件路径 + 数据格式约定 + Celery 串行约束；
若有派生新任务（主指挥口头追加），必须列出派生任务清单 + 真验证命令
（git log + grep + commit 引用 3 段，缺一不可）；
若有派工调研任务，必须列出调研状态真验证命令（git log main | grep agent-id
+ git show commit-hash 3 段）。
```

## §2 交付物与操作边界（沿用 v8 + 派工 v9 升级）

```text
交付物：
1. <文件一>：<内容和大致规模>
2. <文件二>：<内容和大致规模>
禁止：<代码/配置/数据库/部署等不应修改的对象>。

【v9 升级】若涉及 SubAgent 编排接口，必含 type hint 字段：
- 所有 SubAgent 输入/输出 dataclass 必须有完整 type hint（`from typing import ...`）
- 跨 agent 数据传递必须用 Pydantic BaseModel 显式 schema（防 `missing field` 500）
- 编译产物 grep 验证 type hint 出现次数 ≥ 1（避免被 minify 吃掉）

【v9 升级】若涉及派生新任务清单，必含派生任务真验证 3 段：
- 派生任务清单逐项 `git log --grep="<派生任务 keyword>"` 输出
- 派生任务实际 commit hash + 简述
- 派生任务与原 plan 串链关系（backlog docs 路径 + Status 段引用）
```

若需要脚本，列出运行时版本（Windows PowerShell 5.1 或 PowerShell 7）和调用约定；若需要 migration，列出 revision 命名范围及明确的 `down_revision` 上游。

## §3 任务描述、前置验证与风险门禁（沿用 v8 + W72 实战升级）

```text
开始前：
- git status；确认基线没有未授权修改。
- plans 任务：grep -rn "<keyword>" C:/Users/pc/.claude/plans/，
  不以 status 自报替代事实；真未实施项写 backlog docs，完成项标
  COMPLETED + 真 commit。
- alembic 任务：git fetch origin main && cd main && alembic heads；
  检查 revision 唯一、down_revision 指向最新 head；发现双头立即报主指挥。
- 前端任务（v8 沿用）：git fetch origin main && 检查 5 hot-fix 链路
  （H-1 dashboard timer / H-2 nginx 410 / H-3 main.js unregister /
  H-4 checkSwBlacklist 删除 / H-5 heartbeat 静默）是否全在基线；如不是，
  不能贸然修前端，**先复现根因**再决定走哪种修复路径。
- PWA / SW 状态（v8 沿用）：若任务涉及 SW 或 PWA，必先确认
  `vite-plugin-pwa` 是否 `disable: true`、nginx `/sw.js` `/registerSW.js`
  `/manifest.webmanifest` 是否 410、本地 main.js 顶部是否 unregister + 清 cache。

【v9 升级】W72 起步纪律 4 项必读（v9 新增）：
- W71 B 路线 5 agents commit + merge 真验证：
  git log --oneline main | grep -E "w71st-batch-(b1|b2|b3|b4|b5)"
  期望 ≥ 5 commits 输出
- W71 子 plan ② 7 维评分数据 + KB 闭环验证：
  QaBenchDashboard 数据拉取 + KB 闭环审计触发写入
- W72 子 plan ③ UI redesign 三大件（NavRail + ThinkingModeSwitch + ChatBreadcrumb）
  起步前必读 v8 段 8 + v9 段 8（v9 实战反馈 3 类）
- W72 batch 派工调研真验证（v9 新增）：派工调研 agent 必先 git log
  真验证派工状态，缺一不可

【v9 升级】SubAgent 编排接口（v8 沿用 + v9 实战）：
- 若本 agent 涉及 SubAgent 输入/输出 dataclass 或 Pydantic schema，
  必先 grep 老 schema 看是否齐全 type hint：
  `grep -rnE "dataclass|BaseModel" <本 agent 范围> --include="*.py"`
- 跨 agent 串接时必先验证 schema 兼容：
  `python -c "from app.schemas.<x> import <Y>; Y.model_validate(<sample>)"`
- 新加字段必须用 keyword-only（防位置参数歧义）+ Optional 默认 None（防缺字段 500）
- 派生新任务（主指挥口头追加子任务）必先写 backlog docs：
  `C:/Users/pc/.claude/plans/<plan-keyword>.md` + Status 段
  + 真验证命令（git log + grep + commit 引用 3 段）

【v9 升级】B 路线 5 agents 接口协调（v8 沿用 + v9 新派生任务实战）：
- 若本 agent 是 B-1/B-2/B-3/B-4/B-5 之一，必先列出接口契约表：
  | 上游 agent | 输出文件 | 输出格式 | 本 agent 接收字段 | 校验方式 |
- Celery 串行任务必先确认依赖：b-3 必等 b-1 + b-2 commit + merge 后才启动
- dashboard / CI smoke 必先确认上游 5 agents commit + 测试基线守恒
- 【v9 新增】派生 B 路线新任务必含 Celery 串行约束 + 数据流向图

- 其他任务：<领域特定检查>。
```

迁移 agent 不得自动替换有争议的 down_revision；必须给出冲突矩阵。合并后由主指挥 rebase 重命名（如 070→075/074/076）、串单链并再跑 heads。

## §4 完成定义、测试与 PS 5.1 约束（沿用 v8）

```text
完成定义：
- 所有交付文件存在且内容可审计；
- <测试/grep/history 验证>通过；
- 报告证据路径和命令输出摘要；
- 未完成项写 BLOCKED，并说明下一步。
- web 改动必须 `npm run build`（唯一合法命令，PWA 410 铁律），
  禁止 `vite build` 直跑（绕开 postbuild → 服务器 410 + PWA install 失败）。
- web 改动必须 grep 验证（v8 沿用）：编译产物里禁用项 grep 为 0，
  保留项 grep ≥ 1。例：H-4 派工要求编译后 checkSwBlacklist=0,
  SW content OK=0, SKIP_WAITING=0, unregister=1。
- runtime 心跳 / console 噪声（v8 沿用）：若任务涉及 setInterval
  或 console.warn，主指挥要求"静默"时**只删 console.warn**，保留
  timer 重置逻辑（避免 W68 H-5 heartbeat 循环 bug）。

【v9 升级】派生新任务真验证 grep（v9 新增）：
- 派生任务清单逐项 git log + grep 输出
- 派生任务实际 commit hash 引用 ≥ 1
- 派生任务与原 plan 串链关系（backlog docs 路径 + Status 段引用）≥ 1
```

PowerShell 5.1：使用 --mode <value>（空格），[string]$Mode，仅用 $Mode -eq 'session' 判断 session；附两种模式实跑证据。

完成定义不能只写"代码已写"或"测试通过"。测试需说明是单元、集成、静态检查还是人工检查，以及是否受环境限制。对于 docs-only 任务，至少做文件计数、关键词检查、git diff --check。

## §5 经验反馈循环（v9 升级：12 项 → 15 项必填）

```text
回传反馈（必填，15 项缺一不可）：

【v8 沿用 12 项】
1. 段 1–4 哪些段 / 句子有效？（具体指明段号 + 句子/短语 + 帮到了什么）
2. 哪些段多余 / 偏离 / 重复？（具体句子 + 偏离原因）
3. 新增段 7 候选：本次任务是否暴露了"应纳入模板"的新段？
4. 旧段升级建议：段 1–4 哪一句应被改写？（原句 + 改写后 + 一句话理由）
5. 派工前提错误：本批派工蕴含哪些前提？哪个前提事后被证伪？（详见段 7）
6. 锚点范式变化：本批是否推进了锚点范式数字？推进多少？为什么？
7. 浏览器状态轨迹（前端任务必填）：主指挥 console 仍刷哪条日志？
   修前/修后 grep 编译产物的关键字符串几次？是否还会 ERR_ABORTED 404
   老 chunk？devtools Application → Service Workers 状态是否 `redundant`？
8. PWA / SW 副作用自检（前端任务必填）：PWA 永久禁用四步（main.js
   顶部 unregister + VitePWA disable + nginx 410 + postbuild 兼容）
   是否全做？checkSwBlacklist 这类自检函数是否在 if(false) 包裹
   或整段删除（避免 fetch + r.text() self-loop）？新加自检函数时
   是否考虑 PWA 禁用后还该不该存在？
9. runtime 心跳 / setInterval 策略（前端任务必填）：本次任务是否
   涉及 setInterval / setTimeout / console.warn？timer 句柄是否存到
   变量、onUnmounted 时清理？console 警告按主指挥"完全静默"还是
   "降为 info"还是"保留 warn"？删除 console.warn 但 timer 重置
   逻辑必须保留（避免循环）。
10. SubAgent 编排接口 type hint（涉及 SubAgent 串接必填）：
    本次任务是否涉及 SubAgent 输入/输出 dataclass / Pydantic schema
    跨 agent 传递？type hint 齐全度（grep `dataclass|BaseModel`
    出现次数 vs 缺 type hint 字段数）？编译产物里 type hint 标识
    grep 几次？跨 agent 串接时是否跑过 `model_validate(sample)`
    校验？新加字段是否 keyword-only + Optional 默认 None？
11. 派生新任务真验证（主指挥口头追加子任务必填）：
    本次派工是否含主指挥口头追加的派生子任务？派生任务清单
    写进 backlog docs 了吗（`C:/Users/pc/.claude/plans/<plan>.md`
    + Status 段）？派生任务"已完成"自报是否经 git log + grep +
    commit 引用 3 段真验证？与原 plan 是否串链？
12. B 路线 5 agents 接口契约 / Celery 串行（B 路线 agent 必填）：
    本 agent 是 B-1/B-2/B-3/B-4/B-5 之一吗？上游 agent 输出文件 +
    输出格式 + 接收字段 + 校验方式是否全列出？Celery 串行任务依赖
    （b-3 等 b-1 + b-2 commit + merge）是否在 prompt 显式声明？
    dashboard / CI smoke 数据源与上游 5 agents 权重 schema 是否一致？
    baseline 守恒（71 PASS + 7 SKIP）联动验证通过了吗？

【v9 新增 3 项（W72 batch 派生调研实战）】
13. **W72 batch 派工调研必含"派生新任务真验证"**（v9 新增）：
    本次派工调研是否派生新任务清单（C-1 容器 rebuild / C-2 商业化 /
    C-3 ppt-word 5 缺口 等）？派生任务清单逐项 git log --grep=
    真验证了吗？派生任务清单"已完成"自报是否经 git log + grep +
    commit 引用 3 段？派生任务与原 plan 串链关系是否含 backlog docs
    路径 + Status 段引用？
14. **派工 v8 段 8 W72 起步纪律 4 项必读**（v9 新增）：
    本次派工调研 agent 是否读了 v8 段 8 W72 子 plan ③ 起步纪律 4 项
    （W71 B 路线 5 agents commit + merge 真验证 / 7 维评分数据 + KB 闭环
    验证 / UI redesign 三大件独立回归 / 13 类派工前提错误必含）？W72 起步
    纪律 4 项缺一是否立报主指挥？若缺，调研结果是否仍可信？
15. **派工必先 git log 真验证状态**（v9 新增）：
    本次派工调研 agent 是否先 git log main | grep agent-id 真验证了
    派工状态？branch-pushed ≠ merged 是否区分？D-2 partial 守恒（仅聚合
    已合并到 origin/main 的 commit + branch-pushed commit）实战类是否
    沉淀？调研文档必含"git log 真验证状态"段，缺一视为派工违规？

不填任一项视为完工未达标，主指挥合并时不视为有效交付。
```

主指挥汇总 N agents 反馈后升级 v10。新铁律按"反馈必须 15 项齐全 + 至少 1 条派工前提错误实例 + 0 条负面偏离才进入 v10 候选"规则筛选。

## §6 主指挥合并顺序表（沿用 v8 + W72 实战升级）

```text
主指挥合并链（本 agent 必须遵守）：

| 步骤 | agent-id | 任务标题 | commit 范围 | 前置依赖 | 串单链位置 | 接口契约 / Celery 依赖 |
|---|---|---|---|---|---|---|
| Step 1 | <id> | <标题> | docs/.../file.md | 基线 | — | — |
| Step 2 | <id> | <标题> | alembic/versions/070_*.py | Step 1 | base=068 down_revision=068 | — |
| Step 3 | <id> | <标题> | tests/qa-bench/scoring/seven_dim.py | 基线 | — | 输出 → B-2/B-3 |
| Step 4 | <id> | <标题> | tests/qa-bench/kb_queue/*.py | Step 3 | — | 输入 ← B-1，输出 → B-3 |
| Step 5 | <id> | <标题> | app/services/auto_intake_rollback_task.py | Step 3+4 | — | 串行：b-1 → b-2 → b-3 |
| Step 6 | <id> | <标题> | app/services/audit_trigger.py | Step 5 | — | Celery beat 调度 |
| Step 7 | <id> | <标题> | web/src/views/admin/QaBenchDashboard.vue + .github/workflows/qa-bench-smoke.yml | Step 3+4+5+6 | — | 数据源 ← B-1 7 维权重 schema |
| ... | ... | ... | ... | ... | ... | ... |

【v8 沿用】实战 5 hot-fix 必含三段串联：
- alembic 串单链：docker cp + clear cache + upgrade + restart（CLAUDE.md 752 行）
- web dist rebuild：npm run build（不是 vite build）+ git add -f dist + push
- nginx reload：若改 nginx config 必跑 nginx -t + nginx -s reload
  （或 docker compose restart nginx）

【v8 沿用】B 路线 5 agents 接口协调实战：
- B-1/B-2/B-3/B-4/B-5 五个 agent 之间接口契约（输出文件 + 输出格式 +
  接收字段 + 校验方式）必须在段 5 反馈里必填，避免 merge 后 dashboard
  / CI smoke 数据源与上游权重 schema 不一致。
- Celery 串行任务必须显式声明依赖：b-3 必等 b-1 + b-2 commit + merge
  后才启动；b-4 audit 必等 b-3 rollback_task commit 后才接。
- baseline 守恒（71 PASS + 7 SKIP）联动：任意 B agent 新增 PASS 或 SKIP
  即视为回归，主指挥必须立即报 pytest 增量表。

【v9 升级】W72 batch 实战合并顺序升级：
- W72 batch 15 agents 合并顺序必按 4 路线（A 4 + B 5 + C 3 + D 3）
  分批合并：A 路线 docs/memory 先行 → B 路线 qa-bench 新增 → C 路线
  调研沉淀 → D 路线 6 类文档同步收尾。
- B 路线新派生任务必含 Celery 串行约束（b-3 等 b-1 + b-2 commit + merge
  后才启动），与 v8 沿用一致。
- D 路线 6 类文档同步必须先聚合已合并到 origin/main 的 commit + branch-pushed
  commit（**不伪造**未实施 agent 工作内容，遵守派工 v6 §1.2 "Status 段必真验证"）。

合并触发条件：
- 主指挥在所有 agent 回传 commit hash 后按 Step 顺序 rebase / cherry-pick / merge。
- alembic 串单链中途若发现双头，停止合并并报主指挥拍板（v4 §1.1）。
- B 路线 Celery 串行任务若发现顺序错位，停止合并并报主指挥拍板。
- D 路线 6 类文档同步若发现"未实施 agent 工作内容"被伪造，停止合并并报主指挥拍板。
- agent 不主动 merge 或 push（除非派工明文授权）。

agent 完工后必须确认 commit hash 出现在顺序表的正确行；如发现顺序与派工不一致，立报主指挥。
```

合并顺序表让 agent 提前知道：(1) 谁在它前面，谁在它后面；(2) 是否需要等 alembic 上游 / B 路线上游 / SubAgent schema 上游；(3) 是否需要被 docs 下游引用；(4) 主指挥合并时如何串链；(5) 是否含 web dist rebuild + nginx reload 串联（v8）+ Celery 串行约束（v8）+ D 路线 partial 守恒（v9）。

## §7 派工前提错误复盘（v9 升级：13 类 → 16 类，24h 内必填）

```text
派工前提错误（24h 内必填，至少 16 类各 1 例）：

【v8 沿用 13 类】
| 类别 | 派工时假设 | 实际验证结果 | 修正方式 | 沉淀位置 |
|---|---|---|---|---|
| alembic 串单链 | B-1 down_revision 接 077 | 实际 merge 后 revision 重命名 070→074 | 主指挥改 063 down_revision | memory/w68-alembic-...md |
| PS 5.1 binding | 使用 --mode session | 实际传入 '--mode "session"' 被解析为多 token | 改 [string]$Mode + 严格 -eq | docs/派工 v4 §4 |
| plans 真验证 | plan Status 段标 completed | 实际未实施 (commit 4b215220 refactor 意外删除) | grep plans + git show + 审计单证 | memory/verified-plans-w68.md |
| web `npm run build` | 只需 vite build | 实际需 postbuild 自动 3 件事 + 健全性自检 + force-add dist | 禁止 vite build 直跑，postbuild 唯一合法 | docs/pwa-manifest-410.md |
| baseline 守恒 | 71 PASS + 7 SKIP | 实际增加新 PASS 或 SKIP 即视为回归 | 守恒 = 0 PASS 增 + 0 SKIP 增 | scripts/ci_qa_bench_baseline.sh |
| 浏览器老 SW cache 强制清 | 只改 nginx + 删 dist 即可 | 浏览器 SW Registration Cache 仍保留老 SW 实例，老 chunk 404 | main.js 顶部同步 unregister + 清 Cache Storage + 编译产物 grep 验证 | memory/w68-route-14-hotfix-h3-kill-old-sw-2026-07-24.md |
| PWA 永久禁用四步 | 只在 main.js 不调 useRegisterSW | vite-plugin-pwa 仍在 build 阶段注入 SW + 生成 dist 文件 | VitePWA disable: true + main.js 顶部 unregister + nginx 410 + postbuild 兼容 | memory/w68-route-14-hotfix-h2-clear-sw-2026-07-24.md |
| checkSwBlacklist self-loop | 函数还在，仅注释调用方 | 函数定义被 bundler 保留，仍 fetch + r.text() 持续调用 | 整段函数定义 + 调用方 + 相关常量一起 if(false) 包裹或彻底删除 | memory/w68-route-14-hotfix-h4-disable-sw-checkloop-2026-07-24.md |
| setInterval timer 句柄泄漏 | 写在 setup() 里跑就行 | 路由切换 / 组件 unmount 后 timer 仍跑，触发 dashboard 刷新循环 | timer 存到 ref + onUnmounted 时 clearInterval（Dashboard.vue 实战） | memory/w68-route-14-hotfix-h1-dashboard-refresh-loop-2026-07-24.md (commit 49ebe9b33) |
| heartbeat console.warn 噪声 | 保留 console.warn 让主指挥看到 | 主指挥要求完全静默，但仍要保留 timer 重置逻辑避免循环 | 只删 console.warn 那行，注释更新策略，timer 重置保留 | memory/w68-route-14-hotfix-h5-silent-heartbeat-2026-07-24.md |
| 跨 agent 接口契约 | B-1 seven_dim.py 7 维权重 + B-2 dedup embedding 余弦各自定义 | B-2 输入依赖 B-1 输出，权重 schema 不一致 → dashboard 数据源失败 | 段 5 必填接口契约表 + Celery 串行约束 + 段 6 合并顺序表新增"接口契约 / Celery 依赖"列 | memory/w71-route-71st-batch-b1-b5-interface-contract-2026-07-24.md |
| SubAgent type hint | SubAgent 输入/输出 dataclass 自动传递 | 跨 agent 串接时 Pydantic 校验报 `missing field` 或 runtime `AttributeError` | 段 3 强制 type hint grep + 段 4 编译产物 grep + 段 5 必填第 10 项 | memory/w71-route-71st-batch-c2-subagent-orch-v2-2026-07-24.md |
| 派生新任务真验证 | 主指挥口头追加子任务 → agent 自报完成 | `git log` 显示派生任务实际未派工 / 未实施 | 段 3 必先写 backlog docs + 段 5 必填第 11 项 + 真验证 3 段 | memory/w71-route-71st-batch-c1-d8-survey-2026-07-24.md |

【v9 新增 3 类（W72 batch 派生调研实战）】
| 派工 v8 段 8 W72 起步纪律必读 | W72 子 plan ③ UI redesign 派工调研必先读 v8 段 8 4 项起步纪律 | 实际派工时 W72 起步纪律被部分忽略（仅 7 维评分数据 + KB 闭环验证 2 项，未含 UI redesign 三大件独立回归 + 13 类派工前提错误） | 段 3 必先读 v8 段 8 + 段 5 必填第 14 项 + W72 起步纪律 4 项缺一不可 | memory/w72-route-72nd-batch-*.md (派工调研实战) |
| 派工调研文档必含"git log 真验证状态" | D-2 partial 守恒必含 git log 真验证 | D-2 文档同步 agent 报告"W71 15 agents 全部合并 main"但 `git log main \| grep` 仅 3 commit 落地，12 agent 仍 base HEAD `0ae74f477` 0 commit 状态（自报偏差） | 段 1.2 升级"branch-pushed ≠ merged"原则 + 段 5 必填第 15 项 + 段 6 合并顺序表 D 路线 partial 守恒 | memory/w71-route-71st-batch-d2-docs-sync-2026-07-24.md |
| B 路线 5 agents 新派生 Celery 串行 | W72 B-1..B-5 五个新派生 agent（NavRail.vue + ThinkingModeSwitch.vue + ChatBreadcrumb.vue + 商业化分析脚本 + 容器 rebuild 脚本）默认并行开发 | 实际数据流向 NavRail → ThinkingModeSwitch → ChatBreadcrumb 有先后依赖（chat engine 必须先于 breadcrumb），Celery 串行约束未在派工 prompt 显式声明 | 段 3 必含 Celery 串行约束 + 段 5 必填第 12 项升级（"派生 B 路线新任务必含 Celery 串行约束 + 数据流向图"） | memory/w72-route-72nd-batch-b1-b5-*.md (待 W72 batch 沉淀) |

沉淀规则：
- 每类前提错误必须有真实案例引用（commit hash / file path / commit message）；
- 沉淀位置统一在 memory/w68-<batch>-<route>-<topic>-<date>.md 或 memory/w71-<route>-<topic>-<date>.md 或 memory/w72-<route>-<topic>-<date>.md；
- 主指挥在 grand closure 时汇总本批所有派工前提错误，更新 CLAUDE.md 永久锚点节；
- 24h 内未填视为派工流程违规，主指挥应在下批派工前提检查清单中加严；
- v9 新增 3 类（W72 起步纪律必读 / 派生调研 git log 真验证 / B 路线新派生 Celery 串行）
  必须与 v8 原 13 类并列回填。
```

派工前提错误不是"派工失败"，而是"派工时主指挥拍板的隐含前提事后被证伪"。v9 新增 3 类已经把"W72 batch 派生调研实战（W72 起步纪律 + D-2 partial 守恒 + B 路线新派生 Celery 串行 三类实战）"全部沉淀；下一批派工（特别是 W72 派生 / W73 调研 / W74 B 路线新派生场景）必须把这些前提显式写进 prompt，避免重蹈 W72 实战事故。

## §8 v9 升级实战反馈（v9 新增，W72 batch 派工调研实战）

```text
【W72 batch 派工实战暴露 3 类新缺口】

1. W72 派工调研"派生新任务"真验证缺口：
   - 场景：W72 batch C-1（容器 rebuild 调研）+ C-2（商业化调研）+ C-3（ppt-word 5 缺口调研）
     三个 agent 派工时主指挥口头追加"派生新任务清单"作为后续 W73 派工基础
   - 问题：agent 自报完成但 `git log` 显示派生任务清单实际**只在 plan 文件内**
     未派工到独立 worktree
   - v9 修复：段 5 必填第 13 项 + 段 7 派工前提错误新增"派生调研 git log 真验证"类
   - 沉淀：memory/w72-route-72nd-batch-c1-container-rebuild-*.md +
     memory/w72-route-72nd-batch-c2-monetization-*.md +
     memory/w72-route-72nd-batch-c3-ppt-word-gaps-*.md (待 W72 batch 沉淀)

2. W72 派工调研"git log 真验证状态"缺口：
   - 场景：W72 batch D-2 文档同步 agent 报告"W71 15 agents 全部合并 main"
   - 问题：`git log main | grep` 仅 3 commit 落地，12 agent 仍 base HEAD
     `0ae74f477` 0 commit 状态（自报偏差）
   - v9 修复：段 1.2 升级"branch-pushed ≠ merged"原则 + 段 5 必填第 15 项
     + 段 6 合并顺序表 D 路线 partial 守恒
   - 沉淀：memory/w71-route-71st-batch-d2-docs-sync-2026-07-24.md (W71 D-2 partial 守恒实战)

3. W72 派工 B 路线 5 agents 串单链"Celery 串行约束"缺口：
   - 场景：W72 batch B-1..B-5 五个新派生 agent（NavRail.vue + ThinkingModeSwitch.vue
     + ChatBreadcrumb.vue + 商业化分析脚本 + 容器 rebuild 脚本）派工
   - 问题：Celery 串行约束未在派工 prompt 显式声明，agent 默认并行开发；
     数据流向 NavRail → ThinkingModeSwitch → ChatBreadcrumb 有先后依赖
     （chat engine 必须先于 breadcrumb）
   - v9 修复：段 3 B 路线 5 agents 接口协调升级"派生 B 路线新任务必含 Celery
     串行约束 + 数据流向图" + 段 5 必填第 12 项升级
   - 沉淀：memory/w72-route-72nd-batch-b1-b5-*.md (待 W72 batch 沉淀)

【W72 派工 4 路线 15 agents 调研必含】
- A 路线（A-1/A-2/A-3/A-4）：主拍部署 + 派工纪要 v9 + plans 调研 + grand closure
- B 路线（B-1/B-2/B-3/B-4/B-5）：子 plan ② 实施（NavRail + ThinkingModeSwitch
  + ChatBreadcrumb + 商业化分析 + 容器 rebuild）
- C 路线（C-1/C-2/C-3）：调研与小修（容器 rebuild 调研 + 商业化调研 + ppt-word 5 缺口）
- D 路线（D-1/D-2/D-3）：收尾与拍板（派工 v10 反馈 + 6 类文档同步 + 锚点范式收束）

【W72 派工 0 production code 改动铁律 14/15 守恒预期】
- 14/15 守恒：路线 A + C + D 完全维持（纯 docs/memory/scripts/ 范畴）
- 1/15 例外已批：B-1 NavRail.vue 涉及路由级双栈改造（桌面 EP + 移动 NutUI），
  算 web 例外清单允许（不动老 view）
- 例外不扩大到老路径重构：app/services/task_service.py / meeting_service.py /
  knowledge_service.py 0 改动，alembic 老迁移 0 改动，app/agent/chat_engine.py 0 改动
- W19 选项 A 维持：4 留未来 PR（Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E）
  不发起新排期

【W72 派工调研实战反馈显式沉淀 3 类】
- v9 段 7 升级 16 类（v8 13 类 + v9 3 类）
- v9 段 5 升级 15 项（v8 12 项 + v9 3 项）
- v9 段 6 升级合并顺序表 D 路线 partial 守恒 + B 路线新派生 Celery 串行约束
```

W72 batch 派工调研实战反馈是 v9 升级的核心增量。W72 batch 实战发现：v8 段 8 缺"W72 batch 派生调研实战反馈"段，导致 W72 派工调研 agent 不知道主指挥派工时的隐含前提（"派生新任务清单"必须 git log 真验证、"D-2 partial 守恒"必须 git log main | grep、"B 路线新派生任务"必须含 Celery 串行约束）。v9 新增段 8 显式列出 3 类 W72 实战缺口 + 4 路线调研必含 + 14/15 守恒预期 + 3 类实战反馈沉淀，把"W72 batch 派工调研实战反馈"从主指挥口头约定升级到派工模板强制约束。

## §9 兼容性矩阵（v8 → v9 升级路径）

| 版本 | 兼容 v9? | 升级路径 |
|---|---|---|
| v1 | 否 | 整模板替换为 v9 |
| v2 | 否 | 整模板替换为 v9 |
| v3 | 否 | 整模板替换为 v9 |
| v4 | 部分（缺段 5/6/7/8/9）| 段 5 升级 15 项 + 段 6 + 段 7 16 类 + 段 8 v9 升级实战 + 段 9 v9 实战反馈 |
| v5 | 部分（缺段 7/8/9）| 段 7 16 类 + 段 8 + 段 9 |
| v6 | 部分（缺段 5/7/8/9）| 段 5 15 项 + 段 7 16 类 + 段 8 + 段 9 |
| v7 | 部分（缺段 3/4/5/7 升级 + 段 8/9）| 段 3 SubAgent 接口 + 段 4 type hint grep + 段 5 升级 12 项 + 段 7 升级 13 类 + 段 8 W72 起步 + 段 9 v9 实战 |
| v8 | 几乎兼容（缺段 5/7 升级 + 段 9）| 段 5 升级 15 项 + 段 7 升级 16 类 + 段 9 v9 升级实战 |
| v9（目标版本）| — | — |

## §10 v9 发布前自检清单

- [ ] 段 1 写清角色、范围、不变量、当前分支、基线 commit、依赖 agent。
- [ ] 段 1 含 B 路线 5 agents 接口契约 + 派生新任务清单 + 派工调研 git log 真验证（v8/v9 升级）。
- [ ] 段 2 列出文件、规模和禁止修改项。
- [ ] 段 2 含 SubAgent 编排 type hint 强制约束 + 派生新任务真验证 3 段（v8/v9 升级）。
- [ ] 段 3 含 plans grep 和 Alembic heads 前置检查。
- [ ] 段 3 写明双头必须报主指挥，不能私改。
- [ ] 段 3 含"前端任务 5 hot-fix 链路检查" + "PWA / SW 状态检查"（v8 沿用）。
- [ ] 段 3 含"SubAgent 编排接口" + "B 路线 5 agents 接口协调" + "W72 起步纪律 4 项必读"（v8/v9 升级）。
- [ ] 段 4 含 PS 5.1 三项 binding 约束。
- [ ] 段 4 显式 "web 改动必须 `npm run build`，禁止 vite build 直跑"。
- [ ] 段 4 含"web 改动必 grep 验证" + "runtime 心跳 / setInterval 策略"（v8 沿用）。
- [ ] 段 4 含"SubAgent type hint 编译产物 grep" + "派生新任务真验证 grep"（v8/v9 升级）。
- [ ] 段 5 必填 15 项提示词齐全（v8 12 项 + v9 3 项）。
- [ ] 段 5 含"15 项缺一不可"约束。
- [ ] 段 6 含合并链表格 + alembic 串单链位置列。
- [ ] 段 6 含"实战 5 hot-fix 必含 alembic + dist rebuild + nginx reload 三段串联"（v8 沿用）。
- [ ] 段 6 含"B 路线 5 agents 接口契约 / Celery 串行"列 + Celery 串行约束 + D 路线 partial 守恒（v8/v9 升级）。
- [ ] 段 6 含"agent 不主动 merge / push"约束。
- [ ] 段 7 必填 16 大类派工前提错误（v8 13 类 + v9 3 类）。
- [ ] 段 7 沉淀规则统一在 memory/。
- [ ] 段 7 24h 内未填视为派工违规。
- [ ] 段 8 v9 升级实战反馈（W72 batch 派生调研实战 3 类新缺口 + 4 路线调研必含 + 14/15 守恒预期 + 3 类实战反馈沉淀）。
- [ ] 文档任务完成 `git diff --check`。
- [ ] migration 合并完成后只有一个 head。
- [ ] plans 调研结果有 backlog docs 或 COMPLETED 真 commit。
- [ ] web 改动 grep 验证关键字符串次数 ≥ 0 / ≤ 1（v8 沿用）。
- [ ] SubAgent 编排 type hint grep ≥ 1 + 派生新任务真 commit hash 引用 ≥ 1（v8/v9 升级）。
- [ ] 段 5 反馈至少收到 N ≥ 5 agents 才能汇总升级 v10。
- [ ] 锚点范式变化显式追踪（段 5 第 6 项 + 段 7 第 16 类）。

## §11 v9 默认应用范围

- **W68 第 14 批 H-1~H-5 已应用 v6 / v7**：commit `49ebe9b33` / `3207aea62` / `72eaae07f` / `ff9b6b3e2` / `960f8abe1` / `85619c012`。
- **W71 batch 派工**：默认 v7；实战暴露 v7 三层缺口（B 路线 5 agents 接口协调 / SubAgent type hint / 派生任务真验证），v8 必含。
- **W72 batch 派工**：默认 v8；实战暴露 v8 三层缺口（派生调研真验证 / W72 起步纪律必读 / git log 真验证状态），v9 必含。
- **W73 batch 派工**：默认 v9；尤其是 B 路线新派生 / SubAgent 编排 / 派生调研场景，必须把对应 v9 段 3/4/5/6/7/8 门禁原样写进 prompt。
- **W74+ 调研任务**：必须用 v9（避免派生调研自报偏差 + W72 起步纪律缺失 + B 路线新派生 Celery 串行缺失）。

## §12 9 条新铁律（v9 沉淀，4 类合并展示）

v9 在 v8 9 条铁律基础上新增/升级：

1. **段 5 反馈必填 15 项**（v8 升级 v9）——agent 完工回传必须含段 5 v9 15 项必填（v8 原 12 项 + 派生调研真验证 / 派工 v8 段 8 W72 起步纪律 4 项必读 / 派工必先 git log 真验证状态 3 项），否则视为"完工未达标"。
2. **段 6 合并顺序表必含 alembic 串单链 + web dist rebuild + nginx reload 三段串联 + B 路线 Celery 串行约束 + D 路线 partial 守恒**（v8 升级 v9）——前端任务必须显式含"npm run build + git add -f dist + push"步骤；nginx 改动必跑 `nginx -t + nginx -s reload`；B 路线 5 agents 必含 Celery 串行依赖（b-3 等 b-1 + b-2 commit + merge）；D 路线 6 类文档同步必须先聚合已合并到 origin/main 的 commit + branch-pushed commit（**不伪造**未实施 agent 工作内容）。
3. **v9 默认应用从 W73 batch 开始**（v8 升级 v9）——任何 W73 及以后的派工必须使用 v9；W74+ 调研任务**必须**用 v9。
4. **段 7 派工前提错误必含 16 大类**（v8 升级 v9）——v8 13 类 + v9 新 3 类（W72 起步纪律必读 / 派生调研 git log 真验证 / B 路线新派生 Celery 串行）。任何派工必含这 16 类前提的隐含假设。
5. **SubAgent 编排接口必含 type hint**（v8 沿用）——所有 SubAgent 输入/输出 dataclass / Pydantic schema 必须有完整 type hint（`from typing import ...`）；跨 agent 串接时必跑 `model_validate(sample)` 校验；新加字段 keyword-only + Optional 默认 None；编译产物 grep 验证 type hint 出现次数 ≥ 1。
6. **派生新任务必含真验证**（v8 沿用 + v9 升级）——主指挥口头追加子任务时，agent 必先写 backlog docs（`C:/Users/pc/.claude/plans/<plan-keyword>.md` + Status 段 + 真验证命令）；完工后必含 git log + grep + commit 引用 3 段真验证。**v9 升级**：派工调研 agent 派生新任务清单必逐项 git log --grep 真验证；派生任务"已完成"自报必须经 3 段真验证。
7. **B 路线 5 agents 接口协调必走 Celery 串行 + 接口契约表 + 数据流向图**（v8 升级 v9）——B-1/B-2/B-3/B-4/B-5 五个 agent 之间接口契约（输出文件 + 输出格式 + 接收字段 + 校验方式）必须在段 5 反馈里必填；Celery 串行任务必须显式声明依赖（b-3 等 b-1 + b-2 commit + merge 后才启动）；dashboard / CI smoke 数据源与上游 5 agents 权重 schema 一致。**v9 升级**：派生 B 路线新任务必含 Celery 串行约束 + 数据流向图。
8. **W72 起步纪律必走 4 项必含 + 4 项派工必写 + 3 项 24h 必填**（v8 沿用）——W72 子 plan ③ UI redesign 派工前必读段 8；W71 B 路线 5 agents 全部 commit + merge 后才启动；7 维评分数据 + KB 闭环回归必通过；NavRail / ThinkingModeSwitch / ChatBreadcrumb 三大件独立回归必通过。
9. **v9 升级实战反馈必走 3 类新缺口显式沉淀**（v9 新增）——W72 batch 派工调研实战暴露 3 类新缺口（派生调研真验证 / W72 起步纪律必读 / git log 真验证状态）必须在段 8 显式沉淀；任何 W73+ 派工调研必读段 8 实战反馈；派生新任务清单逐项 git log --grep 真验证；D 路线 6 类文档同步必须先聚合已合并到 origin/main 的 commit + branch-pushed commit。

## 结语

v9 不是替换 v8，而是补一段让模板"W72 batch 派生调研实战反馈（W72 起步纪律 + 派生调研 git log 真验证 + B 路线新派生 Celery 串行 三类实战）派工前提显式沉淀 + 反馈颗粒度强制提升到 15 项 + 段 6 合并顺序表新增 D 路线 partial 守恒 + 段 8 v9 升级实战反馈"。段 5 升级让 agent 反哺模板更具体（含派生调研真 commit 引用 + W72 起步纪律 4 项必读 + git log 真验证状态），段 7 让主指挥派工的隐含前提（W72 实战 16 类）事后被显式记录。这样 W73 batch + W74/W75 派工可以基于"经过 W72 B 路线 5 agents + SubAgent 编排 + 派生任务 + 派生调研 + W72 起步纪律实战反馈的模板 + 经过 16 类前提沉淀的纪律 + 经过段 8 v9 实战反馈强约束的命令"启动下一轮，更可预测、更易追溯、更不易合并错。

---

**版本 v9，2026-07-24/27，W72nd batch A-2 起草，主指挥合并后正式生效。**

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**