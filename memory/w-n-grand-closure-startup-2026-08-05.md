# W-N-GRAND grand closure 起步 (2026-08-05)

## 1. 派工 brief 锚定 (W73 铁律)

- 任务 ID: W-N-GRAND 总 grand closure
- 锚点范式: W-N-GRAND +0..+2
- 当前 main HEAD: `1cc5362e2` (feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档)
- 当前 alembic head: `104_add_knowledge_chunk_late_embedding` (派工 brief 估 105 偏差据实, +1 实际为 104)
- DB schema: code head 104 vs DB alembic_version 099 (drift 待 W-N-G+ 修)
- 0 production code 改动铁律: 仅 `docs/w-n-grand-closure-runbook.md` + `memory/MEMORY.md` #25 段 + `CLAUDE.md` 顶部新段 + 2 份 memory 文件范畴

## 2. 派工起点必 fetch (类 20.131 沿用)

派工 brief: "W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/D++ 已经 8 phase agents 完成"
- 已实测 git log origin/main -50: W-N-A 1 cherry-pick + W-N-B 7 + W-N-C 4 + W-N-D 5 + W-N-D+ 4 + W-N-D++ 1 + W-N-E 2 + W-N-F 3 + W-N-GC 2 + W-N-ARC 1 + W-N-ANC 2 + W-N-MEM 3 = **35 commits 据实累计** (派工 brief 估 ~30 偏差据实 +5)
- W-N-D +3 DFT 集成 (`5c609663b` `a528fab7d` `ef44aa929`) 是 DFT agent 用了 W-N-D +1/+2/+3 锚点 (类 20.172 实战), 与 W-N-D 原本 +1/+2 DFT-集成重叠, **桥下不算 W-N-D**

## 3. W-N-G+/OBS/RAG/BGE/FILL 5 阶段派工据实实测 (派工 v6 §13 仓库实情真查)

派工 brief 假设: "5 阶段正在并行跑 (本任务最后一跑)"
- 实测 main git log: **0 commits 推 main** (W-N-G+ / OBS / RAG / BGE / FILL 全部)
- 实测 memory 文件: **3 个 startup 文件存在但未合入 main**:
  - `memory/w-n-g-plus-schema-drift-startup-2026-08-05.md` (W-N-G+ +0, untracked)
  - `memory/w-n-bge-m3-realpath-startup-2026-08-05.md` (W-N-BGE +0)
  - `memory/w-n-rag-eval-set-startup-2026-08-05.md` (W-N-RAG +0)
- 实测 git log --all: W-N-RAG +0 commit `d2173276a` + W-N-BGE +0 commit `04f9c9dcc` 存在 (其他 worktree 分支, 未合 main)
- W-N-OBS / W-N-FILL: 无 startup 文件, **未派工** (派工 brief 估错配据实)

**派工 brief 偏差据实 (类 20.157 沉淀)**:
- brief 假设 5 阶段派工成功 → 实测仅 3 阶段起步 (G+/RAG/BGE), 2 阶段 (OBS/FILL) 未派
- brief 假设 alembic head 105 → 实测 104 (W-N-D 104 迁移)
- brief 假设锚点 ~537 → ~XXX → 实测 35 commits 据实累计 +30 净增

## 4. 实测 W-N 周期 14+ stages 全部沉淀清单

