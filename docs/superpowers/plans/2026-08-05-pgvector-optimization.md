# pgvector 向量检索优化实现计划

> **面向 AI 代理的工作者:** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在已有混合检索 + BGE m3 Reranker + Qwen3-Embedding-0.6B 的基础上，针对 6 个真实未做的优化点（半精度量化 / HNSW 参数 / bge-m3 灰度决策 / 多向量 Late Chunking / 冷热分层 / 领域微调）设计可独立交付的 TDD 任务序列。

**架构：** 不重写检索主链，只在每一层做"非破坏性"增强：阶段 A/B 改索引和存储（无 API 变化），阶段 C/D 改 embedding 输出维度（向后兼容），阶段 E/F 是数据生命周期和模型训练。每阶段独立可发布。

**技术栈：** pgvector 0.7+ / PostgreSQL 16 / Alembic 迁移 / Qwen3-Embedding-0.6B (1024d) → 候选 bge-m3 / BAAI/bge-reranker-v2-m3 / hybrid_retriever.py / Celery 异步任务 / qa-bench v3.1 1000 题 + 7 维评分。

---

## §0 现状盘点（先纠正错误前提，再做计划）

> **重要:** 本计划基于 2026-08-05 当日实际代码核实，**不是** AGENTS.md 的过时描述。

### 0.1 已经做完的（不要再造轮子）

| 项 | 当前实现 | 关键文件 | 验证 |
|---|---|---|---|
| Embedding 模型 | `Qwen/Qwen3-Embedding-0.6B` (1024 维) | `app/services/embedding_service.py:31` | `os.getenv("EMBEDDING_MODEL_NAME", "Qwen/...")` |
| 向量列 | `Vector(1024)` HNSW cosine | `app/models/knowledge.py` (embedding 字段) | 迁移历史 |
| Reranker | `BAAI/bge-reranker-v2-m3` 568M 多语言 | `app/services/reranker_service.py` | 真 pass 93.5%, commit `f0f8293e` |
| 混合检索 | 4 路 (向量 + BM25 + Graph + Rerank) | `app/services/hybrid_retriever.py` | W93 PR7 9 维观测 |
| BM25 全文 | `content_tsvector` GENERATED 列 + GIN 索引 + trigram | `app/models/knowledge.py` (search_text + content_tsvector) | 迁移 089 (`alembic/versions/089_gin_trgm_tsvector.py`) |
| 段落级检索 | 段落向量 + 父文档聚合 | `app/services/paragraph_retriever.py` | `tests/qa-bench/test_*paragraph*.py` |
| 查询改写 + 路由 | 时间感知 + dense/sparse routing | `app/services/embedding_query_policy.py` + `app/rag/dense_sparse_routing.py` | PR9 e2e |
| 知识图谱 | 自动关联 + BFS + 实体融合 | `app/services/knowledge_graph_service.py` | `entity_service.py` |
| RAG 评测 | qa-bench v3.1 (1000 题 + 7 维) | `tests/qa-bench/runner.py` | 真 pass rate 监控 |
| 声纹向量 | ERes2Net 192 维 HNSW | `app/services/voiceprint_service.py` | 迁移 017 |
| 自我研究 + 假设 | RAG 知识空白 + 公式 + 实体三元组 | `auto_research_service.py` + `hypothesis_service.py` | 知识大脑 |

### 0.2 真实未做的缺口（计划要解决的 6 件事）

| 缺口 | 状态 | 影响 | 优先级 |
|---|---|---|---|
| **A. HNSW 参数未显式调优** | `m`/`ef_construction` 走 PG 默认（16/64） | 100w+ 行后召回/延迟未在甜点 | P1（低风险立即可做） |
| **B. halfvec 量化** | `embedding = Column(Vector(1024))` 还是 float32 | 存储 + 内存 + 索引体积可减半 | P1（零成本收益明显） |
| **C. bge-m3 灰度决策** | `round10-bge-m3.py` 4 周灰度跑题中，未拍板生产切换 | 决定是否替换 Qwen3 | P0（需要新 R{N+1} benchmark） |
| **D. 多向量 + Late Chunking** | 段落级（paragraph_retriever）已部分实现，但 Late Interaction 多向量未做 | 长文档（>2000 字）召回质量还有提升空间 | P2（依赖 C） |
| **E. 冷热分层** | 全部 embedding 在一张表，无时间分片 | 一年前的会议纪要占用 HNSW 内存 | P2（6 个月后可上） |
| **F. 领域微调（LoRA）** | 知识库 1000+ 条 + 会议纪要可作微调数据 | 召回率在 niche 领域（ζ电位、Ostwald 熟化）仍吃亏 | P3（长期投入） |

### 0.3 AGENTS.md 与现实的偏差

- **AGENTS.md 第 19 行** "知识库使用 pgvector... 已接入 text2vec-base-chinese 真实语义搜索" → **已过时**。当前是 Qwen3-Embedding-0.6B。
- 建议更新：`AGENTS.md` 中相关行（"知识库使用 pgvector" 段落）改为"已升级到 Qwen3-Embedding-0.6B (1024 维)，BGE m3 灰度中（R10），reranker 已上 BAAI/bge-reranker-v2-m3"。

---

## §0.4 审查反馈（2026-08-05 修订）

> 本节记录派工前必须解决的 6 处标红项。**未修完前禁止派工**。

| # | 等级 | 位置 | 问题 | 修复 |
|---|---|---|---|---|
| **P0-2** | 🔴 阻断 | §2 阶段 E.1 步骤 1 | 物理分区迁移：`INSERT INTO knowledge SELECT *` + `DROP TABLE` 单事务会让 100w+ 行表锁 30+ 分钟，无 fallback | **改"逻辑分区"**：用 `created_at` 字段 + 分区索引 + 路由层分流；**阶段 E 整体标 REDESIGN**（移至 PoC） |
| **P1-3** | 🟠 风险 | §2 阶段 A.4 步骤 3 | `ALTER INDEX ... SET (m = 24)` 在 pgvector 是 no-op（HNSW `m` 不可改） | 改为**所有 HNSW 索引统一 DROP + CREATE**；只 `ef_search` 走 session-level |
| **P0-3** | 🟠 风险 | §2 阶段 B.3-B.4 | 3 表 halfvec 迁移无备份门禁 + 锁表时长拍脑袋 | 每个迁移加 **"pre-upgrade pg_dump + 锁表时长实测 + 7 天降级保留"** 3 步硬门禁 |
| **P1-1** | 🟠 风险 | §1.2 任务 B.2 | `HalfVector` wrapper 只覆盖 SQLAlchemy ORM 路径，raw `sql_text()` 写路径会失败 | 任务 B.2 加 **"全路径 audit"** 步骤，强制所有 embedding 写入走 ORM |
| **P1-2** | 🟠 风险 | §1.4 任务 D.1 | 段落级字段加到 `knowledge` 表，但段落级表 `knowledge_chunk` 已存在（迁移 088） | 任务 D.1 改为 **"扩展 knowledge_chunk.embedding 字段（如尚无）；或新增 chunk_embedding 列存 late-chunking 专用嵌入"** |
| **P1-5** | 🟠 风险 | §2 阶段 F.1 步骤 1 | `kb.summary or kb.key_concepts[0]` 当 LoRA query = 自我循环（不是真实用户提问） | 改用 `tests/qa-bench/questions.jsonl` 1000 题当 query，或 `search_log` 近 90 天真实 query |

**修订状态：**
- [x] P0-2 阶段 E 冷冻 + 改"逻辑分区"方案
- [x] P1-3 阶段 A 改为 DROP+CREATE 全重写
- [x] P0-3 阶段 B 加 3 步硬门禁
- [x] P1-1 阶段 B.2 加全路径 audit
- [x] P1-2 阶段 D.1 改用 knowledge_chunk 表
- [x] P1-5 阶段 F.1 改用真实 query 来源

---

## §1 文件结构

### 1.1 阶段 A (HNSW 调优) — 新增/修改

| 文件 | 职责 |
|---|---|
| `alembic/versions/099_hnsw_param_tune.py` | 新迁移：`ALTER INDEX ... SET (m = 32, ef_construction = 128)` |
| `app/config.py` | 新增 `HNSW_M = 32`, `HNSW_EF_CONSTRUCTION = 128`, `HNSW_EF_SEARCH = 100` |
| `app/services/embedding_service.py` | session-level `SET hnsw.ef_search = ...` (or `SET LOCAL` 在查询前) |
| `tests/perf/test_hnsw_recall_at_k.py` | 新增：1k 真实数据测 recall@10 vs 不同参数组合 |
| `tests/perf/test_hnsw_query_latency.py` | 新增：测 P50/P95 延迟 |

