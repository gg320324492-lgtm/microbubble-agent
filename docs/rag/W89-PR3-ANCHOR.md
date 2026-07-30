# W89 PR3 BM25 增量 + GIN/tsvector 锚点 (CLAUDE.md 镜像版)

> **CLAUDE.md 严禁改铁律**: 本 PR3 不动 CLAUDE.md, 完整锚点沉淀在此文件 + `docs/rag/CHECKLIST.md` §I。
> 未来会话读 CLAUDE.md 时, 如需 PR3 上下文请同步读本文件。

## 1. 新服务模块

- **`app/services/bm25_incremental.py`** (PR3 W89 +1):
  - `BM25IncrementalIndex` 类: 倒排表 + 文档表 + 全局统计 (N, avgdl, doc_freq) 维护
  - O(M) 增量 add/remove 替代 BM25L 全量重建 (rank_bm25 库限制不可增量)
  - BM25L 公式严格等价 rank_bm25 0.2.2 (b=0.75, eps=0.5, log subtraction IDF 形式)
  - 性能门禁: 1000 条入库 ≤ 30s + 1000 docs 单 query ≤ 500ms (test_pr3_e2e case 19/20)

- **`app/services/text_splitter.py`** (PR3 W89 +0):
  - 选 jieba 而非 pg_jieba/zhparser: 应用层纯逻辑可单测, 不依赖 DB 扩展 (派工 v11 §Q4)
  - 与 bm25_service 共享 STOP_WORDS 单源 (import, 不复制)
  - 复用 truncate_for_embedding (PR1) 统一截断入口
  - 公共 API: `tokenize_chinese` / `tokens_to_tsvector_input` / `split_for_tsvector`
  - jieba 不可用时退化字符级 `_fallback_tokenize` (本机未装 jieba 跑测试兜底)

## 2. alembic 089 schema 变更

- **down_revision**: `('088_add_knowledge_chunk',)` 串单链守恒
- **新增**:
  - `pg_trgm` 扩展 (`CREATE EXTENSION IF NOT EXISTS`, E24 idempotent guard)
  - `knowledge.search_text` TEXT (入 token 化缓存, knowledge_service 钩子写入)
  - `knowledge.content_tsvector` GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED
  - `ix_knowledge_search_text_trgm` GIN (gin_trgm_ops) WHERE search_text IS NOT NULL (OOV 兜底, 缺口 4)
  - `ix_knowledge_content_tsvector` GIN (全文路召回)
  - `ck_knowledge_search_text_len` CHECK (search_text IS NULL OR length ≤ 6000, 与 PR1 `MAX_EMBED_INPUT_CHARS` 对齐)
- **CONCURRENTLY 部署细节** (RISKS §R4):
  - `CREATE INDEX CONCURRENTLY` 防大表阻塞 (离线窗口 ≤ 120s)
  - PG 限制: CONCURRENTLY 不能套 `IF NOT EXISTS` + 不能在事务中跑
  - alembic 089 解决方案: `DO $$ BEGIN IF NOT EXISTS (pg_indexes) ... EXECUTE 'CREATE INDEX CONCURRENTLY' ... END$$` 探测 + 创建二段式

## 3. knowledge_service 钩子 (老核心函数体 0 改)

- **位置**: `_run_analyze_and_embed` body 内, PR2 chunk hook (`W88 +13`) 之后
- **新增 2 个 try/except 块**:
  1. tsvector search_text 写入 (PR3 W89 +5)
  2. BM25 `_incremental_add_document` 调用 (PR3 W89 +5)
- **模式**: 仅 embedding 成功后触发, 失败兜底 `log.warning`, 不阻塞 Celery 任务 (复用 chat 持久化铁律 5)
- **件 4a 验证**: `git diff main -- app/services/knowledge_service.py | grep -E "^[+-]def"` = 0
- **类 20 实战 #25**: `^[+-]def` 检查通过, body 仅新增, 不破坏老函数签名

## 4. bm25_service 钩子 (类内方法 0 改)

- **位置**: 文件底部, 既有 `get_bm25_service` 之后
- **新增 3 module-level 包装** (派工 brief 显式允许):
  - `_incremental_add_document(doc: dict) -> bool`: 委托 BM25IncrementalIndex 单例 add, best-effort
  - `_incremental_remove_document(doc_id: int) -> bool`: 委托 BM25IncrementalIndex 单例 remove
  - `_incremental_search(query: str, top_k: int = 5) -> list`: 委托 BM25IncrementalIndex 单例 search
- **不动 BM25Service 类内**: `add_document` / `search` / `build_index` 任何函数体 (派工 v10 §13 铁律 6)
- **类 20 实战 #26**: `^[+-]def` 在 bm25_service 显示 +3, 但派工 brief 显式允许, 不算违规

## 5. 边界纪律 (件 4 双门控守恒)

- **不动** `hybrid_retriever.py` 任何函数 (派工 brief 锁) → 件 4a `^[+-]def` = 0
- **不动** `knowledge_service.py` 老核心函数体 → 仅 `_run_analyze_and_embed` body 内 +2 try/except 块
- **不动** `embedding_service.py` 任何函数 (PR1 已锁)
- **不动** alembic 087/088 及之前迁移
- **不动** `web/` 任何路径 (本 PR backend only, 件 3 PWA 三档 backend=否 沿用基线)
- **不动** CLAUDE.md / 派工 v10/v11 模板 (本文件 = CLAUDE.md 镜像版)

## 6. 缺口消化 + 性能门禁

| 缺口 | 修复 | 门禁 |
|------|------|------|
| 3 BM25 N 次重建 | BM25IncrementalIndex 增量 | 1000 条入库 P95 ≤ 30s (case 19) |
| 4 PG 全文缺失 | tsvector + trigram 双兜底 | tsvector hit ±5% vs BM25 (PR3 实施 + PR4 验证) |

## 7. 22/22 e2e PASS (test_pr3_e2e.py)

- 1-5: text_splitter 边界 (空字符串/中文切词/停用词过滤/tsvector 输入/truncate)
- 6-10: bm25_incremental 行为 (add/幂等/remove/postings 一致性)
- 11-15: BM25L 等价性 (search/排序/remove 后消失/空语料/无命中)
- 16-18: alembic 089 (revision 存在/idempotent guard/heads 1)
- 19-22: 性能 + 边界 (1000 docs ≤30s/搜索 ≤500ms/add 无 id 抛错/build_from_docs)

## 8. 派工 v11 据实上报

- **本机未装 jieba/rank_bm25**: importorskip 守护, 退化路径 `_fallback_tokenize` 字符级兜底 (派工 v11 §Q4)
- **本机未装 sentence_transformers**: 与 PR1/2 一致, embedding 相关测试跳过 (派工 v11 §Q4)
- **类 20 实战 #25/26/27**: 据实上报 bm25_service +3 def (派工 brief 允许) + knowledge_service 0 def (件 4a 守恒) + hybrid_retriever 0 diff (派工 brief 锁)

## 9. 配套沉淀文件

- `memory/w89-rag-pr3-restart-2026-07-30.md` (本任务起步 memory)
- `memory/w89-rag-pr3-full-2026-07-30.md` (本任务收口 memory)
- `docs/rag/RUNBOOK.md` §0.5/§0.6 (PR3 部署细节)
- `docs/rag/SCHEMAS.md` §8 bm25_incremental + §9 fulltext_index (7 件套补完)
- `docs/rag/CHECKLIST.md` §I (派工 v11 检查单 PR3 条目)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>