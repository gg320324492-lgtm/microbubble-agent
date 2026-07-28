# W71 启动前 Plans 真验证 — 派工纪要 v4 铁律 3 实战

> W71 第 1 批 A-3 启动前调研, 2026-07-27
> 范围: 只做 plans/docs/memory 调研, 不实施 production code.
> 基线: W68 第 14 批 A-3 [`docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md`](./w70-w71-plans-backlog-survey-v2-2026-07-24.md); 主拍 [`docs/w71-final-decision-2026-07-24.md`](./w71-final-decision-2026-07-24.md); 派工纪要 v6 段 5 反馈循环 + 段 6 合并顺序表.
> 当前 worktree HEAD: `0ae74f477` (W68 第 14 批 H-5 静默 heartbeat rebuild 后).
> 目标锚点范式: **第 194 守恒**.

---

## 1. TL;DR — W71 启动前真验证结论

**派工 v4 铁律 3 实战结论 (W71 启动前 4 grep + 7 grep 真验证)**:

1. **子 plan ② 状态盘点** — W68 第 14 批 A-3 调研 (锚点范式第 171 守恒) 结论"已分批落地但文件布局不同"仍然有效, 但 **HEAD 现状** 与 **W68 第 14 批 A-3 调研基准 HEAD (9b7c0e8a9 之前)** 不一致 — `tests/qa-bench/scoring/` 在 9b7c0e8a9 之前实际未 merge 入 main. `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` 分支 commit `63cdac3bb` 含 scoring dir, 但 merge 状态待主指挥 verify.
2. **plan 中未完成内容清单 (5 项)** — B-1 7 维评分代码路径有但未 merge / B-2 5 道防线 3 缺 / B-3 Celery auto_intake_rollback 缺 / B-4 KB 闭环 5 道防线各自独立 / B-5 Dashboard MVP 4 卡片缺 2.
3. **派生新任务清单 (6 项)** — C-1 D8 后续 / C-2 SubAgent 编排 / C-3 notify v2 仓库模板回测 + D-1 派工纪要 v8 / D-2 6 类文档同步 / D-3 锚点范式守恒.
4. **W71 派工 5 agents 路径调整建议** — B-1 必先 verify merge `63cdac3bb` (避免重复实施); B-2 必先补 3 缺防线模块; B-3 必先建 `app/services/qa_bench_tasks.py`; B-4 必先补串联 5 步; B-5 必先补 2 el-card + 5min polling.
5. **风险等级** — 🟡 中 (qa-bench 7 维首次落地, 但 scoring dir merge 待 verify, 灰度发布开关 `AUTO_KB_INTAKE_ENABLED=False` 默认关).

**W71 派工 5 agents 真验证表见 §2**, **W71 启动前 4 grep 真验证见 §3**, **plan 中未完成内容清单见 §4**, **派生新任务清单见 §5**, **W71 batch 15 agents 派工建议表见 §6**.

---

## 2. W71 派工 5 agents 真验证表 (B-1/B-2/B-3/B-4/B-5)

### 2.1 真验证命令标准化

每个 agent 必跑 4 步真验证 (派工 v4 铁律 3):
1. **plan body 描述** — `cat ~/.claude/plans/chatgpt-structured-floyd.md` 抽出 agent 对应段落
2. **真验证命令** — `git log --all --grep` + `grep -rE` + `git ls-tree` 三重
3. **当前状态 (实施/部分/未实施)** — 三重验证交叉判定
4. **缺口 + 优先级** — 派生补实施内容

### 2.2 B-1 — 7 维评分算法

| 维度 | 内容 |
|------|------|
| **plan body 描述** | `chatgpt-structured-floyd.md` §3.1-3.2 + §5 — 7 维 intent(10%)/tool(25%)/content(30%)/rich(5%)/defense(15%)/perf(10%)/consistency(5%) 评分, `tests/qa-bench/scoring/seven_dim.py` + `weights.json` |
| **真验证命令** | `git log --all --grep "7-dim\|seven_d"` + `git ls-tree HEAD tests/qa-bench/scoring/` + `grep -rE "score_seven_dim\|seven_dim" tests/qa-bench/runner.py` |
| **真验证命令输出** | commit `63cdac3bb` 在分支 `feat/w68-10th-batch-b1-7d-scoring-2026-07-24`, scoring dir 450 行 `seven_d_scoring.py` + 146 行 `verdict_consensus_v2.py` + 376 行 `test_seven_d_scoring.py`; **HEAD `0ae74f477` 无 scoring/ 目录**; runner.py 内联 `score_seven_dim` 函数 (历史降级) |
| **当前状态** | **部分实施 + 待 merge verify** — 7 维评分算法已在分支 commit `63cdac3bb` (W68 第 10 批 B-1), 但 merge 进 main 状态需主指挥 verify. main HEAD 看到的是 runner.py 内联简化版 (无 scoring/ 子目录) |
| **缺口** | ① `63cdac3bb` merge 进 main 状态 (优先级 P0) ② scoring/ 目录命名差异 (`seven_d_scoring.py` vs plan 期望 `seven_dim.py`) ③ weights.json 未独立, 权重由模块常量承载 (W68 第 14 批 A-3 §3.1 记录) ④ verdict_consensus_v2.py 是否合并进 main 待 verify ⑤ 11 个单测是否随 merge 进 main 待 verify |
| **优先级** | **P0** — 必先 verify `63cdac3bb` merge 状态再决定是否补建 scoring/ 目录, 避免重复实施 7 维算法 |

### 2.3 B-2 — save_to_kb.py 5 道防线

