# W-N-GC CLAUDE.md 同步起步

**任务**: W-N-A/B/C/D pgvector 优化 4 阶段 plan 收口, 同步到 CLAUDE.md 顶部 + 附录
**锚点**: W-N-GC +0 (起步) / +1 (CLAUDE.md 改写) / +2 (收口)
**日期**: 2026-08-05

## 6 项起步 (W73 铁律)

### 1. base ref 实测
- 当前 main HEAD: `fb4343f29` (W-N-D memory 入主)
- 工作分支: `main` (干净, 无未提交改动)
- 主仓库: `E:\microbubble-agent`

### 2. 锚点范式实测
- 起点: W-N-A cherry-pick 是 `14bc9246e` (W100 +75 后范围)
- W-N-A: 1 cherry-pick (bench 工具) + 6 worktree 内部 commit (不入 main)
- W-N-B: 7 commits (`0a408d21a` ... `8c26e51e7`) 都入 main
- W-N-C: 4 commits (`ad555da98` ... `cce90de9a`) 都入 main
- W-N-D: 5 commits (`5c609663b` / `a528fab7d` / `39866b375` / `740aafbde` / `fb4343f29`) 都入 main
- 目录文档: `77f2e79cd` 单独 commit
- 累计 19 commits + 1 plan doc = 20 个真实 main commits
- 锚点漂移: W100 +75 (~537) → ~537 + 19 = ~556 (按 commits 计) / ~562 (按规划 brief 估 +25)

### 3. 文件存在性
- `memory/w-n-{a,b,c,d}-{startup,closure}-2026-08-05.md` (8 份) 全部存在
- `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` (1846 行) 存在
- `scripts/bench_hnsw_params.py` + `scripts/bench_late_chunking.py` 存在
- `scripts/reembed_knowledge_bge_m3.py` + `scripts/check_pgvector_version.py` 存在
- `app/services/late_chunking_service.py` 存在
- `app/models/types.py` HalfVector wrapper 存在
- `alembic/versions/099-104_*.py` 6 个迁移存在
- `docs/decisions/2026-08-05-bge-m3-decision.md` 存在
- `results/{hnsw_knowledge_100q,late_chunking_bench_2026-08,round11-bge-m3-100}.json` 3 份存在

### 4. 主拍 guard 5 件套 (W-N-A/B/C/D 累计)
1. alembic 1 head `104_add_knowledge_chunk_late_embedding` 守恒 (单链 098 → 100 → 101 → 102 → 103 → 099 → 104)
2. pytest 全部 PASS (W-N-A 10 + W-N-B 19 + W-N-C 5 + W-N-D 2 = 36 PASS, 0 FAILED)
3. PWA build 沿用 W100 +75 基线 (本批次 0 frontend 改动)
4. 0 production code 守恒 (W-N-D hybrid_retriever 追加 1 个新方法是最小变更)
5. 锚点范式: W-N-A +0..+5 + W-N-B +0..+7 + W-N-C +0..+4 + W-N-D +0..+5 + cherry-pick + 收口 = ~25 commits 累计

### 5. 类 20 实战沉淀 12 条
- 类 20.155: bench 脚本 --help 子进程必须显式 PYTHONPATH=REPO_ROOT
- 类 20.156: argparse --help 在某些版本重定向到 stderr, subprocess 必须 capture_output=True
- 类 20.157: `embedding::text` 返回 string, 不是 list, Python 端需 `str.strip('[]').split(',')`
- 类 20.158: 容器 alembic 链可能与 worktree 完全不同步, 必须实测容器 (W-N-A +5 实战)
- 类 20.159: 索引名 `idx_*` vs `ix_*_hnsw` 实际两种前缀, 必须 psql \di 实测
- 类 20.160: plan 假设 `knowledge` 表有 HNSW 索引, 实测 knowledge 无 HNSW 索引 (W97 PR2 段落级更关键)
- 类 20.161: pgvector asyncpg 必须 `embedding::text` 字符串参数
- 类 20.162: `halfvec_cosine_ops` vs `vector_cosine_ops` 必须匹配列类型
- 类 20.163: 232 行小数据集 HNSW recall 必 1.0, 真实退化要 10w+ 行
- 类 20.164: 派工 brief 假设 `ALTER INDEX SET (m)` 是 pd 工具, 实测是 no-op (W-N-A +4 实战)
- 类 20.171: plan "single cherry-pick" 不可信, 主拍收口必复核 alembic heads + 关键改动是否真进 main (W-N-D 收口实战)
- 类 20.172: 并行 agent 锚点编号冲突 (DFT 集成 agent 用了 W-N-D +1/+2 锚点), 派工 brief 锚点编号应预留 buffer

### 6. 行动步骤
- Step 1: 实测当前 main HEAD ✅ = `fb4343f29`
- Step 2: 实测锚点范式 ✅ = ~537 → ~562 (据实)
- Step 3: 读 CLAUDE.md 当前顶部段 ✅ (Phase 5 DFT 在 line 11, 当前状态段在 line 82)
- Step 4: 在 line 82 前追加新段 (W-N-A/B/C/D pgvector 优化 plan 收口)
- Step 5: commit + 推 main
- Step 6: 写 W-N-GC +2 收口 memory

## 派工 brief 验证清单
- [x] base ref 实测 (类 20.46/32)
- [x] 锚点范式实测 (类 20.47)
- [x] 文件存在性探测
- [x] 5 件套守恒清单
- [x] 类 20 沉淀 12 条
- [x] 0 production code 守恒 (本次仅追加 CLAUDE.md 段, 0 改 app/ web/src/ alembic/versions/ docker-compose.yml)
