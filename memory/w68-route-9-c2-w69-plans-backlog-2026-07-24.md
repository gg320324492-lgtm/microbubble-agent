# W68 第 9 批 C-2：W69 Plans Backlog 监控与触发评估

**日期**：2026-07-24
**任务**：W68 第 9 批 C-2
**范围**：docs + memory only
**锚点范式**：第 112 守恒
**分支**：`docs/w69-plans-backlog-2026-07-24`
**基线**：`main` HEAD `f14cb43c1`

---

## 1. 背景与范围

W68 第 6+7 批留下若干 W69 监控对象，混合三种状态：

1. 真正未实现的小缺口。
2. 已实施但 Status commit 错配。
3. 不能直接派小修的长期路线。

标题写“6 plans”，输入实际列 7 个文件。
本次逐文件覆盖 7 个，按工作性质归并为 6 个监控对象，
再组合成 5 个 W69 agent 包，既不漏项也不浪费名额。

本任务维持 **0 production code 改动铁律**：

- 新建 W69 backlog docs。
- 新建本 memory。
- 不改 `plans/*.md` Status/body。
- 不改 app/web/scripts/config/migration。
- 不运行改变数据库或模型资产的命令。

---

## 2. 核心结论

旧审计必须用当前 HEAD 复核。
读源码并执行 `git log/show/blame` 后确认：

- ST 5.6.0 已实施：`c8d4df3e2`。
- MeetingRoom token 已实施：`c741de9d47`，后续 `77eb700d81`。
- dedup toggle 已删除：`425e579944`。
- Drive MIME/样式去重已实施：`0d03d2e528`。
- benchmark report/results 已由 `4dd199dda` 入库；Ollama 启停脚本仍缺。

因此设四级状态：

- **T0**：已实现，只做验真/Status 闭环。
- **T1**：0.5-2 人天小缺口。
- **T2**：8-12 人天路线，先 gap matrix。
- **T3**：4-24 人月商业化，仅留未来。

### 6 个监控对象

| 对象 | plan 文件 | 当前判定 |
|---|---|---|
| ST 5.6.0 | plan-playwright-greedy-flurry | T0 验真 |
| Mobile Drive 入口 | memoized-pondering-marble | T1 未做 |
| Drive 长期路线 | ppt-word-replicated-swing | T2 先 audit |
| Ollama scripts | dazzling-leaping-pretzel | T1 脚本缺 |
| Status A | delegated + distributed | T0 真 commit 已找到 |
| Status B | fizzy | T0 真 commit 已找到 |

### 5-agent 预排

1. Agent 1：ST 运行时验真 + Ollama scripts。
2. Agent 2：Mobile TabBar Drive 入口。
3. Agent 3：三个 Status 证据闭环。
4. Agent 4：Drive 后端 gap/首 tranche。
5. Agent 5：Drive 前端/mobile gap/首 tranche。

短期默认只批准 Agent 1-3。
Agent 4-5 第一阶段只读，不自动获得 production 实施授权。

---

## 3. 锚点范式第 112 守恒

第 112 守恒不是新增代码，而是把“模糊留尾”转换成可验证触发系统：

- 7 个输入文件 100% 覆盖。
- 6 个对象 100% 分级。
- 5-agent 派工不重叠、不漏项。
- 每项有触发与 STOP 条件。
- 短期/中期/长期边界明确。
- 已完成项不再因旧 Status 被重复实现。
- 最终 diff 只有 docs + memory。

锚点含义是让事实、计划和实施授权重新对齐，
不是把所有候选强行标 COMPLETED 或增加提交数量。

---

## 4. 五条新铁律

### 铁律 1：留 W69 plans 必调研，旧审计不能直接当当前事实

上轮写“未实施”的功能，可能已被其他批次完成。
本次 ST、MeetingRoom、dedup、Drive MIME 都找到真实 commit。

派工前必须：

1. 读 plan body。
2. 读当前源码。
3. `git log` 搜主题。
4. `git show` 验产物。
5. 多候选时用 `git blame` 定主归因。

缺一步只能标“待核验”，不能标“待实施”。

### 铁律 2：派工预排必须清晰到输入、输出、依赖和 STOP 条件

每个派工包必须写明：

- 输入文件/证据。
- T0/T1/T2/T3 状态。
- 允许改动范围。
- 前置主指挥决策。
- 验收方式。
- STOP 条件。