| 维度 | 内容 |
|------|------|
| **plan body 描述** | `chatgpt-structured-floyd.md` §3.5 — 5 道防线 (分数门控 ≥4 / 内容 ≥200 字 / 意图白名单 / 灰度开关 / 7 天 rollback + 人工 feedback <10%) |
| **真验证命令** | `grep -E "MIN_SCORE\|MIN_CONTENT\|ALLOWED_INTENTS\|dedup\|confidence" tests/qa-bench/save_to_kb.py` + `grep -rE "kb_queue\|dedup" app/ tests/qa-bench/` + `ls tests/qa-bench/kb_queue/` |
| **真验证命令输出** | `save_to_kb.py` 含防线 1 (DEFAULT_MIN_SCORE=4) + 防线 2 (DEFAULT_MIN_CONTENT_LENGTH=200) + 防线 3 (DEFAULT_ALLOWED_INTENTS=[explain_concept, search_info]) + 防线 4 (AUTO_KB_INTAKE_ENABLED env) + 防线 5 (backups/auto_intake/ + 7 天 rollback), 共 398 行. **独立 kb_queue/dedup.py 模块不存在** — dedup 通过 `--force-no-dedup` flag + 客户端 IntegrityError 处理, 未抽为独立模块 |
| **当前状态** | **部分实施** — 5 道防线在 `save_to_kb.py` 单文件实现, 但 ① 无独立 `kb_queue/dedup.py` 模块 (W68 第 14 批 A-3 §3.2 记录缺口) ② LLM 拒答检测 (kb_queue/llm_refusal.py) 缺口 ③ 敏感词/placeholder/filler 防线未独立, 由 runner/detector 分散覆盖 ④ 人工抽检 5% admin queue 未证实完整 |
| **缺口** | ① 防线 3+4 重构为独立 kb_queue/ 模块 ② LLM 拒答检测逻辑 ③ 敏感词独立防线 ④ admin 抽检队列 + 界面 ⑤ 5% 抽检工作流 |
| **优先级** | **P0** — 5 道防线是子 plan ② 风险最高的环节 (CLAUDE.md 2026-06-15 教训: "QA 入库必须人工把关"), 必须配齐独立模块 + 抽检工作流 |

### 2.4 B-3 — Celery auto_intake_rollback_task

| 维度 | 内容 |
|------|------|
| **plan body 描述** | `chatgpt-structured-floyd.md` §3.5 — Celery beat 3:30 跑, 入库后 7 天 review, 引用 ref 失效或用户点击 <3 次 → 自动 rollback |
| **真验证命令** | `grep -rE "auto_intake_rollback_task\|celery.*beat\|app/services/qa_bench_tasks" app/` + `ls scripts/auto_intake_rollback.py` + `grep -rE "celery_app.conf.beat_schedule" app/` |
| **真验证命令输出** | `scripts/auto_intake_rollback.py` 119 行 CLI 工具 (psycopg2 直连 DB, 7 天 rollback), 备份目录 `backups/auto_intake/`, app API `app/api/v1/knowledge.py` 读取 `auto_intake_rollback_*.json`. **app/services/qa_bench_tasks.py 不存在** — 计划要求的 Celery beat 任务未实施, 是 CLI 工具形态 |
| **当前状态** | **部分实施 (脚本形态, 非 Celery)** — 7 天 rollback 逻辑在 `scripts/auto_intake_rollback.py` 119 行 CLI 工具, 非计划要求的 Celery beat 任务. plan 任务 `app/services/qa_bench_tasks.py:auto_intake_rollback_task` 未实施 |
| **缺口** | ① `app/services/qa_bench_tasks.py` (新文件 ~100 行) ② Celery beat 注册 `app.core.celery_app.conf.beat_schedule` ③ 幂等键 (基于 KB ID + created_at) ④ 时区处理 (CLAUDE.md tz-aware vs naive 教训) ⑦ worker 运行证据 (celery beat 日志) |
| **优先级** | **P0** — 自动化 rollback 是 KB 闭环兜底, CLI 工具需手动跑 → 7 天后无主动 rollback 风险 |

### 2.5 B-4 — KB 闭环端到端

| 维度 | 内容 |
|------|------|
| **plan body 描述** | `chatgpt-structured-floyd.md` §3.5 — 候选 → 评分门禁 → 防线逐项 → 入库审计 → 24h/7d review → rollback/alert → dashboard 反映, 7 步闭环 |
| **真验证命令** | `grep -rE "kb_queue\|KB 闭环\|closed_loop\|save_to_kb.*intake" tests/qa-bench/ app/services/` + `ls scripts/auto_intake_summary.py` + `grep -rE "auto_intake_summary" app/api/` |
| **真验证命令输出** | `app/api/v1/knowledge.py` 含 rollback JSON 监控端点; `tests/qa-bench/runner.py` 调 `save_to_kb.run_intake` + observer.record_intake. **5 道防线各自独立, 缺串联** — alembic `072_kb_closed_loop.py` + `073_kb_links_placeholder.py` 是 bridge 占位 (pass), 无实质 schema 改动 |
| **当前状态** | **部分实施 + 无串联** — 5 道防线 + save_to_kb + observer + rollback JSON 各自独立, 缺端到端串联 (W68 第 14 批 A-3 §3.4 结论: "五道防线的独立可审计证据、失败回滚、负反馈暂停和灰度开关仍需验收") |
| **缺口** | ① 7 步闭环 audit event 链 ② 24h/7d review scheduler ③ 负反馈暂停机制 (`submit_feedback negative > 10%` → 暂停入库) ④ 灰度发布开关 UI ⑤ 失败回滚负测 |
| **优先级** | **P0** — KB 闭环是子 plan ② 终极交付物, 必须 7 步全贯通, 否则不算闭环 |

### 2.6 B-5 — Dashboard MVP + CI smoke 200 题

