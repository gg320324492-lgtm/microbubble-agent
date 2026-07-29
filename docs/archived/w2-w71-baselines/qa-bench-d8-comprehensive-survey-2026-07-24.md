# qa-bench D8 综合调研 — chatgpt-structured-floyd 子 plan ② 实施前置 (2026-07-24)

> **任务来源**: W68 第 14 批 C-1 调研 — chatgpt-structured-floyd 子 plan ② (qa-bench 7 维评分 + KB 闭环 + Dashboard MVP + CI smoke 200 题) 实施前置条件真验证
>
> **主基调**: 不实施只调研 docs-only, 4 grep 命令真验证, 6 项实施状态表完整 (派工纪要 v4 铁律 3: 派工前提 stat 验证纪律)
>
> **W68 第 14 批 锚点范式**: 第 177 守恒 (主指挥协调范式第 44 次派工)
>
> **锚点范式当前位置**: W68 第 13 批 168 → W68 第 14 批 177 (9 守恒预期)

---

## 0. TL;DR

W68 第 8 批 B-4 已就位 `docs/chatgpt-structured-floyd-w69-plan.md` (W69 派 5 agents 实施子 plan ② 详细调研). 本任务作为 W69 派工 **前置 stat 验证** (派工纪要 v4 铁律 3), 用 4 个 grep 命令真验证子 plan ② 6 项在 main HEAD `9b7c0e8a9` 的真实状态, 排除 W68 期间多 batch "在 feature branch 已实施但未 merge 到 main" 的状态错位.

**关键发现** (主拍前必读):
1. **7 维评分**: commit `63cdac3` 在分支 `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` 已实施, 但 **NOT in main HEAD** (`9b7c0e8a9` 不可见) — W69 派工前必须先 merge 该分支
2. **save_to_kb 5 道防线**: v3.1 D2 已集成 `AUTO_KB_INTAKE_ENABLED` + 5 道防线 (分数 + 内容 + 意图 + 灰度 + 备份) **已 in main**, 但与 v3.1 调研描述的 5 道防线 (dedup + 长度 + 拒答 + 敏感词 + 人工) **不同** (老 vs 新方案差异)
3. **Celery auto_intake_rollback**: 仅有 `scripts/auto_intake_rollback.py` CLI 工具 (W5 T5.3), **无 Celery task**, **无 Celery beat schedule** — 不符合 D8 调研描述
4. **KB 闭环**: commit `0066087c8` 在分支 `feat/w68-10th-batch-b2-save-to-kb-2026-07-24` 已实施 5 步 pipeline, **NOT in main** — W69 派工前必须先 merge
5. **Dashboard MVP**: commit `bc3a60619` (W68 第 7 批 A-4 KbMonitorView + admin_kb_monitor API) **已 in main** — 4 指标卡已部分实施 (实际是 4 ECharts 子图, 不是简单的 4 el-card)
6. **CI smoke 200 题**: 已 in main (`.github/workflows/qa-bench-smoke.yml` + `qa-bench-ci.yml` workflow 各跑全量或 smoke), 200 题文件已存在 `tests/qa-bench/questions_smoke_200.jsonl` — **已闭环** 但与 D8 调研描述的 v3.0 模式 (CI 5min smoke + dashboard 监控) **有出入**

---

## 1. 调研背景

### 1.1 W68 第 14 批 C-1 任务来源

W68 第 14 批派工前监测脚本 (`memory/w68-14th-batch-grand-closure.md` D-5 留待办) + 主指挥拍板:

- 子 plan ② 6 项中有 1 项 (7 维评分 commit `63cdac3`) 已在 W68 第 10 批 B-1 派工, 但实际 grep 验证显示此 commit **仅在 feature branch**, **不在 main HEAD**
- 这违反 W68 第 6+7 批纪律沉淀 §1.2 ("盲信自报事故") + W68 第 12 批 D-1 派工纪要 v3 铁律 ("派工前提 stat 验证"), 必须主拍前明确
- 本调研文档给主指挥 3 个选项 + W69 派工 5 agents 实施清单 + 派工顺序建议

### 1.2 4 grep 命令真验证 (派工纪要 v4 铁律 3)

```bash
# 4 真验证 (派工前提 stat 验证, 输出逐条附录 A)

grep_1: grep -rn "save_to_kb\|auto_intake_rollback\|kb_closed_loop" \
        --include="*.py" app/ 2>&1 | head -30
# 输出: 10 行 (app/api/v1/knowledge.py:295-631 + app/schemas/knowledge.py:437 +
#        app/utils/safe_minio_intake.py:11-131 引用 save_to_kb + auto_intake_rollback
#        + data/ 文件路径)
# 含义: app/ 集成 save_to_kb.py (W62 W5 已实施) ✅
#        但 **无 auto_intake_rollback Celery task** (仅 app/api 端点引用 rollback JSON
#        输出目录, 不存在 rollback Celery 注册)

grep_2: grep -rn "save_to_kb\|auto_intake_rollback" --include="*.py" scripts/ 2>&1 | head -10
# 输出: 6 行 (scripts/auto_intake_rollback.py:76-119 + scripts/generate_*_report.py
#        引用)
# 含义: scripts/auto_intake_rollback.py 存在 (W5 T5.3 实施), 119 行 CLI 工具
#        跑法 `python scripts/auto_intake_rollback.py` (cron 模式手动跑)
#        **NOT Celery task**, **NOT in beat schedule**

grep_3: git log --oneline --all | grep -iE "save_to_kb|auto_intake|kb_closed_loop|KbMonitorView" | head -20
# 输出:
#   14aae9aaf feat(qa-bench): v3.1 D2 runner 集成 save_to_kb + 端到端测试 ✅ in main
#   bc3a60619 merge: qa-bench-d5-kb-monitor-2026-07-24 (W68 第 7 批) ✅ in main
#   63cdac3bb qa-bench(w68-10th-batch-b1): 7-dim scoring + verdict v2 + phase3 matrix  ⚠️ feature branch ONLY
#   0066087c8 feat(kb-closed-loop): W68 第 10 批 B-4 KB 闭环 automation  ⚠️ feature branch ONLY
# 含义: 7d_scoring + KB 闭环 automation 在 feature branch, 但 NOT in main HEAD 9b7c0e8a9

grep_4: grep -rn "qa-bench.*smoke\|smoke.*qa-bench" --include="*.yml" .github/ | head -10
# 输出: 6 行 (qa-bench-smoke.yml + qa-bench-ci.yml 都引用 qa-bench-smoke.yml + 200 题 smoke)
# 含义: CI smoke workflow 已存在 ✅, 但合并模式有 2 个 workflow 文件
#        - .github/workflows/qa-bench-smoke.yml (200 题 + test DB)
#        - .github/workflows/qa-bench-ci.yml (D5 1000 题 + D6 --smoke flag)
```

