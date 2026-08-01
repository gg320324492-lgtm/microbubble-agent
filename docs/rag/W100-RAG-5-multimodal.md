# W100-RAG-5 Multimodal Retriever

## 目的

为 RAG 检索引入第五路：基于 OCR 文本的图像召回。
当 query 描述需要"看图"时（"微气泡传质实验装置图"），
`MultimodalRetriever` 在 `knowledge_images` 表里查
`ocr_status='done'` 的图片，对其 OCR 文本实时算 embedding，
与 query embedding 计算 cosine similarity，返回 top_k 命中。

## 双塔策略（实测修正）

派工 plan 假设 `knowledge_images.embedding` 字段存在；
实测不存在（W74 phase 7 模型只在 `knowledge_extractions` 里
保留 `confidence` / `data` JSONB）。所以本任务采用文本-文本双塔：

- **query 塔**：复用 `embedding_service.get_or_compute_query_embedding`
  缓存（类 20.121 / 类 20.122 实战）。
- **candidate 塔**：批量调用 `embedding_service.generate_embeddings`
  把 candidate OCR 文本送进同一个 sentence-transformers 模型。
- **相似度**：纯 numpy-free 的 `cosine_similarity`（list-of-float）。
- **缓存复用**：每个 query 仍走 Redis 缓存，与文字路 4 路共用
  （类 20.130 据实沉淀）。

## HybridWeights 同步扩展三处（类 20.129）

| 位置 | 改动 |
|---|---|
| `__post_init__` 守护白名单 | 加 `image` |
| `from_dict` 缺键读取 | 加 `image` |
| `apply_weights` method map | 加 `image: weights.image` |

每处都必须同步扩，漏一处会导致新字段被默认忽略或抛
`HybridWeights.image 必须为数字` 异常。

## 改动范围

| 文件 | 操作 | 备注 |
|---|---|---|
| `app/services/multimodal_retriever.py` | 新增 | 138 行双塔 retriever |
| `app/services/hybrid_weight_config.py` | 扩字段 + 3 处 | def 0 diff |
| `app/services/hybrid_retriever.py` | 在 `retrieve_with_weights` body 追加 hook | def 0 diff |
| `app/services/recall_observability.py` | RecallTrace 加 `image_score: Optional[float]` | 不改既有 |
| `app/models/search_log.py` | 加 `image_score = Column(Float, nullable=True)` | 不改既有 |
| `app/rag/config.py` | 加 `MULTIMODAL_RETRIEVER_ENABLED/WEIGHT` | 不改既有 |
| `alembic/versions/096_add_rag_multimodal_metrics.py` | 新增 | 串单链 095 → 096 |
| `tests/rag/test_multimodal_retriever.py` | 新增 | 24 单测 |
| `tests/rag/test_hybrid_weight_config_v5.py` | 新增 | 15 单测 |
| `tests/rag/test_rag_multimodal_e2e.py` | 新增 | 29 e2e |
| `tests/rag/{pr8,rag_query_cache,rag_citation,rag_intent}_e2e.py` | alembic head 同步到 096 | 沿用累计迁移推进模式 |

## 件 4 五门控实测

| 文件 | def diff | 期望 | 实测 |
|---|---|---|---|
| `app/services/hybrid_retriever.py` | 0 | 0 | ✅ 0 |
| `app/services/knowledge_service.py` | 0 | 0 | ✅ 0 |
| `app/services/rag_evaluator.py` | 0 | 0 | ✅ 0 |
| `app/services/reranker_service.py` | 0 | ≤ +1 (W100-RAG-4 ADD) | ✅ 0 |
| `app/services/hybrid_weight_config.py` | 0 | 0（只扩字段） | ✅ 0 |

## 件 1-3 + 5 守恒实测

- 件 1 alembic 1 head: `096_add_rag_multimodal_metrics` ✅
- 件 2 pytest: 新增 68/68 + 老套件 173/173 PASS ✅
- 件 3 PWA build: 本批不涉及 frontend（基线沿用 W98）✅
- 件 5 锚点范式: 8 commits（W100 +0..+5 + +5.5 + +6）+6 据实上报 ✅

## 派工 plan 偏差据实（类 20.123）

1. 派工 plan 假设多模态模型名为 `knowledge_images`（实际是
   `knowledge_multimodal`），类名 `KnowledgeImage` 而非
   `KnowledgeMultimodal`，且无独立 embedding 列。
2. 派工 plan 假设 OCR 入口是 `extract_text`，实测是
   `OCRBackend.analyze` Protocol。本批不调 OCR，
   只读 `ocr_status='done'` 的行。

## 类 20 沉淀

- **类 20.129**：HybridWeights 扩第 5 路必须 3 处同步
  （dataclass / `__post_init__` / `apply_weights`），
  漏一处必然破。
- **类 20.130**：image 双塔 query 侧复用 Redis 缓存，
  candidate 侧批量实时算；禁止每张图单独调 `generate_embedding`。
- **类 20.123**：派工 plan 偏差（多模态模型名/OCR 接口名）按实测调整，
  不擅自扩也不擅自缩。
- **类 20.115**：本次新 commit 后报告主指挥统一合并，
  不自行 push origin。