| 维度 | 内容 |
|------|------|
| **plan body 描述** | `chatgpt-structured-floyd.md` §3.4 — Dashboard 4 卡片 (入库数 / 通过率 / 抽检数 / 告警数) + 5min polling + 待抽检 + 告警详情; CI smoke 200 题 `< 5min` |
| **真验证命令** | `ls tests/qa-bench/dashboard/` + `cat web/src/views/Dashboard.vue` + `ls .github/workflows/qa-bench-smoke.yml` + `grep -rE "qa-bench-dashboard\|el-card.*入库" web/src/views/` |
| **真验证命令输出** | `tests/qa-bench/dashboard/index.html` + `gen_data.py` + `data.json` 已存在, 用 ECharts 4 子图 (seven_dim/grade/category/趋势). **web 端 `/admin/qa-bench-dashboard` 路由缺失** — vue 端只有 `Dashboard.vue` 主仪表盘, 无 qa-bench 专项 4 卡片 (入库/通过率/抽检/告警). CI `.github/workflows/qa-bench-smoke.yml` 已存在 |
| **当前状态** | **部分实施 (数据页有, 前端 4 卡片缺)** — tests/qa-bench/dashboard 有 index.html 但 vue 端 4 卡片组件缺 2 (入库数 + 抽检数), 5min polling 未配置 |
| **缺口** | ① web/src/views/admin/QaBenchDashboard.vue 新建 ~350 行 (4 el-card + ECharts) ② 5min polling composable (useQaBenchPolling.js) ③ 7 天统计视图 ④ 待抽检队列 UI ⑤ 告警详情对话框 |
| **优先级** | **P1** — Dashboard MVP 数据来源已有 (data.json + gen_data.py), 缺前端可视化层. CI smoke 200 题已就位 |

---

## 3. W71 启动前 4 grep 真验证 (W68 第 14 批 A-3 4 步实战)

### 3.1 修前 (W68 第 14 批 A-3 真验证结论)

W68 第 14 批 A-3 调研 (`docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md` §3, 锚点范式第 171 守恒) 结论摘要:

| 子 plan ② 项 | W68 第 14 批 A-3 调研结论 | 调研 commit 锚点 |
|--------------|--------------------------|-----------------|
| 7 维评分 | **已实施, 路径改名** — `tests/qa-bench/scoring/seven_d_scoring.py` (450 行) + `verdict_consensus_v2.py` (146 行) + `test_seven_d_scoring.py` (376 行, 11 测试全 PASS). 7 维基线与矩阵报告已落地 | `63cdac3bb` W68 第 10 批 B-1 (锚点范式第 124 守恒) |
| save_to_kb.py 5 道防线 | **部分实施** — `save_to_kb.py` 398 行含 5 道防线 (分数 + 内容 + 意图 + 灰度 + rollback); 缺独立 kb_queue/ 模块 | commit `14aae9aaf` (W68 第 5 批 集成历史) |
| Celery rollback | **部分实施, 部署契约未闭环** — `scripts/auto_intake_rollback.py` 119 行 CLI 工具 (psycopg2 直连), `app/api/v1/knowledge.py` 监控 rollback JSON; 缺 Celery beat 任务 | n/a (CLI 形态) |
| KB 闭环 | **部分实施 + 无串联** — 5 道防线各自独立; `app/api/v1/knowledge.py` 监控端点; `data/auto_intake_summary.json` 约定; 缺 7 步 audit event | `64660718c` (自动入库回滚/重试/告警闭环) + `0066087c8` (KB 闭环 automation) |
| Dashboard MVP | **部分实施 (数据页 MVP)** — `tests/qa-bench/dashboard/index.html` + `gen_data.py` + `data.json` 有; `/admin/qa-bench-dashboard` 4 卡片 + 5min polling + 抽检 + 告警详情 待确认 | n/a (历史散落) |
| CI smoke 200 题 | **部分实施 + 环境依赖未闭环** — `.github/workflows/qa-bench-smoke.yml` + `questions_smoke_200.jsonl` + `scripts/ci_qa_bench_baseline.sh` + D7 workflow 已存在; 本地基线实跑 69 passed + 7 skipped + 2 Redis 失败 (目标文档称 71 passed + 7 skipped) | `4c7816c1e` (D7 baseline conservation gate) |

### 3.2 修后 (W71 派工前再跑, 确认状态)

W71 启动前 2026-07-27 再跑 4 grep 真验证 (派工 v4 铁律 3):

```bash
# Step 1: cat plans/chatgpt-structured-floyd.md 子 plan ② 部分
cat /c/Users/pc/.claude/plans/chatgpt-structured-floyd.md | grep -A 5 "^## 2\.\|^## 3\." | head -50
# 输出: plan §2 (题库结构) + §3 (评估框架 7 维 + save_to_kb 5 道防线 + 检测器) 已确认

# Step 2: git log 看相关 commits 在 main
git log --oneline origin/main | grep -iE "qa-bench|chatgpt|7 维|save_to_kb|rollback" | head -10
# 输出 (按时间倒序):
# 1f3c210e0 merge: chore/w68-14th-batch-c1-d8-survey-2026-07-24 (W68 第 14 批 C-1 qa-bench D8 综合调研)
# 539b3832e chore(w68-14th-batch-b4): claude-code notify v2 部署验证 (6 trigger 实跑 + rollback 验证)
# b190cbf4e chore(w68-14th-batch-c1): qa-bench D8 综合调研 (子 plan ② 实施前置 7 项)
# 4c7816c1e ci(qa-bench): add D7 baseline conservation gate
# b9ada515e merge: test/qa-bench-phase3-matrix-2026-07-24 (W68 第 10 批)
# 7b43ae661 merge: chatgpt W69 plan (W68 第 10 批)
# e3c6a2d72 docs(w68-9th-batch-b4): chatgpt-structured-floyd W69 子 plan ②/③ 调研 + 5 新铁律
# c496862b7 qa-bench D6 Phase 3 matrix 4 runner 并行 (W68 第 8 批 B-4)
# cc5a36397 merge: qa-bench-phase2-dry-2026-07-24 (W68 第 8 批)
# bc3a60619 merge: qa-bench-d5-kb-monitor-2026-07-24 (W68 第 8 批)

# Step 3: grep 看实施状态
grep -rE "scoring|seven_dim|7 维" /e/microbubble-agent/tests/qa-bench/ 2>&1 | head -5
# 输出: tests/qa-bench/dashboard/data.json + gen_data.py + index.html 含 seven_dim 数据消费
# runner.py 内联 score_seven_dim 函数
# ⚠️ 关键发现: HEAD 无 tests/qa-bench/scoring/ 目录 (commit 63cdac3bb 在分支未 merge)

grep -rE "def save_to_kb|5 道防线|dedup" /e/microbubble-agent/tests/qa-bench/ 2>&1 | head -5
# 输出: tests/qa-bench/GUIDE.md + MILESTONES.md + results/*.md 含 "5 道防线" + "KB dedup" 描述
# tests/qa-bench/save_to_kb.py 头注释 W5 T5.1 升级 - 全自动入库模式 (5 道防线)
# ⚠️ 关键发现: tests/qa-bench/kb_queue/ 目录不存在 (5 道防线仍单文件实现)

grep -rE "auto_intake_rollback_task" /e/microbubble-agent/app/ 2>&1 | head -5
# 输出: app/api/v1/knowledge.py 监控 auto_intake_rollback_*.json (数据消费端)
# ⚠️ 关键发现: app/services/qa_bench_tasks.py 不存在 (Celery task 未实施, 仅有 scripts/auto_intake_rollback.py CLI)

# Step 4: alembic 当前 head
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('HEADS:', s.get_heads())"
# 输出: HEADS: ['078_drive_dedupe_audit']
# ✅ 单链 1 个 head, W68 第 8 批 §2.3 串单链纪律守恒
```

