# Chunking Service 派工模板 (PR2 RAG 系列)

> **用途**: RAG 大改造 PR2 (chunking service) 派工模板
> **适用 PR 范围**: PR2 (chunking service + rag_chunks 表)
> **依赖前序 PR**: PR1 (Embedding 一致性) 已合并 main HEAD
> **目标锚点范式区间**: W86 第 1 批 320 → W86 mini-3 322 (+2, 守恒 +1 实施 +1)
> **CLAUDE.md 引用章节**:
> - "服务层结构" 节 (knowledge_service.py 当前职责, chunking 是其扩展)
> - "2026-06-29 #043 账号持久化聊天历史" 段 7 — 异步不阻塞 (chunking 应异步任务)
> - "派工 v4 铁律 3 实战" — 实施前 plans 真验证
> - "派工前提铁律 12 第 5 条" — 实施前必先 information_schema 实查
> - `docs/rag-templates/alembic-migration-template.md` — rag_chunks 表 schema 模板

---

## 派工 v10 段 0-9 内容 (主拍预填, agent 实施时按段实拍)

### 段 0: down_revision 接续关系 (必填首行)

```bash
# 派工 prompt 第 1 行必含 down_revision (派工前提铁律 12 第 11 条)
down_revision = "086_backfill_drive_file_versions"
# alembic 088_rag_chunks.py 已派 B 路线 agent 实施, 本 PR2 实施时必须等 088 合并入 main
```

### 段 1: 派工范围 (PR2 chunking service 主体)

```
- 新增 app/services/chunking_service.py (主拍决策: 独立 service 文件, 不入 knowledge_service.py)
- 新增 app/api/rag_chunks.py (5 端点: GET / POST / DELETE / POST /search / GET /{id})
- 新增 app/tasks/chunking_tasks.py (Celery 异步 chunking 任务, 入 Celery beat schedule)
- 新增 tests/test_chunking_service.py + tests/test_chunking_e2e.py (单测 + e2e)
- alembic 088_rag_chunks.py (B 路线 alembic agent 已派, 本 PR2 仅 verify 已合并)
```

### 段 2: 分块策略选项 (3 选 1, 主拍拍板)

#### 策略 A: 800 字窗口 + 100 字重叠 (W3 推荐, 工程简单)

```python
# app/services/chunking_service.py
from typing import List

WINDOW_SIZE = 800   # 中文字符数
OVERLAP = 100       # 重叠字符数

def chunk_text_window(text: str) -> List[dict]:
    """800 字窗口 + 100 字重叠, 简单滑动窗口"""
    chunks = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(start + WINDOW_SIZE, len(text))
        chunk_content = text[start:end]
        chunks.append({
            "chunk_index": chunk_index,
            "content": chunk_content,
            "token_count": len(chunk_content),
        })
        chunk_index += 1
        if end == len(text):
            break
        start += WINDOW_SIZE - OVERLAP
    return chunks
```

**优点**: 实现简单, 无 NLP 依赖
**缺点**: 中文按字计数不精确, 可能切碎段落

#### 策略 B: 段落 + 标题 (W3 推荐, 中文友好)

```python
# app/services/chunking_service.py
import re
from typing import List

HEADING_PATTERNS = [
    r'^#+\s',          # Markdown ## 标题
    r'^第[一二三四五六七八九十]+章',  # 中文章节
    r'^\d+\.\d+',      # 1.1 / 2.3 编号
]

def chunk_text_paragraph(text: str) -> List[dict]:
    """按段落 + 标题切分, 中文友好"""
    chunks = []
    chunk_index = 0
    current_chunk = ""
    for line in text.split('\n'):
        is_heading = any(re.match(p, line) for p in HEADING_PATTERNS)
        if is_heading and current_chunk:
            chunks.append({
                "chunk_index": chunk_index,
                "content": current_chunk.strip(),
                "token_count": len(current_chunk),
            })
            chunk_index += 1
            current_chunk = ""
        current_chunk += line + "\n"
    if current_chunk:
        chunks.append({
            "chunk_index": chunk_index,
            "content": current_chunk.strip(),
            "token_count": len(current_chunk),
        })
    return chunks
```

**优点**: 保持段落完整性, 中文标题友好
**缺点**: 长段落可能超 800 字 (需 max chunk size 兜底)

#### 策略 C: 中文章节 (W3 备选, PDF/PPTX 提取后用)

