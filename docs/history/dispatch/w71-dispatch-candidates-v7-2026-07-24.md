# W71 派工纪要候选：Prompt Template v7

> 版本：v7（2026-07-24/27）
> 适用：主指挥、并行 agent、文档/调研/迁移派工
> 沿用：v6 七段全部 + 段 5 升级 6 → 9 项 + 段 7 升级 → 派工 v7 实战新纪律（5 条）
> 原则：先验证、再派工；先串链、再合并；先反馈、再升级；合并顺序可见；派工前提错误必沉淀；**W71 实战新发现的隐含纪律强制入模板**。

## §1 升级背景：v6 → v7 增量

### §1.1 v6 已经解决了什么

v6 在 v5 基础上做了 2 项关键升级：

| 能力 | v6 段位 |
|---|---|
| 反馈循环颗粒度强制 | 段 5（必填 6 项，每项需具体句子/短语）|
| 派工前提错误显式沉淀 | 段 7（24h 内必填 5 大类前提表格）|
| web `npm run build` 强约束 | 段 4（禁止 vite build 直跑）|
| 锚点范式显式追踪 | 段 5 第 6 项 |

v6 在 W68 第 14 批 D-1 落地（commit `93dbd2cc7`）。W72 调研任务默认 v6。

### §1.2 W71 batch 派工实战暴露的 3 类缺口

W71 batch 派工实战后，H-1 / H-2 / H-3 / H-4 / H-5 五次连续 hot-fix 揭示 v6 仍缺 3 类纪律：

**缺口 1：派工前提假设里"web / PWA / 浏览器状态"完全没覆盖。** v6 段 7 的 5 大类前提（alembic 串单链 / PS 5.1 / plans 真验证 / web `npm run build` / baseline 守恒）**全部是后端 + 文档层**，对"浏览器老 SW cache 污染"+"PWA 永久禁用手顺"+"自检函数 self-loop"+"setInterval 泄漏"+"heartbeat 警告噪声" 5 类**纯前端 + 浏览器场景**0 覆盖。H-1 到 H-5 五次 hot-fix 全部踩在前端/浏览器状态，根因都是派工时没把这些隐含前提显式写进 prompt。

**缺口 2：段 5 反馈颗粒度仍不够。** v6 段 5 必填 6 项对"具体有效 / 具体多余 / 新增段 7 候选 / 旧段升级 / 派工前提 / 锚点变化"已足够，但实战发现还差 3 类信号：(a) **web 浏览器状态轨迹**——主指挥 console 报错是否仍刷？(b) **PWA / SW 禁用后的副作用**——checkSwBlacklist 这类自检函数何时该删？(c) **runtime 心跳警告噪声**——是否保留 console.warn 还是直接静默？v7 必加这 3 项。

**缺口 3：段 7 派工前提"5 大类"已经过期。** W71 五次 hot-fix 暴露 5 类**纯前端/浏览器派工前提错误**——浏览器 SW cache 强制清时机、PWA 永久禁用四步、checkSwBlacklist self-loop 删除、setInterval timer 句柄、heartbeat 静默策略。这 5 类必须和 v6 原 5 类并列进入 v7 段 5 + 段 7。

### §1.3 v7 增量

v7 严格遵循"只增可验证门禁，不删除 v6 已有兼容项"原则：

| 升级 | 段位 | 内容 |
|---|---|---|
| 段 5 反馈循环升级 | 段 5 | 必填 6 项 → **9 项**（+浏览器状态 / PWA 副作用 / runtime 心跳）|
| 段 7 实战新纪律 | 段 7 | v6 5 大类 → **v7 5 + 5 共 10 大类**派工前提错误（+浏览器 SW cache / PWA 禁用四步 / checkSwBlacklist 删除 / setInterval 句柄 / heartbeat 静默）|
| 段 5 派工前提升级 | 段 5 | 必含"浏览器老 SW cache 处理 / PWA 禁用四步 / setInterval 句柄 / heartbeat 静默策略"4 类实战信号 |
| 段 6 合并表升级 | 段 6 | 实战 5 hot-fix 必含 alembic 串单链 + web dist rebuild + nginx reload 3 步串联 |

v7 默认应用从 W71 batch 开始；W72 默认应用 v7；W73 调研任务**必须**用 v7。

## §2 v7 完整 8 段模板（沿用 v6 7 段 + 段 7 实战新纪律合并）

以下模板可直接复制到派工消息；尖括号内容必须替换。

### 段 1：角色、范围与不变量（沿用 v6）

```text
你是 Agent <编号>：<标题>。目标是 <一句话目标>。
范围：<文件/目录>；不范围：<明确排除项>。
硬规则：0 production code（如适用）；不得 merge；不得覆盖他人改动；
输出必须包含证据路径、测试结果、commit hash 和阻塞项。
当前分支：<worktree 分支名>；基线 commit：<hash>；
依赖 agent：<agent-id>（说明是否等待其 commit）。
```

### 段 2：交付物与操作边界（沿用 v6）