### 3.3 修前 vs 修后对比 (核心发现)

| 维度 | 修前 (W68 第 14 批 A-3) | 修后 (W71 派工前) | 差异 |
|------|------------------------|------------------|------|
| **7 维评分文件布局** | `tests/qa-bench/scoring/seven_d_scoring.py` 已存在 (commit 63cdac3bb) | **HEAD `0ae74f477` 无 scoring/ 目录** — 63cdac3bb 仅在分支 `feat/w68-10th-batch-b1-7d-scoring-2026-07-24`, merge 状态待 verify | ⚠️ **关键差异**: 调研基准与当前 HEAD 状态不一致, 必须 verify merge 状态 |
| **save_to_kb 5 道防线** | 398 行单文件含 5 道防线 | 398 行单文件含 5 道防线 (无变化) | 一致 |
| **Celery rollback** | 119 行 CLI + app API 监控 | 119 行 CLI + app API 监控 (无变化) | 一致 |
| **KB 闭环** | 5 道防线独立, 缺串联 | 5 道防线独立, 缺串联 (无变化) | 一致 |
| **Dashboard MVP** | 数据页 index.html 有 | 数据页 index.html 有 (无变化) | 一致 |
| **CI smoke 200 题** | `.github/workflows/qa-bench-smoke.yml` + D7 workflow | `.github/workflows/qa-bench-smoke.yml` + D7 workflow (无变化) | 一致 |
| **alembic head** | 多 head 风险 (W68 第 8 批 §2.3 串单链) | **单链 1 head `078_drive_dedupe_audit`** | ✅ 单链守恒 |

**核心结论**: 调研基准 (W68 第 14 批 A-3 §3) 与当前 HEAD (0ae74f477) 在 7 维评分布局有差异 — 调研基准假设 `tests/qa-bench/scoring/` 已 merge 入 main, 但实际仅在分支未 merge. **W71 B-1 必先 verify `63cdac3bb` merge 状态再决定补建 scoring/ 目录**.

---

## 4. plan 中未完成内容清单 (W71 B 路线 5 agents 必含)

### 4.1 B-1 — 7 维评分算法缺口 (优先级 P0)

| 缺口项 | plan body 要求 | 当前 HEAD 状态 | 必做内容 |
|--------|---------------|---------------|---------|
| **merge verify** | `tests/qa-bench/scoring/seven_dim.py` 在 main HEAD | commit `63cdac3bb` 仅在分支, 未确认 merge | 主指挥 verify `63cdac3bb` 在 main HEAD; 若未 merge → 立即 merge (W68 第 10 批 B-1 早已落地) |
| **路径改名** | `seven_dim.py` (plan 期望) | 分支内 `seven_d_scoring.py` (实际命名) | 改名 `seven_d_scoring.py` → `seven_dim.py` (符合 plan + W68 第 6 批 §1.3 命名规范) |
| **weights.json 独立** | `tests/qa-bench/scoring/weights.json` (plan §3.2) | 权重由 `seven_d_scoring.py` 常量承载 | 抽出 weights.json + 配置加载函数 |
| **verdict_consensus_v2** | plan §3.1 提到 consensus v2 | 分支内 146 行 verdict_consensus_v2.py | merge 进 main (随 63cdac3bb 一起) |
| **11 个单测** | plan §3.1 提到 11 测试全 PASS | 分支内 376 行 test_seven_d_scoring.py | merge 进 main + 跑通验证 |
| **基线复跑** | plan §3.3 4 类报告 (单题/维度/趋势/雷达图) | phase2/phase3 runner 有报告产物 | 固化 JSON schema + 版本号 + 阈值 + 回归快照 (W68 第 14 批 A-3 §3.1) |

**W71 B-1 Agent 必做**: ① merge verify ② 路径改名 ③ weights.json 独立 ④ 780 题/分层样本复跑 (W68 第 14 批 A-3 §3.1 第 3 列 "已实施" 行) ⑤ 7 维基线报告固化.

### 4.2 B-2 — save_to_kb.py 5 道防线缺口 (优先级 P0)