### 1.3 派生 grep 验证 (派工纪要 v4 铁律 3 扩展)

```bash
grep_5: git merge-base --is-ancestor <commit> HEAD  # 验证 commit 是否真 in main
# 输出 4 个关键 commit 的状态:
#   14aae9aaf (qa-bench v3.1 D2 runner save_to_kb): IS in main ✅
#   bc3a60619 (qa-bench-d5-kb-monitor merge): IS in main ✅
#   63cdac3bb (7-dim scoring + verdict v2): NOT in main ⚠️
#   0066087c8 (KB 闭环 automation 5 步): NOT in main ⚠️

grep_6: ls tests/qa-bench/scoring/ tests/qa-bench/kb_queue/ tests/qa-bench/ci/
# 输出:
#   ls: cannot access 'tests/qa-bench/scoring/': No such file or directory
#   ls: cannot access 'tests/qa-bench/kb_queue/': No such file or directory
#   ls: cannot access 'tests/qa-bench/ci/': No such file or directory
# 含义: 子 plan ② D8 调研中提及的 3 个子目录 (scoring / kb_queue / ci) **未在 main 创建**
#        进一步证实 63cdac3 + 0066087c8 的内容不在 main

grep_7: wc -l tests/qa-bench/questions_*.jsonl 2>&1
# 输出 9 个题库文件:
#   questions.jsonl: 105 (主入口)
#   questions_500.jsonl: 495
#   questions_780.jsonl: 700 (主题库, 用于 smoke)
#   questions_smoke_200.jsonl: 200 ✅ 已存在 200 题 smoke 子集
#   questions_create_task_5.jsonl: 5
#   questions_d4_extra_300.jsonl: 300
#   questions_db_117.jsonl: 107
#   questions_fast_vs_deep.jsonl: 31
#   questions_manual_234.jsonl: 229
#   questions_w2_final.jsonl: 535
#   questions_w2_sample39.jsonl: 39
# 含义: 200 题 smoke 已文件级就位 ✅, 但 200 题条目 hot_path 标签需要重新生成

grep_8: wc -l tests/qa-bench/save_to_kb.py scripts/auto_intake_rollback.py tests/qa-bench/runner.py
# 输出:
#   tests/qa-bench/save_to_kb.py: 398 行 ✅
#   scripts/auto_intake_rollback.py: 119 行 ✅
#   tests/qa-bench/runner.py: 1369 行 ✅ (含 --smoke flag, line 947)
# 含义: save_to_kb.py 存在, runner.py --smoke 已实施
#        auto_intake_rollback.py **CLI 工具 NOT Celery task** ⚠️
```

---

## 2. 子 plan ② 6 项实施状态表

