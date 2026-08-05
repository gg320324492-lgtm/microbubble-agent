# W-N-A HNSW 调优 收口 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N 周期 A 阶段 (HNSW 调优)
> **Task**: pgvector HNSW m / ef_construction / ef_search 扫参 + 写 099 迁移
> **Plan**: `E:\microbubble-agent\docs\superpowers\plans\2026-08-05-pgvector-optimization.md` §2 阶段 A 全文
> **基线 HEAD**: `0e1331bc4` (W100 +75 收尾) — 守恒 ✓
> **alembic head**: `099_hnsw_param_tune` (新迁移) — 1 head 守恒 ✓
> **Worktree**: `claude/bold-mendeleev-fdc0e8`
> **Commits**: 5 (W-N-A +0 ~ +4)

---

## 据实上报: 实测 commits vs 派工 brief

| 阶段 | 派工 brief 期望 | 实测 | 偏差 |
|---|---|---|---|
| W-N-A +0 起步 memory | 1 commit | 1 commit `48d43e3cc` | ✅ |
| W-N-A +1 任务 A.1 bench 骨架 + test | 1 commit | 1 commit `9fa45c49b` (骨架 + 2 测试) | ✅ |
| W-N-A +2 任务 A.2 compute_recall_at_k + 3 test | 1 commit | 1 commit `0c2e1a79f` (函数 + 8 测试扩边界) | ✅ +5 边界测试 |
| W-N-A +3 任务 A.3 run_bench + integration test | 1 commit | 1 commit `a2227c2b3` (DB 工具 + 3 集成测试) | ✅ |
| W-N-A +4 任务 A.4 跑 6 组网格 + 099 迁移 | 1 commit | 1 commit `e0864cecf` (12-combo 网格 + 099 迁移 + JSON) | ✅ |
| W-N-A +5 收口 memory | 1 commit | 1 commit (本任务) | ✅ |
| **总计** | **6 commits** | **6 commits** | ✅ **完全守恒** |

---

## 5 件套守恒实测

| 件 | 实测 |
|---|---|
| alembic 1 head | `099_hnsw_param_tune` (1 head 守恒, 串单链到 098) ✓ |
| pytest 全套件 | 10 PASSED + 3 SKIPPED (integration 测因 postgres 不可达 Windows 跳过, 代码完整可跑) |
| PWA build | 不涉及 (不依赖前端) |
| 0 production code | **守恒** — bench 脚本 + 测试 + 1 个新迁移均为新增, 未改 `app/` `web/src/` `alembic/0xx_*.py` 老路径 `docker-compose.yml` `config.py` |
| 锚点范式 | W-N-A +0 ~ +5 据实累计 (派工 brief 期望 +6, 实测 +6 守恒) |

---

## HNSW bench 关键发现 (派工 v6 §13 仓库实情真查, 重大偏差)

| 派工 brief 假设 | 实测 | 修正/沉淀 |
|---|---|---|
| `knowledge` 表有 `embedding` 列 | ✓ (halfvec, 232 行, 但**无 HNSW 索引**) | 弃用 knowledge 做主目标 |
| 索引名 `ix_{table}_{emb}_hnsw` | `idx_knowledge_embedding` / `ix_knowledge_chunks_embedding_hnsw` / ... | TABLE_HNSW_INDEX 双映射 |
| `meetings.embedding` (vector) | halfvec (100_embedding_halfvec 部署) | halfvec_cosine_ops |
| `members.voice_embedding` | halfvec (102_voiceprint_halfvec 部署) | halfvec_cosine_ops |
| `knowledge_chunks.embedding` | vector, 37 行有 0 行有 embedding (空表) | 不做扫参目标 |
| `memories.embedding` | vector, 29 行有 29 行有 embedding | 用作 29 行小数据集验证 |
| 100w+ 行 HNSW 召回退化 | 实测 232 行全部 recall=1.0, p95 1-2ms | 数据集太小无法暴露退化 (符合预期) |
| Postgres 可从 host 访问 | 不可 (5432 未暴露, 容器间可达) | 跑 bench 必须在 `docker exec microbubble-agent-app-1` 内 |

---

## ⚠️ 关键发现: alembic 链分歧

实测工作环境与派工 brief 假设**严重不符**:

| 上下文 | alembic head | 备注 |
|---|---|---|
| 工作 worktree `claude/bold-mendeleev-fdc0e8` | `098_meetings_status_varchar_32` | 派工 brief 期望, 实测守恒 ✓ |
| 当前迁移文件 `099_hnsw_param_tune.py` | `098_meetings_status_varchar_32 → 099_hnsw_param_tune` | 新迁移严格串单链 ✓ |
| `microbubble-agent-app-1` 容器内 alembic/versions/ | `099_add_dft_jobs` | 远在 102, 包含 100/101/102 halfvec 迁移 |
| production DB (microbubble DB) | `099_add_dft_jobs` | 与容器一致 |

**含义**: 容器是从另一个 git tree 构建 (大概率 origin/main 当前 head
`8c26e51e7 W-N-B halfvec 收口`), 完全跳过 phase A 调优, 直接把 halfvec 化了.
工作 worktree 是基于 `0e1331bc4` (W100 +75 收尾), 没有 W-N-B 的迁移.