```text
交付物：
1. <文件一>：<内容和大致规模>
2. <文件二>：<内容和大致规模>
禁止：<代码/配置/数据库/部署等不应修改的对象>。
```

若需要脚本，列出运行时版本（Windows PowerShell 5.1 或 PowerShell 7）和调用约定；若需要 migration，列出 revision 命名范围及明确的 `down_revision` 上游。

### 段 3：任务描述、前置验证与风险门禁（沿用 v6 + 派工 v7 升级）

```text
开始前：
- git status；确认基线没有未授权修改。
- plans 任务：grep -rn "<keyword>" C:/Users/pc/.claude/plans/，
  不以 status 自报替代事实；真未实施项写 backlog docs，完成项标
  COMPLETED + 真 commit。
- alembic 任务：git fetch origin main && cd main && alembic heads；
  检查 revision 唯一、down_revision 指向最新 head；发现双头立即报主指挥。
- **前端任务（v7 新增）**：git fetch origin main && 检查 5 hot-fix 链路
  （H-1 dashboard timer / H-2 nginx 410 / H-3 main.js unregister /
  H-4 checkSwBlacklist 删除 / H-5 heartbeat 静默）是否全在基线；如不是，
  不能贸然修前端，**先复现根因**再决定走哪种修复路径。
- **PWA / SW 状态（v7 新增）**：若任务涉及 SW 或 PWA，必先确认
  `vite-plugin-pwa` 是否 `disable: true`、nginx `/sw.js` `/registerSW.js`
  `/manifest.webmanifest` 是否 410、本地 main.js 顶部是否 unregister + 清 cache。
- 其他任务：<领域特定检查>。
```

迁移 agent 不得自动替换有争议的 down_revision；必须给出冲突矩阵。合并后由主指挥 rebase 重命名（如 070→075/074/076）、串单链并再跑 heads。

### 段 4：完成定义、测试与 PS 5.1 约束（沿用 v6 + 派工 v7 升级）

```text
完成定义：
- 所有交付文件存在且内容可审计；
- <测试/grep/history 验证>通过；
- 报告证据路径和命令输出摘要；
- 未完成项写 BLOCKED，并说明下一步。
- **web 改动必须 `npm run build`（唯一合法命令，PWA 410 铁律）**，
  禁止 `vite build` 直跑（绕开 postbuild → 服务器 410 + PWA install 失败）。
- **web 改动必须 grep 验证（v7 新增）**：编译产物里禁用项 grep 为 0，
  保留项 grep ≥ 1。例：H-4 派工要求编译后 checkSwBlacklist=0,
  SW content OK=0, SKIP_WAITING=0, unregister=1。
- **runtime 心跳 / console 噪声（v7 新增）**：若任务涉及 setInterval
  或 console.warn，主指挥要求"静默"时**只删 console.warn**，保留
  timer 重置逻辑（避免 W68 H-5 heartbeat 循环 bug）。
PowerShell 5.1：使用 --mode <value>（空格），[string]$Mode，
仅用 $Mode -eq 'session' 判断 session；附两种模式实跑证据。
```

完成定义不能只写"代码已写"或"测试通过"。测试需说明是单元、集成、静态检查还是人工检查，以及是否受环境限制。对于 docs-only 任务，至少做文件计数、关键词检查、git diff --check。

### 段 5：经验反馈循环（v7 升级：6 项 → 9 项必填）

```text
回传反馈（必填，9 项缺一不可）：

【v6 沿用 6 项】
1. 段 1–4 哪些段 / 句子有效？（具体指明段号 + 句子/短语 + 帮到了什么）
2. 哪些段多余 / 偏离 / 重复？（具体句子 + 偏离原因）
3. 新增段 7 候选：本次任务是否暴露了"应纳入模板"的新段？
4. 旧段升级建议：段 1–4 哪一句应被改写？（原句 + 改写后 + 一句话理由）
5. 派工前提错误：本批派工蕴含哪些前提？哪个前提事后被证伪？（详见段 7）
6. 锚点范式变化：本批是否推进了锚点范式数字？推进多少？为什么？

【v7 新增 3 项（W71 实战）】
7. **浏览器状态轨迹**（前端任务必填）：主指挥 console 仍刷哪条日志？
   修前/修后 grep 编译产物的关键字符串几次？是否还会 ERR_ABORTED 404
   老 chunk？devtools Application → Service Workers 状态是否 `redundant`？
8. **PWA / SW 副作用自检**（前端任务必填）：PWA 永久禁用四步（main.js
   顶部 unregister + VitePWA disable + nginx 410 + postbuild 兼容）
   是否全做？checkSwBlacklist 这类自检函数是否在 if(false) 包裹
   或整段删除（避免 fetch + r.text() self-loop）？新加自检函数时
   是否考虑 PWA 禁用后还该不该存在？
9. **runtime 心跳 / setInterval 策略**（前端任务必填）：本次任务是否
   涉及 setInterval / setTimeout / console.warn？timer 句柄是否存到
   变量、onUnmounted 时清理？console 警告按主指挥"完全静默"还是
   "降为 info"还是"保留 warn"？删除 console.warn 但 timer 重置
   逻辑必须保留（避免循环）。

不填任一项视为完工未达标，主指挥合并时不视为有效交付。
```