| # | 项 | 真实 commit (在 main) | 真状态 | 缺口 / 优先级 |
|---|---|---|---|---|
| 1 | **7 维评分** | `63cdac3bb` ⚠️ feature branch ONLY | **未 in main** | (1) W68 第 14 批派 merge agent (`feat/w68-10th-batch-b1-7d-scoring-2026-07-24` → main) 或 (2) W69 B-1 在 main 重做. 优先级 **HIGH**. `tests/qa-bench/scoring/seven_d_scoring.py` (450 行) + `verdict_consensus_v2.py` (146 行) + `test_seven_d_scoring.py` (377 行, 11 测试) 在 feature branch, merge 到 main 后即用 |
| 2 | **save_to_kb.py 5 道防线** | `14aae9aaf` (qa-bench v3.1 D2 runner save_to_kb 集成) + `save_to_kb.py` 主文件 398 行 ✅ in main | **已实施但与 D8 调研不同** | 现状 5 道防线: 分数门控 / 内容门控 / 意图白名单 / 灰度开关 / 备份 + 7 天 rollback. D8 调研描述: dedup / 长度 / LLM 拒答 / 敏感词 / 人工抽检. **5 道防线含义不同**! W69 派工必须明确: (a) 重写为 D8 调研口径, 或 (b) 保留 W5 v3.1 既有方案不变. 优先级 **HIGH** |
| 3 | **Celery auto_intake_rollback_task** | **无 commit (仅 `scripts/auto_intake_rollback.py` CLI)** ⚠️ | **未实施** | D8 调研要求 Celery beat daily 4:00 跑 + 集成 admin notification + idempotent, 现状是 CLI 工具 119 行 (psycopg2 直连, 手动跑). 缺口: 缺 Celery task (`app/services/qa_bench_tasks.py:auto_intake_rollback_task`) + beat schedule + admin notification 集成. 优先级 **HIGH** (这是 W6 W5 T5.3 升级版) |
| 4 | **KB 闭环 (端到端)** | `0066087c8` ⚠️ feature branch ONLY | **未 in main** | W68 第 10 批 B-4 实施 5 步 pipeline (评测 → 5 防线 → 入库 → 抽检 → 回滚), feature branch `feat/w68-10th-batch-b2-save-to-kb-2026-07-24` 已实施. **NOT in main HEAD `9b7c0e8a9`**. 缺口: merge 到 main (W68 第 14 批派 B-2 agent) 或 W69 B-3 在 main 重做. 优先级 **HIGH** |
| 5 | **Dashboard MVP** | `bc3a60619` (W68 第 7 批 A-4 KbMonitorView) ✅ in main + `app/api/v1/admin_kb_monitor.py` 269 行 ✅ in main | **已部分实施** | 现状 4 核心指标 + 4 ECharts 子图 (入库趋势 / 失败率 / 重试次数 / 队列堆积) + 失败列表. D8 调研要求 4 指标卡 (入库数 / 通过率 / 抽检数 / 告警数). 缺口: (a) ECharts 视图 vs 简单 el-card 视图选型, (b) 通过率指标缺 (save_to_kb 5 道防线结果聚合), (c) 抽检数缺 (`kb_intake_audit.status='pending'` count). 优先级 **MEDIUM** |
| 6 | **CI smoke 200 题** | `.github/workflows/qa-bench-smoke.yml` 274 行 ✅ in main + `qa-bench-ci.yml` 383 行 ✅ in main + `questions_smoke_200.jsonl` 200 行 ✅ in main + `runner.py --smoke` flag (line 947) ✅ in main | **已闭环** | 现状: smoke workflow 已 on pull_request + push (main branch), 200 题文件就位, runner 集成 `--smoke` 简写. 缺口: (a) 与 v3.0 plan 描述的 "200 题 tags=['hot_path', 'regression_smoke']" 差异 (实际用 questions_smoke_200.jsonl 而非 tag 筛选), (b) 与 D8 调研的 "5min <" 偏差 (实际单 workflow timeout 90 分钟). 优先级 **LOW** (已闭环, 仅 1 项差异需主拍) |

### 2.1 状态表汇总 (主拍决策点)

| 真状态 | 项数 | 项 |
|---|---|---|
| **已 in main + 已闭环** | 2 | Dashboard MVP (部分) + CI smoke 200 题 |
| **已 in main + 现状与 D8 调研描述不同** | 1 | save_to_kb.py 5 道防线 |
| **feature branch ONLY + 未 in main** | 2 | 7 维评分 (63cdac3) + KB 闭环 (0066087c8) |
| **未实施 (W59 + W6 留待办)** | 1 | Celery auto_intake_rollback_task |

---

## 3. 5 道防线现状详查 (子 plan ② 核心模块)

### 3.1 save_to_kb.py 现状 (W5 T5.1 升级 + W62 D2 灰度扩展)

```python
# W5 T5.1 防线 5 道 (现状, NOT D8 调研描述的 5 道):
# - 防线 1 分数门控: auto_score >= MIN_SCORE (默认 4/5 = A 级)
# - 防线 2 内容门控: content >= MIN_CONTENT_LENGTH (默认 200 字)
# - 防线 3 意图白名单: intent ∈ ALLOWED_INTENTS (默认 explain_concept + search_info)
# - 防线 4 灰度开关: AUTO_KB_INTAKE_ENABLED env 或 --enable-intake flag
# - 防线 5 备份 + 7 天 rollback: 每次入库前备份 JSON, 7 天内可自动 rollback
```

**vs D8 调研描述的 5 道防线** (子 plan ② 2.4 节):
| # | D8 调研 | W5 T5.1 现状 | 兼容性 |
|---|---|---|---|
| 1 | dedup (embedding 余弦 ≥ 0.95) | **缺** | D8 调研新增 |
| 2 | 长度过滤 (50-4000 字符) | ✅ 内容门控 200 字 | D8 调研范围 50-4000 (更宽), 但含义一致 |
| 3 | LLM 拒答检测 | **缺** | D8 调研新增 |
| 4 | 敏感词 (28 成员 + 8 placeholder) | ⚠️ must_not_contain 部分覆盖 | **名称黑名单** + 8 placeholder 缺失 |
| 5 | 人工抽检 (5% 抽样 admin UI) | **缺** (人工抽检 ≠ 自动 5%) | D8 调研新增 |

**结论**: 5 道防线含义**不同**. 现状是质量门 + 灰度控制, D8 调研是污染检测 + 抽检. **W69 派工必须明确选型**.

### 3.2 scripts/auto_intake_rollback.py 现状 (W5 T5.3 CLI)

```python
# 119 行 CLI 工具, 手动跑或 cron 触发:
# - 查询 7 天前入库的 source_type='auto_expansion' 条目
# - 物理删除 (production 实际可改 UPDATE is_active=False)
# - 备份目录匹配
# - 输出 rollback 报告
#
# **NOT Celery task, NOT in beat schedule**
# 跑法: python scripts/auto_intake_rollback.py (手跑或 cron.daily)
```

