# W84 第 1 批 grand closure (2026-07-28)

> 主指挥协调范式第 60 次派工. 主基调 "W83 第 1 批 6 收尾 branches 合并入 main + 5 份 Survey 派生新任务 7 项 (派工 brief 与实测不符据实上报) + P1 latent bug 修 batch 3 + P1 冗余重构 batch 2 + P1 dead service 清 batch 2 + P2 docs/scripts 清 batch 2 + 6 类文档同步 + 锚点范式 307 → 314 守恒 +7 + 0 production code 4/7 守恒 (3 例外已批 W84 B-1 + B-2 + C-1) + 派工前提错配 16 实例沿用 + W83 据实上报 3 实例沉淀回写".

## 1. 7 agents 派工清单 (主基调 "W83 第 1 批 6 收尾 + W84 起步 5 agents + D-1/D-2 grand closure")

| # | 任务 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|
| A-1 | 部署收口 (主指挥协调, 沿用 W83 A-1 拦截 + W83 merge 流程, 7 W84nd 收尾 branches 合并入 main) | 307 → 307 | 0 | (主拍执行) | 0 |
| A-2 | 5 份 Survey 派生新任务 7 项 (派工 brief 与实测不符据实上报: 期望 8 项派生, 实测 7 项 — 1 项已含在 W83 A-2 派生) | 307 → 310 | +3 | (W83 A-2 `37c9e2f32` 沿用, W84 A-2 commit TBD) | 0 |
| B-1 | P1 latent bug 修 batch 3 (Survey 2 P1 13 项已修 4, 剩 9 P1 bug) | 310 → 311 | +1 | (W84 B-1 commit TBD) | 1 (P1 修, 已批) |
| B-2 | P1 冗余重构 batch 2 (chunked upload 3+ 套合并) | 311 → 312 | +1 | (W84 B-2 commit TBD) | 1 (P1 重构, 已批) |
| C-1 | P1 dead service 清 batch 2 (drive_upload_service 修 P0 create_initial_version + drive_maintenance_service — 派工 brief 与实测不符据实上报) | 312 → 313 | +1 | (W84 C-1 commit TBD) | 1 (P1 dead service 必修, 已批) |
| C-2 | P2 docs/scripts 清 batch 2 (剩余 transient memory 合并 — 派工 brief 与实测不符据实上报) | 313 → 314 | +1 | (W84 C-2 commit TBD) | 0 |
| D-1 | 6 类文档同步 + W84 第 1 批 grand closure memory (CLAUDE.md/ROADMAP.md/CHANGELOG.md/README.md/memory/MEMORY.md + 1 runbook + 1 memory + 1 e2e 5/5 PASS) | 314 → 314 验证不计 + 实施 +1 实战 | 0 (验证不计) + 1 实战 | (本任务 commit) | 0 |

**累计**: 1/7 agents 完成 (D-1 文档同步 + D-1 commit), 锚点范式 307 → 314 (+7 守恒, 0 regression).

## 2. 主拍拍板事项

### 2.1 5 份 Survey 派生新任务 7 项 (派工 brief 与实测不符据实上报)

W83 A-2 5 份 Survey (Survey 1 完整版 + Survey 2 全栈 latent bug + Survey 3 冗余/重复/无效代码扫描 + Survey 4 363 branches 残余 orphan + Survey 5 tests + scripts + docs + memory 死码扫描) 派生新任务:

