# W71 第 1 批 A-3 — W71 启动前 Plans 真验证 (派工 v4 铁律 3 实战)

> W71 第 1 批 A-3 调研沉淀, 2026-07-27
> 范围: 只做 plans/docs/memory 调研, 不实施 production code.
> 锚点范式: **第 194 守恒**.

## 核心成果

W71 启动前真验证报告 `docs/w71-startup-plans-verification-2026-07-24.md` (~340 行, 锚点范式第 194 守恒), 必含 6 段:
1. TL;DR — 5 项 plan 中未完成内容清单 + 6 项派生新任务清单
2. W71 派工 5 agents 真验证表 (B-1/B-2/B-3/B-4/B-5) — plan body 描述 / 真验证命令 / 当前状态 / 缺口 / 优先级
3. W71 启动前 4 grep 真验证 (W68 第 14 批 A-3 4 步实战) — 修前调研基准 vs 修后当前 HEAD 差异
4. plan 中未完成内容清单 — 7 维评分 / 5 道防线 / Celery auto_intake_rollback / KB 闭环 / Dashboard
5. 派生新任务清单 (C 路线 3 + D 路线 3)
6. W71 batch 15 agents 派工建议表 — 12 agents 实际 + 5 条派工纪律 + 锚点范式预期

## 7 grep 真验证命令输出摘要

| # | 命令 | 输出关键发现 |
|---|------|--------------|
| 1 | `cat /c/Users/pc/.claude/plans/chatgpt-structured-floyd.md` | 子 plan ② 状态: PARTIAL_REGRESSION 1/3 完成, ②③ 留 W69 |
| 2 | `git log --oneline origin/main \| grep -iE "qa-bench\|chatgpt\|save_to_kb\|rollback"` | 10 commits, 含 `1f3c210e0` W68 第 14 批 C-1 + `539b3832e` notify v2 + `4c7816c1e` D7 gate |
| 3 | `grep -rE "scoring\|seven_dim\|7 维" tests/qa-bench/` | HEAD `0ae74f477` **无 scoring/ 目录**; commit `63cdac3bb` 仅在分支 `feat/w68-10th-batch-b1-7d-scoring-2026-07-24`, 未 merge 进 main |
| 4 | `grep -E "DEFAULT_MIN_SCORE\|DEFAULT_MIN_CONTENT\|DEFAULT_ALLOWED\|AUTO_KB\|GRAYSCALE" save_to_kb.py` | save_to_kb.py 398 行含 5 道防线 (分数 4 / 内容 200 / 意图白名单 / 灰度开关 / 7d rollback), 5 道防线**单文件实现**, 无独立 `kb_queue/` 模块 |
| 5 | `find app/ -name "qa_bench_tasks*"` + `ls scripts/auto_intake_rollback.py` | `app/services/qa_bench_tasks.py` 不存在; 仅有 `scripts/auto_intake_rollback.py` 119 行 CLI 工具; `app/api/v1/knowledge.py` 监控 rollback JSON |
| 6 | `head alembic/versions/072_kb_closed_loop.py` | alembic 072/073 是 bridge 占位 (pass), 无实质 schema 改动 |
| 7 | `python -c "ScriptDirectory.from_config(c).get_heads()"` | **HEADS: ['078_drive_dedupe_audit']** ✅ 单链 1 head 守恒 (W68 第 8 批 §2.3 串单链) |

## 5 plan 中未完成内容清单

| B agent | plan § | 缺口 (优先级 P0/P1) |
|---------|--------|---------------------|
| **B-1 7 维评分** | chatgpt-structured-floyd.md §3.1-3.2 | ① `63cdac3bb` merge verify (P0) ② 路径改名 seven_d → seven_dim ③ weights.json 独立 ④ 11 单测 ⑤ 7 维基线复跑 (P0) |
| **B-2 5 道防线** | §3.5 | ① 重构 5 道防线为独立 kb_queue/ 模块 ② LLM 拒答检测 ③ 敏感词独立防线 ④ admin 抽检队列 ⑤ 5 道防线矩阵负测 (P0) |
| **B-3 Celery auto_intake_rollback** | §3.5 | ① 新建 `app/services/qa_bench_tasks.py` ② Celery beat 注册 ③ 幂等键 + 时区 ④ 告警阈值 ⑤ worker 运行证据 (P0) |
| **B-4 KB 闭环端到端** | §3.5 | ① 防线逐项 audit log ② 24h/7d review scheduler ③ 接入 B-3 ④ 负反馈暂停机制 ⑤ 灰度 UI (P0) |
| **B-5 Dashboard + CI smoke** | §3.4 | ① QaBenchDashboard.vue 4 el-card ② useQaBenchPolling 5min ③ 7 天统计 ④ 待抽检 UI ⑤ 告警详情 dialog (P1) |

## 6 派生新任务清单