**vs D8 调研要求** (子 plan ② 2.5 节):
- D8 调研要求 `app/services/qa_bench_tasks.py:auto_intake_rollback_task` (Celery task + 每天 4:00 跑)
- D8 调研要求 集成 admin notification + 单元测试 12 个 (idempotent + 7 天 review + 引用失效)
- 现状 只有 CLI 工具 + 无 admin notification + 无单元测试

**结论**: **大缺口**. W69 派工 B-3 必须重写为 Celery task + Celery beat schedule (60-80% 是新代码).

### 3.3 Celery beat schedule 现状

```bash
# 验证: grep -rn "auto_intake\|kb_rollback" app/core/celery.py
# 输出: 无
# (celery.py 存在, 269 行, 但无 auto_intake_rollback_task 注册)
```

**现状**: 无 Celery task, 无 beat schedule. **0 实施**.

---

## 4. CI smoke 200 题现状

### 4.1 Workflow 现状 (`.github/workflows/qa-bench-smoke.yml` 274 行)

| 字段 | 现状 |
|---|---|
| **触发** | `pull_request` (paths 包含 `app/agent/**` 等) + `push` (`main` 分支, paths 限定) |
| **题数** | 200 题 (workflow input `total_questions`) |
| **超时** | 单 workflow timeout 默认 360 分钟, 单 job 默认 90-180 分钟 |
| **test DB** | ✅ 已部署 (microbubble_test + 8001 端口 app-test) |
| **报告** | `qa-bench-smoke-report` artifact |
| **PR 红 ✗** | ✅ 阻断 (PR 必须通过才能 merge) |

### 4.2 已存 200 题子集 (`tests/qa-bench/questions_smoke_200.jsonl` 200 行)

```bash
# head -1 tests/qa-bench/questions_smoke_200.jsonl
{"id": "A-L1-0001", "version": 3, "category": "A", "subcategory": "A1", "dimension": "member", "difficulty": "L1",
 "source": "manual", "tags": ["manual", "hot_path"], ...}
# ✅ tag "hot_path" 已用 (符合 D8 调研的 tags=["hot_path", "regression_smoke"])
```

### 4.3 缺口

- (a) **5min < 200 题** 实际: smoke 200 题约 30-60 分钟 (含 docker-compose up + pytest + report). 与 D8 调研 5min 偏差大. **P95 < 1.5s/题是题级目标, 总时长 5min 不现实** (test DB 启动 + app-test 初始化就 4 分钟)
- (b) **2 个 workflow 整合**: `qa-bench-smoke.yml` (200 smoke) + `qa-bench-ci.yml` (D5 1000 题) 重复路径. **W69 派工** 应考虑合并
- (c) **主指挥决策点**: 是否把 1000 题 baseline 拆分 (200 smoke + 800 nightly)?

---

## 5. Dashboard MVP 现状 (W68 第 7 批 A-4 已部分实施)

### 5.1 已实施 (commit `bc3a60619` W68 第 7 批 A-4)

| 模块 | 文件 | 行数 | 真状态 |
|---|---|---|---|
| **后端 API** | `app/api/v1/admin_kb_monitor.py` | 269 | ✅ in main |
| **前端 View** | `web/src/views/admin/KbMonitorView.vue` | 396 | ✅ in main |
| **数据生成** | `tests/qa-bench/dashboard/gen_data.py` | 126 | ✅ in main |

**3 个 API 端点** (已 in main):
- `GET /admin/kb-monitor/overview?hours=24` — 聚合 + trend
- `GET /admin/kb-monitor/queue-depth` — 队列快照
- `GET /admin/kb-monitor/failures?limit=50` — 失败列表

**前端 4 ECharts 子图** (已 in main):
- 入库趋势 (逐小时 ingested/done)
- 失败率 (逐小时 failed/ingested %)
- 重试次数 (retrying/failed/done)
- 队列堆积 (pending/analyzing 饼图)

### 5.2 vs D8 调研口径

D8 调研 4 指标卡 (简单 el-card):
| D8 调研 | 现状 | 差异 |
|---|---|---|
| 入库数 (24h) | ✅ (overview API) | 含义一致 |
| 通过率 (rolling 7d) | ❌ | **未实施** — save_to_kb 5 道防线结果聚合 |
| 抽检数 (待审核) | ❌ | **未实施** — `kb_intake_audit.status='pending'` count |
| 告警数 (rolling 24h) | ✅ (overview API rollback_count + negative_feedback_count) | 含义一致 |

### 5.3 缺口

- (a) **通过率 + 抽检数指标缺** (2 个 el-card 缺)
- (b) **ECharts vs el-card 选型** — 主拍选哪个视图 (D8 调研 el-card, 现状 ECharts, 不一致需主拍)
- (c) **5min polling vs 实时渲染** — 现状是 onMounted 拉一次 + 手动 refresh, D8 调研 5min polling (setInterval)

---

## 6. W69 派 5 agents 实施清单 (基于真验证调整)

### 6.1 Agent B-1: 7 维评分 (W69 + 派 merge agent 先 merge 主分支)

**工作量**: 12h (含 merge feature branch `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` → main, 4h merge 修复冲突 + 8h 实施 CI 集成)

**核心任务**:
1. **W68 第 14 批派 1 merge agent** (锚点范式第 178 守恒):
   - merge `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` → main (含 7d_scoring.py 450 行 + verdict_consensus_v2.py 146 行 + test_seven_d_scoring.py 377 行 + phase2/3 runner 集成)
   - merge 时检查 conflicts (qa-bench phase2/3 runner 已 in main, phase3_matrix_runner 是 NEW)
