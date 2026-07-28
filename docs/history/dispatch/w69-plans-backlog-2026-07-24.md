# W69 Plans Backlog：监控、触发评估与派工预排（2026-07-24）

> **任务**：W68 第 9 批 C-2 — 6 个留 W69 plans 监控 + 触发评估
> **基线**：`main` HEAD `f14cb43c1`
> **范围**：仅 docs + memory 调研，不修改 production code 或 plans Status
> **授权原则**：本 backlog 不是实施授权；只有主指挥拍板后才发起 W69 任务
> **估时**：包含调研、实施、测试、回归和提交收口

---

## 0. 执行摘要与计数口径

任务标题写“6 plans”，输入清单实际列出 7 个 plan 文件。
本报告逐文件覆盖全部 7 个，并按工作性质归并为 6 个监控对象：

1. ST 5.6.0 验真：`plan-playwright-greedy-flurry`
2. Mobile TabBar Drive 入口：`memoized-pondering-marble`
3. Drive v2 长期路线：`ppt-word-replicated-swing`
4. Ollama scripts/report：`dazzling-leaping-pretzel`
5. Status 闭环 A：`delegated-orbiting-curry` + `distributed-coalescing-stallman`
6. Status 闭环 B：`fizzy-cooking-puzzle`

6 个监控对象再组合成 5 个 W69 agent 包，避免纯 Status 核验浪费独立 agent。
当前 HEAD 复核发现 4 类候选已有真实实现：

- ST 5.6.0：commit `c8d4df3e2`。
- MeetingRoom token：commit `c741de9d47`，后续 `77eb700d81`。
- dedup toggle 删除：commit `425e579944`。
- Drive MIME/样式去重：commit `0d03d2e528`。

因此 W69 必须区分：

| 等级 | 含义 | 默认动作 |
|---|---|---|
| T0 | 已实现，仅归因未闭环 | 验真/Status-only，不重做 |
| T1 | 0.5-2 人天明确小缺口 | W69 1-2 周内候选 |
| T2 | 8-12 人天多模块路线 | 先 audit，再二次拍板 |
| T3 | 4-24 人月商业化路线 | Q4 仅保留未来 |

---

## 1. 6 个监控对象详细调研

### 1.1 `plan-playwright-greedy-flurry`：sentence-transformers 2.3.1 → 5.6.0

#### 背景

W68 将该名称映射到 sentence-transformers 跨三大版本升级。
目标包括依赖升级、Qwen3 native loading、wrapper 清理和兼容验证。
输入完整实施估时为 **1-2 人天**。

#### 当前进度

当前仓库已有完整实现证据：

- `requirements.txt` 锁定 `sentence-transformers==5.6.0`。
- commit `c8d4df3e2` 明确完成 Phase 1+2。
- `app/services/embedding_service.py` 使用 ST 5.6.0 native loading。
- `tests/test_st5_compat.py` 断言版本与关键 API 不变量。
- ROADMAP 和升级文档均记录已上线。

**判定：T0。W68“未升级”结论已被当前 HEAD 覆盖。**

#### W69 预排与触发

所属 **Agent 1：运行时与 LLM 工具链验真包**。
默认只跑版本断言、兼容测试和容器 freeze 核对。
任一条件出现才恢复 production 实施：

1. 容器实际版本不是 5.6.0。
2. `tests/test_st5_compat.py` 失败。
3. Qwen3 embedding 初始化、维度或查询出现回归。
4. requirements 与生产镜像漂移。

#### 估时与风险

- 当前验真：**0.25-0.5 人天**。
- 若运行环境漂移：恢复 **1-2 人天**。
- 风险：只看源码不看容器，会产生“代码完成、运行环境未完成”假阳性。
- 验收：运行时版本、embedding 初始化、兼容测试三层全绿。

---

### 1.2 `memoized-pondering-marble`：Mobile TabBar Drive 入口

#### 背景

Drive 已有独立移动端页面，但底部固定 TabBar 应提供“网盘”入口。
输入估时为 **0.5 人天**，实质是在 Mobile TabBar 增加 1 项并验证导航。

#### 当前进度

- `/drive` 已路由到 `MobileDriveView`。
- `MobileDriveView.vue` 已有文件/收藏/最近/团队 4 tab。
- `web/src/components/mobile/TabBar.vue` 当前固定为：
  `首页 / 听会 / 对话 / 任务 / 我的`。
- `items` 数组没有 `/drive` 或“网盘”。

**判定：T1。页面和路由已具备，入口明确未做。**

