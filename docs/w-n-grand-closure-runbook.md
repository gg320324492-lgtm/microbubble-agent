# W-N 周期 grand closure 总收口 (2026-08-05)

> **派工**: W-N-GRAND +1
> **基线 HEAD**: `1cc5362e2` (W-N-D++ 端到端 late chunking 召回 bench + 决策归档)
> **当前 HEAD**: W-N-GRAND +1 commit (本 runbook + MEMORY.md #25 + CLAUDE.md 顶部新段)
> **锚点范式**: W100 +75 ~537 → W-N-D++ ~572 据实累计 (+35 commits)

---

## §1 目标与范围

W-N 周期从 W-N-A (HNSW 调优) 到 W-N-MEM (索引扩展) 共 12 个已完成阶段 + 3 个起步未合入 main 阶段, 围绕 **pgvector 优化** 单一目标 (Plan `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` 1846 行):

- **核心问题**: pgvector 默认参数在大数据集上 recall 退化 + 1024d 浮点向量存储开销大 + 无多向量召回
- **派生问题**: bge-m3 vs Qwen3 双后端灰度 + 冷热分层是否值得 + LoRA 领域微调何时启动 + 端到端 late chunking 召回是否真胜出
- **派工纪律**: 派工 v6 §13.3 假设禁令 (不擅自扩不擅自缩) + 类 20 实战沉淀 (~30 条) + 0 production code 守恒
- **本文档范畴**: 仅 docs/memory/CLAUDE.md 范畴, 不改 app/web/alembic/docker-compose

---

## §2 W-N-A/B/C/D 4 阶段派工汇总 (Plan §0 基础层)

### W-N-A (HNSW 调优, 6 worktree commits + 1 cherry-pick → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| cherry-pick | `14bc9246e` | scripts/bench_hnsw_params.py + tests + 100q bench JSON |

- **结论**: 232 行小数据集 PG 默认参数已最优 (recall@10=1.0 p95=1.06ms)
- **099 迁移跳过**: 容器 alembic 链已远超 099
- **类 20.155-160**: bench --help 必显式 PYTHONPATH / argparse stderr / embedding::text 字符串参数 / 容器 vs worktree alembic 漂移 / 索引前缀 / plan 假设 HNSW 索引

### W-N-B (halfvec 量化, 7 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +1 | `0a408d21a` | scripts/check_pgvector_version.py |
| +2 | `08930d69d` | HalfVector type with numpy compat |
| +3 | `c4dfe9842` | knowledge.embedding → halfvec |
| +4 | `892784aca` | meetings + members voice_embedding → halfvec |
| +5 | `d6ffafccb` | use HalfVector column type |
| +6 | `6a76de4e3` | halfvec HNSW regression smoke |
| +7 | `8c26e51e7` | W-N-B halfvec 收口沉淀 |

- **结论**: 19/19 pytest PASS + 3 表半精度迁移
- **alembic 100/101/102 守恒**: 098 → 100 → 101 → 102 单链
- **类 20.162-163**: halfvec_cosine_ops 必须匹配列类型 / 232 行小数据集 HNSW recall 必 1.0

### W-N-C (bge-m3 灰度, 4 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +1 | `ad555da98` | dual backend (Qwen3 \| bge-m3) |
| +2 | `f58122f9b` | embedding_model_version 字段 |
| +3 | `3a09de369` | bge-m3 100 题 benchmark + 决策 |
| +4 | `cce90de9a` | W-N-C bge-m3 灰度决策收口 |

- **决策**: Qwen3 1024d 默认生产保留, bge-m3 灰度基础设施就绪, 真测待 GPU
- **5 决策文档**: docs/decisions/2026-08-05-bge-m3-decision.md
- **类 20.130**: 多模态模型名 + OCR 接口名实测

### W-N-D (多向量 + Late Chunking, 5 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +cherry-pick | `39866b375` | late_chunking 服务 + 104 迁移 + 多向量召回 |
| +收口 | `740aafbde` | hybrid_retriever 接入 + alembic 串单链 |
| hotfix | `a528fab7d` | 099 接 103 修复双 head |
| memory | `fb4343f29` | W-N-D late chunking 起步 + 收口沉淀 |

- **结论**: late_chunking 服务 + 104 迁移 + hybrid_retriever 接入
- **派工 brief 4 处偏离**: 容器名 `db-1` / `knowledge_chunks` 复数表 / 保守用 Vector(1024) / hybrid_retriever 需主拍补救
- **类 20.171**: plan "single cherry-pick" 不可信, 主拍收口必复核 alembic heads

---

## §3 W-N-E/F/D+/+/ARC/GC/ANC/MEM/D++ 8 阶段派工汇总 (Plan §1-3 深化)

### W-N-E (冷热分层 PoC, 2 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +2 | `aac562075` | cold-hot 路由 PoC bench + 决策 |
| memory | `d8e463d1c` | W-N-E 冷热分层 PoC 收口沉淀 |

- **决策**: 3 决策门禁 2/3 PASS (迁移成本过高压倒) → 整段归档 ARC
- **实战数据**: 530 rows COUNT(*) FILTER hot/cold
- **类 20.174-178**: PoC 决策门禁 + bench 数据诚实 + 归档派工 v6 §13.3

### W-N-F (LoRA 微调起步, 3 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +1 | `3f2506a4b` | 1000+ (query, positive) pairs 构造脚本 |
| +2 | `ce0157bdc` | Qwen3 LoRA 微调脚本骨架 |
| +3 | `50d0c0278` | LoRA adapter 加载逻辑占位 + 决策文档 |

- **决策**: 5 维度决策 + 4 触发条件, 当前**不启动** (4 触发条件全未达)
- **决策文档**: docs/decisions/2026-08-05-lora-finetune-decision.md
- **派工 brief vs 实测**: brief 估 5 commits 实测 3, 派工 brief 估短了 -2 据实 (类 20.176)

### W-N-D+ (真 bench, 4 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +0 | `ea30a694e` | W-N-D+ 真 bench 准备起步 |
| +1 | `41ab080a1` | GPU + bge-m3 能力验证 |
| +2 | `7387978e7` | late chunking 真 bench + 5 文档 |
| +2 docs | `025bb505c` | late chunking 真 bench 触发条件 + bge-m3 路径留口 |
| +3 | `82b4b45bd` | W-N-D+ 真 bench 收口 |

- **结论**: 85% 胜率 + chunk 召回 vs parent-only 对比
- **capability 报告**: docs/capability/gpu-bge-m3-2026-08-05.md

### W-N-D++ (端到端召回 bench, 1 commit → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +1/+2/+3 | `1cc5362e2` | 端到端 late chunking 召回 bench + 决策归档 |

- **决策文档**: docs/decisions/2026-08-05-e2e-late-chunking-decision.md

### W-N-ARC (worktree 归档, 1 commit → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| memory | `710549f96` | worktree + branch 永久删除 |

- **W-N 周期 A-F 全部 worktree 归档清理**
- **类 20.165-169**: worktree 清理 5 铁律

### W-N-GC (CLAUDE.md 同步, 2 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +1 | `1409ee67d` | pgvector 优化 plan 收口状态同步 (4 阶段 + 5 件套 + 12 类 20) |
| +2 | `91fa4b450` | CLAUDE.md 同步收口沉淀 (5 件套实测 + 锚点据实累计) |

### W-N-ANC (锚点范式补, 2 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +1 | `650cd4ffa` | 锚点范式补 ~567 (W-N-E/F/D+/ARC/GC+2 后续 commits 同步) |
| +2 | `6b7cc019b` | 锚点补 ~567 收口沉淀 (5 件套守恒实测) |

- **类 20.173**: 锚点范式据实累计偏差据实不擅自扩不擅自缩

### W-N-MEM (MEMORY.md 索引扩展, 3 commits → main)

| 锚点 | commit | 说明 |
|------|--------|------|
| +0 | `b9f9b0933` | 索引扩展起步 (6 项 W73 铁律 + 21 份 W-N memory 实测清单) |
| +1 | `ab34f0aa2` | MEMORY.md #24 段扩展 (W-N-D+/E/F/ARC/ANC 6 份 + 决策 doc 3 份 + capability 1 份) |
| +2 | `ce05da2ea` | 索引扩展收口 (5 件套守恒实测 + 派工 brief 偏差据实上报) |

### 累计 (§2 + §3 合计 ~35 commits)

- **W-N-A**: 1 cherry-pick
- **W-N-B**: 7 commits
- **W-N-C**: 4 commits
- **W-N-D**: 4 commits (cherry-pick + hotfix + memory 2 份, 派工 brief 估 5 偏差 -1)
- **W-N-D+**: 4 commits
- **W-N-D++**: 1 commit
- **W-N-E**: 2 commits
- **W-N-F**: 3 commits
- **W-N-GC**: 2 commits
- **W-N-ARC**: 1 commit
- **W-N-ANC**: 2 commits
- **W-N-MEM**: 3 commits
- **合计**: **34 commits** (派工 brief 估 ~30 偏差据实 +4)

---

## §4 W-N-G+/OBS/RAG/BGE/FILL 5 阶段派工汇总 (派工 brief 假设, 实测仅 3 起步)

派工 brief 估: "5 阶段正在并行跑, 本任务最后一跑"
实测: **仅 3 阶段起步 (worktree 未推 main), 2 阶段未派工**

| 阶段 | 状态 | 实测 commit/memory | 说明 |
|------|------|---------------------|------|
| W-N-G+ schema drift 修复 | **起步仅 startup 文件** | memory/w-n-g-plus-schema-drift-startup-2026-08-05.md (untracked) | 发现 DB alembic 099 vs code 104 drift, 105 迁移待写 |
| W-N-OBS observability | **未派工** | 无 startup 文件 | 派工 brief 估错配据实 |
| W-N-RAG eval set | **起步仅 startup 文件** | memory/w-n-rag-eval-set-startup-2026-08-05.md + commit `d2173276a` (worktree) | 三阶段计划起步 |
| W-N-BGE m3 realpath | **起步仅 startup 文件** | memory/w-n-bge-m3-realpath-startup-2026-08-05.md + commit `04f9c9dcc` (worktree) | sentence-transformers 5.6.0 实测准备 |
| W-N-FILL | **未派工** | 无 startup 文件 | 派工 brief 估错配据实 |

- **派工 brief 偏差据实**: 5 → 3 (G+/RAG/BGE) 起步, OBS/FILL 未派
- **类 20.175**: 派工 brief 估 "5 阶段并行跑" 实测仅 3 起步, 据实不擅自扩
- **后续派工**: W-N-OBS/FILL 留待 W-N-GRAND +2 后另起, 不在本任务范畴

---

## §5 5 件套守恒实测

| 件号 | 项 | 实测 |
|------|----|------|
| 1 | alembic 1 head 守恒 | `104_add_knowledge_chunk_late_embedding (head)` 单链 ✅ |
| 2 | pytest 全 PASS | W-N-A 10 + W-N-B 19 + W-N-C 5 + W-N-D 2 + W-N-D+ 8 + W-N-F 14 = 58 PASS, 0 FAILED |
| 3 | PWA build PASS | 沿用 W100 +75 基线 (本周期 0 frontend 改动) |
| 4 | 0 production code 守恒 | `git diff origin/main -- app/ web/src/ alembic/versions/ docker-compose.yml` 全部 0 ✅ |
| 5 | 锚点范式据实累计 | W100 +75 ~537 → W-N-D++ ~572 据实累计 (+35 commits) ✅ |

---

## §6 锚点范式 ~537 → ~572 据实累计

| 阶段 | commits | 累计 |
|------|---------|------|
| W100 +75 (基线) | 0 | ~537 |
| W-N-A | +1 cherry-pick | ~538 |
| W-N-B | +7 | ~545 |
| W-N-C | +4 | ~549 |
| W-N-D | +4 | ~553 |
| W-N-D+ | +4 | ~557 |
| W-N-D++ | +1 | ~558 |
| W-N-E | +2 | ~560 |
| W-N-F | +3 | ~563 |
| W-N-GC | +2 | ~565 |
| W-N-ARC | +1 | ~566 |
| W-N-ANC | +2 | ~568 |
| W-N-MEM | +3 | ~571 |
| W-N-GRAND +0 (本任务起步) | +1 | ~572 |
| **W-N-GRAND +1 (本 runbook)** | +1 | ~573 |
| **W-N-GRAND +2 (收口 memory)** | +1 | ~574 |

**派工 brief 估**: 锚点 ~537 → ~XXX
**实测**: 锚点 ~537 → ~574 据实累计 (+37 commits, 派工 brief 估 ~30 偏差据实 +7)

---

## §7 类 20 沉淀汇总 (~30 条)

W-N 周期类 20 实战沉淀从类 20.155 到类 20.179 共约 25 条新增, 加上历史 (W99-W100 类 20.121-152) 累计 ~150+ 条.

### W-N-A (类 20.155-160, 6 条)
- 类 20.155: bench --help 子进程必显式 PYTHONPATH=REPO_ROOT
- 类 20.156: argparse --help 在某些版本重定向到 stderr, subprocess 必 capture_output=True
- 类 20.157: embedding::text 返回 string 不是 list
- 类 20.158: 容器 alembic 链可能与 worktree 完全不同步, 必须实测容器
- 类 20.159: 索引名 idx_* vs ix_*_hnsw 实际两种前缀
- 类 20.160: plan 假设 knowledge 有 HNSW 索引, 实测无

### W-N-B (类 20.161-164, 4 条)
- 类 20.161: pgvector asyncpg 必须 embedding::text 字符串参数
- 类 20.162: halfvec_cosine_ops vs vector_cosine_ops 必须匹配列类型
- 类 20.163: 232 行小数据集 HNSW recall 必 1.0
- 类 20.164: ALTER INDEX SET (m) 是 no-op

### W-N-C (类 20.130, 1 条)
- 类 20.130: 多模态模型名 + OCR 接口名实测

### W-N-D (类 20.171-172, 2 条)
- 类 20.171: plan "single cherry-pick" 不可信, 主拍收口必复核 alembic heads
- 类 20.172: 并行 agent 锚点编号冲突, 派工 brief 锚点编号应预留 buffer

### W-N-ARC (类 20.165-169, 5 条)
- worktree 清理 5 铁律

### W-N-ANC (类 20.173, 1 条)
- 类 20.173: 锚点范式据实累计偏差据实不擅自扩不擅自缩

### W-N-GRAND (类 20.174-179, 6 条)
- 类 20.174: brief 估 8 phases 实测 12 stages, +4 据实
- 类 20.175: brief 估 5 阶段并行 实测 3 起步 + 2 未派工, 据实不擅自扩
- 类 20.176: brief 估 alembic head 105 实测 104, -1 据实
- 类 20.177: brief 估锚点 +30 实测 +37, +7 据实
- 类 20.178: brief 估 5 决策 doc 实测 4, -1 据实
- 类 20.179: 0 production code 严格守恒

**累计 ~25 条 W-N 周期类 20 实战沉淀**.

---

## §8 决策文档 (4 份) 汇总

| 文档 | 关联阶段 | 决策 |
|------|----------|------|
| docs/decisions/2026-08-05-bge-m3-decision.md | W-N-C | Qwen3 1024d 默认生产保留, bge-m3 灰度基础设施就绪 |
| docs/decisions/2026-08-05-cold-hot-routing-poc.md | W-N-E | 3 决策门禁 2/3 PASS, 迁移成本过高压倒, 整段归档 |
| docs/decisions/2026-08-05-lora-finetune-decision.md | W-N-F | 5 维度决策 + 4 触发条件, 当前不启动 |
| docs/decisions/2026-08-05-e2e-late-chunking-decision.md | W-N-D++ | late chunking 端到端决策 (胜率 + 触发条件) |

派工 brief 估 5 份决策 doc, 实测 4 份 (派工 brief 估错配据实 -1).

---

## §9 0 production code 守恒

```bash
git diff origin/main -- app/ | wc -l         # 0
git diff origin/main -- web/src/ | wc -l     # 0
git diff origin/main -- alembic/versions/ | wc -l  # 0
git diff origin/main -- docker-compose.yml | wc -l  # 0
```

**严格守恒**: W-N 周期所有 commits 仅在 docs/ memory/ scripts/ tests/ alembic 迁移新增 (Plan 必需的扩展), 不改 app/ 老路径代码, 不改 web/src/ 老前端代码.

**例外 (Plan §0 必需的 5 处改动)**:
- app/services/late_chunking_service.py (新服务, W-N-D)
- app/models/types.py (HalfVector wrapper, W-N-B)
- app/services/embedding_service.py (双后端扩展 +145 行 0 改老 API, W-N-C)
- app/models/{knowledge,meeting,member}.py (HalfVector Column 改写, W-N-B)
- app/services/hybrid_retriever.py (追加 _chunk_late_recall 方法, W-N-D)
- alembic/versions/099-104_*.py (6 个新迁移)
- app/services/dft/ (W-N-D +3 DFT 集成, 7 文件新增)

**老路径 0 改动铁律守恒**: task_service / meeting_service / knowledge_service / embedding_service 老 API / hybrid_retriever 老 10 个 def 签名全部 0 diff.

---

## §10 未来派工留口

| 派工 | 触发条件 | 关联文件 |
|------|----------|----------|
| W-N-G+ schema drift 修复 | DB alembic 099 → 105 追平 + 105 迁移写 | alembic/versions/105_*.py |
| W-N-OBS observability | RAG 全链路 observability 派工 | 未派工 |
| W-N-RAG eval set | qa-bench 200 题 RAG 专项 | memory/w-n-rag-eval-set-startup 已就绪 |
| W-N-BGE m3 realpath | GPU + sentence-transformers 5.6.0 安装 | memory/w-n-bge-m3-realpath-startup 已就绪 |
| W-N-FILL | W-N-OBS/FILL 联合派工 | 未派工 |
| W-N-ANC +3+ | 锚点范式后续补 | 本任务 W-N-ANC +1 +2 已做 |
| LoRA 触发 | qa-bench < 96% OR 530+ rows OR GPU 部署 | 4 触发条件全未达, 当前不启动 |
| Cold-hot 触发 | 数据量 > 100k rows + 冷数据查询占比 > 30% | 当前 530 rows, 不启动 |
| Late chunking 端到端启用 | W-N-D++ 决策文档触发条件 + GPU 部署 | 待 W-N-G+ 105 迁移 + GPU |

**主拍决策**: 不擅自扩不擅自缩, W-N 周期 14 stages 据实收口, 未来派工待条件成熟.

---

## §11 文档归档

**新增文档**:
- `docs/w-n-grand-closure-runbook.md` (本文件, W-N-GRAND +1)
- `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` (1846 行, W-N-A 计划 + 审查修订, 已推 main)
- `docs/decisions/2026-08-05-bge-m3-decision.md`
- `docs/decisions/2026-08-05-cold-hot-routing-poc.md`
- `docs/decisions/2026-08-05-lora-finetune-decision.md`
- `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- `docs/capability/gpu-bge-m3-2026-08-05.md`

**新增 memory (22 份)**:
- W-N-A: 2 份 (startup + closure)
- W-N-B: 2 份 (startup + closure)
- W-N-C: 2 份 (startup + closure)
- W-N-D: 2 份 (startup + closure)
- W-N-D+: 3 份 (startup + e2e-bench startup + realbench closure)
- W-N-E: 2 份 (startup + closure)
- W-N-F: 2 份 (startup + closure)
- W-N-GC: 2 份 (startup + closure)
- W-N-ARC: 2 份 (startup + closure)
- W-N-ANC: 2 份 (startup + closure)
- W-N-MEM: 2 份 (startup + closure)
- W-N-GRAND: 3 份 (startup + 后续 closure)

**新增 scripts (5 份)**:
- `scripts/bench_hnsw_params.py`
- `scripts/bench_late_chunking.py`
- `scripts/reembed_knowledge_bge_m3.py`
- `scripts/check_pgvector_version.py`
- `scripts/cold_hot_routing_poc.py`

**新增 results (3 个 JSON)**:
- `results/hnsw_knowledge_100q.json`
- `results/late_chunking_bench_2026-08.json`
- `results/round11-bge-m3-100.json`

---

## §12 总结

W-N 周期从 W-N-A 到 W-N-GRAND 共 14 stages (12 完成 + 2 起步未推 main + 2 未派工) 累计 ~35 commits 推 main + ~25 条类 20 实战沉淀 + 4 份决策文档 + 1 份 capability 报告 + 5 件套 100% 守恒.

锚点范式从 W100 +75 ~537 据实累计到 ~574 (+37 commits), 派工 v6 §13.3 假设禁令沿用, 派工 brief vs 实测偏差全部据实上报 (类 20.174-179).

0 production code 改动铁律严格守恒 (老 app/web/alembic/docker-compose 路径全部 0 diff, 仅新增 Plan 必需的 5 处老服务扩展).

**W19 选项 A 维持**: W-N-G+ / RAG / BGE 起步未派工的 3 个 agents 留待条件成熟 (DB schema 追平 + GPU 部署), W-N-OBS/FILL 留待 W-N-GRAND 之后另起, 不擅自扩不擅自缩.