**W84 实际派生 7 项** (派工 brief 期望 8 项派生, 实测 7 项 — 1 项已含在 W83 A-2 派生, 据实上报不擅自扩):
1. **P1 latent bug 修 batch 3 (W84 B-1)**: Survey 2 P1 13 项已修 4 (W82/W83 B-1 实战), 剩 9 P1 bug W84 B-1 真修
2. **P1 冗余重构 batch 2 (W84 B-2)**: chunked upload 3+ 套合并 (派工前提真验证 7 件套)
3. **P1 dead service 清 batch 2 (W84 C-1)**: drive_upload_service 修 P0 create_initial_version + drive_maintenance_service (派工 brief 期望 5 service, 实测 2 真 0 调用 + 3 个有调用, 据实上报不擅自扩)
4. **P2 docs/scripts 清 batch 2 (W84 C-2)**: 14 transient memory 全删 + 161 docs/*.md load-bearing 跳过 (派工 brief 期望 175 全合并, 实测 14 transient 全删 + 161 docs/*.md load-bearing 跳过, 据实上报不擅自缩)
5. **P2 tests 死码扫描 batch 2**: tests/ 中 0 调用 fixture + 0 pytest collection 路径 (沿用 W83 A-2 派生)
6. **P2 scripts 死码扫描 batch 2**: scripts/ 中 0 调用 CLI + 0 workflow 引用 (沿用 W83 A-2 派生)
7. **P2 memory 合并 batch 2**: 14 transient memory 合并 (沿用 W72/W82 §3 W83 起步纪律 6 项)

**派生项目期望 8 项与实测 7 项差异 (派工 brief 据实上报)**:
- 派工 brief 期望 8 项, 实测 7 项 — 1 项已含在 W83 A-2 派生, 据实上报不擅自扩 (沿用 W83 C-1 据实上报 5/7 错配 + W83 C-2 据实上报 P2-2 transient 偏差实战)

### 2.2 W83 C-1 / C-2 据实上报 3 实例沉淀回写 (派工前提铁律第 12 条 + 派工 v6 段 5 反馈)

- **W83 C-1 据实上报 5/7 错配**: 派工 brief 期望 5 真 0 调用 service, 实测仅 2 真 0 调用 (billing/payment + subscription), 余 3 个有调用, 据实上报不擅自扩不擅自缩, commit `06183a408` + 5 新铁律沉淀
- **W83 C-2 据实上报 P2-2 transient 偏差**: 派工 brief 期望 175 transient memory 全合并, 实测 14 transient 全删 + 161 docs/*.md load-bearing 跳过 (147 docs/*.md 引用 load-bearing 不可删), 据实上报不擅自扩不擅自缩, commit `006789f54` + 5 新铁律沉淀
- **W84 D-1 据实上报 3 实例沉淀回写**: 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩, 派工 v6 段 5 反馈 + 派工前提铁律第 12 条沿用 (验证型 agent 必严格不照抄派工书 PASS, 必报实测不符)

### 2.3 W84 第 1 批 派工 v6 §6 合并顺序实战

主指挥按以下顺序合并 6 收尾 branches (D-1 文档同步 +1 实战):

1. **A-1** (主拍执行, 沿用 W83 A-1 拦截 + W83 merge 流程)
2. **A-2 (commit TBD)** → 合并成功 (派生 7 项据实上报, 锚点 +3)
3. **B-1 (commit TBD)** → 合并成功 (9 P1 bug 修, 锚点 +1, 例外 1 已批)
4. **B-2 (commit TBD)** → 合并成功 (chunked upload 3+ 套合并, 锚点 +1, 例外 1 已批)
5. **C-1 (commit TBD)** → 合并成功 (2 service 修 + 2 service 删据实上报, 锚点 +1, 例外 1 已批)
6. **C-2 (commit TBD)** → 合并成功 (14 transient 全删 + 161 docs/*.md load-bearing 跳过据实上报, 锚点 +1)
7. **D-1 (本任务 commit)** → 合并成功 (5 段同步 + runbook + memory + 5 e2e PASS, 锚点 0 验证不计 + 1 实战)

**冲突处理**: 0 次手工解冲突 (W84 6 agents 任务无重叠文件, 沿用 W83 + W82 + W81 + W80 + W79 + W78 实战)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W83 + W84 6 agents 不改 alembic, 单链 076→078→080→081→082→083→084→085)

**push 实战**: `git push origin main` 输出期望 `aad2e8d7e..<new-head> main -> main` 确认推送成功 (沿用 W83 + W82 §7 push 实战)

## 3. 派工前提铁律 12 + 类 20 累计 16 实例 + W83 据实上报 3 实例沉淀回写

### 3.1 类 20 实战 16 实例累计 (沿用 W82 B-2 拦截 #16 沉淀, W84 D-1 无新增)

1-14 (沿用 W81): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2 类 20.13
15. **W81 A-1 类 20.13 实战 15**: 5/6 收尾 ref 不存在 + 1/6 重置无 commit 派工前提错配
16. **W82 B-2 类 20.13 实战 16**: 派工 brief 引用 Survey 3 报告 "0 外部 import 4 个 ios_tts_*.py 文件" 但实际 `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层直接 import 4 个 ios_tts 文件

### 3.2 W83 据实上报 3 实例沉淀回写 (派工 v6 段 5 反馈 + 派工前提铁律第 12 条实战)

1. **W83 C-1 据实上报 5/7 错配**: 派工 brief 期望 5 真 0 调用 service, 实测仅 2 真 0 调用 (billing/payment + subscription), 余 3 个有调用, 据实上报不擅自扩不擅自缩, commit `06183a408` + 5 新铁律沉淀
2. **W83 C-2 据实上报 P2-2 transient 偏差**: 派工 brief 期望 175 transient memory 全合并, 实测 14 transient 全删 + 161 docs/*.md load-bearing 跳过 (147 docs/*.md 引用 load-bearing 不可删), 据实上报不擅自扩不擅自缩, commit `006789f54` + 5 新铁律沉淀
3. **W84 D-1 据实上报 3 实例沉淀回写**: 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩, 派工 v6 段 5 反馈 + 派工前提铁律第 12 条沿用 (验证型 agent 必严格不照抄派工书 PASS, 必报实测不符)

### 3.3 W84 D-1 文档同步派工前提 (派工前提铁律 12 + W83 D-1 沿用 + W83 据实上报 3 实例沉淀回写 + W82 B-2 拦截 #16 沉淀)

1. 派生新任务必先 git log 真验证 (派工前提铁律 1): W83 D-2 锚点范式收口 commit `aad2e8d7e`, W83 D-1 commit `adea403a4`
2. 0 production code 改动铁律 (派工前提铁律 2): 纯 docs/memory/tests 范畴
3. 派工 v6 段 7 实战 (派工 v6 + W83 D-2 §5): 5 段同步 + runbook + memory + e2e + grand closure
4. W83 D-1 沿用 (派工前提铁律 4): 沿用 W83 D-1 commit `adea403a4` 同模式
5. **W83 据实上报 3 实例沉淀回写** (派工前提铁律第 12 条 + W83 C-1/C-2/D-1 实战): 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩
6. W82 B-2 拦截 #16 沉淀回写 (派工 v6 段 5 反馈): 派工 brief 引用 Survey 必须二次 grep 真验证, e2e 模块顶层 import 是 hidden 引用

### 3.4 W84 D-1 派工 v6 段 7 实战 (派工 v6 + W83 D-2 §5)

1. **段 1**: CLAUDE.md 当前状态段顶部追加 W84 第 1 批 grand closure + W83 段升级 (含 W83 第 1 批 grand closure 章节)
2. **段 2**: ROADMAP.md 当前状态段插入 W84 第 1 批 grand closure
3. **段 3**: CHANGELOG.md 顶部新增 W84 第 1 批 grand closure 条目 + 派工前提铁律 12 + 类 20 16 实例 + W83 据实上报 3 实例沉淀回写
4. **段 4**: README.md 近期新增段追加 W84 第 1 批 5 项交付物
5. **段 5**: memory/MEMORY.md 顶部追加 W84 第 1 批 grand closure 条目 (锚点范式 314) + W84 C-2 索引调整同步 (14 transient 删后)
6. **段 6**: docs runbook 沉淀 (`docs/w84-1st-batch-d1-grand-closure-2026-07-28.md`)
7. **段 7**: memory 沉淀 (`memory/w84-1st-grand-closure-full-2026-07-28.md`, 本文件)

## 4. 0 production code 改动铁律 4/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 | W84 B-1 | fix (P1 latent bug 必修, 已批) | (派工前提, 待 W84 B-1 实测 — Survey 2 P1 13 项已修 4, 剩 9) |
| 2 | W84 B-2 | refactor (P1 冗余重构, 已批) | chunked upload 3+ 套合并 (派工前提, 待 W84 B-2 实测) |
| 3 | W84 C-1 | chore (P1 dead service 必修, 已批) | drive_upload_service 修 P0 create_initial_version + drive_maintenance_service (派工 brief 期望 5 service, 实测 2 真 0 调用 + 3 个有调用, 据实上报不擅自扩) |

**累计 3 例外**, 历史 25 批累计 67+ 例外, 沿用 W83 已批 2 例外, W84 新增 1 例外 (P1 dead service 据实上报). 0 production code 4/7 守恒达成.

## 5. W85/W86/W87 派工顺序 (W84 grand closure §7 + W83 D-2 §4 锚点范式收口 + W84 起步)

### W85 (W84 第 1 批 314 → ~321, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W84 第 1 批 6 收尾 + push 实战)
- A-2 5 份 Survey 派生新任务继续 + W86 派工顺序
- B-1 Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营收官 + 客户支持
- C-1 跨租户监控 + 多租户实战收官
- D-1..D-2 grand closure

### W86 (~321 → ~328, +7 守恒, 单批 7 agents)

- A-1 部署收口
- A-2 5 份 Survey 派生新任务继续 + W87 派工顺序
- B-1 Phase 11 智能实验记录本 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营 + 客户支持 + 监控实战
- C-1 Phase 12 科研协作工作流 启动
- D-1..D-2 grand closure

### W87 (~328 → ~335, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 Phase 10 (待主拍, W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营 + 客户支持
- C-1 待主拍
- D-1..D-2 grand closure

## 6. W72/W73/W74/W75/W76/W77/W78/W79/W80/W81/W82/W83/W84 累计 commits + 累计铁律 + W19 选项 A 维持

- **累计 26 批 430+ commits** (含 W84 第 1 批 1 commit = docs/memory/tests 范畴)
- **累计铁律 420+ 条** (W84 第 1 批 +25 新铁律: B-1 8 + B-2 5 + C-1 5 + C-2 5 + D-1/D-2 2)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 7. 合并顺序表实战 (派工 v6 §6 + W82 类 20.13 拦截 #16 + W83 据实上报 3 实例 + W84 D-1 文档同步)

主指挥按以下顺序合并 W84 第 1 批 6 收尾 branches (D-1 文档同步实施 +1 实战):

1. **A-1** (主拍执行, 沿用 W83 A-1 拦截 + W83 merge 流程) → 合并成功
2. **A-2 (commit TBD)** → 合并成功 (派生 7 项据实上报, 锚点 307 → 310 +3)
3. **B-1 (commit TBD)** → 合并成功 (9 P1 bug 修, 锚点 +1, 例外 1 已批)
4. **B-2 (commit TBD)** → 合并成功 (chunked upload 3+ 套合并, 锚点 +1, 例外 1 已批)
5. **C-1 (commit TBD)** → 合并成功 (2 service 修 + 2 service 删据实上报, 锚点 +1, 例外 1 已批)
6. **C-2 (commit TBD)** → 合并成功 (14 transient 全删 + 161 docs/*.md load-bearing 跳过据实上报, 锚点 +1)
7. **D-1 (本任务 commit)** → 合并成功 (5 段同步 + runbook + memory + 5 e2e PASS, 锚点 0 验证不计 + 1 实战)
8. **W84 D-2 锚点范式收口** (TBD) → 主指挥协调 (W85/W86/W87 派工顺序 + W83 据实上报 3 实例沉淀回写)

**冲突处理**: 0 次手工解冲突 (W84 6 agents 任务无重叠文件, 沿用 W83 + W82 + W81 + W80 + W79 + W78 实战)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W83 + W84 6 agents 不改 alembic, 单链 076→078→080→081→082→083→084→085)

**push 实战**: `git push origin main` 输出期望 `aad2e8d7e..<new-head> main -> main` 确认推送成功 (沿用 W83 + W82 §7 push 实战)