#### W69 预排与触发

所属 **Agent 2：Mobile TabBar Drive 入口**。
主指挥必须先决定：

1. 维持 5 项还是扩为 6 项。
2. 若维持 5 项，替换哪一项。
3. 最终入口继续使用 `/drive`，不新增 `/m-drive` 平行 URL。

实施时同步核对 `activeRoute` 对路由名 `Drive` 的小写匹配，
并增加组件或 Playwright 导航断言。

#### 估时与风险

- 实施 + 验证：**0.5 人天**。
- 若需重做信息架构/多尺寸视觉回归：**0.5-1 人天**。
- 风险：6 项在 320-375px 拥挤，触摸目标可能小于 44px。
- 验收：点击到 `/drive`、激活态正确、dark/safe-area 正常、桌面不受影响。

---

### 1.3 `ppt-word-replicated-swing`：Drive v2 路线图 PR2-5/7/8

#### 背景

该 plan 实际是 Drive v2 深度升级路线，不只是 PPT/Word 单点功能。
覆盖回收站、星标、KB/Drive 双模、秒传与版本、分片/配额/缩略图、
文件请求/审计及独立移动端。
W68 曾以“只完成 30-40%”留 W69，输入估时 **8-12 人天**。

#### 当前进度

旧比例不能直接作为当前事实；当前仓库已有大量后续落地：

- alembic `040-048` 覆盖 storage mode、分享、星标、版本、配额、通知、请求和审计。
- PR8 已有独立 MobileDriveView 和移动预览。
- PR9 已有评论 thread、版本历史、版本对比和移动评论。
- PR10 已有 CRDT 调研、骨架表和部署文档。
- PR6 ActivityFeedView 曾实施后按主指挥决策删除。

**判定：T2。路线仍需治理，但必须先重算真实完成度。**

#### W69 预排与触发

所属 **Agent 4 + Agent 5：Drive 双 agent**。

- Agent 4：schema/service/API/权限/migration gap matrix。
- Agent 5：desktop/mobile/PWA/E2E/设计系统 gap matrix。

先并行只读审计 0.5-1 天，每项标记：
`DONE / PARTIAL / DELETED_BY_DECISION / NOT_STARTED / SUPERSEDED`，
并附 commit、文件和测试证据。

只有主指挥回答以下问题后才进入 8-12 人天实施：

1. 补旧 plan 缺口，还是按 PR9/PR10 重新定义路线？
2. PR6 已删除功能是否允许恢复？
3. 哪些验收项仍有真实用户痛点？
4. 是否继续维持 W19 选项 A？
5. 先做哪个 4-6 人天 tranche？

#### 估时与风险

- gap matrix：**1-2 人天**（双 agent 并行）。
- 确认后的实施：**8-12 人天**，拆 2-3 个 PR。
- 风险：按旧 plan 重做已有功能；并行 migration 接同一上游造成多 head。
- 验收：每项有证据；只实施批准 tranche；alembic 最终唯一 head。

---

### 1.4 `dazzling-leaping-pretzel`：Ollama scripts + benchmark reports

#### 背景

该 plan 混合 OpenAI-compatible backend、ToolCallConverter、Ollama 本地部署和
3-way benchmark。W68 将遗留概括为 scripts + reports 缺，输入估时 **1-2 人天**。

#### 当前进度

- `app/core/llm.py` 已支持 openai_compat/Ollama dispatch 与 fallback。
- commit `d4fdab3f1` 完成 Ollama backend dispatch。
- commit `4dd199dda` 已提交 `docs/llm-benchmark-2026-07-02.md` 和全量结果。
- `tests/qa-bench/results/` 已有 mimo、qwen3:8b、qwen3:14b 数据。
- 仓库没有 `scripts/start_ollama.ps1` / `scripts/stop_ollama.ps1`。

**判定：T1。报告已有，缺口集中在可复现启停脚本。**

#### W69 预排与触发

所属 **Agent 1：运行时与 LLM 工具链验真包**。
若 Ollama 仍作为 mimo 429/离线 fallback，则：

1. 核对当前 Docker/独立容器运行模式。
2. 补幂等 PowerShell 启停、代理、GPU、volume 和健康检查。
3. 不提交密钥、模型 blob 或 `.ollama` 私有内容。
4. 配置没变化时复用既有 report，不重复 benchmark。

若生产决定彻底移除 Ollama fallback，则转 SUPERSEDED，不补脚本。

#### 估时与风险

