# W72 派工纪要：Prompt Template v10

> 版本：v10（2026-07-27）
> 适用：主指挥、并行 agent、文档/调研/迁移/SubAgent 编排/商业化调研派工
> 沿用：v9 12 段全部 + 段 5 升级 15 → **18 项**必填 + 段 6 升级 13 → **14 段**合并顺序表 + 段 7 升级 16 → **19 类**派工前提错误 + 段 8 升级 4 → **6 项**起步纪律 + **新增段 9 W72 第 1 批实战 11 commit 锚点范式纪律**
> 原则：先验证、再派工；先串链、再合并；先反馈、再升级；合并顺序可见；派工前提错误必沉淀；**W72 第 1 批 11 commit 实战反馈强制入模板**；commit message 必含锚点范式数字；W73+ 派工必须用 v10。

## TL;DR（v9 → v10 升级理由）

W72 第 1 批实战（锚点范式 W71 206 → W72 第 1 批 220，14 守恒，11 commit 全部 commit message 含锚点范式数字）暴露 v9 四层缺口，v10 必含：

1. **SubAgent 编排 type hint 实战缺口**：v9 段 5 第 10 项已含原则但缺"跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md"实战类。W72 第 1 批 B-2 commit `228aa9de3`（ThinkingModeSwitch + ChatBreadcrumb + useUiStore v-model）实战暴露：TypeScript interface 缺 `@deprecated` 警告导致老接口未明示弃用，跨 worktree 接口契约无集中文档。v10 必含"TypeScript interface 必带 @deprecated 警告 + 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md"。

2. **派工 4 阶段流程 v2 缺口**：v9 段 1.1 沿用 v8 4 阶段流程（plan list → 拍板 → 实施 → 收口），但 W72 第 1 批 C-1 commit `08df36e80`（容器镜像 rebuild 调研）+ C-2 commit `a78967661`（商业化 24 人月季度排期调研）+ C-3 commit `f1947d3c7`（ppt-word 5 缺口调研）实战暴露"派生新任务"环节未独立显式（v9 段 8 已含反馈但流程图未升级）。v10 必显式"派工 4 阶段流程 v2（plan list → 拍板 → 派生新任务 → 收口）"。

3. **0 production code 改动铁律 14/15 守恒预期表缺口**：v9 段 8 含"14/15 守恒预期"原则但缺独立表格。W72 第 1 批 D-2 commit `02b7b4dcb`（6 类文档同步）实战发现：B-1 NavRail.vue + B-3 ChatViewSSE.vue + B-5 桌面 ChatViewSSE 顶栏 6 主题 dark mode 共 3 例外已批，但仍需明确"哪些算例外 / 例外上限 1/N 守恒"。v10 必含"0 production code 改动铁律 14/15 守恒预期表（明示每条例外 commit + 文件 + 例外理由）"。

4. **W73/W74 派工顺序表缺口**：v9 段 8 含"4 路线调研必含"但缺"W73/W74 派工顺序表"。W72 第 1 批 C-3 commit `f1947d3c7`（ppt-word 5 缺口）实战发现：缺口 5 含 PR2/PR3/PR5/PR7 + 缺口 5 命名错位，必派工 W73/W74 顺序表（先 W73 调研 → 后 W74 实施），但 v9 无独立 W73/W74 派工顺序段。v10 必含"W73/W74 派工顺序表（v10 段 6 新增 14 段 + v10 段 8 新增 6 项起步纪律 v10 实战预测）"。

**v10 增量**：
- 段 5：升级 15 → **18 项**必填（+ SubAgent type hint 实战 / TypeScript @deprecated / 跨 worktree 接口契约 / 4 阶段流程 v2 / 0 production code 表 / W73/W74 顺序 6 项）
- 段 6：升级 13 → **14 段**合并顺序表（+ 段 14 商业化 B-5 必先于 D-2 doc sync）
- 段 7：升级 16 → **19 类**派工前提错误（+ 命名错位 plan 必重定义差量缺口 / `vite build` 直跑必坏 PWA / commit message 必含锚点范式数字 3 类）
- 段 8：升级 4 → **6 项**起步纪律（+ 商业化 docker base 起步 / gap analysis 文档恢复 2 项）
- **新增段 9**：W72 第 1 批 11 commit 锚点范式数字纪律（11 commit 全部含锚点范式数字 + commit message 实战模板 + W73+ commit message 守恒）

v10 默认应用从 W73 batch 开始；W74+ 调研任务**必须**用 v10；commit message 必含锚点范式数字（v10 段 9 强制约束）。

## §1 角色、范围与不变量（沿用 v9 + 派工 v10 升级）

```text
你是 Agent <编号>：<标题>。目标是 <一句话目标>。
范围：<文件/目录>；不范围：<明确排除项>。
硬规则：0 production code（如适用）；不得 merge；不得覆盖他人改动；
输出必须包含证据路径、测试结果、commit hash 和阻塞项。
当前分支：<worktree 分支名>；基线 commit：<hash>；
依赖 agent：<agent-id>（说明是否等待其 commit）。

【v10 升级】若本 agent 是 B 路线 5 agents 之一，必须在 prompt 里同时列出
<B-1/B-2/B-3/B-4/B-5> 接口契约文件路径（docs/w72-b-route-interfaces.md）
+ 数据格式约定 + Celery 串行约束 + TypeScript interface 必带 @deprecated 警告；
若有派生新任务（主指挥口头追加），必须列出派生任务清单 + 真验证命令
（git log + grep + commit 引用 3 段，缺一不可）+ W73/W74 派工顺序表；
若有派工调研任务，必须列出调研状态真验证命令（git log main | grep agent-id
+ git show commit-hash 3 段）+ 0 production code 改动铁律 14/15 守恒预期表。
```

## §2 交付物与操作边界（沿用 v9 + 派工 v10 升级）