主指挥汇总 N agents 反馈后升级 v8。新铁律按"反馈必须 9 项齐全 + 至少 1 条派工前提错误实例 + 0 条负面偏离才进入 v8 候选"规则筛选。

### 段 6：主指挥合并顺序表（沿用 v6 + 派工 v7 升级实战）

```text
主指挥合并链（本 agent 必须遵守）：

| 步骤 | agent-id | 任务标题 | commit 范围 | 前置依赖 | 串单链位置 |
|---|---|---|---|---|---|
| Step 1 | <id> | <标题> | docs/.../file.md | 基线 | — |
| Step 2 | <id> | <标题> | alembic/versions/070_*.py | Step 1 | base=068 down_revision=068 |
| Step 3 | <id> | <标题> | memory/.../v5-2026-07-24.md | Step 2 | docs ref Step 1+2 |
| ... | ... | ... | ... | ... | ... |

【v7 新增】实战 5 hot-fix 必含三段串联：
- alembic 串单链：docker cp + clear cache + upgrade + restart（CLAUDE.md 752 行）
- web dist rebuild：npm run build（不是 vite build）+ git add -f dist + push
- nginx reload：若改 nginx config 必跑 nginx -t + nginx -s reload
  （或 docker compose restart nginx）

合并触发条件：
- 主指挥在所有 agent 回传 commit hash 后按 Step 顺序 rebase / cherry-pick / merge。
- alembic 串单链中途若发现双头，停止合并并报主指挥拍板（v4 §1.1）。
- agent 不主动 merge 或 push（除非派工明文授权）。

agent 完工后必须确认 commit hash 出现在顺序表的正确行；如发现顺序与派工不一致，立报主指挥。
```

合并顺序表让 agent 提前知道：(1) 谁在它前面，谁在它后面；(2) 是否需要等 alembic 上游；(3) 是否需要被 docs 下游引用；(4) 主指挥合并时如何串链；(5) 是否含 web dist rebuild + nginx reload 串联（v7）。

### 段 7：派工前提错误复盘（v7 升级：5 类 → 10 类，24h 内必填）

```text
派工前提错误（24h 内必填，至少 10 类各 1 例）：

【v6 沿用 5 类】
| 类别 | 派工时假设 | 实际验证结果 | 修正方式 | 沉淀位置 |
|---|---|---|---|---|
| alembic 串单链 | B-1 down_revision 接 077 | 实际 merge 后 revision 重命名 070→074 | 主指挥改 063 down_revision | memory/w68-alembic-...md |
| PS 5.1 binding | 使用 --mode session | 实际传入 '--mode "session"' 被解析为多 token | 改 [string]$Mode + 严格 -eq | docs/派工 v4 §4 |
| plans 真验证 | plan Status 段标 completed | 实际未实施 (commit 4b215220 refactor 意外删除) | grep plans + git show + 审计单证 | memory/verified-plans-w68.md |
| web `npm run build` | 只需 vite build | 实际需 postbuild 自动 3 件事 + 健全性自检 + force-add dist | 禁止 vite build 直跑，postbuild 唯一合法 | docs/pwa-manifest-410.md |
| baseline 守恒 | 71 PASS + 7 SKIP | 实际增加新 PASS 或 SKIP 即视为回归 | 守恒 = 0 PASS 增 + 0 SKIP 增 | scripts/ci_qa_bench_baseline.sh |

【v7 新增 5 类（W68 第 14 批 H-1/H-2/H-3/H-4/H-5 实战）】
| 浏览器老 SW cache 强制清 | 只改 nginx + 删 dist 即可 | 浏览器 SW Registration Cache 仍保留老 SW 实例，老 chunk 404 | main.js 顶部同步 unregister + 清 Cache Storage + 编译产物 grep 验证 | memory/w68-route-14-hotfix-h3-kill-old-sw-2026-07-24.md |
| PWA 永久禁用四步 | 只在 main.js 不调 useRegisterSW | vite-plugin-pwa 仍在 build 阶段注入 SW + 生成 dist 文件 | VitePWA disable: true + main.js 顶部 unregister + nginx 410 + postbuild 兼容 | memory/w68-route-14-hotfix-h2-clear-sw-2026-07-24.md |
| checkSwBlacklist self-loop | 函数还在，仅注释调用方 | 函数定义被 bundler 保留，仍 fetch + r.text() 持续调用 | 整段函数定义 + 调用方 + 相关常量一起 if(false) 包裹或彻底删除 | memory/w68-route-14-hotfix-h4-disable-sw-checkloop-2026-07-24.md |
| setInterval timer 句柄泄漏 | 写在 setup() 里跑就行 | 路由切换 / 组件 unmount 后 timer 仍跑，触发 dashboard 刷新循环 | timer 存到 ref + onUnmounted 时 clearInterval（Dashboard.vue 实战） | memory/w68-route-14-hotfix-h1-dashboard-refresh-loop-2026-07-24.md (commit 49ebe9b33) |
| heartbeat console.warn 噪声 | 保留 console.warn 让主指挥看到 | 主指挥要求完全静默，但仍要保留 timer 重置逻辑避免循环 | 只删 console.warn 那行，注释更新策略，timer 重置保留 | memory/w68-route-14-hotfix-h5-silent-heartbeat-2026-07-24.md |

沉淀规则：
- 每类前提错误必须有真实案例引用（commit hash / file path / commit message）；
- 沉淀位置统一在 memory/w68-<batch>-<route>-<topic>-<date>.md 或 memory/w71-<route>-<topic>-<date>.md；
- 主指挥在 grand closure 时汇总本批所有派工前提错误，更新 CLAUDE.md 永久锚点节；
- 24h 内未填视为派工流程违规，主指挥应在下批派工前提检查清单中加严；
- v7 新增 5 类（浏览器 SW cache / PWA 禁用 / checkSwBlacklist / setInterval / heartbeat）必须与 v6 原 5 类并列回填。
```