纯 Status 小修合并派工，长期路线拆双 agent，
不能机械地一 plan 一 agent。

### 铁律 3：短期、中期、长期必须分层

- 短期 W69 1-2 周：5 个 0.5-2 人天小修/验真包。
- 中期 W69-W70 约 1 月：Drive gap 后 8-12 人天。
- 长期 Q4：`exe-logical-pie` 4-24 人月。

中期先 audit 再拍 tranche；长期只写资源门槛。
agent 不得“顺手”把 T2/T3 带入 T1 提交。

### 铁律 4：估时必须包含风险

人天必须包含调研、实施、测试、回归和收口，
并考虑：

- Status/commit 错配验真。
- 源码与容器依赖漂移。
- source/dist 和 PWA manifest。
- alembic 单链。
- 移动多尺寸和触摸目标。
- Ollama 代理/GPU/volume/backend 漂移。
- 部署和回滚。

不能把“写代码 0.5 天”当作“完整交付 0.5 天”。

### 铁律 5：主指挥拍板才发起，backlog 不是授权

以下事项必须主指挥决定：

- TabBar 5 项还是 6 项。
- Ollama fallback 是否保留。
- plans Status 是否修改。
- Drive 8-12 人天首 tranche。
- Q4 商业化是否启动。

未拍板项默认 STOP，不由 agent 自行扩大范围。

---

## 5. 逐项证据与触发

### ST 5.6.0

证据：`requirements.txt`、`embedding_service.py`、`test_st5_compat.py`、`c8d4df3e2`。
默认只做容器运行时验真；版本/测试/维度异常才恢复 1-2 人天实施。

### Mobile TabBar Drive

证据：`/drive` 和 `MobileDriveView` 已存在；TabBar 仍只有
首页/听会/对话/任务/我的。
主指挥拍板 5/6 项后，0.5 人天实现并做多尺寸导航测试。

### Drive 路线

证据：migrations `040-048`、PR8/PR9/PR10 文档和测试均已存在，
PR6 部分功能曾按决策删除。
旧“30-40%”比例不可直接用；先由 Agent 4/5 重算 gap，
主指挥再选择 4-6 人天首 tranche。

### Ollama

证据：dispatch/fallback 和 benchmark report/results 已有；
`start_ollama.ps1` / `stop_ollama.ps1` 缺。
保留 fallback 才补幂等脚本；若完全移除则标 SUPERSEDED。

### 三个 Status 错配

- delegated：`0d03d2e528` 精确实施 plan body。
- distributed：`c741de9d47` token 化，`77eb700d81` glass 收敛。
- fizzy：`425e579944` 删除 toggle；`cfd486b638` 是前置去重。

主指挥批准后只改 Status，不重做 production，
也不运行历史 KB 数据清理脚本。

---

## 6. 主指挥建议

### 短期

优先关闭 T0 证据不确定性，再做 TabBar，
最后按 Ollama fallback 决策补脚本。
ST 默认验真，不重复升级。

### 中期

批准双 agent gap matrix 不等于批准全量实施：

- 缺口 <20%：2-4 人天单 PR。
- 缺口 20-40%：8-12 人天，拆 2-3 PR。
- 已删除功能：不自动恢复。
- 已演化到 CRDT：转 PR10。
- 新 migration：写死串接，merge 后验证唯一 head。

### 长期

`exe-logical-pie` 覆盖 HA、认证、多组织 SaaS、桌面 EXE、
移动 APP、合规和上架，估时 4-24 人月。
只有外部付费目标、预算/人员、法务运维责任和 W19 重新拍板后才启动。

---

## 7. 0 Production Code 守恒证明

最终 diff 仅包含：

- `docs/w69-plans-backlog-2026-07-24.md`
- `memory/w68-route-9-c2-w69-plans-backlog-2026-07-24.md`

不包含 app/web/alembic/scripts/requirements/config/plans。
因此锚点范式第 112 在只读调研与文档沉淀层完整守恒。

---

## 8. 收官

W69 留尾的真实结构是：

- 4 类已实施但证据/Status 未闭环。
- 2 类明确小缺口：Mobile TabBar、Ollama scripts。
- 1 类中期 Drive 路线，需重新量化。
- 1 个 Q4 商业化路线继续留未来。

核心原则：**下一 wave 先证明“还需要做”，再讨论“怎么做”；主指挥未拍板，默认不发起。**