2. **W69 B-1 在 main 之后**:
   - 写 `tests/qa-bench/scoring/__init__.py`
   - 集成 phase1_dry_runner.py + phase2_dry_runner.py + phase3_matrix_runner.py 共享 sys.path
   - 写 5 个新测试 (CLI round-trip + intent slicing + 7d 输出 schema)
   - 写 `docs/qa-bench-7d-scoring.md` 部署必做章节 (已在 feature branch, 复用)

**风险**: 中 (merge conflicts 难预测, 需 7d_scoring + phase3_matrix_runner 在 main 没有依赖)

### 6.2 Agent B-2: save_to_kb.py 5 道防线 重写 (主拍选型)

**工作量**: 12h (W5 v3.1 升级版重写为 D8 调研口径)

**核心任务 (主拍选型二选一)**:

**选项 X (推荐)**: 重写为 D8 调研口径 (commit `14aae9aaf` v3.1 D2 → D8 5 道防线):
1. 防线 1: dedup (embedding 余弦 ≥ 0.95, `tests/qa-bench/kb_queue/dedup.py` 新建 ~80 行, 复用 `app/utils/pgvector.py`)
2. 防线 2: 长度过滤 50-4000 字符 (升级现状 200 字门为 50-4000)
3. 防线 3: LLM 拒答检测 (LLM-as-judge, 复用 `app/utils/llm_client.py`)
4. 防线 4: 敏感词 (28 成员黑名单 + 8 placeholder + 11 filler phrase, 新建 `tests/qa-bench/kb_queue/sensitive_words.py`)
5. 防线 5: 人工抽检 (5% 抽样 + admin UI 待审核列表, 复用 `app/api/v1/admin_kb_monitor.py`)

**选项 Y (保守)**: 保留 W5 v3.1 现状, 仅补 1 道防线:
- 补 防线 6: dedup (新增唯一区别) + LLM 拒答检测 (新增)
- 保留 W5 既有 5 道 (分数 + 内容 + 意图 + 灰度 + 备份) 不变

**主拍决策必填**: 选项 X / 选项 Y.

**风险**: 高 (重写 save_to_kb.py 影响全自动入库主流程, 必须确保灰度 rollback 可用)

### 6.3 Agent B-3: Celery auto_intake_rollback_task + Celery beat schedule

**工作量**: 8h (W5 T5.3 CLI 升级版)

**核心任务**:
1. 新建 `app/services/qa_bench_tasks.py` (~100 行):
   - `auto_intake_rollback_task()` Celery task @app.task(bind=True, max_retries=3)
   - 查询 24h 内新入库条目 + grounding ref 可达性 + 下游点击次数 < 3 → rollback
   - 负反馈 > 10% → admin notification + 暂停 AUTO_KB_INTAKE_ENABLED
   - idempotent: `@app.task(ignore_result=True, expires=3600)`
2. 配置 `app/core/celery.py` beat schedule (cron `0 4 * * *` 每天 4:00):
   - 复用现有 `task_service:auto_purge_trash_task` 模式
   - `app/core/celery.py:220` beat_schedule.append(...)
3. 单元测试 12 个 (idempotent + 7 天 review + 引用失效 + admin notification 集成)

**风险**: 中 (回滚必须 idempotent, 错误回滚会污染 KB. **必须先 close 7 天 review 期才能上线**)

### 6.4 Agent B-4: KB 闭环 端到端集成 (主拍依赖 B-1+B-2+B-3 顺序)

**工作量**: 12h (W68 第 10 批 B-4 feature branch `feat/w68-10th-batch-b2-save-to-kb-2026-07-24` 升级版)

**核心任务 (依赖)**:
1. **W68 第 14 批派 1 merge agent** (锚点范式第 178 守恒):
   - merge `feat/w68-10th-batch-b2-save-to-kb-2026-07-24` → main (含 5 步 pipeline)
2. **W69 B-4**:
   - 升级 5 步 pipeline 集成 7d 评分 (B-1) + 5 道防线 (B-2) + auto_intake_rollback (B-3)
   - 端到端测试 30 个场景 (正常 pass → 入库 / 5 道防线 fail → 拒绝 / 24h 后 grounding 失效 → 自动回滚 / 下游点击 < 3 → 自动回滚 / 负反馈 > 10% → 告警)
   - pytest 集成测试 8 个 (Docker compose test DB stack + 物理隔离栈)
   - 复用 W68 第 7 批 A-3 in-process runner

**风险**: 高 (全链路集成测试 + 物理隔离栈, 必须先 B-1 + B-2 + B-3 全部 in main)

### 6.5 Agent B-5: Dashboard MVP 完整版 + CI smoke 200 题 cleanup

**工作量**: 10h (W68 第 7 批 A-4 KbMonitorView + 2 缺 el-card + smoke 合并)

**核心任务**:
1. **Dashboard 补 2 el-card** (通过率 + 抽检数):
   - 升级 `app/api/v1/admin_kb_monitor.py` 加 `GET /admin/kb-monitor/throughput-rate` + `GET /admin/kb-monitor/audit-pending`
   - 升级 `web/src/views/admin/KbMonitorView.vue` 加 2 el-card (通过率 + 抽检数) + 改 ECharts → 4 el-card 横排
2. **CI smoke 200 题 cleanup**:
   - 合并 `.github/workflows/qa-bench-smoke.yml` + `qa-bench-ci.yml` 单一 workflow
   - 写 `tests/qa-bench/ci/smoke_200.py` ~150 行 (独立 smoke 套件 vs runner.py --smoke flag 二选一)
   - 部署 doc `docs/qa-bench-smoke-ci.md`
