# W-N-E 冷热分层路由 PoC - 起步 (2026-08-05)

> **派工 anchor**: W-N-E +0 (本文件) → +1 路由层 PoC → +2 bench 决策 → +3 收口
> **Plan**: `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` §2 阶段 E.0 (修订版)
> **Base head**: `fb4343f29` (W-N-D late chunking 收口)
> **Alembic head**: `104_add_knowledge_chunk_late_embedding` 守恒

---

## §1 起步 6 项 (W73 铁律)

### 1.1 base 验证 (类 20.46/97)

```bash
$ git log --oneline -3
fb4343f29 docs(memory): W-N-D late chunking 起步 + 收口沉淀
740aafbde fix(rag): W-N-D 收口 (hybrid_retriever 接入 + alembic 串单链)
39866b375 feat(rag): late chunking 服务 + 104 迁移 + 多向量召回
```

base = `fb4343f29` ✓

### 1.2 alembic 守恒

```bash
$ python -m alembic heads
104_add_knowledge_chunk_late_embedding (head)
```

1 head 守恒 ✓

### 1.3 Postgres 可达

```bash
$ docker ps --filter "name=db-1"
microbubble-agent-db-1   Up 5 hours (healthy)
```

✓

### 1.4 **实测: knowledge 表 created_at 分布 (派工 brief 必加项)**

| 指标 | knowledge (主表) | knowledge_chunks (W-N-D) |
|---|---|---|
| 总行数 | **530** | 37 |
| oldest | 2026-05-17 20:26:11 | 2026-08-04 10:39:29 |
| newest | 2026-07-30 10:45:29 | 2026-08-05 08:43:23 |
| **hot** (≤ 6 months) | **530** (100%) | 37 (100%) |
| **cold** (> 6 months) | **0** | 0 |

**year/month 分布**:
- 2026-05: 12 行
- 2026-06: 183 行
- 2026-07: 335 行

**类 20.153 实战发现 (W-N-E 据实上报)**: 当前 production knowledge 库是 5 个月的项目,5/17 起的全部数据都在 6 个月内 (NOW() - 6 months = 2026-02-05)。**真实 cold 数据 = 0 行**,PoC cold query bench 必须用**全表 seq scan** 模拟 cold,因为:
1. 数据库没有 > 6 个月的真实数据
2. 物理上"cold partition"是一个空集合,latency 必然接近 0 (但无意义)
3. 唯一可证明 cold 价值的实测 = 在 530 行 HNSW 全表上跑 vs HNSW + `created_at` 过滤,看索引是否对分区有效

**HNSW 索引实测**:
- `idx_knowledge_embedding` (knowledge.embedding halfvec_cosine_ops) ✓
- `ix_knowledge_chunks_embedding_hnsw` (knowledge_chunks.embedding vector_cosine_ops) ✓
- `ix_knowledge_content_tsvector` (gin content_tsvector) ✓
- `ix_knowledge_search_text_trgm` (gin search_text gin_trgm_ops) ✓

**created_at 索引**: ❌ **无 B-tree 索引** (重要发现,见 1.5)

### 1.5 **W-N-E 范畴内** (派工 brief 严禁跨)

可动:
- `app/services/cold_hot_router.py` (新文件)
- `app/services/knowledge_service.py` (新增 `list_knowledge_partition` 方法,不动既有)
- `tests/integration/test_cold_hot_routing.py` (新文件)
- `scripts/bench_cold_hot_routing.py` (新文件)
- `results/cold_hot_routing_bench_2026-08.json` (新文件)
- `docs/decisions/2026-08-05-cold-hot-routing-poc.md` (新文件)
- `memory/w-n-e-cold-hot-poc-{startup,closure}-2026-08-05.md` (新文件)

不可动 (派工 brief 严禁):
- ❌ `app/services/hybrid_retriever.py` (W-N-D 范畴)
- ❌ `app/agent/chat_engine.py` (方案 C 6 铁律)
- ❌ `alembic/versions/` (PoC 不动 schema)
- ❌ DFT 集成 dirty 文件 (已 commit)
- ❌ W-N-A/B/C/D commits
- ❌ plan 文件

### 1.6 决策门禁 (派工 brief 严禁跳过)

3 决策门禁:
1. **hot < 50ms?** → 继续 / ❌ 暂停
2. **cold < 500ms?** → 继续 / ❌ 暂停
3. **cold 占总查询比例 > 10%?** → 启动 E.1 物理分区 / ❌ 整段价值不大, 归档

**第 3 门禁的特殊处理**: 派工 brief 写"cold 占总查询比例",但**真实 cold 数据 = 0**,PoC 实测必然是 cold/total = 0%。这意味着"路由层 PoC"在当前数据规模下**没有冷热价值**(还没产生 cold 数据)。决策应据实报告:PoC 本身完整跑通(代码+bench+门禁),但 cold 价值 = 0% → 派工 brief 决策: "❌ 整段价值不大, 归档"。

---

## §2 类 20 实战沉淀 (W-N-E 新增)

### 类 20.153 (新增, 永久铁律)
**PoC cold/hot 分布实测必做**: 任何"冷热分层"PoC 派工,起步必跑 `SELECT MIN/MAX(created_at), COUNT(*) FILTER hot, COUNT(*) FILTER cold FROM <table>`。0 cold 数据的 PoC 仍有意义(证明路由层代码可工作),但**第 3 决策门禁 "cold > 10%" 必然 FAIL** → 据实归档。

### 类 20.154 (新增, 永久铁律)
**PoC 不动 schema 铁律**: 任何 PoC 派工严禁改 `alembic/versions/`。本次 PoC 是"逻辑分区"(只加路由层),不是物理分区(不需要 schema)。判断标准: 看任务 brief 是否要求 `alembic/versions/1XX_xxx.py` 新增,没有就是 PoC。

### 类 20.155 (新增, 永久铁律)
**HNSW 索引对分区是否生效**: pgvector HNSW 是**全表索引**(无分区概念),`WHERE created_at > ...` 不会让 HNSW 更快。冷热分区的真实价值 = 物理分区后,每个分区有独立 HNSW 索引,索引内存占用按分区分布。当前 530 行无意义,100w+ 行才有意义。

---

## §3 关键决策 (W-N-E +1 实施时守恒)

1. **路由层逻辑** (派工 brief 简化版): 关键字匹配 `["去年", "上个月", "去年", "2025", "2024"]` → cold, else hot。**不**接 LLM 时间意图提取(派工 brief 已简化)。
2. **`list_knowledge_partition` 方法签名**: 派工 brief 写 `partition: str = "hot"`,**不**改既有 `list_knowledge` 签名,作为新方法。
3. **`threshold_months: int = 6`**: 派工 brief 默认值。也可参数化。
4. **bench 用真实 Postgres**: `DATABASE_URL` env, 连接 `microbubble-agent-db-1` (host network 或 `localhost:5432` 端口映射)。

---

## §4 起步确认

- [x] 6 项起步 100% 实测
- [x] 类 20.153/154/155 沉淀
- [x] 0 schema 改动守恒 (无 alembic 改)
- [x] 0 production code 改动 (仅新文件 + 1 个新方法)
- [x] 锚点 W-N-E +0 (本文件)
- [x] 决策门禁路径已规划 (cold 0% → 第 3 门禁 FAIL → 据实归档)
