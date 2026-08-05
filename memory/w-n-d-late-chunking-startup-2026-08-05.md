---
name: w-n-d-late-chunking-startup-2026-08-05
metadata:
  node_type: memory
  type: project
---

# W-N-D 多向量 + Late Chunking 起步（2026-08-05）

## 任务背景

阶段 D 实施范围为 `knowledge_chunks` 已存在表上的 late-chunking 专用多向量列、纯服务层 late chunking、保守追加式 chunk 召回和轻量 mock benchmark。禁止改 plan、DFT dirty 文件、chat_engine、embedding_service、web 或旧 migration。

## 1. Base head 守恒

派工要求 base=`cce90de9a`，实际仓库 `main` 在检查时已前进到 DFT 集成 commit `5c609663b`；工作树分支起点包含 W-N-A 与 W-N-C。此阶段不修改 DFT 文件。`git log --oneline -3` 已核验。

## 2. Alembic 实测

本地脚本扫描显示现有代码 head 不止预期：tracked 的 `103_add_embedding_model_version` 接 `102_voiceprint_halfvec`，另有未跟踪 `alembic/versions/099_add_dft_jobs.py` 接同一上游，故 `python -m alembic heads` 实测为 `099_add_dft_jobs` 与 `103_add_embedding_model_version` 两个 head。D 阶段 104 按任务要求接 103，不修改或串接 DFT 文件；最终 head 数量将据实记录。

容器实测使用名为 `microbubble-agent-db-1`（不是派工示例的 postgres 名）。`\\d knowledge_chunks` 确认表为复数 `knowledge_chunks`，已有 `embedding vector(1024)`、HNSW 索引，尚无 `chunk_embedding`。ORM class 实测为 `app.models.knowledge_chunk.KnowledgeChunk`，不是 `app.models.knowledge.py` 中的 class。

## 3. 文件与范围清单

- 新增 `alembic/versions/104_add_knowledge_chunk_late_embedding.py`
- 新增 `app/services/late_chunking_service.py`
- 仅追加 `app/services/hybrid_retriever.py` 的 chunk late recall 方法/调用（不重写既有检索逻辑）
- 新增 unit/integration tests、mock benchmark、结果 JSON、closure memory
- 不改 `app/models/knowledge.py`：既有 ORM embedding 保持不动，migration 为新增专用列提供 schema。

## 4. 风险表

| 风险 | 控制 |
|---|---|
| DFT dirty 文件与 migration 形成双 head | 不碰 DFT；104 明确接 103，heads 据实上报 |
| `knowledge_chunks` 名称/ORM 错配 | 已用容器 `\\d` + `KnowledgeChunk` 源码双确认 |
| halfvec ARRAY 驱动支持差异 | migration 仅新增 nullable 列；服务/测试 mock 与 DB 异常 best-effort |
| late chunking token 输出结构变化 | 服务兼容 dict/对象 output、attention mask，严格 shape 校验 |
| 旧检索回归 | chunk 召回独立追加、异常静默降级，跑定向及 SKIP_DB_SETUP=1 套件 |

## 5. 验证策略

严格 TDD：先写失败测试，再实现并跑 unit；迁移静态/heads 检查；集成测试使用 mock AsyncSession，不要求真实模型。最后运行相关 pytest（含 `SKIP_DB_SETUP=1`）、bench `--help`/mock 输出及 git diff 审计。

## 6. 失败回滚

每个 W-N-D 锚点独立提交。服务/召回异常返回空 chunk 结果，不影响父级检索。迁移 downgrade 删除新增 `chunk_embedding` 列；若 heads 因未跟踪 DFT 仍为双头，保留事实，不擅自改 DFT 链。

## 模型可用性

`sentence_transformers` 5.6.0 可 import；bge-m3 权重未要求下载。本机采用注入 mock model 验证 token-level 输出、mask mean pooling、overlap 和 1024 维 shape。