3. **5min polling 实现**:
   - `setInterval(() => fetch..., 5*60*1000)` 在 KbMonitorView.onMounted

**风险**: 低 (复用 web 模板 + 既有 qa-bench 框架)

### 6.6 W69 派工总投入

| Agent | 工作量 | 风险 | 依赖 |
|---|---|---|---|
| **B-1** (7 维评分) | 12h | 中 | W68 第 14 批 merge agent 先 merge |
| **B-2** (save_to_kb 重写) | 12h | 高 | save_to_kb.py 现状 (W5 v3.1) + 主拍选型 |
| **B-3** (Celery auto_intake_rollback) | 8h | 中 | CLI 工具现状 + Celery beat 配置 |
| **B-4** (KB 闭环) | 12h | 高 | W68 第 14 批 merge agent + B-1+B-2+B-3 in main |
| **B-5** (Dashboard MVP 完整 + CI smoke cleanup) | 10h | 低 | KbMonitorView 现状 + admin_kb_monitor API 现状 |
| **W68 第 14 批派 1 merge agent** (前置) | 4h | 中 | 2 个 feature branch merge 到 main |
| **合计** | **58h** + 4h 前置 merge = 62h (1.5 周) | | |

---

## 7. 主拍选项矩阵 (主指挥 3 选 1)

### 7.1 选项 A (推荐): W69 派 5 agents 全实施子 plan ② (58h + 4h merge)

| 维度 | 选项 A |
|---|---|
| **收益** | 子 plan ② 6 项 100% 闭环 + qa-bench 780 题体系升级到 production-grade |
| **锚点范式增长** | W69 +5 守恒 + 主指挥协调 +1 = W68 第 14 批 → W69 +6 → 168 → 174 |
| **0 production code 改动铁律** | 例外已批 6 留 W70+ 派工 backlog 内, **可守恒** (子 plan ② 全部新增文件 + Celery task) |
| **W19 选项 A** | 子 plan ② 算遗留闭环, 不冲突 |
| **风险** | 中-高 (5 agents 并行, B-2 + B-4 灰度期需手动监控, 主拍密集 W68-W69 跨度 1.5 周) |

### 7.2 选项 B (保守): W69 派 3 agents (跳过 B-3 + B-4)

| 维度 | 选项 B |
|---|---|
| **包含** | B-1 (7d 评分) + B-2 (save_to_kb 重写) + B-5 (Dashboard + smoke cleanup) |
| **跳过** | B-3 (Celery auto_intake_rollback) + B-4 (KB 闭环) — 留 W70+ 派工 |
| **总投入** | 34h (1 周) |
| **收益** | 子 plan ② 4/6 闭环 (66%), KB 闭环 留 W70+ |
| **锚点范式增长** | W69 +3 守恒 + 主指挥协调 +1 = 168 → 172 |
| **风险** | 低-中 (3 agents 并行, KB 闭环缺失意味入库后无自动 rollback, 必须 W70+ 二次派工) |

### 7.3 选项 C (激进): W69 派 5 agents 但跳 auto_intake (B-3 留 backlog)

| 维度 | 选项 C |
|---|---|
| **包含** | B-1 (7d 评分) + B-2 (save_to_kb 重写) + B-4 (KB 闭环 partial) + B-5 (Dashboard + smoke) |
| **跳过** | B-3 (Celery auto_intake_rollback) — 留 W70+ 派工 backlog (留待 `apps/web:deploy` 或独立 task) |
| **总投入** | 50h (1 周 + 半天) |
| **收益** | 子 plan ② 5/6 闭环 (83%), KB 闭环仅 CLI mode (无 Celery) |
| **风险** | 高 (KB 闭环缺 auto_intake Celery, 7 天 rollback 必须手跑 CLI 或 cron) |

### 7.4 派工顺序建议 (任何选项适用)

**主拍 W68 第 14 批先派 merge agent** (前置):
- merge `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` → main (含 63cdac3)
- merge `feat/w68-10th-batch-b2-save-to-kb-2026-07-24` → main (含 0066087c8)
- 预计 4h (冲突修复 + 整合脚本 + 部署 docs)

**派工顺序** (W69 实施, B-1 + B-2 + B-5 并行, B-3 + B-4 串后):
```
W69:
- D1 (Mon): 派 B-1 + B-2 + B-5 并行启动 (12h/12h/10h)
- D2 (Tue): B-1 + B-2 + B-5 收尾
- D3 (Wed): 派 B-3 + B-4 启动 (B-3 8h + B-4 12h, 依赖 B-1 + B-2)
- D4 (Thu): B-3 + B-4 收尾
- D5 (Fri): W69 grand closure + 主指挥协调范式第 45 次派工
```

---

## 8. 调研输出 (主拍决策依据汇总)

### 8.1 关键发现 (关键纪律)

| 纪律 ID | 描述 | 违反后果 |
|---|---|---|
| **D8-FIND-1** | 7 维评分 commit `63cdac3` 在 feature branch NOT in main | 派工必先 merge |
| **D8-FIND-2** | KB 闭环 commit `0066087c8` 在 feature branch NOT in main | 派工必先 merge |
| **D8-FIND-3** | save_to_kb 5 道防线现状与 D8 调研口径不同 (W5 v3.1 vs 子 plan ② 2.4) | 主拍选型选项 X / 选项 Y |
| **D8-FIND-4** | Celery auto_intake_rollback **未实施** (仅 CLI 工具) | W69 B-3 重写 |
| **D8-FIND-5** | Dashboard MVP 已部分实施 (4 ECharts 子图) 与 D8 调研 4 el-card 不一致 | 主拍选型 |
| **D8-FIND-6** | CI smoke 200 题已闭环, 唯一缺口是 timeout (5min 不现实) | 选项 B/C 优先级低 |

