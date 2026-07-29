# PR2 Knowledge Chunk 部署 Runbook

> **PR**: RAG v1.1 §3.2 PR2 Knowledge 子表
> **分支**: `chore/w88-rag-pr2-knowledge-chunk-2026-07-30`
> **alembic**: 087 → 088 (串单链)
> **创建日期**: 2026-07-30
> **派工 v10/v11**: docs/w72-prompt-paradigm-v10 + 段 10 v11 新 6 项

## 0. alembic chain 风险

- **当前 head** (本 PR 前): `087_add_knowledge_original_parent_id` (W85 hotfix)
- **本 PR 新增迁移**: `088_add_knowledge_chunk` (down=087)
- **回滚步骤**: `python -m alembic downgrade -1` (DROP TABLE knowledge_chunks CASCADE)
- **离线窗口**: 预估 < 10s (空表 CREATE, 已有数据按知识条目数 × 5 chunk 估算 INSERT)

## 1. 部署步骤

### 1.1 cp migration 到容器

```bash
docker cp alembic/versions/088_add_knowledge_chunk.py microbubble-agent-app-1:/app/alembic/versions/
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__
docker exec microbubble-agent-app-1 alembic upgrade head
```

### 1.2 验证表创建

```bash
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble \
  -c "\d knowledge_chunks"
```

应见:
- 11 列 (id / knowledge_id / chunk_index / content / embedding / char_start / char_end / char_count / strategy / chunk_metadata / created_at / updated_at)
- 1 FK knowledge_id → knowledge(id) ON DELETE CASCADE
- 2 CheckConstraint (ck_char_range + ck_char_count)
- 1 UniqueConstraint (uq_kid_chunk_index)
- 3 Index (ix_kid + ix_kid_strategy + ix_embedding_hnsw)

### 1.3 重启后端

```bash
docker compose restart app celery-worker
```

### 1.4 验证 22/22 e2e

```bash
SKIP_DB_SETUP=1 python -m pytest tests/rag/test_pr2_e2e.py -v
```

## 2. 验证清单 (5 件套守恒)

| 件 | 阈值 | 命令 |
|----|------|------|
| 1 alembic 1 head | exactly 1 | `python -m alembic heads` 应含 088 |
| 2 baseline pytest | 22/22 PASS | `pytest tests/rag/test_pr2_e2e.py -v --ignore=tests/test_w79_commercial_private_deployment_e2e.py` |
| 3 PWA build | 第 1 层接受 FAIL | `cd web && npm run build` (DERIVE-01 rolldown 修前) |
| 4 0 production code | knowledge_service.py 老核心 diff = 0 (仅 +14 行 hook) | `git diff main -- app/services/knowledge_service.py | wc -l` |
| 5 锚点范式 | W88 +8..+21 锚点全出现 | `git log --grep "W88 +" | wc -l` ≥ 14 |

## 3. 孤儿 chunk 巡检 (W88 +17 配套)

```sql
-- 孤儿 chunk (parent_id 不存在)
SELECT kc.id, kc.knowledge_id
FROM knowledge_chunks kc
LEFT JOIN knowledge k ON k.id = kc.knowledge_id
WHERE k.id IS NULL;

-- 行数异常 (超出 [1.5x, 6x] parent)
SELECT knowledge_id, COUNT(*) AS chunk_count
FROM knowledge_chunks
GROUP BY knowledge_id
HAVING COUNT(*) > 6 OR COUNT(*) < 1.5;

-- char_count 派生漂移
SELECT id, char_start, char_end, char_count
FROM knowledge_chunks
WHERE char_count != char_end - char_start;
```

## 4. 回滚预案

```bash
# 步骤 1: 回滚迁移
python -m alembic downgrade -1
# = DROP TABLE knowledge_chunks CASCADE;

# 步骤 2: (可选) 删除代码
git revert <merge_commit>
```

## 5. 已知风险

- **R1 嵌入不一致**: 沿用 PR1 一致化结果 (PR1 必修完成后再启 PR2)
- **R2 chunking 元数据漂移**: char_count 派生约束 + E22 巡检 SQL 防漂移
- **R8 chunk 表爆炸**: max_chars=6000 fallback window, 上限 parent × 6
- **alembic 串单链**: down_revision 接 ('087_add_knowledge_original_parent_id',) 严格守

## 6. 跨 PR 接口契约 (PR3/4/9 复用)

- **PR3 BM25 增量**: chunk 文本走 PR1 `truncate_for_embedding` 入口
- **PR4 HybridRetriever**: 召回侧量化复用 `retrieve_chunks_by_vector` (本 PR 新增)
- **PR9 auto-research v2**: 新入 KB 时同步写 chunk (复用 `write_chunks_for_knowledge`)

派工 v11 段 7 错误 19 类: E09 chunking 元数据漂移 / E22 派生一致 (本 runbook §3 防)