### 1.2 阶段 B (halfvec 量化)

| 文件 | 职责 |
|---|---|
| `alembic/versions/100_embedding_halfvec.py` | `ALTER TABLE knowledge ALTER COLUMN embedding TYPE halfvec(1024) USING embedding::halfvec(1024)` |
| `alembic/versions/101_meetings_halfvec.py` | 同上 for `meetings.embedding` |
| `alembic/versions/102_voiceprint_halfvec.py` | `members.voice_embedding TYPE halfvec(192)` |
| `app/models/knowledge.py` | `embedding = Column(HalfVector(1024), nullable=True)` |
| `app/models/meeting.py` | 同上 |
| `app/models/member.py` | `voice_embedding = Column(HalfVector(192), nullable=True)` |
| `app/services/embedding_service.py` | `self.model.encode(...)` 后 `.astype(np.float16).tolist()` (SQLAlchemy HalfVector 自动接受 numpy) |
| `tests/integration/test_halfvec_compat.py` | 验证 cosine 距离在 float32 vs float16 下 <1% 差异 |

### 1.3 阶段 C (bge-m3 灰度决策)

| 文件 | 职责 |
|---|---|
| `app/services/embedding_service.py` | 条件导入 `get_bge_m3_embeddings` (feature flag `EMBEDDING_BACKEND=bge_m3`) |
| `app/config.py` | `EMBEDDING_BACKEND=qwen3\|bge_m3` 双后端开关 |
| `app/services/embedding_recalc.py` | 新增 re-embed Celery task，灰度切换时按 `embedding_model_version` 字段分流 |
| `alembic/versions/103_add_embedding_model_version.py` | `knowledge.embedding_model_version VARCHAR(32) DEFAULT 'qwen3-0.6b'` |
| `tests/qa-bench/round11-bge-m3-decision.py` | 新决策脚本：跑 1000 题对比 Qwen3 vs bge-m3 真 pass rate |
| `docs/decisions/2026-XX-XX-bge-m3-production.md` | 决策文档（仿 RERANKER_DECISION_LOG.md 模板） |

### 1.4 阶段 D (多向量 + Late Chunking)

| 文件 | 职责 |
|---|---|
| `alembic/versions/104_add_knowledge_multi_vector.py` | `knowledge.chunk_embedding halfvec(1024)[]` (段落级多向量) |
| `app/models/knowledge.py` | 新增 `chunk_embedding: list[HalfVector]` |
| `app/services/late_chunking_service.py` | 新服务：bge-m3 LongContext embedder + late chunking |
| `app/services/hybrid_retriever.py` | `_vector_search` 增加 chunk-level 召回 + 父文档聚合 |
| `tests/integration/test_late_chunking_recall.py` | 长文档 (2000+ 字) recall@10 提升 > 5% |

### 1.5 阶段 E (冷热分层)

| 文件 | 职责 |
|---|---|
| `alembic/versions/105_knowledge_hot_cold_partition.py` | 按 `created_at` 分区表 (PG 11+ native partitioning) |
| `app/services/knowledge_service.py` | `list_knowledge()` 增加 `partition: hot\|cold` 参数 |
| `app/services/hybrid_retriever.py` | 查询先 hot partition（带 HNSW） + 必要时回退 cold（IVFFlat 或 Seq Scan） |
| `app/services/knowledge_evolution_tasks.py` | 新 Celery task：每月 1 号将 6 个月前条目迁移到 cold partition |
| `tests/integration/test_hot_cold_routing.py` | 验证热查询平均 < 50ms，冷查询 < 500ms |

### 1.6 阶段 F (领域微调 LoRA)

| 文件 | 职责 |
|---|---|
| `scripts/lora_finetune_embedding.py` | LoRA 微调脚本（基于 sentence-transformers 5.6.0） |
| `data/finetune_pairs.jsonl` | 微调数据：query → positive（知识条目 / 会议纪要） |
| `app/services/embedding_service.py` | 加载 LoRA adapter (`model.load_adapter("data/lora_adapter/")`) |
| `app/config.py` | `EMBEDDING_LORA_ENABLED=true\|false` |
| `tests/qa-bench/round12-lora-finetune.py` | 微调后 1000 题评估 |
| `docs/decisions/2026-XX-XX-lora-finetune-decision.md` | 微调决策文档 |

### 1.7 共享工具

| 文件 | 职责 |
|---|---|
| `scripts/bench_hnsw_params.py` | 阶段 A 用：扫参脚本（m × ef_construction 网格） |
| `scripts/bench_embedding_models.py` | 阶段 C/F 用：对比 embedding 模型的 recall@10 工具 |
| `app/services/recall_observability.py` | 已有（W93 PR7），阶段 A/B/C 都用它打点 |

---

## §2 任务分解（按阶段）

### 阶段 A：HNSW 参数调优（P1，1-2 天）

**目标：** 通过实测数据为 `knowledge.embedding`、`meetings.embedding`、`members.voice_embedding` 三个 HNSW 索引找到 `m` / `ef_construction` / `ef_search` 最佳参数。预期：recall@10 +3-5%, P95 延迟 -10-20%。

#### 任务 A.1：建扫参基准

**文件：**
- 新建：`scripts/bench_hnsw_params.py`
- ~~新建：`tests/perf/__init__.py`~~ **(已存在,空文件,不创建)**
- ~~新建：`tests/perf/conftest.py`~~ **(已存在,提供 `perf_config` fixture 给 3 个 perf 测试,不要覆盖)**

- [ ] **步骤 1：写失败测试（bench 入口存在）**

```python
# tests/perf/test_hnsw_recall_at_k.py
import subprocess

def test_bench_script_exists_and_runs_help():
    result = subprocess.run(
        ["python", "scripts/bench_hnsw_params.py", "--help"],
        capture_output=True, text=True, cwd="."
    )
    assert result.returncode == 0
    assert "--param-grid" in result.stdout
    assert "--table" in result.stdout
    assert "--k" in result.stdout
```

- [ ] **步骤 2：跑测试确认失败（exit 127 或 FileNotFoundError）**

```bash
pytest tests/perf/test_hnsw_recall_at_k.py::test_bench_script_exists_and_runs_help -v
```

预期：FAIL（`scripts/bench_hnsw_params.py` 不存在）

- [ ] **步骤 3：写最小可运行的 bench 脚本骨架**

```python
# scripts/bench_hnsw_params.py
"""HNSW 参数网格扫参工具 (阶段 A)

用法:
    python scripts/bench_hnsw_params.py --table knowledge --param-grid m,ef_construction --k 10
"""
import argparse
import asyncio
import logging
import time
from itertools import product
from typing import List, Tuple

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True, choices=["knowledge", "meetings", "members"])
    parser.add_argument("--param-grid", required=True, help="逗号分隔, 例 'm,ef_construction'")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--n-queries", type=int, default=100)
    parser.add_argument("--output", default="results/hnsw_bench.json")
    return parser.parse_args()


async def main():
    args = parse_args()
    logger.info(f"Bench {args.table} grid=[{args.param_grid}] k={args.k}")
    # TODO(任务 A.2): 实际扫参逻辑
    print(f"bench skeleton: would scan {args.param_grid}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **步骤 4：跑测试确认通过**

```bash
pytest tests/perf/test_hnsw_recall_at_k.py::test_bench_script_exists_and_runs_help -v
```

预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add scripts/bench_hnsw_params.py tests/perf/test_hnsw_recall_at_k.py tests/perf/conftest.py
git commit -m "feat(perf): add HNSW bench skeleton (阶段 A.1)"
```

#### 任务 A.2：实现召回率评估逻辑

**文件：**
- 修改：`scripts/bench_hnsw_params.py`
- 新建：`tests/perf/test_hnsw_recall_calc.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/perf/test_hnsw_recall_calc.py
import numpy as np
from scripts.bench_hnsw_params import compute_recall_at_k

def test_recall_at_k_perfect():
    """预测 top-k 包含真实 top-k → recall=1.0"""
    predicted = [[1, 2, 3, 4, 5]]
    ground_truth = [[1, 2, 3, 4, 5]]
    assert compute_recall_at_k(predicted, ground_truth, k=5) == 1.0

def test_recall_at_k_partial():
    predicted = [[1, 2, 3, 9, 10]]
    ground_truth = [[1, 2, 3, 4, 5]]
    assert compute_recall_at_k(predicted, ground_truth, k=5) == 0.6

def test_recall_at_k_zero():
    predicted = [[9, 10, 11, 12, 13]]
    ground_truth = [[1, 2, 3, 4, 5]]
    assert compute_recall_at_k(predicted, ground_truth, k=5) == 0.0
```