| 防线 | 现状 (HEAD) | 缺口 | 必做内容 |
|------|-------------|------|---------|
| **防线 1: 分数门控** | `save_to_kb.py:70 DEFAULT_MIN_SCORE = 4` + line 149 实施 | 无 | 已完成, 必保持 |
| **防线 2: 内容门控** | `save_to_kb.py:71 DEFAULT_MIN_CONTENT_LENGTH = 200` + line 153 实施 | 无 | 已完成, 必保持 |
| **防线 3: 意图白名单** | `save_to_kb.py:72 DEFAULT_ALLOWED_INTENTS` + line 157 实施 | 无 | 已完成, 必保持 |
| **防线 4: 灰度开关** | `save_to_kb.py:64 AUTO_KB_INTAKE_ENABLED env` + `--grayscale` flag | `--force-no-dedup` flag 仍存在, 应改为默认禁止 | 灰度 UI 化 + 默认禁止 `--force-no-dedup` |
| **防线 5: 备份 + 7 天 rollback** | `save_to_kb.py` 备份 `backups/auto_intake/` + `scripts/auto_intake_rollback.py` 119 行 | rollback 仍是 CLI 手动跑, 无 scheduler | 接入 B-3 Celery beat (auto_intake_rollback_task) |
| **独立 kb_queue/dedup.py 模块** | plan §3.5 期望 | **目录不存在**, dedup 散落在 save_to_kb.py 内 `--force-no-dedup` flag + 客户端 IntegrityError | 新建 `tests/qa-bench/kb_queue/` + `dedup.py` + `llm_refusal.py` + `sensitive_word.py` + `human_review.py` |
| **5 道防线矩阵负测** | plan §3.5 要求 | 无负测 | 新建 `tests/qa-bench/test_save_to_kb_5_defenses.py` 覆盖 5 道防线正向 + 反向 |
| **人工抽检 5% admin queue** | plan §3.5 "5 道防线" | 无 admin queue | 新建 `tests/qa-bench/admin_queue.py` + admin UI |

**W71 B-2 Agent 必做**: ① 重构 5 道防线为独立 `kb_queue/` 模块 ② LLM 拒答检测 ③ 敏感词独立防线 ④ admin 抽检队列 ⑤ 5 道防线矩阵负测.

### 4.3 B-3 — Celery auto_intake_rollback_task 缺口 (优先级 P0)

| 缺口项 | plan body 要求 | 当前 HEAD 状态 | 必做内容 |
|--------|---------------|---------------|---------|
| **app/services/qa_bench_tasks.py** | 新文件 ~100 行 (plan §3.5) | **文件不存在** | 新建 `app/services/qa_bench_tasks.py:auto_intake_rollback_task` (Celery task) |
| **Celery beat 注册** | `app.core.celery_app.conf.beat_schedule` | 无 | 在 `celery_app.conf.beat_schedule` 加 `'auto-intake-rollback': {...}` 每天 3:30 跑 |
| **幂等键** | KB ID + created_at | 无 | Celery task 内部用 `WHERE id=? AND created_at < NOW()-7days AND rollback_marker IS NULL` 幂等 |
| **时区处理** | tz-aware UTC (CLAUDE.md 2026-06-05 教训) | scripts/auto_intake_rollback.py 用 `datetime.now() - timedelta(days=7)` naive | 改用 `datetime.now(timezone.utc) - timedelta(days=7)` |
| **告警阈值** | 引用 ref 失效或下游用户点击 <3 次 → 自动 rollback | 无 | Celery task 加查询 `knowledge_usage_stats` 表 (如有) + 阈值判断 |
| **worker 运行证据** | celery beat 日志可查 | 无 worker 运行 | W71 部署后必跑 `docker logs celery-worker | grep auto-intake-rollback` 验证 |

**W71 B-3 Agent 必做**: ① 新建 `app/services/qa_bench_tasks.py` ② Celery beat 注册 ③ 幂等键 + 时区 ④ 告警阈值 ⑤ 部署后 worker 验证.

### 4.4 B-4 — KB 闭环端到端缺口 (优先级 P0)

| 闭环步骤 | plan §3.5 要求 | 当前 HEAD 状态 | 必做内容 |
|----------|---------------|---------------|---------|
| **步骤 1: 候选** | runner.py 收集 high_score candidates | ✅ 已就位 | 必保持 |
| **步骤 2: 评分门禁** | save_to_kb.collect_candidates | ✅ 已就位 | 必保持 |
| **步骤 3: 防线逐项** | 5 道防线逐项记录 | ⚠️ 5 防线已实现, 但缺逐项 audit log | 新建 `save_to_kb.collect_candidates` 内每条候选必写 `defense_audit` dict |
| **步骤 4: 入库审计** | `data/auto_intake_summary.json` | ✅ 已就位 | 必保持 |
| **步骤 5: 24h/7d review** | Celery 周期任务 | ❌ 无 scheduler | 接入 B-3 Celery beat (auto_intake_rollback_task 7d + 新建 review 24h task) |
| **步骤 6: rollback/alert** | scripts/auto_intake_rollback.py 7d rollback | ⚠️ 脚本形态 | 接入 B-3 Celery 形态 |
| **步骤 7: dashboard 反映** | tests/qa-bench/dashboard/index.html | ✅ 数据页 MVP | 必保持 + 接入 B-5 前端 4 卡片 |
| **负反馈暂停** | `submit_feedback negative > 10%` → 暂停入库 | ❌ 无 | 新建 `submit_feedback` API 集成 → `AUTO_KB_INTAKE_ENABLED` 动态切换 |
| **灰度发布开关 UI** | 管理员手动调 grayscale | ❌ 无 UI | 新建 web/src/views/admin/AutoIntakeConfig.vue (灰度 + 暂停 + audit 视图) |

**W71 B-4 Agent 必做**: ① 防线逐项 audit log ② 24h review scheduler ③ 接入 B-3 Celery ④ 负反馈暂停机制 ⑤ 灰度发布开关 UI.

### 4.5 B-5 — Dashboard MVP + CI smoke 200 题缺口 (优先级 P1)

| 缺口项 | plan body 要求 | 当前 HEAD 状态 | 必做内容 |
|--------|---------------|---------------|---------|
| **4 el-card** | 入库数 / 通过率 / 抽检数 / 告警数 | ❌ 仅 tests/qa-bench/dashboard/index.html 数据页, vue 端无 4 卡片 | 新建 `web/src/views/admin/QaBenchDashboard.vue` ~350 行 (4 el-card + ECharts) |
| **5min polling** | 周期刷新 dashboard 数据 | ❌ 无 | 新建 `web/src/composables/useQaBenchPolling.js` 5min interval |
| **7 天统计视图** | 时间序列趋势 | ⚠️ ECharts 趋势图有数据 | 接入 7 天数据聚合 API |
| **待抽检队列 UI** | admin 抽检 5% 工作流 | ❌ 无 | 接入 B-2 admin queue |
| **告警详情对话框** | el-dialog 详情 | ❌ 无 | 接入 rollback JSON 详情 |
| **CI smoke 200 题** | `.github/workflows/qa-bench-smoke.yml` | ✅ 已就位 | 必保持 + D7 baseline 守恒 |