```text
交付物：
1. <文件一>：<内容和大致规模>
2. <文件二>：<内容和大致规模>
禁止：<代码/配置/数据库/部署等不应修改的对象>。

【v10 升级】若涉及 SubAgent 编排接口，必含 type hint 字段 + @deprecated 警告：
- 所有 SubAgent 输入/输出 dataclass 必须有完整 type hint（`from typing import ...`）
- TypeScript interface 必带 `@deprecated` 警告标记老接口（W72 B-2 实战暴露 TypeScript 缺弃用标记）
- 跨 agent 数据传递必须用 Pydantic BaseModel 显式 schema（防 `missing field` 500）
- 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md（W72 第 1 批 B-2 实战）
- 编译产物 grep 验证 type hint 出现次数 ≥ 1（避免被 minify 吃掉）
- 编译产物 grep 验证 @deprecated 标记 ≥ 1（避免被 minify 吃掉）

【v10 升级】若涉及派生新任务清单，必含派生任务真验证 3 段 + W73/W74 顺序：
- 派生任务清单逐项 `git log --grep="<派生任务 keyword>"` 输出
- 派生任务实际 commit hash + 简述
- 派生任务与原 plan 串链关系（backlog docs 路径 + Status 段引用）
- 派生新任务必派工 W73/W74 顺序表（先 W73 调研 → 后 W74 实施）
```

若需要脚本，列出运行时版本（Windows PowerShell 5.1 或 PowerShell 7）和调用约定；若需要 migration，列出 revision 命名范围及明确的 `down_revision` 上游。

## §3 任务描述、前置验证与风险门禁（沿用 v9 + W72 第 1 批实战升级）

```text
开始前：
- git status；确认基线没有未授权修改。
- plans 任务：grep -rn "<keyword>" C:/Users/pc/.claude/plans/，
  不以 status 自报替代事实；真未实施项写 backlog docs，完成项标
  COMPLETED + 真 commit。
- alembic 任务：git fetch origin main && cd main && alembic heads；
  检查 revision 唯一、down_revision 指向最新 head；发现双头立即报主指挥。
- 前端任务（v8/v9 沿用）：git fetch origin main && 检查 5 hot-fix 链路
  （H-1 dashboard timer / H-2 nginx 410 / H-3 main.js unregister /
  H-4 checkSwBlacklist 删除 / H-5 heartbeat 静默）是否全在基线；如不是，
  不能贸然修前端，**先复现根因**再决定走哪种修复路径。
- PWA / SW 状态（v8/v9 沿用）：若任务涉及 SW 或 PWA，必先确认
  `vite-plugin-pwa` 是否 `disable: true`、nginx `/sw.js` `/registerSW.js`
  `/manifest.webmanifest` 是否 410、本地 main.js 顶部是否 unregister + 清 cache。
  必用 `npm run build`（唯一合法命令，PWA 410 铁律），**禁止 `vite build` 直跑**
  （绕开 postbuild → 服务器 410 + PWA install 失败）——v10 段 7 第 18 类必填。

【v10 升级】W72 起步纪律 6 项必读（v9 4 项 → v10 6 项）：
- W71 B 路线 5 agents commit + merge 真验证：
  git log --oneline main | grep -E "w71st-batch-(b1|b2|b3|b4|b5)"
  期望 ≥ 5 commits 输出
- W71 子 plan ② 7 维评分数据 + KB 闭环验证：
  QaBenchDashboard 数据拉取 + KB 闭环审计触发写入
- W72 子 plan ③ UI redesign 三大件（NavRail + ThinkingModeSwitch + ChatBreadcrumb）
  起步前必读 v9 段 8 + v10 段 9（W72 第 1 批 11 commit 实战）
- W72 batch 派工调研真验证（v9 沿用 + v10 升级）：派工调研 agent 必先 git log
  真验证派工状态，缺一不可
- 商业化 docker base 起步必先（v10 新增）：商业化 B-5 起步必先 docker base
  商业化版（不算 0 production code 改动），WAIT 商业化 docker base commit 后
  才启动 B-5
- gap analysis 文档必先恢复/重建（v10 新增）：缺口 5 教训（ppt-word PR2/PR3/
  PR5/PR7 + 缺口 5 命名错位）必先 gap analysis 文档恢复/重建再启动 W73 调研

【v10 升级】SubAgent 编排接口（v9 沿用 + v10 实战）：
- 若本 agent 涉及 SubAgent 输入/输出 dataclass 或 Pydantic schema，
  必先 grep 老 schema 看是否齐全 type hint：
  `grep -rnE "dataclass|BaseModel" <本 agent 范围> --include="*.py"`
- 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md（W72 B-2 commit
  `228aa9de3` 实战，TypeScript interface 必带 @deprecated 警告）
- TypeScript interface 必带 `@deprecated` 警告标记老接口（W72 B-2 实战暴露）
- 跨 agent 串接时必先验证 schema 兼容：
  `python -c "from app.schemas.<x> import <Y>; Y.model_validate(<sample>)"`
- 新加字段必须用 keyword-only（防位置参数歧义）+ Optional 默认 None（防缺字段 500）
- 派生新任务（主指挥口头追加子任务）必先写 backlog docs：
  `C:/Users/pc/.claude/plans/<plan-keyword>.md` + Status 段
  + 真验证命令（git log + grep + commit 引用 3 段）

【v10 升级】B 路线 5 agents 接口协调（v9 沿用 + v10 新派生任务实战）：
- 若本 agent 是 B-1/B-2/B-3/B-4/B-5 之一，必先列出接口契约表（v10 升级）：
  | 上游 agent | 输出文件 | 输出格式 | 本 agent 接收字段 | 校验方式 |
- Celery 串行任务必先确认依赖：b-3 必等 b-1 + b-2 commit + merge 后才启动
- dashboard / CI smoke 必先确认上游 5 agents commit + 测试基线守恒
- 【v10 新增】派生 B 路线新任务必含 Celery 串行约束 + 数据流向图
- 【v10 新增】TypeScript interface 必带 @deprecated 警告（跨 worktree 接口契约）

- 其他任务：<领域特定检查>。
```