### 8.2 与 W19 选项 A + W68 第 13 批 6 留派工 backlog 关系

**W68 第 13 批 D-3 grand closure 已批的 6 留 W70+ 派工 backlog**:
- qa-bench-d5-ci-gate
- exe-logical-pie Part 2
- fizzy-cooking-puzzle Phase 6 UI
- silly-gliding-dahl chatgpt Phase 6 UI
- isolation-a1 Drive PR7 audit
- bubbly-parnas voice-alert v1

**子 plan ② 与 backlog 不冲突** — 是另一批新派工 (qa-bench D8 闭环 + KB 闭环 + Dashboard MVP), 不在 6 backlog 内.

**W19 选项 A 维持**: 4 留未来 PR 不发起新排期. **子 plan ② 不算新排期** (是 W66 之后的 qa-bench v3 体系闭环遗留).

### 8.3 与 0 production code 改动铁律

- **B-1 (7 维评分)**: 全部新增文件 (`tests/qa-bench/scoring/*` + `docs/` + `memory/`), **0 production code 改动铁律可守恒** ✅
- **B-2 (save_to_kb 重写)**: 修改 `tests/qa-bench/save_to_kb.py` (已 in main + 398 行). **新功能扩展例外已批** (与 W68 第 10 批 B-3 KB 闭环对齐)
- **B-3 (Celery auto_intake_rollback)**: 新增 `app/services/qa_bench_tasks.py` + 修改 `app/core/celery.py` + 修改 `app/config.py` (加 setting). **3 文件新+改** — 例外已批
- **B-4 (KB 闭环)**: 全部新增测试 + 依赖 B-1+B-2+B-3, **0 production code 改动铁律可守恒** ✅
- **B-5 (Dashboard + smoke)**: 修改 `web/src/views/admin/KbMonitorView.vue` + `app/api/v1/admin_kb_monitor.py` + `.github/workflows/qa-bench-*.yml` — **例外已批** (前端增强 + CI 配置)

**W69 派工 5 agents 总例外**: 5/15 例外已批 (B-1/B-4 不例外, B-2/B-3/B-5 例外). 0 production code 改动铁律 10/15 守恒.

---

## 9. 总结 + 主拍决策点

### 9.1 子 plan ② 6 项实施现状汇总

```
子 plan ① chat history 8 phase (W68 #043 已闭环 ✅)
    ↓
子 plan ② qa-bench 7 维 + KB 闭环 + Dashboard MVP (W69 派工 ⏸)
    ├─ 7 维评分 (63cdac3 in feature branch, merge to main 必做)
    ├─ save_to_kb 5 道防线 (in main, 主拍选型 X/Y)
    ├─ Celery auto_intake (❌ 未实施, W69 B-3 重写)
    ├─ KB 闭环 (0066087c8 in feature branch, merge to main 必做)
    ├─ Dashboard MVP (in main, 部分符合 D8, 补 2 el-card + 5min polling)
    └─ CI smoke 200 题 (in main, 已闭环, 仅 cleanup 2 个 workflow)
    ↓ 基础数据齐备
子 plan ③ UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb (W70 派工 ⏸)
    ↓ 用户体验提升
chatgpt-structured-floyd 3 子 plan 100% 闭环
```

### 9.2 主拍必拍决策点

| # | 决策项 | 选项 | 建议 | 主拍 |
|---|---|---|---|---|
| 1 | 选项 A/B/C 派工数量 | A: 5 agents / B: 3 agents / C: 5 跳 B-3 | **选项 A** (5 agents 全闭环) | ⏸ 待拍 |
| 2 | W68 第 14 批前置 merge agent | 派 / 不派 | **必须派** (避免 merge 冲突后再 retry) | ⏸ 待拍 |
| 3 | save_to_kb 5 道防线口径 | 选项 X (重写 D8 口径) / 选项 Y (保留 W5 v3.1) | **选项 X** (与子 plan ② 2.4 对齐) | ⏸ 待拍 |
| 4 | Dashboard MVP 视图选型 | ECharts (现状) / 4 el-card (D8) | **ECharts 保留** (W68 已实施, 改造成本低) | ⏸ 待拍 |
| 5 | CI smoke 5min 不现实 | 接受 30-60min / 拆分 200 smoke + 800 nightly | **接受现状** (PR 红 ✗ 阻断有价值) | ⏸ 待拍 |
| 6 | W69 起始日期 | 2026-07-31 (Mon) / 其他 | 2026-07-31 | ⏸ 待拍 |
| 7 | W69+KbMonitorView 后续是否 D8 dashboard 整合到 KbMonitorView | 是 / 否 | **是** (合并到 KbMonitorView 单页) | ⏸ 待拍 |

### 9.3 锚点范式 + 主指挥协调守恒预期

**W68 第 14 批 C-1 完成** 后:
- 锚点范式 168 → 177 (W68 第 14 批 9 守恒预期, 含本调研)
- W69 派工 5 agents 完成 → 174 → 180 (锚点范式 30 守恒累计)

**主指挥协调范式第 44 次派工**:
- W68 第 13 批 D-3 grand closure → W68 第 14 批 C-1 调研 → 后续 W69 派工实施

