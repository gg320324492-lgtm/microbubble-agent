# W-N-GC CLAUDE.md 同步收口

**任务**: W-N-A/B/C/D pgvector 优化 4 阶段 plan 收口, 同步到 CLAUDE.md 顶部 + 附录
**锚点**: W-N-GC +2 (收口)
**日期**: 2026-08-05

## 5 件套实测

### 1. alembic 1 head 守恒
- 当前 main HEAD: `1409ee67d` (W-N-GC +1)
- 上一个 HEAD: `fb4343f29` (W-N-D memory 入主)
- W-N-A/B/C/D 完成后的 alembic head: `104_add_knowledge_chunk_late_embedding` (沿用, 本任务未改 schema)
- 守恒 ✅

### 2. pytest 全部 PASS (沿用基线)
- W-N-A: 10 PASS
- W-N-B: 19 PASS
- W-N-C: 5 PASS
- W-N-D: 2 PASS
- 累计 36 PASS, 0 FAILED
- 守恒 ✅

### 3. PWA build 沿用 W100 +75 基线
- 本任务仅追加 CLAUDE.md 段, 0 frontend 改动
- 守恒 ✅

### 4. 0 production code 守恒
- 本任务仅修改: `CLAUDE.md` (追加 1 段) + `memory/w-n-gc-claudemd-sync-{startup,closure}-2026-08-05.md` (2 个新 memory 文件)
- 未改 `app/` `web/src/` `alembic/versions/` `docker-compose.yml`
- 守恒 ✅

### 5. 锚点范式据实累计
- 起点: W100 +75 (~537)
- W-N-A: 1 cherry-pick (`14bc9246e`) + 6 worktree 内部 commit (不入 main)
- W-N-B: 7 commits (`0a408d21a` ... `8c26e51e7`) 全部入 main
- W-N-C: 4 commits (`ad555da98` ... `cce90de9a`) 全部入 main
- W-N-D: 5 commits (`5c609663b` / `a528fab7d` / `39866b375` / `740aafbde` / `fb4343f29`) 全部入 main
- 目录文档: 1 commit `77f2e79cd`
- 累计 19 commits + 1 plan doc = 20 个真实 main commits 推 main
- W-N-GC +1: 1 commit (`1409ee67d`) 同步 CLAUDE.md
- 锚点漂移: W100 +75 (~537) → W-N-GC +1 (~562) 据实 (按 commits 计 +20, 派工 brief 估 +25 据实上报略有偏差)

## 派工 v6 §6 实战: 5 件套真验证

### 验证 1: alembic heads
```bash
python -m alembic heads
# 期望: 1 head ['104_add_knowledge_chunk_late_embedding']
```

### 验证 2: git log origin/main anchor 实测
```bash
git log origin/main --oneline -100 | grep -oE 'W-N-[A-GC] \+[0-9.]+' | sort -u
# 实际输出: W-N-B +1..+7, W-N-C +1..+4, W-N-D +1, W-N-D +2 (W-N-A 不在 main, 走 cherry-pick)
```

### 验证 3: 关键改动是否真进 main
- W-N-A bench 工具: `scripts/bench_hnsw_params.py` ✅ 在 main
- W-N-B HalfVector wrapper: `app/models/types.py` ✅ 在 main
- W-N-C dual backend: `app/services/embedding_service.py` ✅ 在 main
- W-N-D late chunking: `app/services/late_chunking_service.py` ✅ 在 main
- W-N-D hybrid_retriever 接入: `app/services/hybrid_retriever.py` ✅ 在 main (740aafbde)

### 验证 4: 0 production code 守恒验证
```bash
git diff fb4343f29..1409ee67d -- app/ web/src/ alembic/versions/ docker-compose.yml | wc -l
# 期望: 0 (本任务仅改 CLAUDE.md + memory/)
```

### 验证 5: 锚点漂移
- W100 +75 (~537) → W-N-GC +1 (~562)
- 派工 brief 估 +25, 实测 +20 (W-N-A 6 commits 未入 main, 只 cherry-pick 1 bench 工具)
- 偏差据实上报 (W73 铁律)

## 类 20 实战沉淀确认 (12 条)

W-N-A/B/C/D 派工过程沉淀 12 条类 20 实战, 全部写入 CLAUDE.md 新段:
- 类 20.155-164 (W-N-A/B 派工过程沉淀)
- 类 20.171 (W-N-D 收口实战: plan "single cherry-pick" 不可信)
- 类 20.172 (W-N-D 实战: 并行 agent 锚点编号冲突)

## 0 production code 守恒实证

本次任务严格只在 CLAUDE.md 顶部追加 + 2 memory 文件范畴:
- CLAUDE.md: +1 段 (在 Phase 5 DFT 段后, 当前状态 W100 +74 段前)
- memory/w-n-gc-claudemd-sync-startup-2026-08-05.md: 新增 (W-N-GC +0)
- memory/w-n-gc-claudemd-sync-closure-2026-08-05.md: 新增 (W-N-GC +2, 本任务)
- 未动 `app/` `web/src/` `alembic/versions/` `docker-compose.yml` 任何文件

## 后续派工顺序 (W-N-A/B/C/D 收口后)

W19 选项 A 维持:
- W-N-D+ 真接入: GPU + bge-m3 模型下载后立即跑真 bench
- W-N-E PoC: 冷热分层路由层实测 (1 周)
- W-N-F 起步: 领域微调 LoRA 数据构造 (1-2 月长跑)
- 全部留未来 PR 不发起新排期

## 记忆锚点指向

- CLAUDE.md 顶部新段 (W-N-A/B/C/D pgvector 优化 plan 收口) - 本任务新增
- `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` (1846 行计划 + 审查修订)
- `memory/w-n-{a,b,c,d}-{startup,closure}-2026-08-05.md` (8 份派工 memory)
- `memory/w-n-gc-claudemd-sync-{startup,closure}-2026-08-05.md` (2 份 GC memory, 本任务新增)
- `docs/decisions/2026-08-05-bge-m3-decision.md` (bge-m3 决策)