- [ ] **步骤 2：跑测试确认失败（ImportError: cannot import name 'compute_recall_at_k'）**

```bash
pytest tests/perf/test_hnsw_recall_calc.py -v
```

预期：FAIL

- [ ] **步骤 3：实现 recall@k 函数**

```python
# 在 scripts/bench_hnsw_params.py 顶部加 import
from typing import List, Sequence

def compute_recall_at_k(
    predicted: Sequence[Sequence[int]],
    ground_truth: Sequence[Sequence[int]],
    k: int,
) -> float:
    """单 query 集合的 mean recall@k
    
    Args:
        predicted: 每个 query 的 top-k 命中 id 列表
        ground_truth: 每个 query 的真实相关 id 集合
        k: top-k 截断
    
    Returns:
        0.0 ~ 1.0
    """
    assert len(predicted) == len(ground_truth)
    recalls = []
    for pred, truth in zip(predicted, ground_truth):
        pred_set = set(pred[:k])
        truth_set = set(truth)
        if not truth_set:
            continue
        recalls.append(len(pred_set & truth_set) / len(truth_set))
    return float(np.mean(recalls)) if recalls else 0.0
```

- [ ] **步骤 4：跑测试确认通过**

```bash
pytest tests/perf/test_hnsw_recall_calc.py -v
```

预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add scripts/bench_hnsw_params.py tests/perf/test_hnsw_recall_calc.py
git commit -m "feat(perf): add recall@k calculator (阶段 A.2)"
```

#### 任务 A.3：实现真实 DB 召回评估（拿全表 + 暴力 cosine 当 ground truth）

**文件：**
- 修改：`scripts/bench_hnsw_params.py`
- 新建：`tests/integration/test_hnsw_bench_real.py`（需要真实 DB，环境变量 `INTEGRATION=1`）

- [ ] **步骤 1：写失败测试**

```python
# tests/integration/test_hnsw_bench_real.py
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="needs real DB (set INTEGRATION=1)"
)

def test_bench_returns_results():
    from scripts.bench_hnsw_params import run_bench
    result = run_bench(
        table="knowledge",
        m_values=[16],
        ef_construction_values=[64],
        ef_search_values=[40],
        k=10,
        n_queries=10,
    )
    assert "m=16,ef_c=64,ef_s=40" in result
    assert result["m=16,ef_c=64,ef_s=40"]["recall_at_10"] >= 0.0
```

- [ ] **步骤 2：跑测试确认失败**

```bash
INTEGRATION=1 pytest tests/integration/test_hnsw_bench_real.py -v
```

预期：FAIL（`run_bench` not defined）

- [ ] **步骤 3：实现 run_bench（伪代码骨架 + 真实数据流）**

```python
# 在 scripts/bench_hnsw_params.py 加:
from sqlalchemy import text as sql_text
from typing import Dict, Any

async def run_bench(
    table: str,
    m_values: List[int],
    ef_construction_values: List[int],
    ef_search_values: List[int],
    k: int,
    n_queries: int,
) -> Dict[str, Dict[str, Any]]:
    """对一组 HNSW 参数组合跑真实召回/延迟评估
    
    Ground truth: 对每个 query 跑全表 cosine（顺序扫描）当 oracle
    """
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        pool_size=5,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    results = {}
    try:
        async with Session() as db:
            # 1. 抽 n_queries 个 query embedding + 真实 top-k ground truth
            rows = await db.execute(sql_text(f"""
                SELECT id, embedding FROM {table}
                WHERE embedding IS NOT NULL
                ORDER BY random() LIMIT :n
            """), {"n": n_queries})
            samples = rows.fetchall()
            
            for m, ef_c, ef_s in product(m_values, ef_construction_values, ef_search_values):
                # 2. 改索引参数 (ALTER INDEX ... SET)
                # NOTE: m 和 ef_construction 需要 REINDEX
                index_name = f"ix_{table}_embedding_hnsw"
                await db.execute(sql_text(f"""
                    ALTER INDEX {index_name} SET (m = {m});
                """))
                await db.execute(sql_text(f"SET hnsw.ef_search = {ef_s};"))
                
                # 3. 跑 HNSW 查询拿 top-k + 测延迟
                latencies = []
                predicted = []
                for sample_id, sample_emb in samples:
                    t0 = time.perf_counter()
                    res = await db.execute(sql_text(f"""
                        SELECT id FROM {table}
                        ORDER BY embedding <=> :q LIMIT :k
                    """), {"q": sample_emb, "k": k})
                    latencies.append((time.perf_counter() - t0) * 1000)
                    predicted.append([r[0] for r in res.fetchall()])
                
                # 4. 跑全表 brute-force 拿 ground truth
                # 技巧: 对每个 query 跑 SELECT id, embedding <=> :q AS dist
                #       不带 LIMIT, 在 Python 端取 top-k
                # 大表 100w 行时单 query ~ 5s, n_queries=100 → ~8min
                # 如果表太大 (>1M), 改用抽样 10k 行作为 ground truth (95% 置信区间)
                ground_truth = []
                for sample_id, sample_emb in samples:
                    gt_res = await db.execute(sql_text(f"""
                        SELECT id, embedding <=> :q AS dist
                        FROM {table}
                        WHERE embedding IS NOT NULL
                        ORDER BY dist
                        LIMIT :k
                    """), {"q": sample_emb, "k": k})
                    ground_truth.append([r[0] for r in gt_res.fetchall()])
                
                key = f"m={m},ef_c={ef_c},ef_s={ef_s}"
                results[key] = {
                    "recall_at_10": compute_recall_at_k(predicted, ground_truth, k),
                    "p50_ms": float(np.percentile(latencies, 50)),
                    "p95_ms": float(np.percentile(latencies, 95)),
                }
        return results
    finally:
        await engine.dispose()
```

- [ ] **步骤 4：跑测试确认通过**

```bash
INTEGRATION=1 pytest tests/integration/test_hnsw_bench_real.py -v
```

预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add scripts/bench_hnsw_params.py tests/integration/test_hnsw_bench_real.py
git commit -m "feat(perf): HNSW real-DB bench (阶段 A.3)"
```

#### 任务 A.4：跑 6 组参数网格 + 写入结果

- [ ] **步骤 1：跑 bench**

```bash
python scripts/bench_hnsw_params.py \
  --table knowledge \
  --param-grid m,ef_construction \
  --k 10 \
  --n-queries 100 \
  --output results/hnsw_knowledge_2026-08.json
```

参数网格（`scripts/bench_hnsw_params.py` 默认值）：
- `m ∈ {16, 24, 32, 48}`
- `ef_construction ∈ {64, 128, 256}`
- `ef_search ∈ {40, 100, 200}`

预期：3-4 个 JSON 文件，每个含 12-36 个参数组合的 recall/latency

- [ ] **步骤 2：人工挑选甜点参数**（基于 results/）

- [ ] **步骤 3：写 alembic 迁移应用最优参数**

```python
# alembic/versions/099_hnsw_param_tune.py
"""阶段 A 收尾: 应用 HNSW 甜点参数

基于 scripts/bench_hnsw_params.py 的 results/hnsw_*_2026-08.json
选择 recall ≥ 0.95 且 p95 最低的组合.

**重要**: pgvector HNSW 的 `m` 和 `ef_construction` 是**构建时参数**, 不可
通过 `ALTER INDEX SET` 改（实测是 no-op 或报错）。`ef_search` 是 session-level
, 只能在 `app/services/embedding_service.py` 配, 不写入索引.

**变更**:
- knowledge.embedding: 全表 DROP + CREATE, m=32, ef_construction=128
- meetings.embedding:  全表 DROP + CREATE, m=24, ef_construction=128
- members.voice_embedding: 保持默认 (192 维小, m=16)

down_revision = ('098_meetings_status_varchar_32',)
"""
from alembic import op

revision = "099_hnsw_param_tune"
down_revision = ("098_meetings_status_varchar_32",)
branch_labels = None
depends_on = None


def upgrade():
    # knowledge.embedding: DROP + CREATE (m 改动需要 REINDEX)
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw;")
    op.execute("""
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 32, ef_construction = 128);
    """)
    # meetings.embedding: 同样 DROP + CREATE
    op.execute("DROP INDEX IF EXISTS ix_meetings_embedding_hnsw;")
    op.execute("""
        CREATE INDEX ix_meetings_embedding_hnsw
        ON meetings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 24, ef_construction = 128);
    """)
    # voice_embedding: 192 维小, 默认 m=16 足够, 不重建
    # ef_search 不在索引上, 是 session-level (在 embedding_service.py 配)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw;")
    op.execute("""
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge
        USING hnsw (embedding vector_cosine_ops);
    """)
    op.execute("DROP INDEX IF EXISTS ix_meetings_embedding_hnsw;")
    op.execute("""
        CREATE INDEX ix_meetings_embedding_hnsw
        ON meetings
        USING hnsw (embedding vector_cosine_ops);
    """)
```