**W-N-A HNSW 调优**: 1 cherry-pick `14bc9246e` (bench 工具 → main), worktree 6 commits 未推 main
**W-N-B halfvec 量化**: 7 commits `0a408d21a` ... `8c26e51e7` 全推 main
**W-N-C bge-m3 灰度**: 4 commits `ad555da98` ... `cce90de9a` 全推 main
**W-N-D late chunking**: 5 commits `39866b375` `740aafbde` `fb4343f29` + 2 cherry-pick memory, 104 迁移
**W-N-D+ 真 bench**: 4 commits `41ab080a1` `7387978e7` `025bb505c` `82b4b45bd` 全推 main
**W-N-D++ 端到端**: 1 commit `1cc5362e2` 全推 main
**W-N-E 冷热分层 PoC**: 2 commits `aac562075` `d8e463d1c` 全推 main (W-N-E +1 仅 worktree memory)
**W-N-F LoRA 微调起步**: 3 commits `3f2506a4b` `ce0157bdc` `50d0c0278` 全推 main
**W-N-GC CLAUDE.md 同步**: 2 commits `1409ee67d` `91fa4b450` 全推 main
**W-N-ARC worktree 归档**: 1 commit `710549f96` 全推 main
**W-N-ANC 锚点范式补**: 2 commits `650cd4ffa` `6b7cc019b` 全推 main
**W-N-MEM 索引扩展**: 3 commits `b9f9b0933` `ab34f0aa2` `ce05da2ea` 全推 main
**W-N-G+/RAG/BGE 起步 (worktree 未推 main)**: 3 startup 文件已存在
**W-N-OBS/FILL 未派工**

**累计 ~35 commits 推 main** (派工 brief 估 ~30 偏差据实 +5)

## 5. 决策文档 + capability + bench JSON 沉淀 (4 份决策)

- `docs/decisions/2026-08-05-bge-m3-decision.md` (W-N-C)
- `docs/decisions/2026-08-05-cold-hot-routing-poc.md` (W-N-E)
- `docs/decisions/2026-08-05-lora-finetune-decision.md` (W-N-F)
- `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` (W-N-D++)

**capability 报告 (1 份)**:
- `docs/capability/gpu-bge-m3-2026-08-05.md`

## 6. 后续步骤 (W-N-GRAND +0..+2 派工清单)

- [x] W-N-GRAND +0 起步 memory (本文件)
- [ ] W-N-GRAND +1: 写 `docs/w-n-grand-closure-runbook.md` (11 节完整 runbook)
- [ ] W-N-GRAND +1: 改 `memory/MEMORY.md` 追加 #25 段 (W-N 周期总收口)
- [ ] W-N-GRAND +1: 改 `CLAUDE.md` 顶部新段 (W-N 周期 grand closure 收口状态)
- [ ] W-N-GRAND +1: commit + push main
- [ ] W-N-GRAND +2 收口 memory (5 件套守恒实测 + 派工 brief 偏差据实)

---

## 派工 brief 偏差据实累计 (派工 v6 §13.3 假设禁令沿用)

| brief 假设 | 实测 | 偏差 | 类号 |
|------------|------|------|------|
| 8 phase agents 完成 | 12 stages 完成 (A/B/C/D/D+/D++/E/F/GC/ARC/ANC/MEM) + 3 stages 起步未合 main (G+/RAG/BGE) | +4 stages 据实, 3 起步未合 main | 类 20.174 |
| W-N-G+/OBS/RAG/BGE/FILL 5 阶段并行 | 仅 G+/RAG/BGE 3 起步, OBS/FILL 未派工 | -2 stages 据实 | 类 20.175 |
| alembic head 105 | 实测 104 (W-N-D 104 迁移) | -1 据实 | 类 20.176 |
| 锚点 ~537 → ~XXX | 实测 35 commits 推 main 累计 ~537 → ~572 据实 | +5 偏差据实 | 类 20.177 |
| 5 决策 doc | 实测 4 (bge-m3 / cold-hot / lora / e2e-late-chunking) | -1 决策据实 (e2e-late-chunking 由 W-N-D++ 加) | 类 20.178 |
| 0 production code | 严格守恒 (仅 docs/ + memory/ 范畴) | ✅ | 类 20.179 |

## 实测起点 commit 引用

- `git log origin/main --oneline -50` 列出 ~50 commits W-N 周期
- `python -m alembic heads` 1 head `104_add_knowledge_chunk_late_embedding` 守恒
- `ls memory/w-n-*.md` 21 份 startup/closure + 1 份 untracked = 22 份据实
- `ls docs/decisions/2026-08-05-*.md` 4 份据实
- `ls docs/capability/*.md` 1 份据实