迁移 agent 不得自动替换有争议的 down_revision；必须给出冲突矩阵。合并后由主指挥 rebase 重命名（如 070→075/074/076）、串单链并再跑 heads。

## §4 完成定义、测试与 PS 5.1 约束（沿用 v9 + v10 升级）

```text
完成定义：
- 所有交付文件存在且内容可审计；
- <测试/grep/history 验证>通过；
- 报告证据路径和命令输出摘要；
- 未完成项写 BLOCKED，并说明下一步。
- web 改动必须 `npm run build`（唯一合法命令，PWA 410 铁律），
  禁止 `vite build` 直跑（绕开 postbuild → 服务器 410 + PWA install 失败）。
  ——v10 段 7 第 18 类必填（CLAUDE.md 永久锚点 2026-07-11）。
- web 改动必须 grep 验证（v9 沿用）：编译产物里禁用项 grep 为 0，
  保留项 grep ≥ 1。例：H-4 派工要求编译后 checkSwBlacklist=0,
  SW content OK=0, SKIP_WAITING=0, unregister=1。
- runtime 心跳 / console 噪声（v9 沿用）：若任务涉及 setInterval
  或 console.warn，主指挥要求"静默"时**只删 console.warn**，保留
  timer 重置逻辑（避免 W68 H-5 heartbeat 循环 bug）。

【v10 升级】派生新任务真验证 grep（v9 沿用 + v10 升级）：
- 派生任务清单逐项 git log + grep 输出
- 派生任务实际 commit hash 引用 ≥ 1
- 派生任务与原 plan 串链关系（backlog docs 路径 + Status 段引用）≥ 1
- 【v10 新增】派生任务必含 W73/W74 派工顺序表（先 W73 调研 → 后 W74 实施）

【v10 升级】commit message 锚点范式数字必填（v10 段 9 实战模板）：
- commit message 必含锚点范式数字（如"锚点范式第 N 守恒"）
- commit message 必含 W72 第 1 批实战引用（如 commit hash 或具体路线 B-1/B-2/B-3/B-4/B-5）
- 11 commit 实战模板：
  `feat(w72nd-batch-b<N>): <标题> (~<行数> 行, <要点> + type hint 必含, <测试> PASS, 锚点范式第 N 守恒)`
- 调研类 commit message 模板：
  `chore(w72nd-batch-c<N>): <标题> (<调研主题>, <调研发现> + <派生新任务> + W73/W74 派工顺序, 锚点范式第 N 守恒)`
- 文档/沉淀类 commit message 模板：
  `docs(w72nd-batch-d<N>): <标题> (<6 类文档同步>, 锚点范式 W71 206 → W72 220 守恒预期 +N, 0 production code 改动铁律 N/15 守恒)`
```

PowerShell 5.1：使用 --mode <value>（空格），[string]$Mode，仅用 $Mode -eq 'session' 判断 session；附两种模式实跑证据。

完成定义不能只写"代码已写"或"测试通过"。测试需说明是单元、集成、静态检查还是人工检查，以及是否受环境限制。对于 docs-only 任务，至少做文件计数、关键词检查、git diff --check。

## §5 经验反馈循环（v10 升级：15 项 → 18 项必填）

```text
回传反馈（必填，18 项缺一不可）：

【v9 沿用 15 项】
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
13. W72 batch 派工调研必含"派生新任务真验证"（v9 沿用）：
    本次派工调研是否派生新任务清单（C-1 容器 rebuild / C-2 商业化 /
    C-3 ppt-word 5 缺口 等）？派生任务清单逐项 git log --grep=
    真验证了吗？派生任务清单"已完成"自报是否经 git log + grep +
    commit 引用 3 段？派生任务与原 plan 串链关系是否含 backlog docs
    路径 + Status 段引用？
14. 派工 v8 段 8 W72 起步纪律 4 项必读（v9 沿用）：
    本次派工调研 agent 是否读了 v8 段 8 W72 子 plan ③ 起步纪律 4 项
    （W71 B 路线 5 agents commit + merge 真验证 / 7 维评分数据 + KB 闭环
    验证 / UI redesign 三大件独立回归 / 13 类派工前提错误必含）？W72 起步
    纪律 4 项缺一是否立报主指挥？若缺，调研结果是否仍可信？
15. 派工必先 git log 真验证状态（v9 沿用）：
    本次派工调研 agent 是否先 git log main | grep agent-id 真验证了
    派工状态？branch-pushed ≠ merged 是否区分？D-2 partial 守恒（仅聚合
    已合并到 origin/main 的 commit + branch-pushed commit）实战类是否
    沉淀？调研文档必含"git log 真验证状态"段，缺一视为派工违规？

【v10 新增 3 项（实为 6 项中的关键 3 项，原文段 5 已有 12+3=15 项，v10 升级到 18 项）】
16. **SubAgent 编排 type hint 实战必填**（v10 新增）：
    本次任务是否在跨 worktree 接口契约中显式声明 TypeScript interface
    必带 @deprecated 警告（W72 B-2 commit `228aa9de3` 实战暴露）？
    是否走 docs/w72-b-route-interfaces.md 集中管理？编译产物 grep
    `@deprecated` 出现次数 ≥ 1（避免被 minify 吃掉）？TypeScript
    interface 跨 worktree 串接时是否跑过 schema 校验（Vite plugin
    transform 阶段 / Vitest mock）？新增字段是否 keyword-only +
    Optional 默认 None（防 `missing field` 500）？
17. **派工 4 阶段流程 v2 必填**（v10 新增）：
    本次派工调研是否走 4 阶段流程 v2（plan list → 拍板 → 派生新任务 →
    收口）？派生新任务环节是否独立显式（含派生任务清单逐项 git log
    真验证 + 派生任务与原 plan 串链关系 + W73/W74 派工顺序表）？
    调研 agent 是否在段 5 反馈里必填 4 阶段流程 v2 实操记录？
    0 production code 改动铁律 14/15 守恒预期表是否每条例外明示
    （commit hash + 文件 + 例外理由）？
18. **W73/W74 派工顺序表 + commit message 锚点范式数字必填**（v10 新增）：
    本次派工调研是否含 W73/W74 派工顺序表（先 W73 调研 → 后 W74 实施）？
    commit message 是否含锚点范式数字（如"锚点范式第 N 守恒"）+ W72
    第 1 批实战引用（如 commit hash 或 B-1/B-2/B-3/B-4/B-5 路线）？
    11 commit 实战模板（W72 第 1 批）是否复用？调研类 commit 是否含
    "派生新任务" + "W73/W74 派工顺序"段？
```