派工前提错误不是"派工失败"，而是"派工时主指挥拍板的隐含前提事后被证伪"。v7 新增 5 类已经把"W71 五次 hot-fix 暴露的纯前端/浏览器场景"全部沉淀；下一批派工（特别是前端/PWA/SW/setInterval/heartbeat 类任务）必须把这些前提显式写进 prompt，避免重蹈 H-1~H-5 五次连续修复。

## §3 v6 → v7 diff 详表

### 3.1 段级 diff

| 段位 | v6 | v7 增量 |
|---|---|---|
| 段 1 角色/范围/不变量 | 不变 | 不变 |
| 段 2 交付物/边界 | 不变 | 不变 |
| 段 3 前置验证/门禁 | 不变 | **新增**："前端任务 5 hot-fix 链路检查" + "PWA/SW 状态检查" |
| 段 4 完成定义/PS 5.1 | 已含 npm run build + PS 5.1 | **新增**："web 改动必 grep 验证" + "runtime 心跳 / setInterval 策略" |
| 段 5 反馈循环 | 6 项必填 | **升级为 9 项必填**（+浏览器状态 / PWA 副作用 / runtime 心跳 3 项实战信号） |
| 段 6 合并顺序表 | 含 alembic 串单链 | **新增**："实战 5 hot-fix 必含 alembic + dist rebuild + nginx reload 三段串联" |
| 段 7 派工前提错误 | 5 大类前提（24h 内）| **升级为 10 大类**（+浏览器 SW cache / PWA 禁用 / checkSwBlacklist / setInterval / heartbeat 5 类）|

### 3.2 新增能力 diff

| 维度 | v6 | v7 增量 |
|---|---|---|
| 段数 | 7 段 | 8 段（v7 实战新纪律段 7 合并展示，段 8 = 段 5+6+7 三段实战落地） |
| 模板长度 | ~365 行 | +段 3/4/5/6/7 升级 ~80 行 → ~445 行 |
| 反馈颗粒度 | 6 项必填 | 升级 9 项必填（每项需具体句子/短语 + 浏览器实测 grep 数） |
| 派工前提沉淀 | 24h 内 5 大类各 1 例 | 24h 内 10 大类各 1 例 |
| 锚点范式显式追踪 | 段 5 第 6 项 | 同 v6 + 段 7 第 10 类显式询问 |
| web build 命令约束 | 段 4 强制 `npm run build` | 段 4 强制 + 段 5 第 8 项 grep 验证 |
| PWA / SW 禁用纪律 | 无 | 段 3 + 段 5 第 8 项 + 段 7 新增类 1-3 必填 |
| setInterval / heartbeat 纪律 | 无 | 段 4 + 段 5 第 9 项 + 段 7 新增类 4-5 必填 |
| 合并顺序表串联 | alembic 单链 | alembic + dist rebuild + nginx reload 三段串联 |
| 关门强度 | 段 1-7 必填 | +段 5 必填 9 项 +段 7 必填 10 类 + 24h 限时 |

### 3.3 v7 兼容性矩阵

| 版本 | 兼容 v7? | 升级路径 |
|---|---|---|
| v1（基本角色/范围/交付物）| 否（无反馈/合并表/前提）| 整模板替换为 v7 |
| v2（+ 测试/证据/分支边界）| 否（缺段 5/6/7）| 整模板替换为 v7 |
| v3（5 段雏形）| 否（缺反馈/合并表/前提）| 整模板替换为 v7 |
| v4（5 段完整 + 3 大门禁）| 部分（缺段 6/7 + 段 5 升级）| 追加段 5 v7 9 项版本 + 段 6 + 段 7 v7 10 类版本 |
| v5（+ 段 5 反馈 + 段 6 合并表）| 几乎兼容（缺段 7）| 段 5 升级 9 项 + 追加段 7 v7 10 类 + 段 3/4 升级 |
| v6（+ 段 7 5 大类 + web build）| 几乎兼容（缺段 5 9 项 + 段 7 5 新类）| 段 5 升级 9 项 + 段 7 追加 5 类实战纪律 + 段 3/4 升级 |
| v7（目标版本）| — | — |