```python
# app/services/chunking_service.py
import re

def chunk_text_chinese_section(text: str) -> List[dict]:
    """中文章节切分: 1.x.x / 第 X 章 / (一)"""
    section_pattern = re.compile(r'(第[一二三四五六七八九十百零]+章|\d+\.\d+(?:\.\d+)?|[（(][一二三四五六七八九十]+[）)])')
    parts = section_pattern.split(text)
    chunks = []
    chunk_index = 0
    for i in range(1, len(parts), 2):
        heading = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        content = heading + body
        chunks.append({
            "chunk_index": chunk_index,
            "content": content.strip(),
            "token_count": len(content),
        })
        chunk_index += 1
    return chunks
```

**优点**: 适合中文学术论文 / 课题组文档
**缺点**: 需预定义模式, 维护成本高

**主拍决策 (派工时拍板)**: 默认策略 B (段落 + 标题), 通过 `CHUNKING_STRATEGY` settings 切换。

### 段 3: parent_id FK 约束 (派工前提铁律 12 第 5 条实查)

```sql
-- alembic/versions/088_rag_chunks.py (B 路线 alembic agent 已派)
-- 本段为 PR2 实施时 verify 用, 必查 FK 约束存在
SELECT conname, conrelid::regclass, confrelid::regclass, confdeltype
FROM pg_constraint
WHERE conrelid::regclass::text = 'rag_chunks'
  AND contype = 'f';
-- 期望: 至少 2 行
--   rag_chunks_knowledge_id_fkey  → knowledge.id (CASCADE)
--   rag_chunks_parent_chunk_id_fkey → rag_chunks.id (CASCADE, ON DELETE CASCADE)
```

**Python 端 FK 行为** (CASCADE):
```python
# app/services/chunking_service.py
async def delete_knowledge_chunks(db: AsyncSession, knowledge_id: int) -> int:
    """删除 knowledge 的所有 chunk (FK ON DELETE CASCADE 自动级联 parent_chunk_id)"""
    result = await db.execute(
        delete(RagChunk).where(RagChunk.knowledge_id == knowledge_id)
    )
    await db.commit()
    return result.rowcount
```

**注意**: parent_chunk_id 自引用 FK 用 `ON DELETE CASCADE`, 删除父 chunk 自动级联子 chunk。
**派工 v4 铁律 3 实战**: 实施前必先 information_schema 实查 FK 名 (类 20.7 教训)。

### 段 4: 孤儿 chunk 巡检任务 (Celery beat schedule)

```python
# app/tasks/chunking_tasks.py
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import async_session_factory
import logging

logger = logging.getLogger(__name__)


@shared_task(name="rag.check_orphan_chunks")
async def check_orphan_chunks_task() -> dict:
    """孤儿 chunk 巡检: parent_chunk_id 指向不存在的 chunk_id (FK 已级联, 应为 0 行)"""
    async with async_session_factory() as db:
        result = await db.execute(
            text("""
            SELECT COUNT(*) AS orphan_count
            FROM rag_chunks c
            WHERE parent_chunk_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM rag_chunks p WHERE p.id = c.parent_chunk_id
              );
            """)
        )
        orphan_count = result.scalar()
        if orphan_count > 0:
            logger.error(f"[chunking] ORPHAN CHUNKS DETECTED: {orphan_count} 行")
            return {"orphan_count": orphan_count, "status": "ORPHAN"}
        logger.info(f"[chunking] orphan check PASS: 0 orphan chunks")
        return {"orphan_count": 0, "status": "OK"}
```

**Celery beat 配置** (celery_app.py):
```python
celery_app.conf.beat_schedule["rag-check-orphan-chunks"] = {
    "task": "rag.check_orphan_chunks",
    "schedule": crontab(hour=3, minute=30),  # 每日凌晨 3:30
}
```

**告警**: orphan_count > 0 时 Celery worker logger.error + Sentry 报警 (派工前提铁律 12 第 5 条)。

### 段 5: 异步 chunking 任务 (CLAUDE.md 2026-06-29 段 7 异步不阻塞复用)

```python
# app/tasks/chunking_tasks.py
from celery import shared_task
from app.services.chunking_service import chunk_text_paragraph
from app.services.embedding_service import embed_text
import logging

logger = logging.getLogger(__name__)


@shared_task(name="rag.chunk_knowledge", bind=True, max_retries=3)
def chunk_knowledge_task(self, knowledge_id: int) -> dict:
    """异步 chunking + embedding, 不阻塞 KnowledgeService 上传路径"""
    knowledge = get_knowledge_sync(knowledge_id)  # 同步 DB session
    chunks = chunk_text_paragraph(knowledge.content)
    embeddings = embed_text_batch([c["content"] for c in chunks])  # batch 加速
    save_chunks_with_embeddings_sync(knowledge_id, chunks, embeddings)
    logger.info(f"[chunking] knowledge_id={knowledge_id} → {len(chunks)} chunks")
    return {"knowledge_id": knowledge_id, "chunk_count": len(chunks)}
```