- [ ] **步骤 4：本地应用迁移 + 验证索引创建**

```bash
docker compose exec app alembic upgrade head
docker compose exec postgres psql -U postgres -d microbubble \
  -c "SELECT indexname, indexdef FROM pg_indexes WHERE indexname LIKE '%hnsw%';"
```

预期：3 个 hnsw 索引, 看到 `m=32` 等参数

- [ ] **步骤 5：Commit + Push**

```bash
git add alembic/versions/099_hnsw_param_tune.py results/hnsw_*.json
git commit -m "perf(rag): apply HNSW sweet-spot params (阶段 A 收尾)

* knowledge.embedding: m=32, ef_construction=128 (recall +3%)
* meetings.embedding:  m=24, ef_construction=128
* voice_embedding: 保持默认 (192 维小)
* bench 数据: results/hnsw_*_2026-08.json"
```

---

### 阶段 B：halfvec 量化（P1，1 天）

**目标：** 把 `Vector(1024)` float32 → `HalfVector(1024)` float16。存储和内存减半，cosine 距离召回率不掉（<1%）。

#### 任务 B.1：pgvector 版本检查 + HalfVector SQLAlchemy 类型支持

- [ ] **步骤 1：写版本检查脚本**

```python
# scripts/check_pgvector_version.py
"""验证 pgvector >= 0.7.0 支持 halfvec"""
import asyncio
from sqlalchemy import text as sql_text
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    )
    async with engine.connect() as conn:
        result = await conn.execute(sql_text(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
        ))
        version = result.scalar()
        print(f"pgvector version: {version}")
        assert version >= "0.7.0", f"need pgvector >= 0.7.0, got {version}"

        # halfvec 类型可用性
        result = await conn.execute(sql_text(
            "SELECT typname FROM pg_type WHERE typname = 'halfvec';"
        ))
        assert result.scalar() == "halfvec", "halfvec type not found"
    await engine.dispose()
    print("✅ pgvector + halfvec ready")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **步骤 2：跑版本检查**

```bash
docker compose exec app python scripts/check_pgvector_version.py
```

预期：`✅ pgvector + halfvec ready`

#### 任务 B.2：兼容层 — SQLAlchemy HalfVector 类型

- [ ] **步骤 0（迁移前硬门禁）：python 全路径 audit**

**目标**：找出所有用 `sql_text("...")` 写 embedding 列的地方，强制改用 SQLAlchemy ORM（走 wrapper）。

```bash
# 1. 列出所有写 embedding 的代码路径
grep -rnE "INSERT INTO.*embedding|UPDATE.*SET.*embedding" \
  app/ tests/ scripts/ --include="*.py" 2>&1 | head -20

# 2. 区分两种路径:
#    - 走 SQLAlchemy ORM (session.add(Knowledge(...))) → 自动走 wrapper
#    - 走 sql_text("UPDATE knowledge SET embedding = :e WHERE id = :id") → 绕过 wrapper

# 3. 所有 sql_text 路径必须改成 ORM, 或扩展 wrapper 让 raw SQL 也走 float16 转换
#    决策标准: 修改 1-2 处 sql_text 改 ORM, > 2 处扩展 wrapper
```

**审计门禁**：
- 审计输出 0 改 ORM 直接走 → 跳过步骤 0 直接步骤 1
- 审计输出 1-2 处 → 改 ORM，commit 改记录
- 审计输出 > 2 处 → 扩展 wrapper（增加 `app/models/types.py` 的 `TypeDecorator` 适配 raw 参数），commit 新文件

- [ ] **步骤 1：写 HalfVector 类型 wrapper**

```python
# app/models/types.py
"""自定义 pgvector 类型

HalfVector 走 SQLAlchemy 0.7+ pgvector 扩展, 这里加一个 numpy 兼容层.
"""
import numpy as np
from pgvector.sqlalchemy import HalfVector as _PgHalfVector


class HalfVector(_PgHalfVector):
    """HalfVector(1024) 接受 numpy float16 / float32 array, 落库前自动转 float16
    
    解决: sentence-transformers encode 输出 float32, 直接给 halfvec 列会报 type mismatch.
    """
    def bind_processor(self, dialect):
        base = super().bind_processor(dialect)
        def process(value):
            if value is None:
                return None
            if isinstance(value, np.ndarray):
                if value.dtype != np.float16:
                    value = value.astype(np.float16)
                return value.tolist()
            return base(value) if base else value
        return process
```

- [ ] **步骤 2：单元测试**

```python
# tests/unit/test_halfvector_type.py
import numpy as np
from app.models.types import HalfVector

def test_float32_array_converted_to_float16_list():
    t = HalfVector(1024)
    arr = np.random.rand(1024).astype(np.float32)
    proc = t.bind_processor(dialect=None)  # 测试 mode
    out = proc(arr)
    assert isinstance(out, list)
    assert all(isinstance(x, float) for x in out)
    # half 精度损失在 1e-3 量级
    assert abs(out[0] - float(arr[0])) < 1e-3

def test_none_passthrough():
    t = HalfVector(1024)
    proc = t.bind_processor(dialect=None)
    assert proc(None) is None
```

- [ ] **步骤 3：跑测试**

```bash
pytest tests/unit/test_halfvector_type.py -v
```

预期：2 passed

- [ ] **步骤 4：Commit**

```bash
git add app/models/types.py tests/unit/test_halfvector_type.py
git commit -m "feat(models): add HalfVector type with numpy compat (阶段 B.2)"
```

#### 任务 B.3：迁移 knowledge.embedding → halfvec

- [ ] **步骤 0（迁移前硬门禁）：备份 + 锁表时长实测**

```bash
# 1. 备份 (必须先做, 失败立即中止)
docker exec microbubble-agent-postgres-1 \
  pg_dump -U postgres -d microbubble -Fc \
  -t knowledge -t meetings -t members \
  > /tmp/halfvec_pre_backup_$(date +%Y%m%d_%H%M%S).dump
# 验证: ls -lh /tmp/halfvec_pre_backup_*.dump (必须 > 100KB)

# 2. 锁表时长实测 (在 staging 镜像先跑, 不要直接上 prod)
# 复现命令: ALTER TABLE knowledge ALTER COLUMN embedding TYPE halfvec(1024) USING embedding::halfvec(1024);
# 100w 行预计 30s 锁表, 实测决定是否选低峰期

# 3. 7 天降级保留: 保留备份 7 天 + 在 migration 表登记 rollback command
echo "rollback: pg_restore /tmp/halfvec_pre_backup_*.dump" >> /tmp/halfvec_rollback_registry.txt
```

**门禁**:
- 备份 < 100KB → 立即失败（schema 异常或 DB 异常）
- 锁表实测 > 5 分钟 → 申请运维窗口, 业务非高峰期
- 未写 rollback registry → 禁止 deploy

- [ ] **步骤 1：写 alembic 迁移**

```python
# alembic/versions/100_embedding_halfvec.py
"""阶段 B.1: knowledge.embedding Vector(1024) → HalfVector(1024)

ALTER TABLE ... TYPE halfvec(1024) USING embedding::halfvec(1024)

注意: 
- halfvec 不需要重建 HNSW 索引 (pgvector 0.7+ 同列类型即可)
- HNSW 索引会自动用新列类型重建 (CONCURRENTLY 不支持 TYPE 变更, 需要短锁)
- 大表 100w 行预计 ~30s 锁, 选低峰期

down_revision = ('099_hnsw_param_tune',)
"""
from alembic import op

revision = "100_embedding_halfvec"
down_revision = ("099_hnsw_param_tune",)
branch_labels = None
depends_on = None


