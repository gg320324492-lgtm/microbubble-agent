# qa-bench 里程碑 (Milestones)

> **当前版本**: v3.1 (部分完成, D7+D8 文档交付 2026-07-22)
> **配套**: [GUIDE.md](./GUIDE.md) + [results/REPORT_TEMPLATE.md](./results/REPORT_TEMPLATE.md)
> **决策依据**: `C:/Users/pc/.claude/plans/qa-bench-v3.1-decisions.md`

---

## v3.0 (2026-06-30 收官)

**Commit**: W6 T6.5 final_delivery_report + regression_baseline_v3.0.json lock

### 6 周冲刺成果
- 题库: 360 → 535 题 (+49%, W1 700 + W2 229 手工 + 107 DB 抽真实)
- 评分: 单一 pass/fail → 7 维加权 + 一票否决
- 检测器: 7 → 10 个 (新增 stream_interrupt / tool_error_propagated / first_token_latency 3 个 P0)
- Dashboard MVP + GitHub Actions CI smoke 200 题
- 全自动 KB 入库 5 道防线 + 7 天 rollback
- W3 真实发现 Self-RAG #009 生产 bug (避免 200h 修复成本)

### 周总结
- W1: 题库 700 + 1 detector
- W2: 合并 535 题 + 抽样复核
- W3: 真实发现生产 bug (Self-RAG gate parse-fail)
- W4: 3-tier 阈值 + 性能基线
- W5: 5 防线入库 + 一致性 0% 测出
- W6: 雷达图 + 趋势 + 决策项清单 (D1-D8)

### 关键 memory 文件
- `qa-bench-v3-w1-2026-06-30.md` ~ `qa-bench-v3-w6-2026-06-30.md` (6 memory)
- `qa-bench-smart-filter-round9-2026-07-02.md`
- `qa-bench-smoke-30-2026-07-02.md`

---

## v3.1 目标 (2026-07-22 部分完成)

8 项决策 (D1-D8) 当前完成情况:

| # | 决策 | 状态 | commit/单 test |
|---|---|---|---|
| D1 | LLM 稳定性 (TEMPERATURE/rounds/verdict-consensus) | ✅ agent4 已交付 | runner.py +158/-7 |
| D2 | 全自动 KB 灰度 | ✅ 部分 | save_to_kb.py 已有 AUTO_KB_INTAKE |
| D3 | Retrieval cache + high-conf skip | ✅ agent5 已交付 | retrieval_cache.py + tests 9/9 |
| D4 | 题库 1000+ | ✅ 已交付 | questions_d4_extra_300.jsonl (+300 题, 700→1000) |
| D5 | Dashboard KB 监控 | ✅ 之前已交付 | useKbMonitor.js |
| D6 | 阈值 80% 门禁 | ✅ agent6 已交付 | workflow + --smoke flag |
| **D7** | **文档交付 (GUIDE)** | **✅ agent7 已交付** | **GUIDE.md 316 行** |
| **D8** | **里程碑文档** | **✅ agent7 已交付** | **MILESTONES.md (本文件)** |

### 本批交付 (D7+D8)
- `tests/qa-bench/GUIDE.md` (316 行, 用户指南)
- `tests/qa-bench/results/REPORT_TEMPLATE.md` (报告模板 — 含 7 维评分章节)
- `tests/qa-bench/MILESTONES.md` (本文件)

### 验收 DoD
- [x] GUIDE.md 包含 `python tests/qa-bench/runner.py --help` 输出引用 (5 处)
- [x] REPORT_TEMPLATE.md 包含 7 维评分章节
- [x] MILESTONES.md 包含 v3.0 / v3.1 / v4.0 3 个版本标题
- [x] 引用锚点可达 (相对路径 + 绝对路径混合)
- [x] 0 production code / test / config 改动 (纯文档)

### D4 题库 1000+ 扩展 (2026-07-22 已交付)

- **新增题库**: `tests/qa-bench/questions_d4_extra_300.jsonl` (+300 题, 700 → **1000** 题)
- **类别分布 manifest**: `tests/qa-bench/questions_d4_categories.json` (14 类别 + 难度矩阵)
- **runner.py 改造**: `--include-extra` flag + `QA_BENCH_EXTRA_DATASET` env var (default `questions_d4_extra_300.jsonl`)
  - `python runner.py --include-extra` → 合并 780 + 300, 打印 `700 + 300 = 1000 题`
- **14 类别** (按 questions_780.jsonl 业务比例扩展): A 成员 32 / B 任务 32 / C 会议 32 / D 项目 18 / E 知识 19 / F 公式 13 / G 假设 13 / H 记忆 19 / K 横切 19 / M 多轮 19 / P 高级 38 / U 闲聊 10 / X 跨域 10 / Z 极端 26 (Z1/Z2/Z3/Z4 子类)
- **难度矩阵**: L1 23.3% / L2 40.7% / L3 28.3% / L4 7.7% (对齐 L1 20% / L2 40% / L3 30% / L4 10% 目标)
- **schema 100% 兼容**: 19 字段与 questions_780.jsonl 完全一致
- **验收 DoD**:
  - [x] `wc -l questions_d4_extra_300.jsonl` = 300
  - [x] 合并总题数 = 1000 (≥ 1000)
  - [x] `--include-extra` flag 生效 + 打印 "X + Y = Z 题"
  - [x] `test_qa_bench_runner_smart_filter.py` 14/14 PASS (0 回归)
  - [x] 不破坏 `--smoke` / `--limit` 现有行为

---

## v4.0 目标 (未来, 1-2 年视角)

### 候选方向 (3 选 1-2)
1. **智能 regression** — 自动检测 baseline 抖动 + 给出修复建议
2. **auto-fix suggestion** — 失败题自动归类 + 提 PR 建议 (改 KB / 改 routing / 改 prompt)
3. **题库自动去重 + 冲突检测** — 重复题跨 commit 自动合并
4. **跨项目通用 qa-bench 模板** — 其他研究组复用本套体系

### 触发条件
- D1-D8 全部 100% 收官 (D7+D8 已交付 ✅)
- v3.1 完成 v3.2 立项
- 用户需求冒出新场景 (如 Agent-as-Judge / multi-agent eval)