### 3.4 不破坏既有 v6/v5/v4/v3/v2/v1 历史派工

v7 严格遵循"只增可验证门禁，不删除已有兼容项"原则：

- 段 1–4 完全沿用 v6，仅在段 3 末段新增"前端任务 5 hot-fix 链路检查"和"PWA / SW 状态检查"，段 4 末段新增"web 改动必 grep 验证"和"runtime 心跳 / setInterval 策略"
- 段 5 是"反馈必填"的扩展（6 → 9 项），不替换 v6 的"6 项必填"
- 段 6 完全沿用 v6 表格，仅在"合并触发条件"前加一段"v7 新增 实战 5 hot-fix 必含三段串联"
- 段 7 v6 5 大类**完全保留**，v7 追加 5 大类（纯增量），段 7 表格变为 10 类合并版

## §4 W68 第 14 批 H-1/H-2/H-3/H-4/H-5 实战应用 v6 → v7 升级反馈

W68 第 14 批 H-1 ~ H-5 五次连续 hot-fix 派工时已应用 v6。v7 升级基于这五次实战反馈：

### 4.1 H-1 commit `49ebe9b33` 实战反馈（v7 段 3+ 段 4 + 段 7 新增类 4）

- **症状**: Dashboard 持续刷新循环 + 老 SW reload 触发
- **根因**: `Dashboard.vue` setInterval 时钟未存句柄、组件 unmount 后仍跑；`NotificationBell.vue` 通知 polling 无 30s 限流
- **修复**: timer 存 ref + onUnmounted clearInterval；通知 polling 30s 限流；401 拦截器不再删 token（commit `3207aea62` 修复"删 token + push /login 触发循环"）
- **v6 缺口**: 派工前提里无 "setInterval timer 句柄泄漏" 类，回填时发现根因是派工时没要求"timer 句柄必存 ref + onUnmounted 清理"
- **v7 升级**: 段 3 新增"前端任务 5 hot-fix 链路检查"；段 4 新增"runtime 心跳 / setInterval 策略"；段 7 新增类 4 必填

### 4.2 H-2 commit `72eaae07f` 实战反馈（v7 段 3 + 段 7 新增类 1-2）

- **症状**: 主指挥 console 报 `GET /assets/index-{oldhash}.js net::ERR_ABORTED 404`，nginx `/sw.js` 加 `Cache-Control: no-store` 但仍 200，老 SW 持续拦截
- **根因**（2 层）:
  1. nginx `location = /sw.js` 仅 `add_header Cache-Control "no-store"` 但**不返回 410** → 浏览器 200 OK + 老 SW 内容 → 不会卸载老 SW → 老 chunk 列表仍在 precache
  2. vite-plugin-pwa `disable: true` 比 postbuild 删 sw.js 更彻底，但 postbuild 脚本强依赖 sw.js 存在
- **修复**: vite-plugin-pwa `disable: true` + nginx 3 server block 全加 `return 410` + `build:pwa` 别名用于恢复 PWA
- **v6 缺口**: 派工前提里无 "PWA 永久禁用四步" 类，主指挥在派工时没说"必须同时改 vite.config.js + main.js + nginx + package.json scripts"
- **v7 升级**: 段 3 新增"PWA / SW 状态检查"；段 7 新增类 1-2 必填（浏览器老 SW cache + PWA 永久禁用）

### 4.3 H-3 commit `ff9b6b3e2` 实战反馈（v7 段 7 新增类 1）

- **症状**: H-2 已删 sw.js + manifest + nginx 410，但 console 仍报 `[PWA] SW content OK, no blacklist match`
- **根因**: 仅靠 nginx 410 + 删 dist 文件不够，浏览器 SW Registration Cache 仍保留老 SW 实例，老 SW 持续拦截 fetch
- **修复**: `main.js` 顶部同步 unregister + 清 Cache Storage + vite-plugin-pwa 永久 disable + postbuild 兼容
- **v6 缺口**: 派工前提里无 "浏览器老 SW cache 强制清" 类，H-2 派工时主指挥没说"必须同时在 main.js 顶部加 unregister"
- **v7 升级**: 段 7 新增类 1（浏览器老 SW cache 强制清）

### 4.4 H-4 commit `960f8abe1` 实战反馈（v7 段 7 新增类 3）

- **症状**: H-1/H-2/H-3 三连修后，console 仍持续刷 `[PWA] SW content OK, no blacklist match`，Dashboard 仍持续刷新
- **根因**: `checkSwBlacklist()` 函数定义 + 调用方链没断。每次页面 mount 都跑 `fetch('/sw.js')` + `r.text()` + 扫 SW_BLACKLIST_CONTENT_PATTERNS + console.log → 持续 IO
- **修复**: 整段 SW 检测代码 `if (false) { ... }` 大块包裹（130 行用 false 包起来），调用方 + 函数定义 + 相关常量一起禁用；保留 H-3 顶部 unregister
- **v6 缺口**: 派工前提里无 "self-loop check 函数删除" 类，主指挥没说"PWA 禁用后这类自检函数必整段删"
- **v7 升级**: 段 7 新增类 3（checkSwBlacklist self-loop 删除）