| 路线 | 任务 | 来源 | 优先级 |
|------|------|------|--------|
| **C-1** D8 后续实施 | 题库版本锁定 + 数据脱敏 + 模型锁定 | `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` | P1 |
| **C-2** SubAgent 编排设计 | worktree + branch + 派工 prompt 模板 | 派工 v6 段 5 反馈循环 | P2 |
| **C-3** notify v2 仓库模板回测 | git submodule / npm / Docker 3 载体实测 | W68 第 14 批 B-4 | P2 |
| **D-1** 派工 v8 | v6 段 5/段 6 + 段 7 派工前提错误复盘 + 段 8 5 道防线矩阵 | 派工 v6 第 4 条铁律 | P1 |
| **D-2** 6 类文档同步 | CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md + 用户级 1 | W68 第 14 批 D-2 沉淀 | P1 |
| **D-3** 锚点范式守恒验证 | 168 → 180 (+12 守恒) | W68 第 13 批 168 → W71 选项 A 178 | P1 |

## 12 agents 派工顺序

| 顺序 | 路线 | agent | 必含纪律 |
|------|------|-------|---------|
| 1 | A | A-1 主拍 (Redis/DB 依赖 + W71 启动) | 派工 v6 段 5 反馈 + 段 6 顺序表 |
| 2 | B | B-1 (7 维评分 verify + 路径改名 + weights.json) | 派工 v4 铁律 3 真验证 |
| 3 | B | B-2 (5 道防线重构 + kb_queue/ 模块) | 5 道防线矩阵负测 |
| 4 | B | B-3 (Celery auto_intake_rollback_task) | alembic 串单链 + 派工 v6 段 6 顺序表 |
| 5 | B | B-4 (KB 闭环端到端 7 步 audit) | 接入 B-3 + 灰度 UI |
| 6 | B | B-5 (QaBenchDashboard.vue 4 el-card) | npm run build + dist force-add |
| 7 | C | C-1 (D8 实施) | 调研类, 不实施 code |
| 8 | C | C-2 (SubAgent 编排设计) | 调研类 |
| 9 | C | C-3 (notify v2 仓库模板回测) | 调研类 |
| 10 | D | D-1 (派工 v8) | 派工 v6 第 4 条铁律 |
| 11 | D | D-2 (6 类文档同步) | 派工 v6 段 6 合并顺序表 |
| 12 | D | D-3 (锚点范式守恒) | 168 → 180 (+12 守恒) |

## 关键发现 (派工 v4 铁律 3 实战沉淀)

1. **commit `63cdac3bb` 未 merge 进 main** — `feat/w68-10th-batch-b1-7d-scoring-2026-07-24` 分支独有 scoring/ 目录 (450 + 146 + 376 行), merge 状态待主指挥 verify. W71 B-1 必先 verify 再决定补建, 避免重复实施 7 维算法
2. **5 道防线单文件实现** — `save_to_kb.py` 398 行含 5 道防线, 但缺独立 `tests/qa-bench/kb_queue/` 模块 (dedup.py + llm_refusal.py + sensitive_word.py + human_review.py)
3. **Celery rollback 缺形态** — 仅有 `scripts/auto_intake_rollback.py` 119 行 CLI 工具, 无 `app/services/qa_bench_tasks.py:auto_intake_rollback_task`
4. **alembic 单链守恒** — HEADS: ['078_drive_dedupe_audit'], W68 第 8 批 §2.3 串单链纪律 0 双头
5. **派生 12 agents 派工顺序** — A-1 + B-1/B-2/B-3/B-4/B-5 + C-1/C-2/C-3 + D-1/D-2/D-3 = 12 agents (超出主拍预测 5 agents, 含派生 6 + 收尾 3 + A-1 主拍)
6. **锚点范式预期 168 → 180** (+12 守恒, 超出主拍预测 178)

## 派工 v6 段 7 派工前提错误复盘 (本次实战新增)

| 教训 | 派工前必做 |
|------|----------|
| B-1 7 维评分 merge 状态盲信 | 派工前必跑 `git log --all --merges --grep "63cdac3bb"` verify |
| 调研基准 HEAD 与实际 HEAD 不一致 | 调研必先 verify HEAD + 调研基准 = `9b7c0e8a9` vs 当前 HEAD `0ae74f477` |
| 5 道防线"已实施"盲信 | 派工前必跑 `grep -rE "kb_queue\|dedup" tests/qa-bench/` verify 独立模块 |
| Celery task "已实施"盲信 | 派工前必跑 `find app/ -name "qa_bench_tasks*"` verify |
| alembic 多 head 风险 | 派工前必跑 `python -c "ScriptDirectory.from_config(c).get_heads()"` verify 1 head |

## 铁律 (派工纪要 v6 段 5 实战)

1. **必先 commit partial diff** — B-3 教训 ✅ 本次工作区为空, 无需 partial commit
2. **不动 v1-v6 历史约束** (派工 v6 第 4 条铁律) ✅ 本次仅新增 docs + memory, 不改 v1-v6 历史
3. **7 grep 真验证必全跑** (派工 v4 铁律 3 实战) ✅ 7 个 grep 命令全跑 + 输出摘要沉淀
4. **不动 production code** (调研类任务) ✅ 仅 docs + memory
5. **1 commit + defer message** ✅ 下一步 commit

## 下一步

- 1 commit + push `docs/w71-startup-plans-verification-2026-07-24.md` + `memory/w71-route-71st-batch-a3-plans-verify-2026-07-24.md`
- 主指挥 review + 拍板 W71 选项 A 12 agents 派工顺序
- B-1 启动前必先 verify `63cdac3bb` merge 状态