- 完整脚本 + smoke + 文档：**1-2 人天**。
- 最小启停脚本、不重跑 benchmark：**0.5-1 人天**。
- 风险：Git Bash 路径翻译、容器 localhost、代理/GPU 差异。
- 风险：把 `LLM_BACKEND=ollama` 留在生产，复现 Connection error。
- 验收：start/stop 幂等，`/api/tags`、`/v1/models` 健康，生产 backend 不漂移。

---

### 1.5 Status 闭环 A：`delegated-orbiting-curry` + `distributed-coalescing-stallman`

#### delegated 背景与进度

plan body 要求：

- 删除 `FilePreviewDialog.vue` 重复 `drive-view.css` import。
- 删除 deploy 脚本旧 MIME 注入块，统一使用 `ensure_mime()`。

commit `0d03d2e528` 的说明明确写 “following the delegated-orbiting-curry plan”，
且 diff 精确完成两项改动。

**判定：T0，plan body 已实施，Status 待证据闭环。**

#### distributed 背景与进度

plan body 要求把 MeetingRoom 三处浅色硬编码替换为 theme tokens。
`git blame/show` 找到真实提交：

- `c741de9d47`：`.meeting-room`、`.room-header`、`.room-main` token 化。
- `77eb700d81`：header 后续收敛到共享 glass 样式。

当前源码无 plan 指定的 3 处硬编码浅色。

**判定：T0，不能再按 0.5 人天重复改 CSS。**

#### W69 预排、估时与风险

所属 **Agent 3：Status 证据闭环包**。
主指挥批准后只改 plans Status，不改 plan body 或 production code。

- delegated：记录 `0d03d2e528`。
- distributed：记录 `c741de9d47` + `77eb700d81`。
- 合并耗时：**0.5-1 人天**。
- 若真实视觉回归，distributed 才恢复 **0.5 人天** production 小修。
- 风险：继续用大范围候选 commit 而非行级真实 commit。
- 验收：`git show <hash> -- <target>` 精确命中 plan body diff。

---

### 1.6 Status 闭环 B：`fizzy-cooking-puzzle`

#### 背景

plan body 要求移除知识库 dedup toggle，但保留 `displayedItems` default-on：
删除 switch、prop、emit、KnowledgeView localStorage key 和 watcher，不改后端 stats。
W68 Status 错误引用 PWA InstallPrompt commit。

#### 当前进度

真实 commit 为 `425e579944 fix(web): 移除 dedup toggle UI + displayedItems 永远 default-on`。
当前源码与 plan 一致：

- KnowledgeDashboard 无 switch、prop、emit。
- `displayedItems` 始终按 title 分组取最小 id。
- KnowledgeView 不读取 `mnb:kb:dedupView`。

**判定：T0，功能完成，Status commit 错配待闭环。**

#### W69 预排、估时与风险

所属 **Agent 3：Status 证据闭环包**。
主指挥批准后把 Status 指向 `425e579944`；
注明 `cfd486b638` 是前置去重实现，不是 toggle 删除主 commit。

- 当前闭环：**0.25-0.5 人天**。
- 输入完整小修估时：**0.5 人天**。
- 风险：误跑历史 KB 数据清理脚本，改变生产数据。
- 验收：当前源码无 toggle/localStorage 读取，commit 精确覆盖两组件。

---

## 2. W69 派工预排：5 Agents

| Agent | 派工包 | 覆盖对象 | 工时 | 默认范围 |
|---|---|---|---:|---|
| 1 | 运行时与 LLM 验真 | plan-playwright + dazzling | 1-2d | tests/scripts/docs |
| 2 | Mobile TabBar Drive | memoized | 0.5d | 前端 + 测试，需 5/6 项拍板 |
| 3 | Status 合并小修 | delegated + distributed + fizzy | 0.5-1d | plans Status only |
| 4 | Drive 后端 gap/首 tranche | ppt-word | 4-6d | 先 audit 后实施 |
| 5 | Drive 前端/mobile gap/首 tranche | ppt-word | 4-6d | 先 audit 后实施 |

### 2.1 Agent 1

1. 证明 ST 源码、测试、容器版本一致。
2. 一致则 T0 收口，不重做升级。
3. 核对 Ollama fallback 是否保留。
4. 保留时补幂等脚本；不保留时建议 SUPERSEDED。
5. 不无意义重跑已有 benchmark。

### 2.2 Agent 2

1. 等主指挥决定 5 项或 6 项。
2. 更新 TabBar items 与 activeRoute。
3. 验证 320/375px、横屏、dark、safe area 和 44px 触摸目标。
4. 增加导航测试。