合并顺序表让 agent 提前知道：(1) 谁在它前面，谁在它后面；(2) 是否需要等 alembic 上游 / B 路线上游 / SubAgent schema 上游；(3) 是否需要被 docs 下游引用；(4) 主指挥合并时如何串链；(5) 是否含 web dist rebuild + nginx reload 串联（v8）+ Celery 串行约束（v8）+ D 路线 partial 守恒（v9）+ 商业化 B-5 必先于 D-2 doc sync（v10 段 6 第 14 段新增）。

## §6 合并顺序表（v10 升级：13 段 → 14 段）

```text
【v9 沿用 13 段合并顺序表】

| 阶段 | 内容 | 关联 commit | 是否 alembic / web dist / 派生 Celery | merge 顺序约束 |
|---|---|---|---|---|
| 1. 起点 (alembic 077 + main HEAD) | 077 已 merge | W68 第 13 批 C-3 commit `63d38cc87` | alembic 单链起点 | 必先合并 |
| 2. alembic 066-069 rebase 串单链 | 066/067/068/069 已 merge | W68 第 11 批 commit `ac736a1e9` | alembic 串单链 | 必接 077 |
| 3. 主指挥部署收口 | docs + scripts + memory | W68 第 14 批 A-1 | — | 必先合并 |
| 4. 派工纪要 v8 → v9 | docs + memory | W72 A-2 commit `717d47f08` + `937742218` | — | 必先合并 |
| 5. plans 真验证调研 | docs + memory | W72 A-3 commit `206661254` + `911445ebf` | — | 必先合并 |
| 6. grand closure memory 预期 | memory | W72 A-4 commit `7a1d07df8` | — | 必先合并 |
| 7. B-1..B-5 Celery 串行 | qa-bench 新增 | W71 B-1..B-5 commit `47f8b9c9b` / `0cc1e2699` / `aed47632f` / `bd74f951c` / `ac7946ef6` | Celery 串行 b-3 等 b-1+b-2 | 必串行合并 |
| 8. C-1..C-3 调研沉淀 | docs + scripts | W71 C-1..C-3 commit `94502a664` / `66d68af36` / `495e72b6d` | — | 必先聚合已合并 commit |
| 9. W72 B-1..B-5 派生 UI 三大件 | web + components | W72 B-1..B-5 commit `4f737b61a` / `228aa9de3` / `1a33b816e` / `6c6f7b794` / `b7ad730a6` | Celery 串行 + TypeScript @deprecated | 必串行合并 |
| 10. C-1..C-3 派生调研 | docs + scripts + memory | W72 C-1..C-3 commit `08df36e80` / `a78967661` / `f1947d3c7` | — | 必先聚合已合并 commit |
| 11. D-1 派工 v10 反馈 | docs | W72 第 2 批 D-1（待） | — | 必接 C 路线后 |
| 12. D-3 锚点范式守恒 | memory | W72 D-3 commit `41fe8f0f9` | — | 必接 D-1/D-2 后 |
| 13. D-2 6 类文档同步 | docs + memory | W72 D-2 commit `02b7b4dcb` | D 路线 partial 守恒 | 必聚合已合并 commit |

【v10 新增 1 段：商业化 B-5 必先于 D-2 doc sync】

| 14. 商业化 B-5 必先于 D-2 doc sync（v10 新增）| 商业化 B-5 docker base + 商业化版调研 | W72 第 2 批 B-5（待派工）| 商业化 docker base 必先 docker commit + push + webhook 部署 | 必先于 D-2 doc sync 合并 |
```

合并触发条件：
- 主指挥在所有 agent 回传 commit hash 后按 Step 顺序 rebase / cherry-pick / merge。
- alembic 串单链中途若发现双头，停止合并并报主指挥拍板（v4 §1.1）。
- B 路线 Celery 串行任务若发现顺序错位，停止合并并报主指挥拍板。
- D 路线 6 类文档同步若发现"未实施 agent 工作内容"被伪造，停止合并并报主指挥拍板。
- 商业化 B-5 必先于 D-2 doc sync 合并（v10 新增第 14 段）。
- agent 不主动 merge 或 push（除非派工明文授权）。

agent 完工后必须确认 commit hash 出现在顺序表的正确行；如发现顺序与派工不一致，立报主指挥。

## §7 派工前提错误复盘（v10 升级：16 类 → 19 类，24h 内必填）

