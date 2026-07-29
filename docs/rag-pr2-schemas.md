# KnowledgeChunk Schema (PR2 W88 +19)

> **PR**: RAG v1.1 §3.2 PR2 Knowledge 子表
> **alembic**: `088_add_knowledge_chunk` (down=`087_add_knowledge_original_parent_id`)
> **派工 v10/v11**: docs/w72-prompt-paradigm-v10 + 段 10 v11 新 6 项

## 1. 表结构

```sql
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id              SERIAL PRIMARY KEY,
    knowledge_id    INTEGER NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1024),
    char_start      INTEGER NOT NULL,
    char_end        INTEGER NOT NULL,
    char_count      INTEGER NOT NULL,
    strategy        VARCHAR(20) NOT NULL DEFAULT 'paragraph',
    chunk_metadata  JSONB,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now()
);
```

## 2. 字段说明

| 字段 | 类型 | NOT NULL | 说明 |
|------|------|----------|------|
| `id` | SERIAL | YES | PK |
| `knowledge_id` | INTEGER | YES | FK → knowledge.id ON DELETE CASCADE |
| `chunk_index` | INTEGER | YES | 在 parent 内序号 (0,1,2,...) |
| `content` | TEXT | YES | chunk 原文 |
| `embedding` | vector(1024) | NO | chunk 独立向量 (PR4 召回侧量化) |
| `char_start` | INTEGER | YES | 在 parent.content 的起始位置 |
| `char_end` | INTEGER | YES | 在 parent.content 的结束位置 |
| `char_count` | INTEGER | YES | == char_end - char_start (派生约束) |
| `strategy` | VARCHAR(20) | YES | 'paragraph' / 'heading' / 'window' |
| `chunk_metadata` | JSONB | NO | {section_title?, window_size?, overlap?, ...} |
| `created_at` / `updated_at` | TIMESTAMP | YES | TimestampMixin |

## 3. 约束 (5 项)

| 约束名 | 类型 | 约束 |
|--------|------|------|
| `pk_knowledge_chunks` | PRIMARY KEY | id |
| `fk_kc_knowledge_id` | FOREIGN KEY | knowledge_id → knowledge.id ON DELETE CASCADE |
| `uq_knowledge_chunks_kid_chunk_index` | UNIQUE | (knowledge_id, chunk_index) |
| `ck_knowledge_chunks_char_range` | CHECK | char_start >= 0 AND char_end > char_start |
| `ck_knowledge_chunks_char_count` | CHECK | char_count > 0 AND char_count = char_end - char_start |

## 4. 索引 (3 项)

| 索引名 | 列 | 类型 | 用途 |
|--------|-----|------|------|
| `ix_knowledge_chunks_kid` | knowledge_id | btree | FK 自动 + 加速按 parent 过滤 |
| `ix_knowledge_chunks_kid_strategy` | (knowledge_id, strategy) | btree | 按策略过滤 |
| `ix_knowledge_chunks_embedding_hnsw` | embedding | HNSW (vector_cosine_ops) | 向量召回 (与 knowledge.embedding 一致) |

## 5. 与 knowledge 表关系

```
knowledge (1) ──FK CASCADE── (N) knowledge_chunks
  id                                knowledge_id
  content (2605B avg)               char_start/char_end 指回 parent.content
  embedding Vector(1024)            embedding Vector(1024) (独立, 可空)
```

- 1 parent → N chunk (1.5x ≤ N ≤ 6x, 门禁 a)
- parent 删除 → chunk 自动清 (CASCADE, 门禁 c FK 100% 完整)
- parent.embedding 与 chunk.embedding 独立计算, parent 作 fallback

## 6. ORM (SQLAlchemy)

```python
from app.models.knowledge_chunk import KnowledgeChunk
# __tablename__ = "knowledge_chunks"
# 12 字段 + 5 约束 + 3 索引
```

## 7. 写入路径 (chunking_service)

```python
from app.services.chunking_service import write_chunks_for_knowledge
await write_chunks_for_knowledge(
    knowledge_id=42,
    content=parent_content,  # knowledge.content
    session_factory=sf,
    config=ChunkConfig(strategy="paragraph"),  # 或 heading / window
)
# 返回: 实际写入行数 (int)
```

幂等: DELETE 该 knowledge_id 旧 chunk + INSERT 新 chunk

## 8. 召回路径 (hybrid_retriever)

```python
from app.services.hybrid_retriever import retrieve_chunks_by_vector
chunks = await retrieve_chunks_by_vector(
    db=db,
    query_embedding=query_emb,  # 1024 维
    top_k=10,
    knowledge_id=None,  # 可选过滤
    strategy=None,       # 可选策略过滤
)
# 返回: List[{knowledge_id, chunk_id, chunk_index, content, char_start, char_end,
#           char_count, strategy, similarity, retrieval_method='chunk_vector'}]
```

拼上下文 window: parent.content[max(0, char_start-200):min(len, char_end+200)]