### 4.5 H-5 commit `85619c012` 实战反馈（v7 段 4 + 段 5 + 段 7 新增类 5）

- **症状**: H-1 + commit `4b658cbb2` 修 heartbeat 无限循环 bug 后，仍 `console.warn('[Notify] W68 heartbeat timeout...')`，主指挥要求**完全静默**
- **根因**: 派工前提里无 "heartbeat console 噪声策略" 类，主指挥没明示"静默 console.warn 但保留 timer 重置逻辑"
- **修复**: 删 console.warn 那行，保留 `lastServerPingTs = Date.now()` timer 重置逻辑，避免循环
- **v6 缺口**: 派工前提里无 "heartbeat 静默" 类
- **v7 升级**: 段 4 新增"runtime 心跳 / console 噪声"策略；段 5 新增第 9 项；段 7 新增类 5

### 4.6 v6 段 5 在 W71 五次实战中暴露的颗粒度问题

v6 段 5 必填 6 项（有效段 / 多余段 / 新增段 7 候选 / 旧段升级 / 派工前提 / 锚点变化）在 H-1~H-5 五次回传时分析：

- 3/5 agents 仅写"全部有效"或"无 fail"，未指明具体句子
- 1/5 agents 写了"段 7 派工前提有 5 大类但不含前端" → 主动建议 v7 段 7 加 5 类前端派工前提
- 1/5 agents 完全未填段 5，主指挥合并时才发现

**v7 升级方案**: 必填 9 项（v6 6 项 + v7 新增 3 项：浏览器状态轨迹 / PWA / SW 副作用 / runtime 心跳），每项需具体句子 / 短语 + 浏览器实测 grep 数 + devtools 状态截图（如适用）。

### 4.7 v6 段 7 在 W71 五次实战中暴露的 5 类缺口

v6 段 7 派工前提 5 大类（alembic / PS 5.1 / plans / web build / baseline）在 H-1~H-5 五次实战中**完全无匹配**：

| 实战根因 | v6 段 7 是否覆盖 | v7 升级方式 |
|---|---|---|
| Dashboard setInterval 泄漏（H-1）| 否 | v7 段 7 新增类 4 |
| nginx `add_header` 不 return 410（H-2）| 否 | v7 段 7 新增类 2（PWA 永久禁用四步）|
| main.js 缺顶部 unregister（H-3）| 否 | v7 段 7 新增类 1（浏览器老 SW cache 强制清）|
| checkSwBlacklist fetch + r.text() 持续调用（H-4）| 否 | v7 段 7 新增类 3 |
| heartbeat console.warn 噪声（H-5）| 否 | v7 段 7 新增类 5 |

**v7 升级**: 段 7 必须含 10 大类派工前提错误（v6 5 类 + v7 5 类），覆盖后端 + 前端 + 浏览器 + PWA + SW + 心跳 + console 全部场景。

## §5 8 条新铁律（v7 沉淀，4 类合并展示）

v7 在 v6 7 条铁律基础上新增/升级：

1. **段 5 反馈必填 9 项**（v6 升级 v7）——agent 完工回传必须含段 5 v7 9 项必填（v6 原 6 项 + 浏览器状态轨迹 / PWA & SW 副作用 / runtime 心跳 & setInterval 策略 3 项），否则视为"完工未达标"。
2. **段 6 合并顺序表必含 alembic 串单链 + web dist rebuild + nginx reload 三段串联**（v6 升级 v7）——前端任务必须显式含"npm run build + git add -f dist + push"步骤；nginx 改动必跑 `nginx -t + nginx -s reload`。
3. **v7 默认应用从 W71 batch 开始**——任何 W71 及以后的派工必须使用 v7；W73 调研任务**必须**用 v7（避免 plans 自报偏差 + 前端派工前提缺失）。
4. **段 7 派工前提错误必含 10 大类**（v6 升级 v7）——v6 5 类（alembic / PS 5.1 / plans / web build / baseline）+ v7 新 5 类（浏览器老 SW cache / PWA 禁用 / checkSwBlacklist 删除 / setInterval 句柄 / heartbeat 静默）。任何派工必含这 10 类前提的隐含假设。
5. **PWA 永久禁用必走四步**（v7 新增）——vite-plugin-pwa `disable: true` + main.js 顶部 unregister + nginx 3 server block 全 `return 410` + postbuild 脚本兼容 sw.js 缺失（`process.exit(0)`）。任何 PWA 禁用任务必含四步 + 缺一步 nginx curl 验证 410。
6. **checkSwBlacklist 这类 self-loop check 必整段删**（v7 新增）——仅注释调用方不够，函数定义 + 调用方 + 相关常量一起 `if(false)` 包裹或彻底删除；新加自检函数必考虑"PWA 禁用后还该不该存在"。
7. **setInterval / setTimeout 必存 timer 句柄 + onUnmounted 清理**（v7 新增）——timer 存 ref + 组件 unmount 时 `clearInterval(ref.value)`，避免 Dashboard 时钟 / 通知 polling / 日志推送等场景泄漏触发刷新循环。
8. **heartbeat / setTimeout 警告按主指挥策略执行**（v7 新增）——保留 timer 重置逻辑（避免 W68 H-5 heartbeat 循环 bug），console 警告按主指挥"完全静默 / 降为 info / 保留 warn"策略调整；删 console.warn 但 timer 必保留。