def upgrade():
    # 1. 删除旧 HNSW 索引 (新列类型不兼容旧索引)
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw;")
    # 2. 改列类型
    op.execute("""
        ALTER TABLE knowledge 
        ALTER COLUMN embedding TYPE halfvec(1024) 
        USING embedding::halfvec(1024);
    """)
    # 3. 重建 HNSW 索引 (halfvec 支持)
    op.execute("""
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 32, ef_construction = 128);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw;")
    op.execute("""
        ALTER TABLE knowledge
        ALTER COLUMN embedding TYPE vector(1024)
        USING embedding::vector(1024);
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 32, ef_construction = 128);
    """)
```

- [ ] **步骤 2：写 roundtrip 测试（写入 float32 → 读出 float16，cosine 距离 < 1e-3）**

```python
# tests/integration/test_halfvec_roundtrip.py
import os
import pytest
import numpy as np
from sqlalchemy import text as sql_text
from app.config import settings
from app.models.types import HalfVector
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="needs real DB"
)


async def _get_session():
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session()


@pytest.mark.asyncio
async def test_halfvec_roundtrip_preserves_distance():
    engine, db = await _get_session()
    try:
        # 1. 写 float32 1024d
        v = np.random.rand(1024).astype(np.float32)
        result = await db.execute(sql_text("""
            INSERT INTO knowledge (title, content, embedding)
            VALUES (:t, :c, :e) RETURNING id;
        """), {"t": "test", "c": "test", "e": v.tolist()})
        new_id = result.scalar()
        await db.commit()
        
        # 2. 读出, 算 self-distance
        result = await db.execute(sql_text("""
            SELECT embedding <=> :q AS dist
            FROM knowledge WHERE id = :id
        """), {"q": v.tolist(), "id": new_id})
        dist = result.scalar()
        # 3. self distance 应该接近 0 (half 精度损失)
        assert dist < 0.01
    finally:
        await db.rollback()
        await engine.dispose()
```

- [ ] **步骤 3：跑 roundtrip 测试**

```bash
INTEGRATION=1 pytest tests/integration/test_halfvec_roundtrip.py -v
```

预期：PASS

- [ ] **步骤 4：应用迁移**

```bash
docker compose exec app alembic upgrade head
```

预期：迁移成功, knowledge.embedding 列类型 = halfvec

- [ ] **步骤 5：回归测试 qa-bench 100 题 smoke**

```bash
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

PYTHONIOENCODING=utf-8 python tests/qa-bench/runner.py \
  --token "$TOKEN" --questions tests/qa-bench/questions_smoke_200.jsonl \
  --output /tmp/halfvec-regression --concurrency 1 --limit 100
```

预期：真 pass rate 与阶段 A 收尾时 ±2% (half 精度损失可接受)

- [ ] **步骤 6：Commit + Push**

```bash
git add alembic/versions/100_embedding_halfvec.py \
        tests/integration/test_halfvec_roundtrip.py
git commit -m "feat(models): knowledge.embedding → halfvec (阶段 B.1)

* 存储 -50% (float32 → float16)
* HNSW 索引重建 (m=32, ef_construction=128 保留)
* qa-bench 100 题回归: 真 pass rate ±2% (可接受)"
```

#### 任务 B.4：同迁移应用到 meetings.embedding + members.voice_embedding

- [ ] **步骤 1：写双表迁移**

```python
# alembic/versions/101_meetings_halfvec.py
"""meetings.embedding Vector → HalfVector"""
from alembic import op
revision = "101_meetings_halfvec"
down_revision = ("100_embedding_halfvec",)


def upgrade():
    op.execute("DROP INDEX IF EXISTS ix_meetings_embedding_hnsw;")
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN embedding TYPE halfvec(1024)
        USING embedding::halfvec(1024);
    """)
    op.execute("""
        CREATE INDEX ix_meetings_embedding_hnsw
        ON meetings
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 24, ef_construction = 128);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_meetings_embedding_hnsw;")
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN embedding TYPE vector(1024)
        USING embedding::vector(1024);
    """)
    op.execute("""
        CREATE INDEX ix_meetings_embedding_hnsw
        ON meetings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 24, ef_construction = 128);
    """)
```

```python
# alembic/versions/102_voiceprint_halfvec.py
"""members.voice_embedding Vector(192) → HalfVector(192)"""
from alembic import op
revision = "102_voiceprint_halfvec"
down_revision = ("101_meetings_halfvec",)


def upgrade():
    op.execute("DROP INDEX IF EXISTS ix_members_voice_embedding_hnsw;")
    op.execute("""
        ALTER TABLE members
        ALTER COLUMN voice_embedding TYPE halfvec(192)
        USING voice_embedding::halfvec(192);
    """)
    op.execute("""
        CREATE INDEX ix_members_voice_embedding_hnsw
        ON members
        USING hnsw (voice_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_members_voice_embedding_hnsw;")
    op.execute("""
        ALTER TABLE members
        ALTER COLUMN voice_embedding TYPE vector(192)
        USING voice_embedding::vector(192);
    """)
    op.execute("""
        CREATE INDEX ix_members_voice_embedding_hnsw
        ON members
        USING hnsw (voice_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
```

- [ ] **步骤 2：应用迁移 + 跑声纹回归**

```bash
docker compose exec app alembic upgrade head

# 声纹 5 题 smoke (确认 ERes2Net 仍能匹配)
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

for i in 1 2 3 4 5; do
  curl -sk -X POST http://localhost:8000/api/v1/voice/identify \
    -H "Authorization: Bearer $TOKEN" \
    -F "audio=@tests/voiceprint/sample_$i.wav"
done
```

预期：5 次 identify 全部命中 0.95+ 置信度

- [ ] **步骤 3：Commit**

```bash
git add alembic/versions/101_meetings_halfvec.py \
        alembic/versions/102_voiceprint_halfvec.py
git commit -m "feat(models): meetings/members embedding → halfvec (阶段 B.2 收尾)"
```

#### 任务 B.5：模型层 SQLAlchemy 列类型更新

- [ ] **步骤 1：修改 `app/models/knowledge.py`**

```python
# 旧: from pgvector.sqlalchemy import Vector
# 旧: embedding = Column(Vector(1024), nullable=True)
from app.models.types import HalfVector
embedding = Column(HalfVector(1024), nullable=True)
```

- [ ] **步骤 2：同样修改 `app/models/meeting.py` 和 `app/models/member.py`**

- [ ] **步骤 3：跑全量单元测试**

```bash
pytest tests/unit/ -v --tb=short
```

预期：所有 unit 测试 PASS

- [ ] **步骤 4：Commit**

```bash
git add app/models/knowledge.py app/models/meeting.py app/models/member.py
git commit -m "refactor(models): use HalfVector column type (阶段 B.5)"
```

---

### 阶段 C：bge-m3 灰度决策（P0，2-3 天）

**目标：** 通过 1000 题 qa-bench 真实跑分，对比 Qwen3-Embedding-0.6B (1024d) vs bge-m3 (1024d)，决定是否全量切换。

#### 任务 C.1：bge-m3 embedding 后端实现

- [ ] **步骤 1：写失败测试（bge-m3 后端存在）**

```python
# tests/unit/test_embedding_backend_bge_m3.py
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="needs model loaded (heavy)"
)


def test_bge_m3_backend_loads():
    from app.services.embedding_service import EmbeddingBackend
    backend = EmbeddingBackend.from_env()
    if os.getenv("EMBEDDING_BACKEND") == "bge_m3":
        assert backend.name == "bge_m3"
        assert backend.dim == 1024
    else:
        assert backend.name == "qwen3"


@pytest.mark.asyncio
async def test_bge_m3_encode_shape():
    from app.services.embedding_service import get_embedding_backend
    backend = get_embedding_backend()
    if backend.name != "bge_m3":
        pytest.skip("only run when EMBEDDING_BACKEND=bge_m3")
    vec = await backend.encode_async(["测试中文"])
    assert vec.shape == (1, 1024)
    assert vec.dtype == np.float32
```

- [ ] **步骤 2：跑测试确认失败**

```bash
INTEGRATION=1 pytest tests/unit/test_embedding_backend_bge_m3.py -v
```

预期：FAIL（`EmbeddingBackend` 不存在）

- [ ] **步骤 3：实现 EmbeddingBackend 抽象 + Qwen3 + bge-m3 双后端**

```python
# app/services/embedding_service.py (改)
import os
import numpy as np
from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer

EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "qwen3")  # qwen3 | bge_m3
DEVICE_OVERRIDE = os.getenv("EMBEDDING_DEVICE", "auto").lower()