```text
派工前提错误（24h 内必填，至少 19 类各 1 例）：

【v9 沿用 16 类】
1. alembic 串单链（v4）
2. PS 5.1 binding（v4）
3. plans 真验证（v4）
4. web `npm run build`（v4）
5. baseline 守恒（v4）
6. 浏览器老 SW cache 强制清（v8）
7. PWA 永久禁用四步（v8）
8. checkSwBlacklist self-loop（v8）
9. setInterval timer 句柄泄漏（v8）
10. heartbeat console.warn 噪声（v8）
11. 跨 agent 接口契约（v8）
12. SubAgent type hint（v8）
13. 派生新任务真验证（v8）
14. 派工 v8 段 8 W72 起步纪律必读（v9）
15. 派工调研文档必含"git log 真验证状态"（v9）
16. B 路线 5 agents 新派生 Celery 串行（v9）

【v10 新增 3 类（W72 第 1 批实战 11 commit 反馈）】
17. **命名错位 plan 必重定义"差量缺口"**（v10 新增）：
    - 场景：W72 第 1 批 C-3 commit `f1947d3c7`（ppt-word 5 缺口调研）
      实战暴露：ppt-word 5 缺口实际是 PR2 sharing + PR3 comment v2 + PR5 trash
      + PR7 request + 缺口 5，命名"5 缺口"与实际内容不符（缺口 5 命名错位）
    - 假设：命名错位 plan 必重定义"差量缺口"（plan 标题 vs 实际调研内容）
    - 修正：段 1 角色范围必含"plan 标题 vs 实际内容是否一致"自检 +
      段 3 plans grep 必含命名 vs 实际 diff 段 + 段 5 第 16 项必填
    - 沉淀：memory/w72-route-72nd-batch-c3-pptword-gap-2026-07-24.md
18. **`vite build` 直跑必坏 PWA**（v10 新增）：
    - 场景：CLAUDE.md 永久锚点 2026-07-11 PWA manifest 410 回归
      （commit `59187ce8` cascade folder delete 引入，`5d2bcdfd` 修复）
    - 假设：web 改动 = `vite build` 直跑 = 必坏 PWA（manifest.webmanifest
      保持 unhashed → nginx `location = /manifest.webmanifest { return 410; }`
      拦截 → 浏览器 `Manifest fetch failed, code 410` → PWA install 失败）
    - 修正：段 4 完成定义必显式 "web 改动必须 `npm run build`（唯一合法命令），
      禁止 `vite build` 直跑" + 段 5 第 17 项必填 + 段 7 第 18 类沉淀
    - 沉淀：memory/pwa-manifest-410-regression-2026-07-11.md
19. **commit message 必含锚点范式数字**（v10 新增）：
    - 场景：W72 第 1 批 11 commit 全部 commit message 含锚点范式数字
      （如 commit `228aa9de3` "锚点范式第 212 守恒"、commit `f1947d3c7`
      "锚点范式第 218 守恒"），但 v9 模板未明示"commit message 必含锚点范式
      数字 + W72 第 1 批实战引用"，agent 自报可能省略锚点范式数字
    - 假设：W73+ commit message 必含锚点范式数字 + W72 第 1 批实战引用
      （commit hash 或具体路线 B-1/B-2/B-3/B-4/B-5）
    - 修正：段 4 完成定义加 commit message 锚点范式数字必填 + 段 5 第 18 项
      必填 + 段 9 W72 第 1 批实战 11 commit 锚点范式数字纪律
    - 沉淀：memory/w72-2nd-route-a2-prompt-v10-2026-07-27.md（本任务沉淀）

沉淀规则：
- 每类前提错误必须有真实案例引用（commit hash / file path / commit message）；
- 沉淀位置统一在 memory/w68-<batch>-<route>-<topic>-<date>.md 或 memory/w71-<route>-<topic>-<date>.md 或 memory/w72-<route>-<topic>-<date>.md；
- 主指挥在 grand closure 时汇总本批所有派工前提错误，更新 CLAUDE.md 永久锚点节；
- 24h 内未填视为派工流程违规，主指挥应在下批派工前提检查清单中加严；
- v10 新增 3 类（命名错位 plan 必重定义差量缺口 / `vite build` 直跑必坏 PWA /
  commit message 必含锚点范式数字）必须与 v9 原 16 类并列回填。
```

派工前提错误不是"派工失败"，而是"派工时主指挥拍板的隐含前提事后被证伪"。v10 新增 3 类已经把"W72 第 1 批实战 11 commit 反馈（命名错位差量缺口 / `vite build` 必坏 PWA / commit message 必含锚点范式数字 三类实战）"全部沉淀；下一批派工（特别是 W73 调研 / W74 实施 / 商业化 B-5 / 跨 worktree 接口契约场景）必须把这些前提显式写进 prompt，避免重蹈 W72 第 1 批实战事故。

## §8 W73 起步纪律（v10 升级：4 项 → 6 项）

```text
【v9 沿用 4 项】
1. W71 B 路线 5 agents commit + merge 真验证
2. W71 子 plan ② 7 维评分数据 + KB 闭环验证
3. W72 子 plan ③ UI redesign 三大件独立回归
4. 13 类派工前提错误必含

【v10 新增 2 项（W72 第 1 批实战 + 商业化 docker base）】
5. **商业化 docker base 起步必先**（v10 新增）：
   - 场景：商业化 B-5（docker base 商业化版 + 商业化版调研）起步必先 docker base
     商业化版（不算 0 production code 改动，因为 docker base 是新业务模块容器镜像
     rebuild，不破坏老任务/会议/知识库路径）
   - 纪律：商业化 B-5 必先 docker commit + push + webhook 部署 + 商业化版镜像
     pull + 商业化版 smoke test 全通过后才启动 B-5 调研代码；商业化 B-5 commit
     message 必含"商业化 docker base 起步必先" + "商业化版 smoke test 全通过"
   - 沉淀：memory/w72-2nd-route-c2-monetization-docker-base-2026-07-27.md（待沉淀）
6. **gap analysis 文档必先恢复/重建**（v10 新增）：
   - 场景：缺口 5 教训（ppt-word PR2/PR3/PR5/PR7 + 缺口 5 命名错位）
     暴露 W72 第 1 批前 gap analysis 文档未恢复/重建，导致 C-3 commit `f1947d3c7`
     调研时无 baseline diff
   - 纪律：gap analysis 文档必先恢复（git checkout 已删 gap analysis 文档
     或 git revert 已删 commit）+ 重建（新增缺口 baseline diff + 派生新任务清单
     + W73/W74 派工顺序表）才启动 W73 调研
   - 沉淀：memory/w72-2nd-route-c3-pptword-gap-analysis-rebuild-2026-07-27.md（待沉淀）

【W73 起步纪律 6 项实战预测】
- 派工 W73 调研 agent 时 prompt 必含 W73 起步纪律 6 项必读
- W73 调研 agent 必先 git log 真验证 W72 第 1 批 11 commit 落地状态
- W73 调研 agent 派生新任务清单必逐项 git log --grep 真验证
- W73 调研 agent 必含 gap analysis 文档恢复/重建验证段
- W73 调研 agent 必含商业化 docker base 起步必先验证段
- W73 调研 agent commit message 必含锚点范式数字 + W72 第 1 批实战引用
```