## §6 v1/v2/v3/v4/v5/v6/v7 完整兼容矩阵

| 版本 | 段数 | 核心能力 | Alembic 门禁 | PS 5.1 门禁 | plans 真验证 | web build 约束 | 反馈循环 | 合并顺序 | 派工前提沉淀 | 适用 |
|---|---|---|---|---|---|---|---|---|---|---|
| v1 | 3 | 基本角色/范围/交付物 | 未明确 | 未明确 | 未明确 | 未明确 | 无 | 无 | 无 | 历史单 agent 小任务 |
| v2 | 4 | + 测试/证据/分支边界 | 有基本 heads | 有调用示例但不严格 | 以 status 为主 | 未明确 | 无 | 无 | 无 | 一般文档/前端任务 |
| v3 | 5 | 5 段结构雏形 | 强调串链但未覆盖 070 三方 | 未覆盖 PS 5.1 | 未覆盖自报偏差 | 未明确 | 无 | 无 | 无 | W68 第 12 批 |
| v4 | 5 | 完整 5 段 + 前置门禁 + 证据闭环 | revision 唯一 + 最新 head + 双头拍板 + 重编号串链 | 空格参数 + [string] + 严格 -eq + 双模式实跑 | grep plans + 5 项 backlog + COMPLETED+真 commit | 未明确 | 无 | 无 | 无 | W68 第 13 批 + W71 |
| v5 | 6 | v4 + 段 5 反馈 + 段 6 合并顺序 | 同 v4 | 同 v4 | 同 v4 | 未明确 | 段 5 必填 3 项 | 段 6 表必含 | 无 | W68 第 14 批 + W71+ |
| v6 | 7 | v5 + 段 5 升级 6 项 + 段 7 5 大类 + web build | 同 v4 + 预分配 revision 号段 | 同 v4 | 同 v4 | 强制 `npm run build` | 段 5 必填 6 项 + 24h 内 | 段 6 表 + 跨 PR 部署 checklist | 段 7 5 类 + 24h 内 | W68 第 15 批 + W72 |
| **v7** | **8** | **v6 + 段 5 升级 9 项 + 段 7 升级 10 大类 + web grep + PWA 禁用四步 + setInterval 句柄 + heartbeat 静默** | **同 v6** | **同 v6** | **同 v6** | **强制 `npm run build` + 编译产物 grep** | **段 5 必填 9 项 + 24h 内** | **段 6 表 + 三段串联（alembic + dist rebuild + nginx reload）** | **段 7 必填 10 类 + 24h 内** | **W71 batch + W73** |

### v6 → v7 升级路径

1. 段 1–2：完全沿用 v6，不改任何字。
2. 段 3：在"其他任务"前新增"前端任务（v7 新增）" + "PWA / SW 状态（v7 新增）" 两类检查。
3. 段 4：在"未完成项写 BLOCKED"前新增"web 改动必须 grep 验证（v7 新增）" + "runtime 心跳 / console 噪声（v7 新增）" 两类策略。
4. 段 5：从 6 项必填升级为 9 项必填（保留 v6 6 项 + 新增 3 项实战信号）。
5. 段 6：在合并触发条件表前新增"v7 新增 实战 5 hot-fix 必含三段串联"段。
6. 段 7：从 5 类必填升级为 10 类必填（保留 v6 5 类 + 新增 5 类实战派工前提）。

### v5 → v7 升级路径（两步到位）

1. **Step 1（v5 → v6）**：段 5 升级为 6 项 + 追加段 7（v6 5 类）+ 段 4 加 web build 约束。
2. **Step 2（v6 → v7）**：段 3/4 升级 + 段 5 9 项 + 段 6 三段串联 + 段 7 10 类。

### v4/v3/v2/v1 → v7 升级路径

不推荐逐步升级；直接整模板替换为 v7。v3 及之前无反馈 / 合并 / 前提机制，无法兼容。

### v7 默认应用范围

- **W68 第 14 批已应用 v6**：H-1 ~ H-5 五次 hot-fix 派工时已用 v6。
- **W71 batch 派工**：默认 v7；不再回退到 v6。
- **W73 调研任务**：必须用 v7（避免 plans 自报偏差 + 前端派工前提缺失）。

## §7 v7 发布前自检清单