### 2.3 Agent 3

- delegated → `0d03d2e528`
- distributed → `c741de9d47` + `77eb700d81`
- fizzy → `425e579944`

必须主指挥批准；只改 Status，不改 body；每个 hash 先 `git show`。

### 2.4 Agent 4/5

第一阶段共同输出带证据的 gap matrix。
第二阶段只实施主指挥选择的一个 tranche。
如有新 migration，派工必须写明 `down_revision` 串接顺序；
前端必须用 `npm run build`，source/dist 同 commit。

### 2.5 时间盒

| 时间 | 动作 | 输出 |
|---|---|---|
| Day 1 | Agent 1-3 启动；4-5 只读审计 | 小修状态 + gap 初稿 |
| Day 2 | 短期验证；Drive 交叉复核 | 证据链 + 决策材料 |
| Day 3 | 主指挥 gate | STOP / STATUS-ONLY / IMPLEMENT |
| W69-W70 | 若批准，Drive 分 PR | 8-12 人天可回滚交付 |

---

## 3. 主指挥决策建议

### 3.1 短期：W69 1-2 周

按 5 个 0.5-2 人天包管理：

1. ST 运行时验真：默认 T0，异常才恢复 1-2d。
2. TabBar Drive：T1，0.5d，先拍板信息架构。
3. Ollama scripts：T1，1-2d，report 已有不重复生成。
4. Drive MIME + MeetingRoom Status：T0，0.5d。
5. dedup Status：T0，0.5d，严禁重跑数据清理。

建议先 T0 证据闭环，再做 TabBar，最后按 fallback 决策补 Ollama。

### 3.2 中期：W69-W70 约 1 月

先批准双 agent gap matrix，不直接批准 8-12 人天全量实施：

- 真实缺口 <20%：收缩为 2-4 人天单 PR。
- 缺口 20-40%：8-12 人天，拆 2-3 PR。
- 缺口来自已删除功能：尊重删除决策，不自动恢复。
- 已演化到 CRDT：转 PR10，不继续复用旧路线。
- 新 migration：严格单链，merge 后验证唯一 head。

### 3.3 长期：Q4 2026

`exe-logical-pie` 覆盖数据库 HA、认证、多组织 SaaS、桌面 EXE、
iOS/Android/HarmonyOS、合规、签名与上架，估时 **4-24 人月**。
它不是 W69 小修，不与 Drive backlog 混派。

触发条件：外部试用/付费目标、预算和人员、法务运维责任人、
多租户隔离与备份优先级、W19 选项 A 正式重新拍板。
条件未满足时只维护路线图。

---

## 4. 风险与禁止事项

估时必须包含 Status 验真、容器漂移、测试回归、PWA source/dist、
alembic 单链、移动多尺寸、Ollama 代理/GPU 和回滚时间。

禁止：

- 因旧报告写“未完成”就重做已有 commit。
- 在本任务修改 plans Status。
- agent 自行决定 TabBar 删除哪个入口。
- 复制已有 benchmark 生成假新报告。
- 两个 Drive agent 并行接同一 migration 上游。
- Ollama 脚本永久覆盖生产 backend。
- 未经主指挥拍板启动 T2/T3。

---

## 5. 完成定义与证据索引

- [x] 7 个输入 plan 文件全部覆盖。
- [x] 按任务口径归并为 6 个监控对象。
- [x] 每项有背景、进度、派工、估时、风险和验收。
- [x] 5-agent 预排明确。
- [x] 短期/中期/长期分层。
- [x] 0 production code 改动。
- [x] 不修改 plans Status。

| 对象 | 关键证据 |
|---|---|
| ST | `requirements.txt`; `test_st5_compat.py`; `c8d4df3e2` |
| Mobile | `TabBar.vue`; `MobileDriveView.vue`; router |
| Drive | migrations `040-048/061-064`; PR8/9/10 docs/tests |
| Ollama | `app/core/llm.py`; benchmark report/results; `4dd199dda` |
| MIME | `0d03d2e528` |
| MeetingRoom | `c741de9d47`; `77eb700d81` |
| dedup | `cfd486b638`; `425e579944` |
| 商业化 | `C:/Users/pc/.claude/plans/exe-logical-pie.md` |

**一句话建议**：W69 先用 3 个短期 agent 关闭证据不确定性和明确小缺口，
再让 2 个 Drive agent 只读量化真实缺口；没有主指挥二次拍板，不启动 8-12 人天实施。