## §9 W72 第 1 批 11 commit 锚点范式数字纪律（v10 新增）

```text
【W72 第 1 批 11 commit 实战锚点范式数字表】

| Commit | 路线 | 锚点范式数字 | commit message 实战片段 |
|---|---|---|---|
| `6e074ffd9` | A-1 | 锚点范式第 207 守恒 | docs(w72nd-batch-a1): W72 第 1 批 15 agents 派工调研依据 ... 锚点范式第 207 守恒 |
| `937742218` | A-2 | 锚点范式第 208 守恒 | memory(w72nd-batch-a2): 派工纪要 v9 模板升级 memory ... 锚点范式第 208 守恒 |
| `206661254` | A-3 | 锚点范式第 209 守恒 | docs(w72nd-batch-a3): W72 启动前 plans 真验证 ... 锚点范式第 209 守恒 |
| `7a1d07df8` | A-4 | 锚点范式第 210 守恒 | memory(w72nd-batch-a4): W72 grand closure memory 预期版 ... 锚点范式第 210 守恒 |
| `4f737b61a` | B-1 | 锚点范式第 211 守恒 | feat(w72nd-batch-b1): NavRail.vue 新组件 ... 锚点范式第 211 守恒 |
| `228aa9de3` | B-2 | 锚点范式第 212 守恒 | feat(w72nd-batch-b2): ThinkingModeSwitch + ChatBreadcrumb + useUiStore v-model ... 锚点范式第 212 守恒 |
| `1a33b816e` | B-3 | 锚点范式第 213 守恒 | feat(w72nd-batch-b3): ChatViewSSE 顶栏 3-zone 重构 ... 锚点范式第 213 守恒 |
| `6c6f7b794` | B-4 | 锚点范式第 213 守恒 | feat(w72nd-batch-b4): NavRail 跨端点路由 + 6 主题 dark mode ... 锚点范式第 213 守恒 |
| `b7ad730a6` | B-5 | 锚点范式第 215 守恒 | feat(w72nd-batch-b5): 桌面端 ChatViewSSE 顶栏 6 主题 dark mode 完整版 ... 锚点范式第 215 守恒 |
| `08df36e80` | C-1 | 锚点范式第 216 守恒 | chore(w72nd-batch-c1): 容器镜像 rebuild 5 步操作 + bash 脚本 ... 锚点范式第 216 守恒 |
| `a78967661` | C-2 | 锚点范式第 217 守恒 | docs(w72nd-batch-c2): W72 商业化 24 人月季度排期更新 ... 锚点范式第 217 守恒 |
| `f1947d3c7` | C-3 | 锚点范式第 218 守恒 | chore(w72nd-batch-c3): ppt-word 5 缺口调研 ... 锚点范式第 218 守恒 |
| `02b7b4dcb` | D-2 | 锚点范式 W71 206 → W72 220 守恒预期 | chore(w72nd-batch-d2): 6 类文档同步 ... 锚点范式 W71 206 → W72 220 守恒预期 |
| `41fe8f0f9` | D-3 | 锚点范式第 221 守恒 | chore(w72nd-batch-d3): 锚点范式守恒 ... 锚点范式第 221 守恒 |

【commit message 实战模板（v10 强制约束）】
- 调研类 commit：
  `chore(w72nd-batch-c<N>): <标题> (<调研主题>, <调研发现> + <派生新任务> + W73/W74 派工顺序, 锚点范式第 N 守恒)`
- 实施类 commit：
  `feat(w72nd-batch-b<N>): <标题> (~<行数> 行, <要点> + type hint 必含, <测试> PASS, 锚点范式第 N 守恒)`
- 文档/沉淀类 commit：
  `docs(w72nd-batch-d<N>): <标题> (<6 类文档同步>, 锚点范式 W71 206 → W72 220 守恒预期 +N, 0 production code 改动铁律 N/15 守恒)`
- memory 沉淀类 commit：
  `memory(w72nd-batch-<a/b/c/d<N>>): <标题> (<沉淀主题>, 锚点范式第 N 守恒)`

【W73+ commit message 守恒预期】
- 锚点范式数字 + W72 第 1 批实战引用 必含（commit hash 或具体路线 B-1/B-2/B-3/B-4/B-5）
- 调研类 commit 必含"派生新任务"段 + "W73/W74 派工顺序"段
- 实施类 commit 必含"type hint 必含"段 + "<测试> PASS"段
- 文档/沉淀类 commit 必含"6 类文档同步"段 + "0 production code 改动铁律 N/15 守恒"段
```

## §10 兼容性矩阵（v9 → v10 升级路径）

| 版本 | 兼容 v10? | 升级路径 |
|---|---|---|
| v1 | 否 | 整模板替换为 v10 |
| v2 | 否 | 整模板替换为 v10 |
| v3 | 否 | 整模板替换为 v10 |
| v4 | 部分（缺段 5/6/7/8/9/10）| 段 5 升级 18 项 + 段 6 14 段 + 段 7 19 类 + 段 8 6 项 + 段 9 + 段 10 |
| v5 | 部分（缺段 7/8/9/10）| 段 7 19 类 + 段 8 6 项 + 段 9 + 段 10 |
| v6 | 部分（缺段 5/7/8/9/10）| 段 5 18 项 + 段 7 19 类 + 段 8 6 项 + 段 9 + 段 10 |
| v7 | 部分（缺段 3/4/5/7 升级 + 段 8/9/10）| 段 3 SubAgent 接口 + 段 4 type hint grep + 段 5 18 项 + 段 7 19 类 + 段 8 6 项 + 段 9 + 段 10 |
| v8 | 部分（缺段 5/7/9/10）| 段 5 18 项 + 段 7 19 类 + 段 9 + 段 10 |
| v9 | 几乎兼容（缺段 5/7/8/9/10 升级）| 段 5 升级 18 项 + 段 6 14 段 + 段 7 升级 19 类 + 段 8 升级 6 项 + 段 9 W72 第 1 批 11 commit + 段 10 兼容矩阵 |
| v10（目标版本）| — | — |