**W71 B-5 Agent 必做**: ① QaBenchDashboard.vue 4 el-card ② useQaBenchPolling 5min ③ 7 天统计 ④ 待抽检 UI ⑤ 告警详情 dialog.

---

## 5. 派生新任务清单 (C 路线 3 agents + D 路线 3 agents)

### 5.1 C 路线 (qa-bench 后续 + SubAgent + notify)

#### C-1 — qa-bench D8 后续实施 (派生自 `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md`)

- **来源**: W68 第 14 批 C-1 调研报告, 7 项实施前置 (题库版本锁定 + 数据脱敏 + 模型/endpoint 锁定 + 阈值与 gate + CI secret 检查 + baseline 对照 + 失败重跑/产物保留策略)
- **当前状态**: 调研完成 ≠ 生产实施 (W68 第 14 批 C-1 §1 明确)
- **W71 C-1 必做**: 题库版本锁定 (questions_780.jsonl 加 `version: 3.1.0`) + 数据脱敏 (PII 字段 hash) + 模型/endpoint 锁定 (LLM_BACKEND + LLM_MODEL 在 baseline report 固化)
- **优先级**: **P1** — D8 调研已就位, 实施不阻塞子 plan ② 但 CI smoke 200 题依赖

#### C-2 — SubAgent 编排 (派生自 W72 UI redesign 准备)

- **来源**: 派工纪要 v6 段 5 反馈循环 + W71 选项 B 调研 (NavRail 双栈 SubAgent 编排)
- **当前状态**: 无 SubAgent 编排, 派工全靠主指挥手动 prompt 派发
- **W71 C-2 必做**: SubAgent orchestration design doc (worktree + branch + commit 命名 + merge 顺序 + 派工 prompt 模板), 不实施代码
- **优先级**: **P2** — W72 续, W71 不阻塞

#### C-3 — notify v2 仓库模板回测 (派生自 W68 第 14 批 B-4)

- **来源**: `539b3832e` claude-code notify v2 部署验证, 6 trigger 实跑 + rollback 验证
- **当前状态**: 部署验证报告就位, 仓库模板回测缺 (git submodule / npm package / Docker image 3 种载体哪个最优?)
- **W71 C-3 必做**: 3 种载体实测 (5 min/载体) + 推荐方案 docs, 不实施代码
- **优先级**: **P2** — 不阻塞子 plan ②

### 5.2 D 路线 (派工纪要 + 文档同步 + 锚点范式)

#### D-1 — 派工纪要 v8 (基于 W71 启动前真验证反馈)

- **来源**: 派工 v6 段 5 反馈循环 (W71 第 1 批 5 agents 派工反馈) + W68 第 14 批 A-2 v5 + W68 第 13 批 D-1 v4
- **W71 D-1 必做**: 在 v6 段 5/段 6 基础上加段 7 "派工前提错误复盘" (W71 第 1 批派工反馈) + 段 8 "5 道防线矩阵" (B-2 真验证)
- **优先级**: **P1** — 派工 v6 第 4 条铁律 "不动 v1-v6 历史约束", v8 是增量非覆盖

#### D-2 — 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + 用户级 1 + 1 新增)

- **来源**: W68 第 14 批 D-2 沉淀 (主仓库 5 + 用户级 1 + 1 新增)
- **W71 D-2 必做**: 6 类文档同步 W71 第 1 批 grand closure (B-1/B-2/B-3/B-4/B-5 + C-1/C-2/C-3 + D-1/D-2/D-3)
- **优先级**: **P1** — 派工 v6 段 6 合并顺序表必含 D-2

#### D-3 — 锚点范式守恒验证 (W71 168 → ~178)

- **来源**: W68 第 13 批 168 → W71 选项 A 178 (+10 守恒)
- **W71 D-3 必做**: 锚点范式守恒 verification (5 agents × 2 锚点 + 3 agents × 1 锚点 + 收口 3 锚点 = 16 锚点, 0 regression)
- **优先级**: **P1** — 锚点范式是派工 v6 段 6 合并顺序表必守纪律

---

## 6. W71 batch 15 agents 派工建议表 (主拍必看)

### 6.1 4 路线 15 agents 完整派工顺序

| 路线 | 派工顺序 | agent 数 | 必含纪律 |
|------|----------|---------|---------|
| **A 部署收口** | A-1 主拍 (W71 启动 + Redis/DB 依赖) | 1 | 派工 v6 段 5 反馈循环 + 段 6 合并顺序表 |
| **B 子 plan ②** | B-1 (7 维评分 verify) → B-2 (5 道防线重构) → B-3 (Celery auto_intake_rollback) → B-4 (KB 闭环端到端) → B-5 (Dashboard + CI smoke) | 5 | 派工 v6 段 6 顺序表 + alembic 串单链 (B-3 新增) + 派工 v4 铁律 3 真验证 |
| **C 派生** | C-1 (D8 实施) → C-2 (SubAgent 编排) → C-3 (notify v2 仓库模板回测) | 3 | 调研类, 不实施 code |
| **D 收尾** | D-1 (派工 v8) → D-2 (6 类文档同步) → D-3 (锚点范式守恒) | 3 | 派工 v6 第 4 条铁律 (不动 v1-v7) + 锚点范式 168 → 178 |
| **总计** | A-1 + B-1/B-2/B-3/B-4/B-5 + C-1/C-2/C-3 + D-1/D-2/D-3 | **12 agents** | — |

**实际派工 = 12 agents** (派工 v6 段 6 合并表允许主拍调整, A-1 主拍可拆为多个 sub-action).