**触发点**: `KnowledgeService.upload()` 末尾触发 `chunk_knowledge_task.delay(knowledge_id)` (CLAUDE.md 2026-06-29 段 7 异步不阻塞复用)。

### 段 6: 派工 brief 据实上报铁律

派工 brief 描述**必须**与实际工作内容一致:
- 派工 brief 写"3 策略可选" → 实际必须实现 ≥ 1 策略 (派工 v10 段 7 19 类实战)
- 派工 brief 写"parent_id FK CASCADE" → 实际必须 `ON DELETE CASCADE` (不是 SET NULL)
- 派工 brief 写"孤儿巡检 Celery beat" → 实际必须接入 beat schedule (不是仅写 task)

类 20.13 实战 19 (W85 D-2 据实上报): 锚点范式 +6 不凑 +7 — PR2 实测 +1/+2 守恒, 不虚报 +3。

### 段 7: 与 PR1/3/5/8 接续关系

| PR | 共享 schema | 依赖 |
|----|------------|------|
| PR1 (Embedding 一致性) | 统一 embedding model (text2vec-base-chinese, 384 dim) | 无 |
| **PR2 (本 PR, chunking)** | rag_chunks 表 (alembic 088) | PR1 |
| PR3 (GIN + tsvector) | rag_chunks.content GIN trgm | **PR2** |
| PR5 (RAGEvaluator) | rag_eval_report 表 | 无 (独立新表) |
| PR8 (rag_search_logs) | rag_search_logs 表 | 无 (独立新表) |

**串单链纪律**: PR3 等 PR2 合并后开工, PR5/PR8 可并行 (见 alembic-migration-template.md 段 6)。

---

## 5 件套验证

| 验证项 | 命令 | 期望 |
|--------|------|------|
| 1. chunking service 存在 | `ls app/services/chunking_service.py` | 文件存在 |
| 2. 3 策略可切换 | `grep -E "CHUNKING_STRATEGY\|chunk_text_window\|chunk_text_paragraph" app/services/chunking_service.py` | ≥ 3 命中 |
| 3. parent_id FK CASCADE | 段 3 实查 SQL | 2 行 (knowledge_id + parent_chunk_id, ON DELETE CASCADE) |
| 4. 孤儿巡检 Celery beat | `grep "rag-check-orphan-chunks" celery_app.py` | 1 行 |
| 5. 异步 chunking task | `grep "rag.chunk_knowledge" app/tasks/chunking_tasks.py` | ≥ 1 命中 |
| 6. e2e PASS | `pytest tests/test_chunking_e2e.py -v` | 全部 PASS |

---

## 据实上报铁律

1. **派工 brief 与实测不符时, 必须据实上报** — 不擅自扩, 不擅自缩 (派工 v10 段 7 19 类实战)
2. **0 hit / 0 改动时不实施** — 例: 派工 brief 写"3 策略"实际只实现 1 策略, 据实上报"1 策略实施 + 2 策略占位"
3. **parent_id FK 必 `ON DELETE CASCADE`** — 不是 SET NULL / RESTRICT, 孤儿巡检发现异常立即报警
4. **Celery beat schedule 必接入** — 不写 beat schedule = 孤儿巡检永远不跑
5. **历史锚点永久保留** — 任何 chunking 实施教训 (e.g. W82 B-2 ios_tts_cache 错配 / W83 C-1 派工偏差) 必入 memory

---

## 引用章节 (CLAUDE.md 永久锚点)

- `## 服务层结构` — knowledge_service.py 当前职责, chunking 是其扩展
- `## 2026-06-29 #043 账号持久化聊天历史` 段 7 — 异步不阻塞 (chunking 应异步任务)
- `## 派工前提铁律 12 + 类 20 实战 18 实例` — 段 5/9 据实上报铁律
- `## 派工 v4 铁律 3 实战` — 实施前 plans 真验证
- `## 派工前提铁律 12 第 5 条` — 实施前必先 information_schema 实查
- `docs/rag-templates/alembic-migration-template.md` — rag_chunks 表 schema 模板

---

**模板版本**: v1.0 (W86 第 1 批 PR2 派工预填, 2026-07-30)
**作者**: support-docs-runbook agent
**沉淀**: memory 主题 9 (W 批 grand closure + 派工纪要 + 锚点范式)