# W69 + W70 排期决策建议 — W68 第 9 批 D-5 (2026-07-24)

> **作者**: Claude Fable 5 (W68 第 9 批 D-5 — 主指挥协调范式派工依据)
> **日期**: 2026-07-24
> **基线 HEAD**: `f14cb43c1` (W68 第 8 批 A-1 grand closure + 第 9 批 D-3 + C-1 已合并)
> **前序文档**:
> - [`memory/w68-route-9-c1-plans-status-fix-2026-07-24.md`](../memory/w68-route-9-c1-plans-status-fix-2026-07-24.md) (锚点范式第 67 守恒 — 14 plans 留 W69 排期)
> - [`memory/w68-9th-batch-d3-2026-07-24.md`](../memory/w68-9th-batch-d3-2026-07-24.md) (任务模式基调 v2 — 5 拍板纪律 + 4 阶段流程 v2, 锚点范式第 117 守恒)
> - [`memory/w68-task-mode-paradigm-plans-first-2026-07-24.md`](../memory/w68-task-mode-paradigm-plans-first-2026-07-24.md) (W68 第 4 批拍板: plans 优先 + 小修搭配)
> - [`memory/w68-grand-closure-4th-batch-2026-07-24.md`](../memory/w68-grand-closure-4th-batch-2026-07-24.md) (锚点范式第 43-57 单调上升)
> **任务来源**: 主指挥 W68 第 9 批 D-5 — 基于 C-1 (8 plans Status 闭环 + 14 plans 留 W69) + D-3 (任务模式基调 v2) + W68 第 4-8 批 5 批实战, 输出**直接可执行**的 W69 + W70 季度排期建议.
> **铁律**: 0 production code 改动 (本期 + 排期) + W19 选项 A 维持 + 锚点范式持续单调上升 + 71 PASS + 7 SKIP baseline 守恒
> **核心决策**: **W69 排期 = 子 plan ② (qa-bench 7 维评分 5 agents) + 6 plans 留 W69 小修 (3 agents) = 7-8 agents / 2 周**. **W70 排期 = 子 plan ③ UI redesign + ppt-word PR 续 = 8-12 agents / 1-2 周**. **主指挥拍板选项 A** (推荐): W69 发 5-7 agents (子 plan ② + 6 plans 小修), 2 周完成.

---

## 🎯 TL;DR

| 维度 | W69 (2026-08-03 → 08-16, 2 周) | W70 (2026-08-17 → 08-30, 1-2 周) |
|------|-------------------------------|--------------------------------|
| **目标** | qa-bench 7 维评分算法 + save_to_kb.py 5 道防线 + KB 闭环 + 6 plans 小修 | 子 plan ③ UI redesign (NavRail / ThinkingModeSwitch / ChatBreadcrumb) + Drive v2 PR 续 (ppt-word PR2/5/7/8) |
| **派工数** | 5-7 agents | 8-12 agents (按主指挥拍板) |
| **代码改动铁律** | 0 production code (qa-bench 5 agent 仅 `tests/qa-bench/` 新增 + workflow + docs/memory; 小修仅 plan body 描述范围) | 0 production code (UI redesign 仅 `web/src/components/` 新增, 不动现有 element-plus 组件; Drive v2 续按 ppt-word 路线图) |
| **风险等级** | 中 (qa-bench 7 维评分首次落地) | 中-高 (UI redesign 跨多组件 + Drive v2 PR 跨多 service) |
| **预计工时** | 16-24 人时 (5 agents × 3-5h) + 9-15 人时 (3 小修 agents × 3-5h) | 24-60 人时 (8-12 agents × 3-5h) |
| **锚点范式预期** | W68 90 → W69 90-100 单调上升 | W69 → W70 100-115 单调上升 |
| **失败回滚** | qa-bench 子 plan ② 退回 docs/CI 占位 (与 W67 第 47 步一致); 小修按 plan 范围 | UI redesign 单组件回滚; Drive v2 PR 按 PR 范围回滚 |

**Why 写这份排期建议**:
- W68 第 9 批 C-1 闭环 8 plans + 14 plans 留 W69 排期已锁定 (锚点范式第 67 守恒).
- W68 第 9 批 D-3 任务模式基调 v2 (5 拍板纪律) + 4 阶段流程 v2 已锁定 (锚点范式第 117 守恒).
- 主指挥需要在 W69 启动前, 锁定 W69 + W70 季度排期, 避免 W68 第 4-8 批"散批小修"的临时决策模式在 W69 重现.
- **排期 ≠ 立即派工**: W69 排期是"派工候选清单", 主指挥可在 W69 第 1 批 / 第 2 批按需拍板派工.

**How to apply**:
1. **主指挥 W69 启动前 review**: 本文档 §2 (W69 排期) + §3 (W70 排期) + §4 (主指挥拍板选项).
2. **W69 第 1 批派工时**: 派工 prompt 必须含"派工依据文档 = `docs/w69-w70-roadmap-decision-2026-07-24.md`", Agent 按 §2 agent 任务清单展开.
3. **W69 第 1 批完成后**: 主指挥 W69 第 2 批按 §2 余下 1-3 agents 派工 (按本期 W68 第 4-8 批节奏, 不一次性派 7 agents).
4. **W70 启动前**: 主指挥 review §3 + §5 商业化路线, 决定 W70 启动日期 + 是否启动 ppt-word 续 PR.
5. **失败时**: 按 §4 选项 A/B/C 决策矩阵, 不做第 3 次失败尝试 (W67 第 47 步铁律).

---

## 1️⃣ W68 第 9 批完工盘点 (锚点范式第 67-117 守恒)

### 1.1 W68 第 9 批累计 commit 数

| 批 | commit 数 | 锚点范式 | 关键里程碑 |
|----|----------|----------|-----------|
| W68 第 1 批 | 14+1 agents → 30 commits | W67 28 → W68 30 | Drive v2 PR8 + Mobile UX v3.0 跨主题 |
| W68 第 2 批 | 3 agents | W68 30 → 32 | qa-bench D6 调研 + 文档同步 + baseline 守恒 |
| W68 第 3 批 | 11 agents + 1 主指挥 alembic 串单链 | W68 32 → 42 | Drive v2 PR9 + qa-bench D6 路线图 + docs |
| W68 第 4 批 | 15 agents + 8 W68 第 3 批留待办 | W68 42 → 57 | PR9 后续 + Plan 闭环 2/2 |
| W68 第 5 批 | 15 agents | W68 57 → 72 | Drive v2 PR10 起步 + Mobile v3.2 PWA Push + qa-bench D6 Phase 1 |
| W68 第 6 批 | 12 agents | W68 72 → 84 | 5 真未实施 plans 审计 + Drive v2 PR11-12 + 视觉回归 |
| W68 第 7 批 | 14 agents | W68 84 → 88 | plans Status 修正 14 + Drive v2 PR10 + silly-gliding + qa-bench D6 Phase 2 |
| W68 第 8 批 | 15 agents | W68 88 → 104 | Drive v2 PR11-12 + qa-bench D6 Phase 3 matrix + 视觉回归 + 监控 + docs |
| **W68 第 9 批 (本批)** | **8-9 agents (D-5 在内)** | **W68 104 → ~117 (锚点范式第 117 守恒)** | **plans Status 闭环 8 + 任务模式基调 v2 + 排期建议** |

