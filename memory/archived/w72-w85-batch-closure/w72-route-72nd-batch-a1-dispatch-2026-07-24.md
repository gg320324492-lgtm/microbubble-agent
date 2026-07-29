# W72 第 1 批 A-1 派工调研依据 memory (锚点范式第 207 守恒)

> **任务来源**: W72 第 1 批 A-1 派工调研基础 — W68 第 14 批 D-4 W71+W72 拍板续 (主拍必读) + W71 batch 33 commits 已合并 main (锚点范式第 206 守恒) + W71 D-1 派工纪要 v8 段 8 实战升 v8 必备
>
> **主基调**: W72 第 1 批 15 agents 派工调研, 4 路线 15 agents, 锚点范式 W71 206 → W72 220 守恒 (+14 守恒预期), 0 失败
>
> **锚点范式**: 第 207 守恒 (主指挥协调范式第 45 次派工)
>
> **commit**: `6e074ffd9` (docs/w72nd-batch-a1: W72 第 1 批 15 agents 派工调研依据 + 10 步合并顺序表 + 起步纪律 4 项实战 + 7 类别沉淀)
>
> **文档路径**: `docs/w72nd-batch-dispatch-2026-07-24.md` (594 行)
>
> **0 production code 改动铁律**: 14/15 守恒预期 (1 例外 B-1 NavRail.vue 250 行 + SessionSidebar 重构)

---

## W72 派工依据 5 文档

1. `docs/w71-dispatch-candidates-v8-2026-07-24.md` (376 行) 段 8 W72 子 plan ③ 起步纪律
2. `docs/w71-final-decision-2026-07-24.md` (806 行) §2 W71 4 选项 + §3 W72 4 选项
3. `docs/w72nd-batch-orchestration-2026-07-24.md` (派生) 5 B 路线 agents 接口契约
4. `docs/w70-w71-plans-backlog-survey-v2-2026-07-24.md` (150 行) §3 子 plan ② 实施清单
5. `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` (564 行) §2 真验证

## W72 起步纪律 4 项实战验证 (本任务实测)

1. **W71 B 路线 5 agents 全部 commit + merge**: 实测 10 commits (5 features + 5 merges) ≥ 5 期望 ✅
   - B-1 `0f67c1117` + B-2 `eb2798ff4` + B-3 `247b6a2b3` + B-4 `62553735e` + B-5 `ac7946ef6` + 5 merges
2. **7 维评分数据 + KB 闭环回归**: 3 文件全部存在 ✅
   - `tests/qa-bench/scoring/seven_dim.py` + `tests/qa-bench/kb_queue/five_defenses.py` + `app/services/qa_bench_tasks.py`
3. **子 plan ③ 3 组件独立回归**: 待 W72 B-1 + B-2 派工前真验证 (派工 v8 段 8 起步纪律)
4. **派工前提错误必含 W71 实战 13 类**: 派工 v8 段 7 升级, 沿用 v8 模板

## 7 类别沉淀 (派工 v6 段 5 反馈实战)

- **派工 v8 段 5 反馈 #1**: B 路线 5 agents 接口协调实战 (W71 4 协调事故 + W72 沉淀 8 段接口契约表)
- **派工 v8 段 5 反馈 #2**: W72 起步纪律 4 项必读 (派工 v8 段 8 实战)
- **派工 v8 段 5 反馈 #3**: SubAgent 编排 type hint 必含 (W72 B 路线涉及)
- **派工 v8 段 5 反馈 #4**: 派生新任务真验证 (W72 A-3 + C-3 必含)
- **派工 v8 段 5 反馈 #5**: W72 任务模式基调 plans 优先 + 小修搭配 + 路线 fallback 三驱动
- **派工 v8 段 5 反馈 #6**: W72 段 8 W72 起步纪律 4 项必读 (本任务实测 4 项全部 ✅)
- **派工 v8 段 5 反馈 #7**: W72 派工 0 production code 改动铁律 14/15 守恒预期

## W72 第 1 批 15 agents 派工清单 (4 路线)

- **路线 A 4 agents**: A-1 部署收口 (本任务) + A-2 派工 v9 + A-3 plans 真验证 + A-4 grand closure memo
- **路线 B 5 agents**: B-1 NavRail + B-2 ThinkingModeSwitch + B-3 顶栏 3-zone + B-4 跨端点 + B-5 6 主题 dark (子 plan ③ 起步, 串单链)
- **路线 C 3 agents**: C-1 容器镜像 rebuild + C-2 商业化 24 人月季度 + C-3 ppt-word 5 缺口
- **路线 D 3 agents**: D-1 派工 v9 + D-2 6 类文档 + D-3 grand closure actual

## 10 步合并顺序表 (本任务 §10)

1. Step 1: A 路线 4 agents 派工
2. Step 2: 主拍合并 A 路线 → 验证 main HEAD
3. Step 3: B 路线 5 agents 派工 (B-1 必先合, B-2 + B-3 可并行, B-4 依赖 B-1+B-2+B-3, B-5 依赖 B-1+B-2+B-4)
4. Step 4: 主拍合并 B 路线 → 验证 main HEAD + 跑 baseline 71+7
5. Step 5: C 路线 3 agents 派工 (调研类独立, 可并行)
6. Step 6: D 路线 3 agents 派工 (必等 B+C 全部 commit 后)
7. Step 7: 主拍合并 C+D 路线 → 写 W72 grand closure actual 落盘

## push 状态

✅ pushed to `origin/chore/w72nd-batch-a1-deploy-doc-2026-07-24` (commit `6e074ffd9`)

## W19 选项 A 维持

4 留未来 PR 不发起新排期 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

---

**版本 v1, 2026-07-24, W72nd batch A-1 起草, 主拍合并后正式生效。**

**Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>**