- [ ] 段 1 写清角色、范围、不变量、当前分支、基线 commit、依赖 agent。
- [ ] 段 2 列出文件、规模和禁止修改项。
- [ ] 段 3 含 plans grep 和 Alembic heads 前置检查。
- [ ] 段 3 写明双头必须报主指挥，不能私改。
- [ ] **段 3 含"前端任务 5 hot-fix 链路检查" + "PWA / SW 状态检查"（v7 新增）**。
- [ ] 段 4 含 PS 5.1 三项 binding 约束。
- [ ] 段 4 显式 "web 改动必须 `npm run build`，禁止 vite build 直跑"。
- [ ] **段 4 含"web 改动必 grep 验证" + "runtime 心跳 / setInterval 策略"（v7 新增）**。
- [ ] 段 4 要求真 commit、测试结果和 BLOCKED 原因。
- [ ] 段 5 必填 9 项提示词齐全（v6 6 项 + v7 浏览器状态轨迹 / PWA 副作用 / runtime 心跳 3 项）。
- [ ] 段 5 含"9 项缺一不可"约束。
- [ ] 段 6 含合并链表格 + alembic 串单链位置列。
- [ ] **段 6 含"实战 5 hot-fix 必含 alembic + dist rebuild + nginx reload 三段串联"（v7 新增）**。
- [ ] 段 6 含"agent 不主动 merge / push"约束。
- [ ] 段 6 含跨 PR 部署 checklist（alembic 场景）。
- [ ] 段 7 必填 10 大类派工前提错误（v6 5 类 + v7 浏览器老 SW cache / PWA 禁用 / checkSwBlacklist / setInterval / heartbeat 5 类）。
- [ ] 段 7 沉淀规则统一在 memory/。
- [ ] 段 7 24h 内未填视为派工违规。
- [ ] 文档任务完成 `git diff --check`。
- [ ] migration 合并完成后只有一个 head。
- [ ] plans 调研结果有 backlog docs 或 COMPLETED 真 commit。
- [ ] **web 改动 grep 验证关键字符串次数 ≥ 0 / ≤ 1**（v7 新增）。
- [ ] 段 5 反馈至少收到 N ≥ 5 agents 才能汇总升级 v8。
- [ ] 锚点范式变化显式追踪（段 5 第 6 项 + 段 7 第 10 类）。

## §8 v6 派工任务如何升级到 v7（兼容方式）

如果主指挥以前用 v6 派工（未含段 3/4/5 v7 升级 + 段 6 三段串联 + 段 7 5 新类），需要升级到 v7：

1. **找到原 v6 prompt**：在派工频道搜索最近 7 天内的 prompt 文本。
2. **升级段 3**：在"其他任务"前新增"前端任务（v7 新增）" + "PWA / SW 状态（v7 新增）" 两类检查。
3. **升级段 4**：在"未完成项写 BLOCKED"前新增"web 改动必 grep 验证" + "runtime 心跳 / console 噪声" 两类策略。
4. **升级段 5**：从 6 项必填升级为 9 项必填（+ 浏览器状态轨迹 / PWA & SW 副作用 / runtime 心跳 3 项）。
5. **升级段 6**：合并链表格前加"v7 新增 实战 5 hot-fix 必含三段串联"段（alembic + dist rebuild + nginx reload）。
6. **升级段 7**：从 5 类必填升级为 10 类必填（+ 浏览器老 SW cache / PWA 禁用 / checkSwBlacklist / setInterval / heartbeat 5 类）。
7. **保留段 1–2 原文**：不要改任何字，否则派工追溯链断。
8. **追加时机**：派工发出后 1 小时内追加 v7 段 3/4/5/6/7 升级给已开工 agent；agent 必须承认收到后再继续。

这种方式保证 v6 派工和 v7 派工可并存，不强制迁移。

## §9 v7 默认应用范围

- **W68 第 14 批 H-1~H-5 已应用 v6**：commit `49ebe9b33` / `3207aea62` / `72eaae07f` / `ff9b6b3e2` / `960f8abe1` / `85619c012`。
- **W71 batch 派工**：默认 v7；尤其是前端 / PWA / SW / setInterval / heartbeat 类任务，必须把对应 v7 段 3/4/5/6/7 门禁原样写进 prompt。
- **W73 调研任务**：必须用 v7（避免 plans 自报偏差 + 前端派工前提缺失）。

## 结语

v7 不是替换 v6，而是补一段让模板"前端/浏览器/PWA/SW/setInterval/heartbeat 五类实战派工前提显式沉淀 + 反馈颗粒度强制提升到 9 项 + web build 命令 + 编译产物 grep + 三段合并串联"。段 5 升级让 agent 反哺模板更具体（含浏览器实测 grep 数），段 7 让主指挥派工的隐含前提（前端派工 5 类 + 后端派工 5 类）事后被显式记录。这样 W71 batch + W73 派工可以基于"经过 W68 H-1~H-5 五次实战反馈的模板 + 经过前后端双 10 类前提沉淀的纪律 + 经过 web build + grep + 三段串联强约束的命令"启动下一轮，更可预测、更易追溯、更不易合并错。

---

**版本 v7，2026-07-24/27，W71st batch A-2 起草，主指挥合并后正式生效。**

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**