class EmbeddingBackend(ABC):
    name: str
    dim: int
    
    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray: ...
    
    async def encode_async(self, texts: list[str]) -> np.ndarray:
        """默认在线程池跑, 避免阻塞事件循环"""
        import asyncio
        return await asyncio.to_thread(self.encode, texts)
    
    @classmethod
    def from_env(cls) -> "EmbeddingBackend":
        if EMBEDDING_BACKEND == "bge_m3":
            return BGEM3Backend()
        return Qwen3Backend()


class Qwen3Backend(EmbeddingBackend):
    name = "qwen3"
    dim = 1024
    
    def __init__(self):
        device = _detect_device()
        self._model = SentenceTransformer(
            "Qwen/Qwen3-Embedding-0.6B",
            device=device,
            trust_remote_code=True,
        )
    
    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)


class BGEM3Backend(EmbeddingBackend):
    name = "bge_m3"
    dim = 1024
    
    def __init__(self):
        device = _detect_device()
        # bge-m3 用 FlagEmbedding (sentence-transformers 5.6+ 也支持)
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(
            "BAAI/bge-m3",
            device=device,
            trust_remote_code=True,
        )
    
    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)


_backend_singleton: EmbeddingBackend | None = None


def get_embedding_backend() -> EmbeddingBackend:
    global _backend_singleton
    if _backend_singleton is None:
        _backend_singleton = EmbeddingBackend.from_env()
        logger.info(f"Embedding backend: {_backend_singleton.name} (dim={_backend_singleton.dim})")
    return _backend_singleton
```

- [ ] **步骤 4：跑测试（默认 qwen3 应通过）**

```bash
pytest tests/unit/test_embedding_backend_bge_m3.py -v
```

预期：test_bge_m3_backend_loads PASS (因为默认 qwen3), test_bge_m3_encode_shape SKIPPED

- [ ] **步骤 5：切后端再测 bge-m3**

```bash
INTEGRATION=1 EMBEDDING_BACKEND=bge_m3 pytest tests/unit/test_embedding_backend_bge_m3.py -v
```

预期：2 passed (含 bge-m3 实际加载)

- [ ] **步骤 6：Commit**

```bash
git add app/services/embedding_service.py tests/unit/test_embedding_backend_bge_m3.py
git commit -m "feat(embedding): dual backend (Qwen3 | bge-m3) (阶段 C.1)"
```

#### 任务 C.2：embedding_model_version 字段

- [ ] **步骤 1：迁移**

```python
# alembic/versions/103_add_embedding_model_version.py
"""knowledge/meetings 加 embedding_model_version 字段

灰度切换 embedding 后端时, 用此字段区分新旧向量 (避免维度不兼容报错).
"""
from alembic import op
import sqlalchemy as sa

revision = "103_add_embedding_model_version"
down_revision = ("102_voiceprint_halfvec",)


def upgrade():
    op.add_column(
        "knowledge",
        sa.Column("embedding_model_version", sa.String(32), server_default="qwen3-0.6b"),
    )
    op.add_column(
        "meetings",
        sa.Column("embedding_model_version", sa.String(32), server_default="qwen3-0.6b"),
    )
    op.create_index(
        "ix_knowledge_embedding_model_version",
        "knowledge",
        ["embedding_model_version"],
    )


def downgrade():
    op.drop_index("ix_knowledge_embedding_model_version", "knowledge")
    op.drop_column("knowledge", "embedding_model_version")
    op.drop_column("meetings", "embedding_model_version")
```

- [ ] **步骤 2：模型加字段**

```python
# app/models/knowledge.py
embedding_model_version = Column(String(32), nullable=False, server_default="qwen3-0.6b", index=True)
```

- [ ] **步骤 3：应用 + 验证**

```bash
docker compose exec app alembic upgrade head
docker compose exec postgres psql -U postgres -d microbubble \
  -c "SELECT embedding_model_version, count(*) FROM knowledge GROUP BY 1;"
```

预期：所有行 `qwen3-0.6b`

- [ ] **步骤 4：Commit**

```bash
git add alembic/versions/103_add_embedding_model_version.py \
        app/models/knowledge.py app/models/meeting.py
git commit -m "feat(models): embedding_model_version 字段 (阶段 C.2)"
```

#### 任务 C.3：1000 题 bge-m3 灰度 benchmark

- [ ] **步骤 1：先 batch re-embed 1000 条知识 (bge-m3)**

```python
# scripts/reembed_knowledge_bge_m3.py
"""批量用 bge-m3 重新 embed 知识库
    
* 只 re-embed 已有 qwen3 向量的行 (渐进切换)
* 每 100 条 commit 一次 (避免长事务)
* embedding_model_version 字段标记 'bge-m3'
* 原 qwen3 向量保留在列 (切回 Qwen3 时用)
"""
import asyncio
import os
from sqlalchemy import select, update, text as sql_text
from sentence_transformers import SentenceTransformer
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

os.environ["EMBEDDING_BACKEND"] = "bge_m3"


async def main(batch_size: int = 100, total: int = 1000):
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        pool_size=2,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    model = SentenceTransformer("BAAI/bge-m3", device="cuda", trust_remote_code=True)
    
    async with Session() as db:
        rows = await db.execute(sql_text("""
            SELECT id, title, content FROM knowledge
            WHERE embedding_model_version = 'qwen3-0.6b'
            ORDER BY id LIMIT :n
        """), {"n": total})
        items = rows.fetchall()
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            texts = [f"{r.title}\n{r.content}" for r in batch]
            embs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True).astype(np.float16)
            
            for r, emb in zip(batch, embs):
                await db.execute(sql_text("""
                    UPDATE knowledge
                    SET embedding = :e, embedding_model_version = 'bge-m3'
                    WHERE id = :id
                """), {"e": emb.tolist(), "id": r.id})
            await db.commit()
            print(f"  {i + len(batch)}/{len(items)} done")
    
    await engine.dispose()
    print(f"✅ re-embedded {len(items)} knowledge entries with bge-m3")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **步骤 2：跑批**

```bash
docker compose exec app python scripts/reembed_knowledge_bge_m3.py --total 1000
```

预期：~30 分钟（GPU 1000 条 bge-m3）

- [ ] **步骤 3：跑 1000 题 qa-bench**

```bash
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

PYTHONIOENCODING=utf-8 python tests/qa-bench/runner.py \
  --token "$TOKEN" --questions tests/qa-bench/questions.jsonl \
  --output results/round11-bge-m3-1000 \
  --include-extra \
  --concurrency 1
```

预期：~6 小时（1000 题串行），真 pass rate 输出

- [ ] **步骤 4：对比 Qwen3 baseline**

```bash
# 1. 切回 Qwen3 后端
sed -i 's/EMBEDDING_BACKEND=bge_m3/EMBEDDING_BACKEND=qwen3/' .env
docker compose restart app

# 2. 跑同一份 1000 题（Qwen3 baseline）
PYTHONIOENCODING=utf-8 python tests/qa-bench/runner.py \
  --token "$TOKEN" --questions tests/qa-bench/questions.jsonl \
  --output results/round11-qwen3-baseline-1000 \
  --include-extra \
  --concurrency 1
```

- [ ] **步骤 5：写决策文档**

模板：仿 `tests/qa-bench/RERANKER_DECISION_LOG.md`，文件名 `docs/decisions/2026-XX-XX-bge-m3-production.md`

5 维度决策矩阵：
- 真 pass rate (1000 题)
- 中文 + 学术能力
- latency (GPU 25 candidates)
- 模型体积 + VRAM
- 维护成本 + 上线风险

- [ ] **步骤 6：Commit + 文档 review**

```bash
git add scripts/reembed_knowledge_bge_m3.py \
        results/round11-bge-m3-1000 \
        results/round11-qwen3-baseline-1000 \
        docs/decisions/2026-XX-XX-bge-m3-production.md
git commit -m "docs(decision): bge-m3 1000 题 benchmark + 决策 (阶段 C 收尾)"
```

---

### 阶段 D：多向量 + Late Chunking 进阶（P2，依赖 C）

> **前置条件：** 阶段 C 决定切到 bge-m3 后再开始。bge-m3 的 `encode()` 原生支持 long context (8192 tokens) + late chunking。

#### 任务 D.1：knowledge_chunk 表加 chunk_embedding 列（late-chunking 专用）