## §11 v10 发布前自检清单

- [ ] 段 1 写清角色、范围、不变量、当前分支、基线 commit、依赖 agent。
- [ ] 段 1 含 B 路线 5 agents 接口契约（docs/w72-b-route-interfaces.md）+ 派生新任务清单 + 派工调研 git log 真验证（v9/v10 升级）。
- [ ] 段 2 列出文件、规模和禁止修改项。
- [ ] 段 2 含 SubAgent 编排 type hint 强制约束 + TypeScript @deprecated 警告 + 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md + 派生新任务真验证 3 段（v9/v10 升级）。
- [ ] 段 3 含 plans grep 和 Alembic heads 前置检查。
- [ ] 段 3 写明双头必须报主指挥，不能私改。
- [ ] 段 3 含"前端任务 5 hot-fix 链路检查" + "PWA / SW 状态检查" + "vite build 必坏 PWA 必读"（v8/v9/v10 升级）。
- [ ] 段 3 含"SubAgent 编排接口" + "B 路线 5 agents 接口协调（含 TypeScript @deprecated）" + "W72 起步纪律 6 项必读（v9 4 项 + v10 商业化 docker base + gap analysis 重建）"（v9/v10 升级）。
- [ ] 段 4 含 PS 5.1 三项 binding 约束。
- [ ] 段 4 显式 "web 改动必须 `npm run build`，禁止 vite build 直跑"（v10 强化，段 7 第 18 类必填）。
- [ ] 段 4 含"web 改动必 grep 验证" + "runtime 心跳 / setInterval 策略"（v8 沿用）。
- [ ] 段 4 含"SubAgent type hint 编译产物 grep" + "派生新任务真验证 grep" + "commit message 锚点范式数字必填"（v9/v10 升级）。
- [ ] 段 5 必填 18 项提示词齐全（v9 15 项 + v10 3 项）。
- [ ] 段 5 含"18 项缺一不可"约束。
- [ ] 段 6 含合并链表格 + alembic 串单链位置列。
- [ ] 段 6 含"实战 5 hot-fix 必含 alembic + dist rebuild + nginx reload 三段串联"（v8 沿用）。
- [ ] 段 6 含"B 路线 5 agents 接口契约 / Celery 串行"列 + Celery 串行约束 + D 路线 partial 守恒（v9 沿用）。
- [ ] 段 6 含"商业化 B-5 必先于 D-2 doc sync"（v10 新增第 14 段）。
- [ ] 段 6 含"agent 不主动 merge / push"约束。
- [ ] 段 7 必填 19 大类派工前提错误（v9 16 类 + v10 3 类）。
- [ ] 段 7 沉淀规则统一在 memory/。
- [ ] 段 7 24h 内未填视为派工违规。
- [ ] 段 8 W73 起步纪律 6 项必读（v9 4 项 + v10 商业化 docker base + gap analysis 重建）。
- [ ] 段 9 W72 第 1 批 11 commit 锚点范式数字纪律（v10 新增，含 commit message 实战模板）。
- [ ] 文档任务完成 `git diff --check`。
- [ ] migration 合并完成后只有一个 head。
- [ ] plans 调研结果有 backlog docs 或 COMPLETED 真 commit。
- [ ] web 改动 grep 验证关键字符串次数 ≥ 0 / ≤ 1（v8 沿用）。
- [ ] SubAgent 编排 type hint grep ≥ 1 + TypeScript @deprecated grep ≥ 1 + 派生新任务真 commit hash 引用 ≥ 1（v9/v10 升级）。
- [ ] commit message 锚点范式数字 grep ≥ 1 + W72 第 1 批实战引用 grep ≥ 1（v10 新增）。
- [ ] 段 5 反馈至少收到 N ≥ 5 agents 才能汇总升级 v11。
- [ ] 锚点范式变化显式追踪（段 5 第 6 项 + 段 7 第 19 类）。

## §12 v10 默认应用范围

- **W68 第 14 批 H-1~H-5 已应用 v6 / v7**：commit `49ebe9b33` / `3207aea62` / `72eaae07f` / `ff9b6b3e2` / `960f8abe1` / `85619c012`。
- **W71 batch 派工**：默认 v7；实战暴露 v7 三层缺口（B 路线 5 agents 接口协调 / SubAgent type hint / 派生任务真验证），v8 必含。
- **W72 第 1 批 派工**：默认 v9；实战暴露 v9 四层缺口（SubAgent type hint 实战 / TypeScript @deprecated / 4 阶段流程 v2 / 0 production code 表 / W73/W74 顺序），v10 必含。
- **W72 第 2 批 派工**：默认 v10；尤其是商业化 B-5 / 跨 worktree 接口契约 / gap analysis 文档恢复场景，必须把对应 v10 段 3/4/5/6/7/8/9 门禁原样写进 prompt。
- **W73 batch 派工**：默认 v10；commit message 必含锚点范式数字（v10 段 9 强制约束）。
- **W74+ 调研任务**：必须用 v10（避免派生调研自报偏差 + W73 起步纪律 6 项缺失 + 商业化 docker base 起步缺失 + gap analysis 文档恢复缺失）。

## §13 9 条新铁律（v10 沉淀，4 类合并展示）

v10 在 v9 9 条铁律基础上新增/升级：