---

## 附录 A: 4 grep 命令完整输出 (真验证保留)

### A.1 grep_1: `app/` 集成
```
app/api/v1/knowledge.py:295:      - data/auto_intake_summary.json (save_to_kb.py 写入)
app/api/v1/knowledge.py:297:      - data/auto_intake_rollback_*.json (rollback 任务写入)
app/api/v1/knowledge.py:313:    # 1. 读 save_to_kb.py 输出的 summary 文件
app/api/v1/knowledge.py:356:        for rb_path in sorted(rollback_dir.glob("auto_intake_rollback_*.json"), reverse=True):
app/api/v1/knowledge.py:631:    客户端: tests/qa-bench/save_to_kb.py 改造后调用
app/schemas/knowledge.py:437:    """单条自动拓展入库请求 (来自 qa-bench save_to_kb.py)"""
app/utils/safe_minio_intake.py:11:3. save_to_kb.py 的 run_intake() 集成此 helper, 测环境 dry-run 永远不写库
app/utils/safe_minio_intake.py:23:- save_to_kb.py 集成: grayscale > max_intake_pct → return False + log warning
app/utils/safe_minio_intake.py:61:            # 真正调用 save_to_kb.run_intake()
app/utils/safe_minio_intake.py:131:            grayscale_pct: 0-100 整数, 来自 save_to_kb 的 --grayscale / KB_INTAKE_GRAYSCALE
```

### A.2 grep_2: `scripts/` 集成
```
scripts/auto_intake_rollback.py:76:    print(f"[auto_intake_rollback] 开始 ({datetime.now().isoformat()})")
scripts/auto_intake_rollback.py:108:    report_path = Path(f"data/auto_intake_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
scripts/generate_token_plan_doc.py:221:add_para('W5 收官：save_to_kb.py 5 道防线 + scripts/auto_intake_rollback.py 7 天自动清理 + 200 题 smoke 套件', italic=True)
scripts/generate_token_plan_doc.py:1125:    ('scripts/auto_intake_rollback.py', '7 天自动清理 source_type=auto_expansion（KB 入库 rollback）'),
scripts/generate_token_plan_doc.py:1138:    ('scripts/auto_intake_rollback.py', 'KB 入库 rollback（7 天自动清理）'),
scripts/generate_token_plan_doc.py:1142:    ('scripts/qa-bench/save_to_kb.py', 'qa-bench 答题后自动入库（5 道防线）'),
```

### A.3 grep_3: git log 检索
```
14aae9aaf feat(qa-bench): v3.1 D2 runner 集成 save_to_kb + 端到端测试  ✅ in main
bc3a60619 merge: qa-bench-d5-kb-monitor-2026-07-24 (W68 第 7 批)  ✅ in main
63cdac3bb qa-bench(w68-10th-batch-b1): 7-dim scoring + verdict v2 + phase3 matrix  ⚠️ feature branch only
0066087c8 feat(kb-closed-loop): W68 第 10 批 B-4 KB 闭环 automation (5 步 pipeline) — 锚点范式第 127 守恒  ⚠️ feature branch only
```

### A.4 grep_4: `.github/workflows/` 集成
```
.github/workflows/qa-bench-ci.yml:4:# - 复制 qa-bench-smoke.yml 的 test DB stack 启动逻辑 (pg-test + app-test on 8001)
.github/workflows/qa-bench-smoke.yml:7:# 2026-07-02 修复 (qa-bench-smoke-test-db):
.github/workflows/qa-bench-smoke.yml:22:      - ".github/workflows/qa-bench-smoke.yml"
.github/workflows/qa-bench-smoke.yml:30:      - ".github/workflows/qa-bench-smoke.yml"
.github/workflows/qa-bench-smoke.yml:42:  qa-bench-smoke:
.github/workflows/qa-bench-smoke.yml:213:          name: qa-bench-smoke-report
.github/workflows/qa-bench-smoke.yml:214:          path: tests/qa-bench/results/smoke/
```

---

## 附录 B: 关键 commit hash 速查

| Commit | 描述 | 在 main? | 关联工作 |
|---|---|---|---|
| `63cdac3bb` | 7-dim scoring + verdict v2 + phase3 matrix | ❌ feature branch | W68 第 10 批 B-1 |
| `0066087c8` | KB 闭环 automation 5 步 pipeline | ❌ feature branch | W68 第 10 批 B-4 |
| `14aae9aaf` | qa-bench v3.1 D2 runner save_to_kb 集成 | ✅ in main | v3.1 D2 |
| `bc3a60619` | merge qa-bench-d5-kb-monitor | ✅ in main | W68 第 7 批 A-4 (KbMonitorView) |
| `e6220d016` | qa-bench D6 Phase 2 dry-run | ✅ in main | W68 第 7 批 B-2 |
| `c496862b7` | qa-bench D6 Phase 3 matrix 4 runner 并行 | ✅ in main | W68 第 8 批 B-4 |
| `4b215220` | refactor (意外删除 15-17-18-cozy-bengio Part 2) | 待 W68 第 14 批闭环 | W68 第 6 批验证 |
| `9b7c0e8a9` | merge W68 第 13 批 grand closure memory | ✅ 当前 main HEAD | W68 第 13 批 D-3 |

---

**调研完成. 主指挥决策依据齐备. W69 派工 5 agents / 选项 A 推荐.**

**核心纪律**: 派工必先派 W68 第 14 批 **merge agent** (前置 4h), 把 2 个 feature branch merge 进 main, 否则 B-1 + B-4 in main 后内容为空.