### 6.2 派工顺序必含纪律 (5 条)

1. **alembic 串单链纪律 (W68 第 8 批 §2.3 实战)** — B-3 新增 `app/services/qa_bench_tasks.py` 无 alembic 改动; 若 B-4 加 audit log 表 → 必须 down_revision 接最新 head (`078_drive_dedupe_audit`); 必跑 `python -c "from alembic.script import ScriptDirectory; print(s.get_heads())"` verify 1 head
2. **web dist rebuild + force-add 派工 v4 铁律** — B-5 web 例外 (新建 QaBenchDashboard.vue + useQaBenchPolling.js) → 必跑 `npm run build` + `git add -f web/dist/manifest.{hash}.webmanifest` (CLAUDE.md 2026-07-11 教训); commit 前必 grep `git diff --cached -- web/dist/ | grep -E '"url":\s*"manifest\.webmanifest"'` 期望空
3. **0 production code 改动铁律 16/15 守恒预期** — 路线 A/C/D 完全维持, 路线 B (5 个新功能扩展) 例外预算 `tests/qa-bench/` + `web/src/views/admin/` <350 行 + `app/services/qa_bench_tasks.py` ~100 行 + `.github/workflows/` <5 行; B-1 不算例外 (仅 verify merge + 路径改名 + weights.json 抽出 < 30 行 + 复跑 < 5 行)
4. **派工 v6 段 5 反馈循环** — B-1 派工后 24h 内必回收 5 项反馈 (merge verify + 路径改名 + weights.json + 11 单测 + 7 维基线报告), 反哺 B-2/B-3/B-4/B-5 派工 prompt
5. **派工 v6 段 6 合并顺序表** — 12 agents 合并顺序: B-1 → B-2 → B-3 → B-4 → B-5 (子 plan ② 强依赖链); C-1 与 B-5 并行 (不冲突); C-2/C-3 任意顺序; D-1 → D-2 → D-3 (强依赖)

### 6.3 风险评估

| 路线 | 风险等级 | 风险点 | 缓解策略 |
|------|----------|--------|---------|
| **A 部署收口** | 🟢 低 | Redis/DB 依赖 | A-1 主拍必先启动 Redis (`docker compose up redis postgres -d`) |
| **B 子 plan ②** | 🟡 中 | ① B-1 merge verify 风险 ② B-2 5 道防线重构可能影响 save_to_kb.py 既有测试 ③ B-3 Celery 部署需 docker compose restart ④ B-4 串联 7 步 audit log 可能影响性能 ⑤ B-5 web dist rebuild 必跑 `npm run build` | ① 主拍必先 `git log --all --merges --grep "63cdac3bb"` verify ② B-2 必跑 `tests/qa-bench/test_save_to_kb.py` + `test_save_to_kb_5_defenses.py` 全 PASS ③ B-3 必跑 `docker logs celery-worker | grep auto-intake-rollback` ④ B-4 必跑 `pytest tests/qa-bench/ -k closed_loop` ⑤ B-5 必跑 `npm run build` + grep dist manifest |
| **C 派生** | 🟢 低 | 调研类不实施 code | 无 |
| **D 收尾** | 🟢 低 | 文档同步 + 锚点范式守恒 | 派工 v6 第 4 条铁律 (不动 v1-v7) |

### 6.4 锚点范式预期

| 阶段 | 锚点范式 | 累计守恒 |
|------|----------|---------|
| W68 第 13 批 grand closure 后 | 168 | 起点 |
| B-1 merge verify + 7 维基线复跑 | +2 | 170 |
| B-2 5 道防线重构 + 5 道防线矩阵负测 | +2 | 172 |
| B-3 Celery auto_intake_rollback + worker 验证 | +2 | 174 |
| B-4 KB 闭环端到端 7 步 audit | +2 | 176 |
| B-5 Dashboard 4 el-card + 5min polling + CI smoke | +2 | 178 |
| C-1 D8 实施 + C-2 SubAgent 设计 + C-3 notify 模板回测 | +1 | 179 |
| D-1 派工 v8 + D-2 6 类文档同步 + D-3 锚点范式守恒 | +1 | **180** |
| **W71 选项 A 累计** | **+12** | **180** (W68 第 13 批 +12 守恒) |

**预测**: W71 选项 A 5 agents + C/D 6 agents = 11 agents → 锚点范式 +12 守恒 → 168 → 180 (超出主拍预测 178).

### 6.5 失败回滚

- **单 agent 失败** → 单 agent 回滚 (删除对应文件 + revert commit)
- **B 路线 5 agents 全部失败** → 接受 docs/CI 占位 (W67 第 47 步铁律), 不做第 3 次尝试
- **3 道防线任一 fail** → 关闭 `AUTO_KB_INTAKE_ENABLED` flag, 走 manual review
- **B-1 merge verify 失败 (63cdac3bb 未 merge)** → 立即 merge (无冲突) 或 cherry-pick

---

## 7. 7 grep 真验证命令完整输出 (附录)

### 7.1 grep 1: chatgpt-structured-floyd 子 plan ② ③ 部分

```bash
$ cat /c/Users/pc/.claude/plans/chatgpt-structured-floyd.md | head -10
## Status (2026-07-24 W68 第 11 批 A-1 闭环)
**PARTIAL_REGRESSION (1/3 子 plan 完成, 2/3 留 W69)**: ① chat history 8 phase: ✅ ...
② qa-bench 7 维评分 + save_to_kb.py 全自动入库 5 道防线 + Celery auto_intake_rollback_task + KB 闭环 + Dashboard MVP + CI smoke 200 题: ❌ 留 W69. ③ UI redesign (NavRail / ThinkingModeSwitch / ChatBreadcrumb): ❌ 留 W69. ...
```

### 7.2 grep 2: git log qa-bench 相关 commits