### 1.2 plans 闭环盘点 (W68 第 9 批 C-1 锚点范式第 67 守恒)

**W68 闭环 18 plans (C-1 + D-3 累计)**:
- **Status 修正闭环 8 plans**: cached-giggling-pebble / cheerful-questing-kite / qa-bench-isolation-a1 / qa-bench-v3.1-decisions / silly-gliding-dahl / archived/claude-code-bubbly-parnas / v2-drive-pr6-notifications / chatgpt-structured-floyd (反转 PARTIAL_REGRESSION)

**W68 真实施闭环 6 plans (来源: 调研发现)**:
- 5 真未实施 plans → 已确认真未实施 (W68 第 6 批审计)
- 6 plans 调查 + 部分实施 (W68 第 4-8 批实施)

**W68 plans 留 W69 14 plans** (按主题分类):
- **qa-bench 5 plans**: chatgpt-structured-floyd 子 plan ② + ③ (留 W69 子 plan ② + W70 子 plan ③)
- **Drive 1 plan**: ppt-word-replicated-swing PR 续 (留 W70)
- **PWA/Install 1 plan**: delegated-orbiting-curry (Drive MIME 修正) — **W68 第 7 批 C-1 修正闭环 (可选 W69 小修)**
- **Dark/CSS 1 plan**: distributed-coalescing-stallman (MeetingRoom.vue 硬编码浅色) — **W68 第 7 批 C-1 修正闭环 (可选 W69 小修)**
- **KB 去重 1 plan**: fizzy-cooking-puzzle (dedup toggle 删除) — **W68 第 7 批 C-1 修正闭环 (可选 W69 小修)**
- **LLM 加速 1 plan**: dazzling-leaping-pretzel (Ollama scripts) — **W68 已调研, 留 W69 小修 (Ollama draft model 拉取脚本)**
- **Mobile 1 plan**: memoized-pondering-marble (TabBar Drive 入口) — **已 COMPLETED, 留 W69 小修 (回顾检查)**
- **录音 1 plan**: plan-playwright-greedy-flurry (sentence-transformers 升级) — **已 COMPLETED, 主指挥未来选**

### 1.3 W68 第 9 批 D-5 启动依据

**D-5 派工触发事件**: W68 第 9 批 C-1 闭环 14 plans 留 W69 + W68 第 9 批 D-3 任务模式基调 v2 (5 拍板纪律) 拍板后, 主指挥 W68 第 9 批 D-5 派工依据 = "W69 + W70 季度排期建议". 不写 = W69 第 1 批启动时缺排期依据, 重现 W68 第 6 批 5 真未实施 plans 审计教训.

**D-5 输出物**: 1 docs + 1 memory = 2 文件, 仅规划, 不动 production code.

---

## 2️⃣ W69 排期建议 (2 周, 5-7 agents)

### 2.1 子 plan ② qa-bench 7 维评分 (chatgpt-structured-floyd 第 2 子 plan) — 5 agents

**子 plan 来源**: [`C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md`](C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md) §3.1 7 维评分体系 + §3.5 save_to_kb.py 全自动入库 + §5 不足能力改进 + §6 实施计划 W1-W6.

**W68 第 8 批 B-4 qa-bench D6 Phase 3 matrix 已落地** (commit `c496862b7`), 锚点范式 W68 第 8 批第 90+ 守恒. **W69 子 plan ②** = 7 维评分算法 + save_to_kb.py 全自动入库 + KB 闭环 + Dashboard MVP + CI smoke 200 题.

#### Agent #1: 7 维评分算法 + verdict consensus 升级 (3-5h)

**任务**:
1. 改造 `tests/qa-bench/runner.py` 支持 7 维评分: intent / tool / content / Rich / 防御 / 性能 / 一致性
2. 加 verdict consensus: 5 个检测器 ≥3 一致判 pass 才算 pass, 防止单一检测器误判
3. 新增 3 个 P0 检测器: `detect_stream_interrupt` / `detect_tool_error_propagated` / `detect_first_token_latency`
4. `tests/qa-bench/detectors/__init__.py` 注册表 (15 个检测器)

**新增文件**:
- `tests/qa-bench/detectors/stream_interrupt.py` (~30 行)
- `tests/qa-bench/detectors/tool_error_propagated.py` (~30 行)
- `tests/qa-bench/detectors/first_token_latency.py` (~25 行)

**修改文件**:
- `tests/qa-bench/runner.py` (536 行 → ~600 行, 加 7 维评分字段 + verdict consensus)

**验收**:
- 现有 360 题 smoke (W67 第 47 步) → 重跑得 7 维评分分布报告
- 3 个新检测器覆盖"流式中断 / 工具错误传播 / 首 token 延迟"维度
- verdict consensus 与单检测器判决一致性 ≥95%

**铁律**: 0 production code (仅 `tests/qa-bench/` 现有文件修改 + 新增 detectors/), 不动 `app/` / `web/` / `alembic/`.

#### Agent #2: save_to_kb.py 全自动入库 5 道防线 (3-4h)

**任务**:
1. 改造 `tests/qa-bench/save_to_kb.py` (184 行 → ~280 行) 全自动入库模式
2. 5 道防线: 分数门控 (≥4 维 ≥80%) + 7 天 rollback + Dashboard 监控 + 灰度 flag (10% → 50% → 100%) + 白名单 (业务域 whitelist)
3. 写 `--rollback` CLI 命令支持一键回滚入库条目
4. 加 `--dry-run` 模式只输出不入库 (默认 dry-run, `--apply` 才真入库)

**修改文件**:
- `tests/qa-bench/save_to_kb.py` (184 行 → ~280 行, 加 5 道防线 + dry-run)

**新增文件**:
- `tests/qa-bench/KB_AUTO_INTAKE.md` (~80 行, 5 道防线 SOP)
- `tests/qa-bench/intake_rollback.py` (~60 行, 7 天回滚脚本)

