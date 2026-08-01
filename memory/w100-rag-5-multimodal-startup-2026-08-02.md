# W100-RAG-5 Multimodal Retriever 启动记录

- 日期: 2026-08-02
- base ref: `49b6b7640aa2112b5bea429d89b7a9c5610dd89d`
- branch: `worktree-agent-w100-rag-5`
- worktree: `E:\microbubble-agent\.claude\worktrees\w100-rag-5`
- `git rev-list --count base..HEAD`: 0
- alembic HEAD: `095_add_rag_citation_metrics`; 本批 096 明确接 095

## 仓库实情

1. 多模态模型位于 `app/models/knowledge_multimodal.py`，实际类名为 `KnowledgeImage`，表名为 `knowledge_images`；不存在独立 image embedding 字段。
2. OCR 统一接口是 `OCRBackend.analyze`，不是 `extract_text`；本批不直接调用 OCR，只读取 `ocr_status=done` 且有 `ocr_text` 的记录。
3. 双塔策略按实情调整：query 侧复用 `get_or_compute_query_embedding` 缓存，candidate 侧批量调用 `generate_embeddings` 实时计算 OCR 文本向量。
4. HybridWeights 第五路需要同步扩展 dataclass 字段、`__post_init__` 白名单、`from_dict` 缺键读取和 `apply_weights` method map；已有函数签名保持不变。

## 边界

- 不改 `knowledge_service.py` / `rag_evaluator.py` / `reranker_service.py`。
- `hybrid_retriever.py` 仅在 `retrieve_with_weights` body 追加 image hook，不改任何 def 签名。
- 新 migration 只向 `search_logs` ADD nullable `image_score`。