1. **段 5 反馈必填 18 项**（v9 升级 v10）——agent 完工回传必须含段 5 v10 18 项必填（v9 原 15 项 + SubAgent type hint 实战 / 派工 4 阶段流程 v2 / W73/W74 派工顺序表 + commit message 锚点范式数字 3 项），否则视为"完工未达标"。
2. **段 6 合并顺序表必含 alembic 串单链 + web dist rebuild + nginx reload 三段串联 + B 路线 Celery 串行约束 + D 路线 partial 守恒 + 商业化 B-5 必先于 D-2 doc sync**（v9 升级 v10）——前端任务必须显式含"npm run build + git add -f dist + push"步骤；nginx 改动必跑 `nginx -t + nginx -s reload`；B 路线 5 agents 必含 Celery 串行依赖（b-3 等 b-1 + b-2 commit + merge）；D 路线 6 类文档同步必须先聚合已合并到 origin/main 的 commit + branch-pushed commit（**不伪造**未实施 agent 工作内容）；商业化 B-5 必先 docker base 商业化版 + 商业化版 smoke test 全通过后才启动调研代码。
3. **v10 默认应用从 W73 batch 开始**（v9 升级 v10）——任何 W73 及以后的派工必须使用 v10；W74+ 调研任务**必须**用 v10。
4. **段 7 派工前提错误必含 19 大类**（v9 升级 v10）——v9 16 类 + v10 新 3 类（命名错位 plan 必重定义差量缺口 / `vite build` 直跑必坏 PWA / commit message 必含锚点范式数字）。任何派工必含这 19 类前提的隐含假设。
5. **SubAgent 编排接口必含 type hint + TypeScript @deprecated 警告 + 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md**（v9 升级 v10）——所有 SubAgent 输入/输出 dataclass / Pydantic schema 必须有完整 type hint（`from typing import ...`）；TypeScript interface 必带 `@deprecated` 警告（W72 B-2 commit `228aa9de3` 实战暴露）；跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md 集中管理；跨 agent 串接时必跑 `model_validate(sample)` 校验；新加字段 keyword-only + Optional 默认 None；编译产物 grep 验证 type hint + @deprecated 出现次数 ≥ 1。
6. **派生新任务必含真验证 + W73/W74 派工顺序表**（v9 升级 v10）——主指挥口头追加子任务时，agent 必先写 backlog docs（`C:/Users/pc/.claude/plans/<plan-keyword>.md` + Status 段 + 真验证命令）；完工后必含 git log + grep + commit 引用 3 段真验证。**v10 升级**：派工调研 agent 派生新任务清单必逐项 git log --grep 真验证 + 含 W73/W74 派工顺序表（先 W73 调研 → 后 W74 实施）。
7. **B 路线 5 agents 接口协调必走 Celery 串行 + 接口契约表 + 数据流向图 + TypeScript @deprecated 警告**（v9 升级 v10）——B-1/B-2/B-3/B-4/B-5 五个 agent 之间接口契约（输出文件 + 输出格式 + 接收字段 + 校验方式）必须在段 5 反馈里必填；Celery 串行任务必须显式声明依赖（b-3 等 b-1 + b-2 commit + merge 后才启动）；dashboard / CI smoke 数据源与上游 5 agents 权重 schema 一致；TypeScript interface 必带 @deprecated 警告（跨 worktree 接口契约）。
8. **W72 起步纪律必走 4 项必含 + 6 项起步 + 3 项 24h 必填**（v9 升级 v10）——W72 子 plan ③ UI redesign 派工前必读段 8；W71 B 路线 5 agents 全部 commit + merge 后才启动；7 维评分数据 + KB 闭环回归必通过；NavRail / ThinkingModeSwitch / ChatBreadcrumb 三大件独立回归必通过；商业化 docker base 起步必先（v10 新增）；gap analysis 文档必先恢复/重建（v10 新增）。
9. **v10 升级实战反馈必走 4 类新缺口显式沉淀 + 11 commit 锚点范式数字纪律**（v10 新增）——W72 第 1 批实战暴露 4 类新缺口（SubAgent type hint 实战 / TypeScript @deprecated / 4 阶段流程 v2 / 0 production code 表 / W73/W74 顺序）必须在段 5/6/7/8/9 显式沉淀；任何 W73+ 派工调研必读段 5/6/7/8/9 实战反馈；派生新任务清单逐项 git log --grep 真验证；commit message 必含锚点范式数字 + W72 第 1 批实战引用。

## 结语

v10 不是替换 v9，而是补一段让模板"W72 第 1 批实战 11 commit 锚点范式数字纪律（SubAgent type hint 实战 + TypeScript @deprecated + 4 阶段流程 v2 + 0 production code 表 + W73/W74 顺序 + 商业化 B-5 必先于 D-2 + 命名错位 plan 必重定义差量缺口 + `vite build` 必坏 PWA + commit message 必含锚点范式数字）派工前提显式沉淀 + 反馈颗粒度强制提升到 18 项 + 段 6 合并顺序表新增 14 段（商业化 B-5 必先于 D-2） + 段 8 升级 6 项起步纪律（商业化 docker base + gap analysis 重建） + 段 9 W72 第 1 批 11 commit 锚点范式数字纪律"。段 5 升级让 agent 反哺模板更具体（含 SubAgent type hint 实战 + 4 阶段流程 v2 + W73/W74 派工顺序表），段 7 让主指挥派工的隐含前提（W72 第 1 批实战 19 类）事后被显式记录。这样 W73 batch + W74/W75 派工可以基于"经过 W72 第 1 批 B 路线 5 agents + SubAgent 编排 + 派生任务 + 派生调研 + W72 起步纪律实战反馈 + W73 起步纪律 6 项实战预测的模板 + 经过 19 类前提沉淀的纪律 + 经过段 9 W72 第 1 批 11 commit 锚点范式数字纪律强约束的命令"启动下一轮，更可预测、更易追溯、更不易合并错。

---

**版本 v10，2026-07-27，W72 第 2 批 A-2 起草，主指挥合并后正式生效。**

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**