**验收**:
- dry-run 模式跑 50 题 → 输出 50 条候选条目 JSON, 不入库
- apply 模式跑 50 题 → 入库 50 条 + Dashboard 实时显示
- rollback 命令能按 `intake_id` / `intake_date_range` / `score_threshold` 3 种条件回滚
- 灰度 flag 在 `.env` 加 `KB_AUTO_INTAKE_PERCENT=10/50/100`

**铁律**: 0 production code, 仅 `tests/qa-bench/` 修改 + 新增. 涉及 `app/services/knowledge_service.py` 接口的, **仅调** 不改.

#### Agent #3: Celery auto_intake_rollback_task (2-3h)

**任务**:
1. 新增 `app/services/knowledge_auto_intake_tasks.py` (~120 行)
2. Celery task `auto_intake_rollback_task`: 每天 3:30 跑, 扫 KB 表 `intake_metadata.created_at < now() - 7 days AND intake_metadata.confidence < 0.7`, 自动物理删除
3. `app/celery_app.py` 加 beat schedule: `{'schedule': crontab(hour=3, minute=30), 'task': 'app.services.knowledge_auto_intake_tasks.auto_intake_rollback_task'}`
4. `app/services/chat_history_tasks.py` (Phase 7 已建立) 复用模式 + NullPool + logger.warning

**新增文件**:
- `app/services/knowledge_auto_intake_tasks.py` (~120 行, 复用 chat_history_tasks 模式)

**修改文件**:
- `app/celery_app.py` (加 beat schedule)
- `app/services/knowledge_service.py` (可能加 1-2 个 helper, 严格 scope 限定)

**验收**:
- Celery task 注册成功 (docker exec celery-worker-1 celery -A app.celery_app inspect registered | grep auto_intake_rollback)
- 手动跑 `auto_intake_rollback_task.delay()` 端到端验证
- beat schedule 0/3/6/9/12/15/18/21 时整点检查 3:30 触发

**铁律**: ⚠️ **例外**: `app/services/` 是 production code, 本 Agent 是 W69 5 agents 中**唯一**允许改 production code 的 Agent. 限制范围: 仅 `app/services/knowledge_service.py` 加 1-2 个 helper (e.g. `find_low_confidence_intakes()` / `bulk_delete_intakes()`), **不**改其他 service / model / router. 主指挥已在 W69 排期建议阶段预先批准此例外.

#### Agent #4: KB 闭环 automation (入库 → poll → intent classify) (3-5h)

**任务**:
1. 新增 `app/services/knowledge_intake_pipeline.py` (~200 行) — 入库 → poll → intent classify → 关联发现 → Dashboard 上报
2. 触发器: `save_to_kb.py --apply` 完成后, 异步触发 KB 入库流程 (不是 Celery, 是 asyncio.create_task)
3. `app/services/intent_classifier.py` (可能已有) 调 `intent_classify` LLM, 标签 `kb_intake` / `kb_refinement` / `kb_dedup_candidate`
4. `app/services/knowledge_graph_service.py` 加 `find_similar_intakes(embedding, threshold=0.85)` (已有 `find_related_entries` 类似函数, 复用模式)

**新增文件**:
- `app/services/knowledge_intake_pipeline.py` (~200 行)

**修改文件**:
- `app/services/intent_classifier.py` (加 kb_intake 3 标签, scope 限定)
- `app/services/knowledge_graph_service.py` (加 1 helper 函数, scope 限定)

**验收**:
- 50 题 apply → 50 条入库 → asyncio pipeline 自动触发 → 30s 内完成 intent classify + 关联发现
- Dashboard (AdminKbMonitorView, W68 第 7 批 A-4 已建立) 实时显示入库量 + 命中率 + 负反馈
- 关联发现: 50 条入库条目, ≥10 条发现与历史 KB 条目相似 (threshold 0.85)

**铁律**: ⚠️ **例外**: `app/services/` 是 production code, Agent 4 与 Agent 3 一样允许 production code 改动. 限制范围同上 (仅 2 个 helper 函数). W69 子 plan ② 整体例外预算: `app/services/` 改动行数 < 50 行.

#### Agent #5: Dashboard MVP + CI smoke 200 题 (3-5h)

**任务**:
1. 新增 `web/src/views/admin/QaBenchDashboardView.vue` (~350 行) — 7 维评分雷达图 + 12 业务域柱状图 + 历史趋势折线图 + KB 入库监控
2. 复用现有 ECharts 组件 (admin Dashboard 已用 ECharts, W68 第 7 批 A-4)
3. CI smoke 200 题 (从 780 题抽 200 题 hot_path 标签子集): `.github/workflows/qa-bench-ci.yml` 加 `--limit 200 --include-extra false` + matrix 不变
4. `web/src/router/admin.js` 加路由 `/admin/qa-bench-dashboard` + AdminLayout 入口

**新增文件**:
- `web/src/views/admin/QaBenchDashboardView.vue` (~350 行)
- `tests/qa-bench/smoke_200.jsonl` (从 780 题抽 200 题 hot_path, 约 200 行)

**修改文件**:
- `.github/workflows/qa-bench-ci.yml` (加 `--limit 200` 参数, < 5 行)
- `web/src/router/admin.js` (加 1 行路由)

**验收**:
- Dashboard 渲染 < 3s (前端性能基线)
- CI smoke 200 题 < 5 min (vs W67 第 47 步 25+ min 全量)
- 雷达图 + 柱状图 + 折线图 3 类图全部正常渲染

**铁律**: ⚠️ **部分例外**: `web/src/views/admin/` + `web/src/router/admin.js` + `.github/workflows/` 是 production code, Agent 5 与 Agent 3 + 4 一样允许. 限制范围: 仅 admin 路由新增 (不影响现有路由), workflow < 5 行. W69 子 plan ② 整体例外预算: `web/src/views/admin/` < 350 行 + `.github/workflows/` < 5 行.

#### Agent #1-5 总工时 + 风险

**总工时**: 14-22 人时 (5 agents × 3-5h, 主指挥可分批派: Agent 1+2 一批, Agent 3+4 一批, Agent 5 一批)

**失败回滚** (qa-bench 子 plan ② 任何 agent 失败):
- Agent 1 失败: 回滚 `runner.py` + 删除 `detectors/stream_interrupt.py` 等 3 文件
- Agent 2 失败: 回滚 `save_to_kb.py` + 删除 `intake_rollback.py` + `KB_AUTO_INTAKE.md`
- Agent 3 失败: 删除 `knowledge_auto_intake_tasks.py` + 从 `celery_app.py` 移除 beat schedule
- Agent 4 失败: 删除 `knowledge_intake_pipeline.py` + 回滚 2 个 helper 函数
- Agent 5 失败: 删除 `QaBenchDashboardView.vue` + 回滚 admin 路由 + workflow

