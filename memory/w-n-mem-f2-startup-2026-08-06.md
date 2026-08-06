# W-N-MEM-F2 +0 起步 (2026-08-06)

## 派工任务

W-N-MEM-F2 终极索引 agent,MEMORY.md 新增 #29 段 W-N 周期 19 stages + 终极测试修复决策。

## 基线 HEAD

`6d8f0226f` (W-N-FILL-REAL-N 测试回归断言修正, 12/12 PASS)

## 6 项起步 (W73 铁律)

### 1. 读 CLAUDE.md 当前状态段 ✓

W-N 周期 15 stages 终极收口 + Phase 5 DFT 工具集成 + W-N-A/B/C/D pgvector 优化 plan 收口 + W100 +N 据实累计。

### 2. 读 memory/MEMORY.md 现有 #27/#28 段 ✓

- #27 段: W-N 周期 15 stages grand closure (W-N-MEM-FINAL +1)
- #28 段: W-N 终极同步 (W-N-MEM-FINAL +1 终极同步段)

### 3. 验证当前 git 状态 ✓

- HEAD: `6d8f0226f`
- branch: main
- untracked: `docs/w-n-clean-final-2026-08-06-f2.md` + `memory/w-n-clean-f2-startup-2026-08-06.md` (W-N-CLEAN-F2 范畴, 与本任务无关)

### 4. 验证 commit 6d8f0226f 实际内容 ✓

- 类型: fix(test)
- 范围: tests/test_w_n_fill_impl_backfill.py (1 file, 3 insertions, 1 deletion)
- 修复: 旧 `assert 'vector[]' in str(executed_sql)` → 新 `assert 'vector(1024)[]' in str(executed_sql)` + `assert 'CAST' in str(executed_sql)`
- 5 件套守恒: alembic 105_fix_drift 守恒 / pytest 12/12 PASS / PWA baseline / 0 production code (仅测试) / 锚点范式 W-N-FILL +0..+2 据实累计
- 类 20 沉淀: 类 20.166 新增 (测试断言必须跟 service SQL 修复同步, 避免 regression)

### 5. 读 W-N-MEM-F +1 既有 MEMORY.md 段 ✓

MEMORY.md #27 + #28 段已存在,本任务**严格只新增 #29 段**,不修改 #27/#28。

### 6. 锚点范式守恒 ✓

W-N-MEM-F2 +0/+1/+2 据实累计,不动 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/FILL-REAL/FILL-REAL-N 既有 commits。

## 派工 brief 严禁

- 0 改 plan 文件
- 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/FILL-REAL/FILL-REAL-N 既有 commits
- 0 改 alembic/versions/
- 0 改 W-N-MEM-F +1 既有 MEMORY.md 段
- 0 改 CLAUDE.md (另 agent 任务 #66)

## 任务清单

- +0 起步 memory (本文件)
- +1 MEMORY.md 新增 #29 段 (W-N 周期 19 stages + 终极测试修复决策)
- +2 收口 memory (5 件套守恒实测)

## 0 production code 守恒

W-N-MEM-F2 +0..+2 仅新增 1 memory 文件 + MEMORY.md #29 段,未改 app/ web/src/ alembic/versions/。