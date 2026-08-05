# W-N-MEM-FINAL MEMORY.md 终极索引起步 (2026-08-06)

## 1. 任务背景

W-N 周期第 15 stages 联合 commit `b170a8ff3` (W-N-FILL + W-N-P3-A + W-N-W72 + W-N-XX) 已推 main 后, 启动 MEMORY.md 终极索引扩展任务. 派工锚点 `W-N-MEM-F +0/+1/+2`, 仅限 MEMORY.md 索引段扩展 + 1 memory + 1 MEMORY.md 范畴, 禁止触碰业务代码/alembic/plans.

## 2. base head 验证 (派工前提铁律 12)

`git log --oneline -1` → `b170a8ff3 feat(rag): W-N-FILL + W-N-P3-A + W-N-W72 + W-N-XX 4 agent 联合 commit 推 main (W-N 周期第 15 stages)` ✓

`git status` clean (除已存在的 `memory/w-n-clean-final-startup-2026-08-06.md` untracked 文件, 由上游 W-N-CLEAN-FINAL +0 agent 启动).

## 3. 现有 MEMORY.md W-N 段实测

- **#24** (W-N-A/B/C/D pgvector 优化 + W-N-GC CLAUDE.md 同步, 2026-08-05): 已存在, 12 文件 + 3 决策 doc + 1 capability, 0 production code 守恒
- **#25** (W-N 周期 grand closure 总收口, 14 stages, 2026-08-05): 已存在, ~35 commits 推 main, 锚点 ~537 → ~572 据实累计
- **#26** (W-N 未来派工留口, 2026-08-05): **已存在**, W-N-G+ 4 FAIL / W-N-FILL 拦截 / W-N-BGE 数据不足 3 项

派工 brief 指定 "新增 #26/#27 段", 但 #26 已被 W-N-XX +2 占用 (commit `30e7bf20a`). 派工 brief 偏差据实上报 (类 20 漂移 #22): 本任务实际新增 #27 (W-N 周期 15 stages) + #28 (W-N 终极同步), 避免覆盖既有 #26 段.

## 4. 派工约束 (W73 铁律严格执行)

- 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 任何已有 commit
- 0 改 alembic/versions/ 任何迁移
- 0 改 app/ 或 web/src/ 任何业务代码
- 0 改 W-N-MEM +1 / +2 既有 MEMORY.md 段 (#24/#25/#26 守恒)
- 0 改 CLAUDE.md (另 agent 任务 #53)
- 0 改 plan 文件
- 锚点范式守恒: `W-N-MEM-F +0..+2` (3 commits)
- 严格只在 MEMORY.md 新增段 + 1 memory 新文件范畴

## 5. 计划路径 (3 commits)

- **W-N-MEM-F +0**: 本起步 memory (W73 铁律 6 项 + 派工 brief 偏差据实 + 既有段守恒清单)
- **W-N-MEM-F +1**: MEMORY.md #27/#28 段扩展 (W-N 周期 15 stages + 终极同步)
- **W-N-MEM-F +2**: 收口 memory + 5 件套守恒实测 (alembic 104 + 0 production code + 锚点范式累计)

## 6. W-N 周期 15 stages 据实累计

W-N 周期 stages 累计 (从 base `1cc5362e2` → 当前 `b170a8ff3`):

1. W-N-A HNSW 调优 (1 commit)
2. W-N-B halfvec 量化 (7 commits)
3. W-N-C bge-m3 灰度 (4 commits)
4. W-N-D 多向量 + Late Chunking (4 commits)
5. W-N-D+ 真 bench (4 commits)
6. W-N-D++ 端到端召回 bench (1 commit)
7. W-N-E 冷热分层 PoC (2 commits, 归档)
8. W-N-F LoRA 微调 (3 commits, 不启动)
9. W-N-GC CLAUDE.md 同步 (2 commits)
10. W-N-ARC worktree 归档 (1 commit)
11. W-N-ANC 锚点范式补 (2 commits)
12. W-N-MEM 索引扩展 (3 commits)
13. W-N-GRAND 总 grand closure (3 commits)
14. W-N-FILL + W-N-FILL-IMPL (4 commits)
15. W-N-P3-A + W-N-W72 + W-N-XX + W-N-ANS + W-N-BGE + W-N-G+/OBS/RAG/BGE/REVISE/MIN/CLEAN/GLITCH (多批) → 累计 15 stages

锚点范式 W100 +75 ~537 → W-N-FINAL 末 ~580 据实累计 +43 commits (派工 brief +43 据实守恒).