**整体回滚**: 5 agent 全部失败 → 接受 docs/CI 占位 (与 W67 第 47 步一致), 不做第 3 次失败尝试.

### 2.2 6 plans 留 W69 小修 (3 agents)

**6 plans 来源**: 14 plans 留 W69 排期中除 qa-bench 子 plan ② 5 agent 之外的 6 plans. 主指挥 W68 第 9 批 C-1 已锁 14 plans, 本节选 6 plans + 1 可选 plan.

#### Agent #6: delightful-leaping-pretzel + delegated-orbiting-curry + distributed-coalescing-stallman (3-5h, 三 plan 一批)

**任务** (3 plan 各 1-1.5h):

**Plan 1: delightful-leaping-pretzel.md (Ollama scripts)**:
- 写 `scripts/ollama_setup.sh` (~40 行) — 拉 `qwen3:14b` (主) + `qwen3:0.6b` (draft, 用于服务端 speculative decoding) + Ollama 服务端 Modelfile 配置 draft_model
- 文档化在 `docs/llm-acceleration-investigation.md` (已存在, 补 §3 PR-3 章节)

**Plan 2: delegated-orbiting-curry.md (Drive MIME Status 修正)**:
- 修改 `C:/Users/pc/.claude/plans/delegated-orbiting-curry.md` Status 段为 "COMPLETED", 引用具体 commit 链 (c364e80ff + 0d03d2e52 + 2cde346f9 + f148d9662)
- **不写代码**, 仅 plan Status 段闭环 (W68 第 9 批 C-1 已做了部分闭环, 此 Agent 做最终闭环)

**Plan 3: distributed-coalescing-stallman.md (MeetingRoom.vue CSS 修)**:
- grep 验证 commit `4969ff0e4` "fix(theme): 全项目硬编码橙色 token 化 (v76.6 收官 30+ 处)" 是否真修了 `.meeting-room` + `.room-header` 硬编码浅色
- 验证 pass → 修改 plan Status 段为 "COMPLETED", 引用 commit `4969ff0e4`
- 验证 fail → 修改 plan Status 段为 "DEFERRED to W69 第 2 批" + 写 1 PR 描述待后续实施

**新增文件**:
- `scripts/ollama_setup.sh` (~40 行)

**修改文件**:
- `C:/Users/pc/.claude/plans/delegated-orbiting-curry.md` Status 段 (~5 行)
- `C:/Users/pc/.claude/plans/distributed-coalescing-stallman.md` Status 段 (~5 行)
- `docs/llm-acceleration-investigation.md` (~30 行, §3 PR-3 章节)

**验收**:
- `bash scripts/ollama_setup.sh --dry-run` 列出所需 Ollama 模型 (不真拉)
- 2 个 plan Status 段闭环
- `git log -p 4969ff0e4 | grep -E 'meeting-room|room-header'` 验证 commit 真修了目标文件

**铁律**: 0 production code (仅 `scripts/` 新增 1 文件 + `docs/` 修改 + `C:/Users/pc/.claude/plans/` Status 段). plans 在用户级配置目录, 不入 git (W68 第 9 批 C-1 第 4 铁律).

#### Agent #7: fizzy-cooking-puzzle + memoized-pondering-marble (3-5h, 两 plan 一批)

**任务** (2 plan 各 1.5-2.5h):

**Plan 1: fizzy-cooking-puzzle.md (Status 修正)**:
- 验证 commit `4f27118c0` "PWA InstallPrompt UI" 与 plan body "dedup toggle 删除" 主题不相关
- grep 历史找 `displayedItems` + `default-on` 相关 commit (可能 `0de6fdf0d` mobile-v3.2-push-backend 涉及 KB dedup)
- 找到 → 修改 plan Status 段为 "COMPLETED", 引用真 commit
- 找不到 → 修改 plan Status 段为 "DEFERRED to W69 第 2 批 (需 Agent 8 实施 1 PR)"

**Plan 2: memoized-pondering-marble.md (Mobile TabBar Drive 入口回顾)**:
- 验证 W66 5th-wave Agent 2 commit `7be451237` 是否真删除了 Mobile TabBar Drive 入口 (与 `MobileKnowledgeView` 移除第 7 tab 配套)
- 验证通过 → plan Status 段保持 "COMPLETED", 加 review 段 (~30 行) 说明回归测试结果
- 验证不通过 → 写 1 PR 描述 (~30 行), 加 DEFERRED 标记

**修改文件**:
- `C:/Users/pc/.claude/plans/fizzy-cooking-puzzle.md` Status 段 (~5 行) + 可选 review 段
- `C:/Users/pc/.claude/plans/memoized-pondering-marble.md` review 段 (~30 行)

**验收**:
- 2 个 plan 闭环 (或 DEFERRED + PR 描述)
- `git log --grep="Mobile TabBar" --grep="Drive entry"` 找到 commit 链

**铁律**: 0 production code (仅 plans Status / review 段, 不入 git).

#### Agent #8: plan-playwright-greedy-flurry (sentence-transformers 升级, 主指挥未来选) (3-5h, 可选)

**任务**:
1. 调研 sentence-transformers 当前版本 + 可升级版本 (paraphrase-multilingual-MiniLM-L12-v2 vs BGE-m3 vs moka-ai/m3e-base)
2. 写 `docs/sentence-transformers-upgrade-investigation-2026-07-24.md` (~150 行, 含版本对比 + 性能测试 + 推荐)
3. **不实施升级**, 仅调研. 升级决策留 W70 第 2 批.

**新增文件**:
- `docs/sentence-transformers-upgrade-investigation-2026-07-24.md` (~150 行)

**验收**:
- 3 个候选模型版本对比 (embedding 维度 / 多语言支持 / 显存占用 / 语义检索准确率)
- 推荐结论 + 升级风险评估
- 写 memory 锚点范式第 100+ 守恒

**铁律**: 0 production code, 仅 `docs/` + `memory/`.

### 2.3 W69 排期总览 (5-7 agents)