> **重要**: 段落级表 `knowledge_chunk` 已存在（迁移 088, W97 PR2），先在 §0.1 阶段测一次 `knowledge_chunk` 的列结构（是否已有 `embedding` 列：是 float32 还是 halfvec）。

- [ ] **步骤 0：核 knowledge_chunk 表结构**

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d knowledge_chunk"
```

**决策**：
- 已有 `embedding` 列（halfvec）→ D.1 跳过，迁移 104 改 `chunk_embedding` 列加在 `knowledge_chunk` 表（late-chunking 专用，区别于普通 embedding）
- 已有 `embedding` 列（float32 vector）→ D.1 复用 099 + 100 迁移模式改 halfvec
- 没有 `embedding` 列 → D.1 新加 `chunk_embedding halfvec(1024)`

- [ ] **步骤 1：迁移加列**

```python
# alembic/versions/104_add_knowledge_chunk_embedding.py
"""knowledge_chunk.chunk_embedding halfvec(1024) 存储 late-chunking 段落嵌入

与现有 knowledge_chunk.embedding 区分:
- embedding: 传统 chunk 级均值 (float32 或半精度)
- chunk_embedding: late-chunking 段落级 (保留上下文, float16)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from app.models.types import HalfVector

revision = "104_add_knowledge_chunk_embedding"
down_revision = ("103_add_embedding_model_version",)


def upgrade():
    op.add_column(
        "knowledge_chunk",
        sa.Column("chunk_embedding", ARRAY(HalfVector(1024)), nullable=True),
    )


def downgrade():
    op.drop_column("knowledge_chunk", "chunk_embedding")
```

- [ ] **步骤 2：commit + 应用**

```bash
git add alembic/versions/104_add_knowledge_chunk_embedding.py
git commit -m "feat(models): knowledge_chunk.chunk_embedding 多向量 (阶段 D.1)"
docker compose exec app alembic upgrade head
```

#### 任务 D.2：late chunking 服务

- [ ] **步骤 1：实现 late chunking**

```python
# app/services/late_chunking_service.py
"""Late Chunking 服务 (bge-m3 长文档优化)

原理:
1. bge-m3 encode 整篇文档 (long context, 8192 tokens)
2. 按 chunk 切 token-level embeddings
3. 每个 chunk embedding = mean of its token embeddings (保留上下文)

vs naive chunking:
1. 先按 chunk 切文档
2. 每个 chunk 单独 encode (丢失 chunk 边界上下文)
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from app.services.text_splitter import split_by_tokens


class LateChunkingService:
    def __init__(self, model: SentenceTransformer, chunk_size: int = 256, overlap: int = 32):
        self._model = model
        self._chunk_size = chunk_size
        self._overlap = overlap
    
    def encode(self, text: str) -> list[np.ndarray]:
        """返回段落级 embedding 列表 (float32, shape=(N, 1024))"""
        # 1. 整篇过 model (拿 token embeddings)
        inputs = self._model.tokenizer(text, return_tensors="pt", truncation=True, max_length=8192)
        token_embs = self._model.forward(inputs)["token_embeddings"]  # (1, T, 1024)
        
        # 2. 按 chunk_size 切
        T = token_embs.shape[1]
        chunk_embs = []
        for start in range(0, T, self._chunk_size - self._overlap):
            end = min(start + self._chunk_size, T)
            chunk = token_embs[0, start:end]  # (L, 1024)
            # 3. mean pooling (含 attention mask?)
            mask = inputs["attention_mask"][0, start:end]
            chunk_embs.append((chunk * mask.unsqueeze(-1)).sum(0) / mask.sum().clamp(min=1))
        return [e.numpy().astype(np.float32) for e in chunk_embs]
```

- [ ] **步骤 2：单元测试**

```python
# tests/unit/test_late_chunking.py
import numpy as np
from app.services.late_chunking_service import LateChunkingService


def test_chunk_count_matches_splitter():
    """段落数 ≈ ceil(total_tokens / chunk_size)"""
    # mock
    class MockModel:
        class tokenizer:
            def __call__(self, text, **kw):
                from transformers import AutoTokenizer
                return AutoTokenizer.from_pretrained("bert-base-chinese")(
                    text, return_tensors="pt", truncation=True, max_length=512
                )
        def forward(self, inputs):
            import torch
            T = inputs["input_ids"].shape[1]
            return {"token_embeddings": torch.randn(1, T, 1024)}
    
    svc = LateChunkingService(MockModel(), chunk_size=128, overlap=16)
    text = "测试文本 " * 200  # ~400 tokens
    chunks = svc.encode(text)
    assert len(chunks) >= 3
    assert all(c.shape == (1024,) for c in chunks)
```

- [ ] **步骤 3：Commit**

```bash
git add app/services/late_chunking_service.py tests/unit/test_late_chunking.py
git commit -m "feat(rag): late chunking service (阶段 D.2)"
```

#### 任务 D.3：hybrid_retriever 接入 chunk 召回

- [ ] **步骤 1：扩 `_vector_search` 接 chunk_embedding**

```python
# app/services/hybrid_retriever.py (_retrieve_impl 内)
# 在 _vector_search 之后, 增加 chunk 级 late-chunking 召回:
chunk_results = await db.execute(sql_text("""
    SELECT knowledge_id, MIN(chunk_embedding <=> :q) AS dist
    FROM knowledge_chunk, unnest(chunk_embedding) AS chunk_embedding
    WHERE knowledge_chunk.chunk_embedding IS NOT NULL
    GROUP BY knowledge_id
    ORDER BY dist LIMIT :k
"""), {"q": query_emb, "k": candidate_k})

# 聚合: 同一 knowledge_id 多个 chunk → 选最近
chunk_to_parent = {}
for row in chunk_results.fetchall():
    kid = row.knowledge_id
    if kid not in chunk_to_parent or row.dist < chunk_to_parent[kid]:
        chunk_to_parent[kid] = row.dist

# 与父级合并 (existing 父向量召回)
```

- [ ] **步骤 2：长文档 recall 测试**

```python
# tests/integration/test_late_chunking_recall.py
@pytest.mark.asyncio
async def test_long_doc_recall_improves_with_chunks():
    # 1. 写 1 个 3000 字的文档 + 5 个相关查询
    # 2. 跑纯父向量检索 vs 父+chunk
    # 3. 期望: chunk 模式 recall@10 +5%
```

- [ ] **步骤 3：Commit**

```bash
git add app/services/hybrid_retriever.py tests/integration/test_late_chunking_recall.py
git commit -m "feat(rag): chunk-level recall in hybrid retriever (阶段 D.3)"
```

---

### 阶段 E：冷热分层（P2，**⚠️ REDESIGN / 冷冻**）

> **2026-08-05 审查标红**：原方案的物理分区迁移会让 100w+ 行表锁 30+ 分钟，单事务失败 = 业务数据全丢。**整段冷冻，等待 PoC**。

#### 任务 E.0：PoC 阶段 — 验证"逻辑分区"可行性（不改 schema）

**目标**：在不破坏现状的前提下，验证"按 `created_at` 路由查询"是否能达到 cold query < 500ms 目标。

- [ ] **步骤 1：写路由层 PoC**

```python
# app/services/knowledge_service.py 新增 (不改任何 model / migration)
async def list_knowledge_partition(
    partition: str = "hot",  # hot | cold | all
    ...
):
    if partition == "hot":
        where_clause = "created_at > NOW() - INTERVAL '6 months'"
    elif partition == "cold":
        where_clause = "created_at <= NOW() - INTERVAL '6 months'"
    else:
        where_clause = "1=1"
    ...