```bash
$ git log --oneline origin/main | grep -iE "qa-bench|chatgpt|7 维|save_to_kb|rollback" | head -10
1f3c210e0 merge: chore/w68-14th-batch-c1-d8-survey-2026-07-24 (W68 第 14 批 C-1 qa-bench D8 综合调研)
539b3832e chore(w68-14th-batch-b4): claude-code notify v2 部署验证 (6 trigger 实跑 + rollback 验证, 锚点范式第 176 守恒)
b190cbf4e chore(w68-14th-batch-c1): qa-bench D8 综合调研 (子 plan ② 实施前置 7 项, 锚点范式第 177 守恒)
4c7816c1e ci(qa-bench): add D7 baseline conservation gate
b9ada515e merge: test/qa-bench-phase3-matrix-2026-07-24 (W68 第 10 批)
7b43ae661 merge: chatgpt W69 plan (W68 第 10 批)
e3c6a2d72 docs(w68-9th-batch-b4): chatgpt-structured-floyd W69 子 plan ②/③ 调研 + 5 新铁律 (锚点范式第 111 守恒)
c496862b7 qa-bench D6 Phase 3 matrix 4 runner 并行 (W68 第 8 批 B-4)
cc5a36397 merge: qa-bench-phase2-dry-2026-07-24 (W68 第 8 批)
bc3a60619 merge: qa-bench-d5-kb-monitor-2026-07-24 (W68 第 8 批)
```

### 7.3 grep 3: scoring/ 目录 merge 状态

```bash
$ git log --oneline --all -- "tests/qa-bench/scoring/*" | head -3
63cdac3bb qa-bench(w68-10th-batch-b1): 7-dim scoring + verdict v2 + phase3 matrix (锚点范式第 124 守恒)
$ git branch -r --contains 63cdac3bb | head -3
  origin/feat/w68-10th-batch-b1-7d-scoring-2026-07-24
$ git ls-tree HEAD tests/qa-bench/ | grep -E "scoring"
(empty)
```

**关键发现**: commit `63cdac3bb` 仅在 `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` 分支, 未 merge 进 main HEAD.

### 7.4 grep 4: save_to_kb 5 道防线

```bash
$ grep -E "DEFAULT_MIN_SCORE|DEFAULT_MIN_CONTENT|DEFAULT_ALLOWED|AUTO_KB|GRAYSCALE" tests/qa-bench/save_to_kb.py | head -10
AUTO_KB_INTAKE_ENABLED = os.environ.get("AUTO_KB_INTAKE_ENABLED", "false").lower() == "true"
def _parse_grayscale_env() -> int:
def is_in_grayscale(qa_id: str, grayscale_pct: int) -> bool:
DEFAULT_MIN_SCORE = 4
DEFAULT_MIN_CONTENT_LENGTH = 200
DEFAULT_ALLOWED_INTENTS = ["explain_concept", "search_info"]
```

### 7.5 grep 5: auto_intake_rollback 任务存在性

```bash
$ find app/ -name "qa_bench_tasks*" -o -name "auto_intake_rollback*" 2>&1 | head -5
(empty)
$ ls scripts/auto_intake_rollback.py
scripts/auto_intake_rollback.py (119 lines)
$ grep -E "auto_intake_rollback_task" app/api/v1/knowledge.py | head -3
- data/auto_intake_rollback_*.json (rollback 任务写入)
for rb_path in sorted(rollback_dir.glob("auto_intake_rollback_*.json"), reverse=True):
```

### 7.6 grep 6: KB 闭环 alembic bridge

```bash
$ head -10 alembic/versions/072_kb_closed_loop.py
"""Bridge: 072_kb_closed_loop"""
revision = "072_kb_closed_loop"
down_revision = "071_knowledge_rejected_retry"
branch_labels = None
depends_on = None
def upgrade() -> None: pass
def downgrade() -> None: pass
```

### 7.7 grep 7: alembic 当前 head

```bash
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print('HEADS:', s.get_heads())"
HEADS: ['078_drive_dedupe_audit']
```

✅ **单链 1 head 守恒 (W68 第 8 批 §2.3 串单链纪律)**.

---

## 8. 结论与建议

### 8.1 核心结论

1. **W68 第 14 批 A-3 调研结论仍然有效**, 但 **7 维评分布局** 有差异 (commit `63cdac3bb` 未 merge 进 main)
2. **B-1 必先 verify merge 状态** 再决定补建 scoring/ 目录, 避免重复实施 7 维算法
3. **5 道防线重构 + Celery 形态 rollback + KB 闭环 7 步 audit + Dashboard 4 卡片** 是 W71 主战场
4. **12 agents 派工建议** 落地 (A-1 + B-1/B-2/B-3/B-4/B-5 + C-1/C-2/C-3 + D-1/D-2/D-3)
5. **锚点范式预期 168 → 180 (+12 守恒)** 超过主拍预测 178

### 8.2 主拍决策建议

- **保持选项 A** (5 agents 子 plan ② + 6 agents 派生 + 收尾 = 12 agents)
- **B-1 必先 merge verify `63cdac3bb`** (避免重复实施 7 维算法)
- **AUTO_KB_INTAKE_ENABLED 默认 False 维持** (CLAUDE.md 2026-06-15 教训)
- **派工 v6 第 4 条铁律**: 派工 v8 增量不覆盖 v1-v7
- **派工 v6 段 5 反馈循环**: B-1 24h 内必回收 5 项反馈

### 8.3 失败兜底

- 任一 intake gate 失败 → 关闭 `AUTO_KB_INTAKE_ENABLED`, 走 manual review
- B-1 merge verify 失败 → 立即 merge (无冲突) 或 cherry-pick
- B 路线 5 agents 全部失败 → 接受 docs/CI 占位 (W67 第 47 步铁律)

---

> W71 第 1 批 A-3 调研; 目标锚点范式 **第 194 守恒**.
> 主拍决策依据 [`docs/w71-final-decision-2026-07-24.md`](./w71-final-decision-2026-07-24.md).
> 调研基准 [`docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md`](./w70-w71-plans-backlog-survey-v2-2026-07-24.md).
> 派工纪要 v6 段 5/段 6/段 7.