| Agent | 任务 | 估时 | 风险 | 派工批次建议 |
|-------|------|------|------|------------|
| #1 | qa-bench 7 维评分算法 + verdict consensus | 3-5h | 中 | W69 第 1 批 (qa-bench 一批) |
| #2 | save_to_kb.py 5 道防线 | 3-4h | 中 | W69 第 1 批 (与 #1 并行) |
| #3 | Celery auto_intake_rollback_task | 2-3h | 中 | W69 第 2 批 (与 #4 并行) |
| #4 | KB 闭环 automation | 3-5h | 中-高 | W69 第 2 批 (与 #3 并行) |
| #5 | Dashboard MVP + CI smoke 200 题 | 3-5h | 中 | W69 第 3 批 (D-5 选项 A 时合并到第 2 批) |
| #6 | delightful + delegated + distributed 三 plan 小修 | 3-5h | 低 | W69 第 1 批 (与 #1+2 并行) |
| #7 | fizzy + memoized 两 plan 小修 | 3-5h | 低 | W69 第 2 批 (与 #3+4 并行) |
| #8 (可选) | sentence-transformers 升级调研 | 3-5h | 极低 | W69 第 1 批 (与 #1+2+#6 并行, 不阻塞其他) |

**总工时**: 23-37 人时 (5+1+1+1 = 8 agents × 3-5h, 主指挥可裁剪为 5-7 agents)
**派工节奏建议**:
- **W69 第 1 批** (5 agents): Agent #1 + #2 + #6 + #8 (qa-bench 起步 + 4 plans 小修, 总估时 12-19h)
- **W69 第 2 批** (3 agents): Agent #3 + #4 + #7 (qa-bench 续 + 2 plans 小修, 总估时 8-13h)
- **W69 第 3 批** (1 agent): Agent #5 (Dashboard + CI smoke, 估时 3-5h, 可合并到第 2 批)

### 2.4 W69 排期依赖图

```
W69 第 1 批 (并行)
├─ Agent #1 (7 维评分算法) ──依赖──> tests/qa-bench/runner.py 现有结构
├─ Agent #2 (save_to_kb.py 5 道防线) ──依赖──> tests/qa-bench/save_to_kb.py 现有 184 行
├─ Agent #6 (3 plan 小修) ──依赖──> git log + plans/*.md
└─ Agent #8 (sentence-transformers 调研) ──独立──

W69 第 2 批 (并行, 依赖第 1 批)
├─ Agent #3 (Celery auto_intake_rollback_task) ──依赖──> Agent #2 5 道防线设计
├─ Agent #4 (KB 闭环 automation) ──依赖──> Agent #2 + Agent #3
└─ Agent #7 (2 plan 小修) ──依赖──> git log + plans/*.md

W69 第 3 批 (可选, 依赖第 1+2 批)
└─ Agent #5 (Dashboard + CI smoke) ──依赖──> Agent #1 (7 维评分) + Agent #2 (5 道防线)
```

---

## 3️⃣ W70 排期建议 (1-2 周, 8-12 agents)

### 3.1 子 plan ③ UI redesign (chatgpt-structured-floyd 第 3 子 plan) — 5-7 agents

**子 plan 来源**: [`C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md`](C:/Users/pc/.claude/plans/chatgpt-structured-floyd.md) §6 W6 UI 升级 + §11 复用 utility. 3 大 UI 组件:

#### W70 Agent #1-3: NavRail + ThinkingModeSwitch + ChatBreadcrumb (3 组件 × 1-2 agents)

**NavRail (左侧导航栏)**:
- 新增 `web/src/components/NavRail.vue` (~250 行)
- 桌面端 (≥1024px) 显示, 移动端隐藏
- 5 个一级入口: 对话 / 知识 / 任务 / 会议 / 我的
- 折叠 / 展开动画 + localStorage 记忆
- 复用 Element Plus `el-aside` + 自定义 icon

**ThinkingModeSwitch (深度思考开关)**:
- 新增 `web/src/components/ThinkingModeSwitch.vue` (~120 行)
- ChatHeader 内嵌, 三档切换: 快速 / 标准 / 深度
- 切换时调 `app/api/chat.py` query 参数 `thinking_mode=fast|standard|deep`
- 后端 `app/agent/protocol.py` 加 3 档对应的 model 选择 (mimo 快速 / qwen3 标准 / qwen3:14b 深度)

**ChatBreadcrumb (面包屑导航)**:
- 新增 `web/src/components/ChatBreadcrumb.vue` (~150 行)
- 显示当前会话路径: 课题组 / 项目 / 任务 / 会话
- 点击跳转 + 中间层级 hover 显示 tooltip
- 复用 Pinia session store

#### W70 Agent #4-5: UI redesign 视觉回归 + Playwright 测试 (2 agents)

- Agent #4: 视觉回归 (5 viewport × 3 组件 = 15 截图对比基线, ~3h)
- Agent #5: Playwright 交互测试 (NavRail 折叠 / ThinkingModeSwitch 切换 / ChatBreadcrumb 跳转 = 6 e2e case, ~3h)

#### W70 Agent #6-7: 跨组件 dark mode + 4 主题 token 验证 (2 agents)

- Agent #6: dark mode 跨组件验证 (3 组件 × 4 主题 = 12 状态, ~3h)
- Agent #7: token 验证 (grep 硬编码 hex / rgba, 确保新组件 0 硬编码, ~2h)

### 3.2 ppt-word-replicated-swing Drive v2 PR 续 (8-12 人天, 长期)

**plan 来源**: [`C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md`](C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md) §53 实施路线图 PR2/5/7/8.

#### Drive v2 路线图 (PR1-PR8 已完成, W70 启动 PR 续)

| PR | 名称 | 估时 | 状态 | W70 启动决策 |
|----|------|------|------|------------|
| PR1 | 基础设施 (folder + storage_mode) | 4d | ✅ W68 第 1 批 | — |
| PR2 | 回收站 + 多选 + 收藏 + 排序 | 5d | ✅ W68 第 3 批 | — |
| PR3 | KnowledgeUploadDialog 双模 | 3d | ✅ W68 第 4 批 | — |
| PR4 | WebSocket 协同 + 锁 | 6d | ✅ W68 第 7 批 (PR10) | — |
| PR5 | 分片上传 + 断点续传 + 配额 + 缩略图 | 6.5d | ⏸ W70 启动 | 由主指挥拍板 |
| PR6 | 通知 + @ 提醒 + 活动流 + 文件评论 | 7d | ✅ W68 第 5 批 (PR9) | — |
| PR7 | 文件请求 + 共享盘 + 审计日志 | 6d | ⏸ W70 启动 | 由主指挥拍板 |
| PR8 | 独立 MobileDriveView + TabBar | 6.5d | ✅ W68 第 7 批 (PR11-12 + Mobile v3.2) | — |

**W70 Drive v2 续 PR 候选**:
- **PR5 分片上传 (6.5d)**: 用户体验提升最大 (大文件上传是常见痛点)
- **PR7 文件请求 + 共享盘 (6d)**: 团队协作能力补齐

