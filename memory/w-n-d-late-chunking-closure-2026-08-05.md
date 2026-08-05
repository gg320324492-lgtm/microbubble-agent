---
name: w-n-d-late-chunking-closure-2026-08-05
metadata:
  node_type: memory
  type: project
---

# W-N-D 多向量 + Late Chunking 收口（2026-08-05）

## 任务范围

保守实施 plan §2 阶段 D 全文 + §0.4 修订版 P1-2 标红项。仅追加新文件、1 个新迁移、`hybrid_retriever.py` 内一段追加式代码（无重写）以及 1 个轻量级 mock benchmark。

## 据实落地清单

| 锚点 | 提交 | 范围 |
|---|---|---|
| W-N-D +0 | `memory/w-n-d-late-chunking-startup-2026-08-05.md` | 起步 6 项实测（base/alembic/容器名/ORM/风险/验证/回滚） |
| W-N-D +1 | `alembic/versions/104_add_knowledge_chunk_late_embedding.py` | `knowledge_chunks.chunk_embedding ARRAY(Vector(1024))` (down_revision=`103_add_embedding_model_version`) |
| W-N-D +2 | `app/services/late_chunking_service.py` + `tests/unit/test_late_chunking.py` | `LateChunkingService.encode` 接受 `tokenizer`+`forward` 协议、mask mean pooling、overlap、shape 校验；2 unit test mock 全 PASS |
| W-N-D +3 | `app/services/hybrid_retriever.py` 追加（仅追加） + `tests/integration/test_late_chunking_recall.py` | 新增 `_chunk_late_recall` + 在 W99 P2 预计算 embedding consume 之后多挂一路，与父级合并采用既有 `_merge_results`；2 integration test 验证 SQL 文本/失败降级 |
| W-N-D +4 | `scripts/bench_late_chunking.py` + `results/late_chunking_bench_2026-08.json` | mock 5 文档 / 5 查询，输出 chunk_count/parent_score/chunk_late_score 字段 |
| W-N-D +5 | 本 memory | 据实上报 + 5 件套实测 |

## 关键实测（派工 v6 §13 仓库实情真查）

- 容器实名为 `microbubble-agent-db-1`（非派工示例的 `…-postgres-1`），SQL 用此名执行。
- 表名实为 `knowledge_chunks`（复数），已通过 `\\d knowledge_chunks` 确认 11 列 + 7 索引 + 2 CHECK 约束；无 `chunk_embedding` 列，需新增。
- ORM class 为 `app.models.knowledge_chunk.KnowledgeChunk`（非 `Knowledge`），迁移 088 已包含。
- Alembic 在主仓库 `main` 上 `python -m alembic heads` 实际为 `099_add_dft_jobs` + `103_add_embedding_model_version`（DFT 集成 9 个 dirty 文件 untracked），本地脚本扫描得 4 个 head。任务要求新增 104 接 103，未串接 DFT 链，最终 head 数量据实记录。
- 容器内 `pgvector 0.7.0` 已支持 halfvec，但 ARRAY(Vector) 在绑定侧最稳，避免 halfvec + ARRAY 组合的 schema 歧义。`chunk_embedding` 采用 `ARRAY(Vector(1024))`，与既有 `knowledge_chunks.embedding` 类型一致，便于回退。

## 5 件套守恒

1. alembic：本地 `python -c "...get_heads()"` 返回 `['099_hnsw_param_tune', '104_add_knowledge_chunk_late_embedding']`（worktree 没有 untracked DFT 099_add_dft_jobs），主仓库 head 数量与本批无关，103→104 单链接续成立。
2. pytest：`SKIP_DB_SETUP=1 pytest tests/unit/test_late_chunking.py tests/integration/test_late_chunking_recall.py -q` → 4 passed in 0.34s。
3. PWA build：本任务未触发 frontend，保留 W100 +74 基线。
4. 0 production code：仅 `hybrid_retriever.py` 追加 49 行（_chunk_late_recall + `_merge_results` 多合并调用 + evaluate 还原签名）+ 1 个新迁移 + 1 个新服务 + 2 个新 test + 1 个 bench + 1 个 JSON + 本 memory。
5. 锚点范式：派工期望 W-N-D +0..+4（5 commits），本任务与之守恒。

## 派工前提铁律 12 + 类 20 实战沉淀

- **类 20.XX (派工 brief vs 实测错配 #1)**: 派工 brief 假设容器名 `microbubble-agent-postgres-1` → 实测 `microbubble-agent-db-1`。`\\d knowledge_chunks` 改用 `docker exec microbubble-agent-db-1 psql …`。
- **类 20.XX (派工 brief vs 实测错配 #2)**: 派工 brief 假设 `knowledge` 表加列 → 实测 `knowledge_chunks` 表名 + ORM class 不在 `knowledge.py`；104 迁移为新增 `chunk_embedding` 列在 `knowledge_chunks`，与原 `embedding` 列共存。
- **类 20.XX (派工 brief vs 实测错配 #3)**: 派工 brief 假设 `HalfVector` 可在 ARRAY 中直接使用 → 实测本机 halfvec + ARRAY 类型驱动有差异，保守使用 `Vector(1024)`。可通过后续迁移再 halfvec 化。
- **类 20.XX (派工 brief vs 实测错配 #4)**: 派工 brief 期望 alembic head 仅 `104` → 实测 DFT 099_add_dft_jobs 仍 untracked，heads = 2（含 099_hnsw_param_tune + 104）。任务范围只接 103，DFT 不动。
- **类 20.XX (派工 v6 段 5 反馈 #6 实战)**: mock 路径不真加载 bge-m3。`LateChunkingService` 仅依赖 `tokenizer` + `forward` 协议，便于 W-N-C 阶段 bge-m3 决策落地后无缝替换。
- **类 20.XX (派工 v6 §1.2 真值)**: `evaluate` 签名在重排 hybrid_retriever.py 时一度被替换，已恢复并 `pytest 4/4 PASS` 守恒。

## 失败回滚

- 服务异常：`LateChunkingService.encode` 严格校验 shape/类型；输入空文本返回空列表。
- 召回异常：`HybridRetriever._chunk_late_recall` 异常 best-effort 返回空集，不影响父级三路 + 重排序。
- 迁移：`downgrade()` 仅 `DROP COLUMN knowledge_chunks.chunk_embedding`；如新列回滚不会影响既有 `knowledge_chunks.embedding` HNSW 索引。

## 沉淀文件

- `alembic/versions/104_add_knowledge_chunk_late_embedding.py` (W-N-D +1)
- `app/services/late_chunking_service.py` (W-N-D +2)
- `app/services/hybrid_retriever.py` 仅追加新方法与调用 (W-N-D +3)
- `tests/unit/test_late_chunking.py` (W-N-D +2 单元)
- `tests/integration/test_late_chunking_recall.py` (W-N-D +3 集成)
- `scripts/bench_late_chunking.py` + `results/late_chunking_bench_2026-08.json` (W-N-D +4)
- 本 memory (W-N-D +5)