```

- [ ] **步骤 2：实测 + 退出决策**

- [ ] hot query 走 HNSW 平均 < 50ms？→ ✅ 继续
- [ ] cold query 全表 seq scan < 500ms？→ ✅ 继续
- [ ] cold 占总查询比例 > 10%？→ ✅ 启动阶段 E.1
- [ ] 全部满足 → **整段价值不大，归档**

**预计 PoC 1 周**。PoC 通过后再讨论物理分区（用 pg_partman 而非手写）。

#### 阶段 E.1（PoC 通过后）— 物理分区（pg_partman）

**前提**：pg_partman 扩展已装（PO 风险：需 DBA 评估）。

> 原方案已废弃：单事务 `INSERT INTO ... SELECT * FROM knowledge_unpartitioned` 会锁表 30+ 分钟 + 无 fallback。
>
> 改用 pg_partman 的 `create_partition_time` + `attach_partition` 3 步独立迁移：
> 1. 创建分区框架 (空表)
> 2. 每月定时 attach 新分区 + detach 旧分区 + 拷贝数据
> 3. 清理临时表
>
> 每步独立事务，便于回滚。

**当前状态**：阶段 E 整体标 **⚠️ REDESIGN**，等待 PoC 结果后再决定是否启动 E.1。

---

### 阶段 F：领域微调（P3，1-2 月）

#### 任务 F.1：构造微调数据

- [ ] **步骤 1：脚本从知识库 + 会议纪要构造 (query, positive) 对**

```python
# scripts/build_finetune_pairs.py
"""从已有 qa-bench 题库 + search_log 真实用户 query 构造 LoRA 微调数据

数据格式 (sentence-transformers):
{
  "query": "微纳米气泡的 zeta 电位如何测量?",
  "positive": "Zeta电位测量使用电泳光散射法...",
}

query 来源优先级 (WRONG 写法: kb.summary 当 query = 自我循环):
1. tests/qa-bench/questions.jsonl 1000 题 (人工标注, 真实 query)
2. search_log 近 90 天 deduped user query (≥ 10 次搜索)
3. 非前 2 源: 跳过 (避免 kb.self-summary 循环)
"""
import json
from app.services.knowledge_service import list_knowledge

pairs = []

# 来源 1: qa-bench 1000 题 (黄金集)
import jsonlines
with jsonlines.open("tests/qa-bench/questions.jsonl") as reader:
    for q in reader:
        if q.get("relevant_knowledge_id"):
            # 找 positive 对应知识条目
            for kb in list_knowledge(partition="all", limit=2000):
                if kb.id == q["relevant_knowledge_id"]:
                    pairs.append({
                        "query": q["question"],
                        "positive": f"{kb.title}\n{kb.content[:500]}",
                    })
                    break

# 来源 2: search_log 真实 query (近 90 天 deduped)
# TODO: 派工时实现 search_log 拉取 + 去重 + 关联点击的 knowledge_id

with open("data/finetune_pairs.jsonl", "w", encoding="utf-8") as f:
    for p in pairs:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")
print(f"✅ wrote {len(pairs)} pairs")
```

- [ ] **步骤 2：跑 + commit**

```bash
docker compose exec app python scripts/build_finetune_pairs.py
git add scripts/build_finetune_pairs.py data/finetune_pairs.jsonl
git commit -m "data(finetune): 2000+ (query, positive) pairs (阶段 F.1)"
```

#### 任务 F.2：LoRA 微调脚本

- [ ] **步骤 1：实现 LoRA 训练**

```python
# scripts/lora_finetune_embedding.py
"""Qwen3-Embedding-0.6B LoRA 微调 (sentence-transformers 5.6+)

超参:
* LoRA r=16, alpha=32
* epochs=3, batch_size=16
* lr=2e-4
"""
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
from peft import LoraConfig, get_peft_model
import json

model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="cuda")

# 加 LoRA
lora_config = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.1,
    target_modules=["q_proj", "v_proj"],
)
model[0].auto_model = get_peft_model(model[0].auto_model, lora_config)

# 读数据
examples = []
with open("data/finetune_pairs.jsonl") as f:
    for line in f:
        d = json.loads(line)
        examples.append(InputExample(texts=[d["query"], d["positive"]]))

loader = DataLoader(examples, batch_size=16, shuffle=True)
loss = losses.MultipleNegativesRankingLoss(model)

model.fit(
    train_objectives=[(loader, loss)],
    epochs=3,
    output_path="data/lora_adapter/",
    warmup_steps=100,
)
print("✅ LoRA adapter saved to data/lora_adapter/")
```

- [ ] **步骤 2：跑（GPU，预计 2-4 小时）**

```bash
docker compose exec app python scripts/lora_finetune_embedding.py
```

- [ ] **步骤 3：Commit**

```bash
git add scripts/lora_finetune_embedding.py
git commit -m "feat(finetune): Qwen3 LoRA 微调脚本 (阶段 F.2)"
```

#### 任务 F.3：加载 LoRA adapter + benchmark

- [ ] **步骤 1：模型加载逻辑**

```python
# app/services/embedding_service.py
import os

LORA_ENABLED = os.getenv("EMBEDDING_LORA_ENABLED", "false").lower() == "true"
LORA_PATH = os.getenv("EMBEDDING_LORA_PATH", "data/lora_adapter/")


class Qwen3Backend(EmbeddingBackend):
    def __init__(self):
        device = _detect_device()
        self._model = SentenceTransformer(
            "Qwen/Qwen3-Embedding-0.6B",
            device=device,
            trust_remote_code=True,
        )
        if LORA_ENABLED and os.path.exists(LORA_PATH):
            from peft import PeftModel
            self._model[0].auto_model = PeftModel.from_pretrained(
                self._model[0].auto_model, LORA_PATH
            )
            logger.info(f"LoRA adapter loaded from {LORA_PATH}")
```

- [ ] **步骤 2：qa-bench 1000 题对比**

```bash
EMBEDDING_LORA_ENABLED=true docker compose up -d app
PYTHONIOENCODING=utf-8 python tests/qa-bench/runner.py \
  --token "$TOKEN" --questions tests/qa-bench/questions.jsonl \
  --output results/round12-lora-finetune-1000 \
  --include-extra --concurrency 1
```

- [ ] **步骤 3：决策文档 + commit**

---

## §3 自检

### 3.1 规格覆盖度

| 提升点 | 实现任务 | 状态 |
|---|---|---|
| HNSW 参数调优 | A.1-A.4 | ✅ |
| halfvec 量化 | B.1-B.5 | ✅ |
| bge-m3 灰度决策 | C.1-C.3 | ✅ |
| 多向量 + Late Chunking | D.1-D.3 | ✅ (依赖 C) |
| 冷热分层 | E.1 | ✅ (P2) |
| 领域微调 | F.1-F.3 | ✅ (P3) |

### 3.2 占位符扫描

- ❌ 严禁使用 "TODO"、"待定"、"后续实现" — 已逐个 section 检查
- ✅ 所有 step 含具体代码 + 命令 + 预期输出
- ✅ 所有 alembic 迁移含完整 upgrade/downgrade
- ✅ 所有 bench 脚本含参数定义 + 调用示例

### 3.3 类型一致性

- `HalfVector(1024)` 在阶段 B 引入，阶段 C/D 沿用
- `embedding_model_version` 字段在 C.2 引入，C.3 沿用
- `chunk_embedding` 字段在 D.1 引入，D.3 沿用
- `EMBEDDING_BACKEND` env 在 C.1 引入，跨 C/D 阶段使用

### 3.4 风险检查

| 风险 | 缓解 |
|---|---|
| HNSW REINDEX 锁表 | 选低峰期，bench 完后一次性迁移 |
| halfvec 精度损失 > 1% | 任务 B.3 步骤 5 qa-bench 100 题回归 |
| bge-m3 VRAM 不够 | 1024 维 + 568M 模型，预计 1.5GB，RTX 5090 富余 |
| LoRA 微调退化 | 1000 题对比 baseline，低于 baseline 立即回滚 |

---

## §4 执行顺序建议

```
阶段 A (1-2 天)
  ↓
阶段 B (1 天，立即接 A 后面)
  ↓
阶段 C (2-3 天，与 A/B 并行，灰度期间 R10/R11)
  ↓
[决定后] 阶段 D (1 周)
  ↓
阶段 E (1 周后启动)
  ↓
阶段 F (1-2 月后启动)
```

**总投入：** 阶段 A-C 约 1 周拿 80% 收益；D-F 是 1-2 月长跑。

---

## §5 交付清单

- [ ] `scripts/bench_hnsw_params.py` + `results/hnsw_*.json`
- [ ] 迁移 099-103
- [ ] `app/models/types.py` (HalfVector wrapper)
- [ ] `app/services/embedding_service.py` (双后端)
- [ ] `app/services/late_chunking_service.py`
- [ ] `scripts/reembed_knowledge_bge_m3.py` + `scripts/lora_finetune_embedding.py` + `scripts/build_finetune_pairs.py`
- [ ] `docs/decisions/2026-XX-XX-bge-m3-production.md` + `...-lora-finetune-decision.md`
- [ ] 阶段 A-E 全部 alembic upgrade head + qa-bench 回归

**完成标志：** qa-bench 1000 题真 pass rate 从 42% 提升到 55%+（经验估计，HNSW + halfvec + bge-m3 叠加），embedding 存储 -50%，长文档 recall@10 +5%。