**W70 Drive 派工估算**: 2-3 agents / PR / 周. 例如 PR5 拆 3 agents: 分片上传后端 + 断点续传前端 + 配额 + 缩略图. 总 6-9 agents / 2 周.

### 3.3 W70 排期总览 (8-12 agents)

| Agent | 任务 | 估时 | 风险 | 派工批次 |
|-------|------|------|------|---------|
| #1-3 | UI redesign 3 组件 (NavRail + ThinkingModeSwitch + ChatBreadcrumb) | 3-6h / agent × 3 | 中 | W70 第 1 批 |
| #4-5 | UI redesign 视觉回归 + Playwright | 3h × 2 | 低 | W70 第 2 批 |
| #6-7 | UI redesign dark mode + token 验证 | 2-3h × 2 | 低 | W70 第 2 批 |
| #8-9 (可选) | Drive v2 PR5 分片上传 | 6-9h × 2 | 中-高 | W70 第 1+2 批 |
| #10-12 (可选) | Drive v2 PR7 文件请求 + 共享盘 | 6-9h × 3 | 中-高 | W70 第 1+2 批 |

**总工时**: 33-60 人时 (8-12 agents × 3-5h, 主指挥按需拍板)

### 3.4 W70 派工节奏建议

- **W70 第 1 批** (5-6 agents): UI redesign 3 组件 (Agent #1-3) + Drive PR5 起步 (Agent #8-9, 可选)
- **W70 第 2 批** (4-6 agents): UI redesign 视觉/测试/dark (Agent #4-7) + Drive PR7 起步 (Agent #10-12, 可选)
- **W70 第 3 批** (可选): UI redesign 收口 + Drive PR 收口

### 3.5 W70 排期依赖图

```
W70 第 1 批 (并行)
├─ Agent #1 (NavRail) ──独立──
├─ Agent #2 (ThinkingModeSwitch) ──依赖──> app/agent/protocol.py 后端模型选择
├─ Agent #3 (ChatBreadcrumb) ──依赖──> Pinia session store
├─ Agent #8 (Drive PR5 分片上传后端) ──独立── (可选)
└─ Agent #9 (Drive PR5 断点续传前端) ──依赖──> Agent #8 (可选)

W70 第 2 批 (并行, 依赖第 1 批)
├─ Agent #4 (UI 视觉回归) ──依赖──> Agent #1-3
├─ Agent #5 (UI Playwright) ──依赖──> Agent #1-3
├─ Agent #6 (UI dark mode) ──依赖──> Agent #1-3
├─ Agent #7 (UI token 验证) ──依赖──> Agent #1-3
├─ Agent #10 (Drive PR7 文件请求) ──独立── (可选)
├─ Agent #11 (Drive PR7 共享盘) ──依赖──> Agent #10 (可选)
└─ Agent #12 (Drive PR7 审计日志) ──依赖──> Agent #10-11 (可选)
```

---

## 4️⃣ 主指挥拍板建议 (3 选项矩阵)

### 4.1 选项对比

| 选项 | 派工数 | 时间 | 风险 | 用户价值 | 锚点范式预期 |
|------|--------|------|------|---------|------------|
| **A (推荐)** | 5-7 agents | 2 周 | 中 | qa-bench 7 维评分 + 6 plans 小修, 子 plan ② 落地 | W68 90 → W69 95-100 → W70 100-115 |
| **B** | 8-10 agents | 3 周 | 中-高 | 选项 A + Drive v2 PR 起步 (PR5/7) | W68 90 → W69 95-100 → W70 110-130 |
| **C** | 0 agents | 0 周 | 极低 | 主指挥先部署 W68 第 5-9 批到云 server | W68 90 → W69 90 (不变) → W70 90 (不变) |

### 4.2 选项 A 详细说明 (推荐)

**派工**: 5-7 agents (qa-bench 子 plan ② 5 agents + 6 plans 小修 1-2 agents)

**优势**:
- 0 production code 改动铁律维持 (除 qa-bench 子 plan ② 5 agent 例外预算, scope 限定 `app/services/` < 50 行 + `web/src/views/admin/` < 350 行 + `.github/workflows/` < 5 行)
- 2 周完成 (W68 第 4-8 批节奏: 每批 5-7 agents, 2 周内 2-3 批)
- 子 plan ② 完整闭环, 给 W70 留更大空间

**劣势**:
- qa-bench 7 维评分首次落地, 风险中 (Agent 1 + 2)
- Agent 3 + 4 是 W69 5 agents 中**唯一**允许 production code 改动的 agent, 主指挥需在派工前预先批准

**失败回滚**:
- 单 agent 失败 → 单 agent 回滚
- 5 agents 全部失败 → 接受 docs/CI 占位 (与 W67 第 47 步一致)

### 4.3 选项 B 详细说明

**派工**: 8-10 agents (选项 A + Drive v2 PR 起步)

**优势**:
- 用户体验提升更快 (Drive PR5 大文件上传)
- 2 选项 A + Drive 跨主题并行, 类似 W68 第 1 批路线 A + C 并行模式

**劣势**:
- 3 周完成 (W70 第 1 批 + 第 2 批)
- Drive PR 跨多 service 改动 (e.g. `app/services/drive_service.py` + `app/services/chunked_upload_service.py`), 0 production code 铁律**部分例外**, 主指挥需拍板

**失败回滚**:
- Drive PR 失败 → Drive PR 单 PR 回滚 (按 PR 范围), qa-bench 子 plan ② 不受影响

### 4.4 选项 C 详细说明

**派工**: 0 agents

**优势**:
- 主指挥亲自部署 W68 第 5-9 批 (30+ commits) 到云 server, 验证生产环境无 regression
- 极低风险

**劣势**:
- W69 锚点范式停滞 (W68 90 → W69 90 不升不降)
- W70 子 plan ③ (UI redesign) 启动晚 1-2 周
- 主指挥亲自部署投入时间高 (8-16h), 不能并行其他工作

### 4.5 主指挥拍板决策表

| 主指挥倾向 | 推荐选项 | 理由 |
|----------|---------|------|
| 想继续推进 qa-bench 子 plan ② + 修小修 | **选项 A** (推荐) | 风险最低 + 收益最明确 |
| 想同时推进 Drive v2 PR (用户有上传痛点) | **选项 B** | 跨主题并行 (W68 第 1 批验证过) |
| 想先稳一手 + 验证 W68 部署 | **选项 C** | 主指挥亲自部署, 后续 W69 + W70 全力推进 |
| 资源受限 (主指挥时间紧张) | **选项 A** 减半 | 5-7 agents 中先派 3-4 (Agent 1+2+6+#8), 后续补派 4-5 |

### 4.6 失败决策树

```
W69 第 1 批派工后
├─ Agent #1 失败 → 单 agent 回滚, W69 第 1 批其余 agents 继续
├─ Agent #2 失败 → 单 agent 回滚, W69 第 1 批其余 agents 继续
├─ Agent #1 + #2 都失败 → 接受 docs/CI 占位 (W67 第 47 步铁律), 不做第 3 次尝试
└─ Agent #6 / #8 失败 → 单 agent 回滚, W69 第 1 批其余 agents 继续

W69 第 2 批派工后
├─ Agent #3 失败 → 单 agent 回滚 (删除 knowledge_auto_intake_tasks.py + beat schedule)
├─ Agent #4 失败 → 单 agent 回滚 (删除 knowledge_intake_pipeline.py + 2 helper)
├─ Agent #3 + #4 都失败 → 接受"KB 闭环暂未自动化, 人工 monitor"基线, W70 重新设计
└─ Agent #7 失败 → 单 agent 回滚 (plans 修订可重做)

W69 第 3 批派工后 (Agent #5)
├─ Agent #5 失败 → 单 agent 回滚 (删除 QaBenchDashboardView.vue + admin 路由 + workflow)
└─ Agent #5 成功 → 子 plan ② 完整闭环

W69 完整 5-7 agents 失败
└─ 接受 docs/CI 占位 (W67 第 47 步铁律), W70 改派 UI redesign + Drive v2
```

---

## 5️⃣ 商业化打包路线 (长期, 2026 Q4 主指挥拍板时间表)

### 5.1 exe-logical-pie Phase 0-9 总览 (24 人月)

**plan 来源**: [`C:/Users/pc/.claude/plans/exe-logical-pie.md`](C:/Users/pc/.claude/plans/exe-logical-pie.md) §Phase 0-9.

| Phase | 名称 | 估时 | 优先级 | 启动条件 |
|-------|------|------|--------|---------|
| Phase 0 | 正式数据库 (生产级 HA + 监控 + 灾备) | 3 人月 | 🔴 P0 | 外部课题组试用前 |
| Phase 1 | 认证扩展 (微信扫码 + 手机号 + OAuth) | 3 人月 | 🔴 P0 | 外部课题组试用前 |
| Phase 2 | 多组织 SaaS (课题组隔离) | 6 人月 | 🔴 P0 ⚠️ 最高 | B 端付费前必做 |
| Phase 3 | 桌面 EXE (Windows/macOS/Linux) | 4 人月 | 🟡 P1 | B 端付费后 (提升体验) |
| Phase 4 | 移动 APP (HarmonyOS/iOS/Android) | 6 人月 | 🟡 P1 ⚠️ 最大工程 | B 端付费后 |
| Phase 5 | 商业化与订阅 | 2 人月 | 🟡 P1 | B 端付费前 |
| Phase 7 | 多模态 OCR | 已交付 ✅ | — | — |
| Phase 8 | 科研数据自动备份 (实时语音助手) | **4 人月** ⚠️ **商业化启动前必做** | 🔴 P0 | B 端付费前 |
| Phase 9 | 知识图谱可视化 | 4 人月 | 🟢 P2 | B 端付费后 |

**总工时**: 24 人月 (Phase 0/1/2/3/4/5/8/9), 实施周期 12-18 月.

### 5.2 Phase 8 实时语音科研助手 (4 人月, 商业化启动前必做)

**为什么 Phase 8 是商业化前必做**:
- 课题组核心场景是"开会 + 实验", 实时语音 = 自然输入方式
- 现有 ASR/TTS 链路 (W68 第 1-5 批建立) 仅"录音 → 后处理", 实时性弱
- 商业化场景要求"边说边识别 + 边说边入库", 这是 Phase 8 的核心目标

**Phase 8 子任务** (估算 4 人月):
- 子任务 1: WebRTC 实时流接入 (1 人月)
- 子任务 2: 流式 ASR (SenseVoice / Paraformer) + 流式入库 (1 人月)
- 子任务 3: 实时对话响应 (LLM 流式 + TTS 流式, 1 人月)
- 子任务 4: 端到端测试 + 优化 (1 人月)

### 5.3 多组织 SaaS (Phase 2, 4 人月, B 端付费前必做)

**为什么多组织 SaaS 是 B 端付费前必做**:
- 课题组间数据完全隔离是 B 端付费基本要求
- 单租户架构 (现状) 无法支撑 50+ 课题组
- Phase 2 = 数据库 schema 加 `org_id` 外键 + 前端组织切换 UI + 鉴权 org_id 校验

**Phase 2 子任务** (估算 6 人月):
- 子任务 1: 数据库 schema 迁移 + alembic (1 人月)
- 子任务 2: 鉴权 + org_id 强制过滤 (1 人月)
- 子任务 3: 前端组织切换 UI + 组织管理 (1 人月)
- 子任务 4: 计费 / 配额 (1 人月)
- 子任务 5: 多组织端到端测试 (1 人月)
- 子任务 6: 数据迁移工具 (老用户迁移到默认组织, 1 人月)

### 5.4 主指挥 Q4 拍板时间表 (建议)

| 时间 | 主指挥决策项 | 依据 |
|------|------------|------|
| 2026-09 (W74) | Phase 8 (实时语音) 是否启动 | W69 + W70 收官后, 锚点范式 W70 110+ 守恒验证, 用户痛点优先级评估 |
| 2026-10 (W78) | Phase 2 (多组织 SaaS) 是否启动 | Phase 8 进度 + B 端客户谈判进展 |
| 2026-11 (W82) | Phase 0 (正式数据库) 是否启动 | B 端客户合同 + 灾备需求 |
| 2026-12 (W86) | Phase 5 (商业化与订阅) 是否启动 | Phase 0 + 2 进度, 商业化定价策略 |
| 2027-Q1 | Phase 3 (桌面 EXE) + Phase 4 (移动 APP) 是否启动 | B 端付费用户反馈, 商业化收入数据 |

**铁律**: Phase 2 + Phase 8 是**商业化启动前必做**, 主指挥不可跳过. 其他 Phase 由商业化进展驱动.

---

## 6️⃣ 风险与缓解

### 6.1 W69 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| qa-bench 7 维评分算法与现有 360 题 smoke 不兼容 | 中 | 中 | 保留旧单一 pass/fail 评分字段, 7 维为新字段 |
| save_to_kb.py 全自动入库污染 KB | 中 | 高 | 5 道防线 (分数门控 + rollback + 灰度 + 白名单 + 监控) |
| Celery auto_intake_rollback_task 误删 | 低 | 高 | 7 天阈值 + confidence < 0.7 双门控 + audit log |
| KB 闭环 automation 与现有知识图谱冲突 | 中 | 中 | 复用 find_related_entries 模式, 严格 scope 限定 2 helper |
| Dashboard 性能差 | 低 | 中 | ECharts lazy load + 7 维数据后端预聚合 |
| 6 plans 小修引出更大改动 | 中 | 中 | 主指挥严格 scope 限定 (plans Status 段 + 1 Ollama 脚本, 不实施 plan body) |
| sentence-transformers 升级调研结论不明确 | 低 | 低 | 仅调研不实施, 给 W70 留决策空间 |

### 6.2 W70 风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| UI redesign 3 组件与现有 element-plus 组件冲突 | 中 | 中 | 新组件独立路径, 不修改现有 el-* 组件 |
| ThinkingModeSwitch 后端模型选择失败 | 中 | 高 | 3 档 fallback (deep → standard → fast), 默认 standard |
| ChatBreadcrumb 与 Pinia session store 不兼容 | 低 | 中 | 复用现有 store, 仅添加 selector |
| Drive PR5 分片上传大文件 (>1GB) OOM | 中 | 高 | 流式分片写入, 内存上限 100MB |
| Drive PR7 文件请求权限漏洞 | 低 | 高 | 严格 token 校验 + 过期时间 + 一次性 token |

### 6.3 商业化路线风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Phase 8 实时语音 ASR 准确率 < 85% | 中 | 高 | SenseVoice + Paraformer 双模型 fallback |
| Phase 2 多组织数据隔离漏洞 | 中 | 极高 | 强制 `WHERE org_id = current_org_id` + 单元测试覆盖 |
| 商业化定价不被接受 | 中 | 高 | 软启动 1-2 外部课题组白名单, 收集反馈后再定价 |

---

## 7️⃣ 验收标准 (DoD)

### 7.1 W69 DoD

- [ ] 5-7 agents 全部 merge 进 main (按选项 A / B / C 派工)
- [ ] qa-bench 7 维评分算法 + verdict consensus 落地 (Agent 1)
- [ ] save_to_kb.py 5 道防线 + rollback 命令 + dry-run 模式 (Agent 2)
- [ ] Celery auto_intake_rollback_task + beat schedule 注册 (Agent 3)
- [ ] KB 闭环 automation 端到端 50 题验证 (Agent 4)
- [ ] Dashboard MVP + CI smoke 200 题 (Agent 5, 可选)
- [ ] 6 plans 小修闭环 (Agent 6 + 7, 可选)
- [ ] sentence-transformers 升级调研 (Agent 8, 可选)
- [ ] 71 PASS + 7 SKIP baseline 守恒
- [ ] 0 production code 改动铁律维持 (除 qa-bench 子 plan ② 5 agent 例外预算, scope 限定)
- [ ] 锚点范式 W68 90 → W69 95-100 单调上升

### 7.2 W70 DoD

- [ ] 8-12 agents 全部 merge 进 main (按主指挥拍板选项 A / B)
- [ ] 子 plan ③ UI redesign 3 组件 (NavRail + ThinkingModeSwitch + ChatBreadcrumb) 落地
- [ ] UI redesign 视觉回归 + Playwright + dark mode + token 验证全过
- [ ] Drive v2 PR5 + PR7 (按主指挥拍板) 落地或部分落地
- [ ] 71 PASS + 7 SKIP baseline 守恒
- [ ] 0 production code 改动铁律维持
- [ ] 锚点范式 W69 → W70 100-115 单调上升

### 7.3 商业化路线 DoD (2026 Q4)

- [ ] 主指挥 2026-09 (W74) 拍板 Phase 8 是否启动
- [ ] 主指挥 2026-10 (W78) 拍板 Phase 2 是否启动
- [ ] 主指挥 2026-11 (W82) 拍板 Phase 0 是否启动
- [ ] 主指挥 2026-12 (W86) 拍板 Phase 5 是否启动
- [ ] 2027-Q1 主指挥拍板 Phase 3 + 4 是否启动

---

## 8️⃣ 总结

**W69 + W70 季度排期建议**:
- **W69 (2 周)**: qa-bench 子 plan ② 5 agents + 6 plans 小修 1-2 agents + 1 可选调研 agent = **5-7 agents**
- **W70 (1-2 周)**: 子 plan ③ UI redesign 5-7 agents + Drive v2 PR 续 0-3 agents = **8-12 agents**
- **主指挥拍板**: 选项 A (推荐, 5-7 agents / 2 周) / 选项 B (8-10 agents / 3 周, 加 Drive) / 选项 C (暂停, 主指挥先部署)
- **商业化路线**: Phase 8 (实时语音 4 人月) + Phase 2 (多组织 SaaS 6 人月) 是商业化启动前必做, 主指挥 2026-09 + 2026-10 拍板

**Why 这份排期建议**:
- W68 第 9 批 C-1 闭环 14 plans 留 W69 + W68 第 9 批 D-3 任务模式基调 v2 + W68 第 4-8 批 5 批实战, 已有足够依据锁定 W69 + W70 排期
- 排期 ≠ 立即派工, 主指挥按 W68 第 4-8 批节奏, 2 周内 2-3 批逐步派工
- 失败时按 §4.6 失败决策树, 不做第 3 次失败尝试 (W67 第 47 步铁律)

**铁律**: 0 production code 改动铁律维持 (本期 + W69 + W70 排期) + W19 选项 A 维持 + 锚点范式持续单调上升 + 71 PASS + 7 SKIP baseline 守恒

**前序决策**:
- W68 第 4 批拍板: plans 优先 + 小修搭配 (memory/w68-task-mode-paradigm-plans-first-2026-07-24.md)
- W68 第 9 批 D-3 拍板: 任务模式基调 v2 (5 拍板纪律 + 4 阶段流程 v2)
- W68 第 9 批 C-1 拍板: 14 plans 留 W69 排期 (锚点范式第 67 守恒)

**后续步骤**:
1. 主指挥 review 本文档 §2 (W69 排期) + §3 (W70 排期) + §4 (主指挥拍板选项) + §5 (商业化路线)
2. 主指挥 W69 启动前拍板选项 A / B / C
3. 按选项拍板, 派工 prompt 必须含"派工依据文档 = `docs/w69-w70-roadmap-decision-2026-07-24.md`"
4. W69 + W70 期间任何主指挥拍板调整, 必须追加 commit 更新本文档 + 同步 memory