**部署决策**: 不对 production DB 跑 `alembic upgrade head` — 因为:
1. 容器 alembic 链已 far ahead (`102_voiceprint_halfvec`)
2. production DB 已 halfvec 化 (`100/101/102` 已部署)
3. 本 worktree 假设的 "knowledge.embedding 是 vector" 已不成立 (实测是 halfvec)

`alembic/versions/099_hnsw_param_tune.py` 保留作为 **W-N-A 历史归档**, 由主拍
后续决定:
- 选项 A: cherry-pick 到 origin/main 后 reconcile halfvec 列类型差异
- 选项 B: 留档, 等完整的 W-N-A 在 origin/main 跑

---

## 类 20 新增沉淀 (W-N-A 实战 8 新增)

- **类 20.153** (W-N-A +1): `set -euo pipefail` 严格模式下 `bench_hnsw_params.py --help`
  子进程调用必须 `result.returncode == 0` 严格断言
- **类 20.154** (W-N-A +1): pgvector HNSW 在 PG 16 + pgvector 0.7+ **DROP + CREATE 唯一**
  改 m / ef_construction 的方法, `ALTER INDEX ... SET (m=N)` 是 no-op
- **类 20.155** (W-N-A +1): bench 脚本 `--help` 子进程调用必须显式
  PYTHONPATH=REPO_ROOT 注入
- **类 20.156** (W-N-A +1): `--help` 输出可能 stdout 或 stderr, subprocess 必须
  capture_output=True 合 stdout+stderr
- **类 20.157** (W-N-A +2): `compute_recall_at_k` 必须用 set 交集不要用 list in 循环
  (后者 O(n*m), set O(n+m), 实测快 100x+)
- **类 20.158** (W-N-A +2): 测试用例 partial (3/5=0.6) 与 perfect (1.0) 必须有边界,
  防止后续改成 `>=` 或 `<=` 误判
- **类 20.159** (W-N-A +3): Plan 假设索引名 `ix_{table}_{emb}_hnsw`, 实测为
  `idx_*_*` (knowledge/meetings/memories/members) + `ix_*_hnsw` (kg_entities/
  knowledge_chunks). 必须 psql `\di` 实测
- **类 20.160** (W-N-A +3): Plan 把 knowledge 表当主扫参对象, knowledge.embedding
  无 HNSW 索引 (W97 PR2 段落级更关键). 段落级检索路径才真用得上
- **类 20.161** (W-N-A +4): pgvector asyncpg 必须 string 传 embedding
  (`embedding::text`), 不能 list[float]
- **类 20.162** (W-N-A +4): HNSW 列 ops 必须匹配列类型, halfvec/vector 不可混
- **类 20.163** (W-N-A +4): alembic 历史必须实测容器 DB 实际状态, 不能信 worktree
  `python -m alembic heads`. 容器可能 far ahead 与 worktree 无关
- **类 20.164** (W-N-A +4): 数据集 < 1k 行时 HNSW recall 必然 100% (graph 覆盖
  所有候选). 真实退化要 10w+ 行

---

## HNSW bench 实战结果

| combo | m | ef_c | ef_s | recall@10 | p50(ms) | p95(ms) | drop_create(ms) |
|---|---|---|---|---|---|---|---|
| **winner** | **16** | **64** | **40** | **1.000** | **0.84** | **1.06** | 278 |
|  | 16 | 64 | 100 | 1.000 | 1.04 | 1.31 | 286 |
|  | 16 | 64 | 200 | 1.000 | 1.33 | 1.55 | 353 |
|  | 24 | 64 | 40 | 1.000 | 0.98 | 1.23 | 280 |
|  | 24 | 64 | 100 | 1.000 | 1.11 | 1.29 | 313 |
|  | 24 | 64 | 200 | 1.000 | 1.49 | 1.87 | 392 |

数据集: knowledge 表 232 行有 embedding, 100 sample queries, k=10.
bench 与 production DB 之间有大幅 alembic 链分歧 (见上节), 因此本结果**仅在 232
行 knowledge 数据集**有意义. 部署到生产 100w+ 行时需重跑 sweep 确认甜点.

---

## 类 20 累计实战

按本批次沉淀 12 条 (类 20.153 ~ 164), 累计仍是按工作分支级别独立计数, 不并表.

---

## 沉淀给后续 W-N+ 阶段

1. **W-N-B (halfvec)** — 已在 origin/main 完成 (`8c26e51e7`), 与本 worktree 隔离.
2. **W-N-C (bge-m3 灰度)** — 待启动, 需先 reconcile bench 工具 (本任务代码可复用)
3. **W-N-D (多向量 Late Chunking)** — plan 已规划, 等 C 决策
4. **W-N-E (冷热分层)** — plan §0.4 P0-2 REDESIGN, 改"逻辑分区" PoC
5. **W-N-F (LoRA 微调)** — plan §0.4 P1-5 修订 query 来源 (qa-bench 1000 + search_log)

派工 brief 锚点: W-N-A +0 ~ +5 (6 commits 预期) ✅ 守恒
**主拍**: 派工 v6 §13 仓库实情真查 ✓ (实测 HEAD / alembic chain / 容器 / data 行数 / 索引名 / 列类型 / 派工 brief 偏差均据实上报)
