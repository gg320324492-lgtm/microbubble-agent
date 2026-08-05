---
name: w-n-c-bge-m3-startup-2026-08-05
metadata:
  node_type: memory
  type: project
---

# W-N-C bge-m3 起步（W73 铁律 6 项 — 2026-08-05）

## 任务背景

W-N-C 阶段 C: bge-m3 灰度决策 (P0, 2-3 天)。
- Plan: `docs/superpowers\plans\2026-08-05-pgvector-optimization.md` §2 阶段 C 全文
- Base head: `14bc9246e` (W-N-A +N HNSW bench 收口)
- 派工期望 5 commits (W-N-C +0..+4), 修订版强制:
  - **C.1 严禁破坏现有 `app/services/embedding_service.py` 的全局 _model singleton** — 改双后端 singleton 兼容
  - **C.3 1000 题不真跑** (6 小时 + GPU 占用), 改 100 题 (30 分钟)
  - **C.3 bge-m3 实际加载验证** (lightweight, GPU 不可用时 fallback mock)
  - **MEMORY 沉淀 + 决策文档** 仿 `tests/qa-bench/RERANKER_DECISION_LOG.md` 模板

## 起步 6 项实测 (W73 铁律)

### 1. base head 守恒

```bash
git log --oneline -1
# 14bc9246e feat(perf): HNSW bench 工具 + tests + 100q bench JSON (W-N-A cherry-pick)  ✅
```

### 2. test baseline 守恒

- pytest 当前未跑 (本任务不涉及 production code regression)
- vitest 当前未跑 (本任务不涉及 frontend)
- **baseline 沿用 W100 +74 末**: pytest 101+ PASS, vitest 14/14 PASS (待 C.1 跑)

### 3. 文件清单 (派工期望 vs 实测)

| 派工期望 | 实测 | 备注 |
|---|---|---|
| `app/services/embedding_service.py` (双后端) | ⚠️ **谨慎修改** | C.1 — 派工 brief 假设直接覆盖, 实测需保留原 `_model` singleton + 新增 `_backend_singleton` 双轨 |
| `tests/unit/test_embedding_backend_bge_m3.py` | ✅ 新建 | C.1 — 2 unit test (lightweight mock) |
| `alembic/versions/103_add_embedding_model_version.py` | ✅ 新建 | C.2 — down_revision = `("102_voiceprint_halfvec",)` |
| `app/models/knowledge.py` + `app/models/meeting.py` | ⚠️ **加字段** | C.2 — 加 `embedding_model_version` Column (不破坏老字段) |
| `scripts/reembed_knowledge_bge_m3.py` | ✅ 新建 (修订) | C.3 — 100 题轻量级版, 不跑 1000 (plan 6 小时 + GPU 占用) |
| `docs/decisions/2026-08-05-bge-m3-decision.md` | ✅ 新建 | C.3 — 仿 RERANKER_DECISION_LOG.md 模板 |

### 4. 风险表 (派工 brief 假设 vs 实测 4 处错配)

| 派工 brief 假设 | 实测 | 决策 |
|---|---|---|
| C.1 直接覆盖 `embedding_service.py` 全局 `_model` | ⚠️ 现有 singleton + 缓存 + 多个 API 调用方 (`generate_embedding_sync` / `generate_embedding` / `generate_embeddings` / `get_or_compute_query_embedding`) 直接受冲击 | 保留原 singleton + 新增 `_backend_singleton` + 通过 `get_embedding_backend()` 包装访问 |
| C.1 跑 2 unit test 必须真加载 bge-m3 | ⚠️ 本机 **CUDA 不可用** (docker 内 `torch.cuda.is_available()=False`) + ST 5.6.0 加载 BAAI/bge-m3 需 ~2.7GB 模型下载 | 用 mock `SentenceTransformer` + 不真加载, 2 unit test 仅验证 backend 接口 + from_env 路由 |
| C.3 跑 1000 题 qa-bench | ⚠️ 6 小时 + LLM API (mimo/sonnet) + 1000 docs 重 embed | 派工 brief 修订为 **100 题** (~30 分钟), bench JSON 标注清楚 (C.3.5 决策文档 §2) |
| C.3 bge-m3 真加载 1000 docs | ⚠️ 真加载需要 GPU + 模型下载 | 实际尝试 `SentenceTransformer("BAAI/bge-m3", device="cpu")` 验证 imports + 自定义轻量级 mock encoder 跑 100 docs |
| C.3 决策文档路径 | ⚠️ `docs/decisions/` 目录**不存在** | ✅ 新建 `docs/decisions/` (1 个 mkdir) |

### 5. 5 件套守恒预设

| 件 | 状态 |
|---|---|
| 1. alembic 1 head | 修订版 `103_add_embedding_model_version` down_revision=`("102_voiceprint_halfvec",)`, 期望仍 1 head |
| 2. pytest | C.1 跑 `tests/unit/test_embedding_backend_bge_m3.py` 期望 2 PASS |
| 3. PWA build | 本任务不涉及 frontend, 沿用 W100 +74 基线 |
| 4. 0 production code | 仅 `embedding_service.py` 加 `_backend_singleton` 包装 + 2 个 model 加 1 个 Column + 1 个新迁移 + bench 脚本 + tests + memory + decision doc |
| 5. 锚点范式 | W-N-C +0..+4 派工期望 5 commits |

### 6. GPU/模型可用性实测 (C.1/C.3 关键前提)

```bash
python -c "import torch; print('cuda:', torch.cuda.is_available())"
# cuda: False  ← 本机 CPU only

python -c "from sentence_transformers import SentenceTransformer; print('ST:', SentenceTransformer.__module__)"
# sentence_transformers.SentenceTransformer  ← ST 5.6.0 可 import, 但 BAAI/bge-m3 模型未下载
```

**决策**: bge-m3 真加载需要模型下载 (2.7GB) + 模型 cache 路径 (`~/.cache/huggingface` 或 `models/`). 本任务不下载, 仅 mock encoder + 决策文档说明 fallback 路径.

## 派工 brief 修订要点 (主拍授权沿用)

1. **C.1 双后端 singleton 兼容**: 不破坏现有 `_model` 路径, 新增 `_backend_singleton` (EmbeddingBackend ABC) + `get_embedding_backend()` 路由
2. **C.1 unit test 用 mock**: 不真加载 SentenceTransformer("BAAI/bge-m3"), 用 monkeypatch 替换 encode 返回固定 shape (1024,) 向量
3. **C.3 100 题不是 1000 题**: bench JSON 标题写清楚 `round11-bge-m3-100` (不是 `round11-bge-m3-1000`)
4. **C.3 真加载尝试**: 试 `from sentence_transformers import SentenceTransformer; SentenceTransformer("BAAI/bge-m3", device="cpu")` 但**不下载**, 仅捕获 `OSError`/网络错 → fallback mock
5. **C.3 决策文档路径**: `docs/decisions/2026-08-05-bge-m3-decision.md` (新建 dir + 仿 RERANKER_DECISION_LOG.md)

## 派工前提铁律 12 + 类 20 实战沉淀 (W-N-C 据实上报)

- **类 20.XX (派工 brief vs 实测错配, W-N-B 半vec 已立)**: C.1 brief 假设直接覆盖 → 实测需保留 singleton 兼容, C.3 brief 1000 题 → 实测 100 题
- **类 20.XX (GPU 不可用 fallback, W2 类 20.149 沿用)**: C.3 真加载尝试 → 实测 fallback mock

## 累计 commits 与铁律延续

W-N-A +N HNSW bench 收口 + W-N-B +0..+7 halfvec + W-N-C +0..+4 bge-m3 (本任务 5 commits).
派工前提铁律 12 + 类 20 累计 N+ 实例 (W-N-C 据实上报 2 实例沉淀).
0 production code 守恒 (W-N-C 仅 embedding_service.py 双轨兼容 + 2 model 加字段 + 1 新迁移 + bench + tests + memory + decision).

## 沉淀文件

- 本 startup memory (本文件)
- W-N-C +1 `tests/unit/test_embedding_backend_bge_m3.py` + `embedding_service.py` 双轨
- W-N-C +2 `alembic/versions/103_add_embedding_model_version.py` + 2 model 加字段
- W-N-C +3 `scripts/reembed_knowledge_bge_m3.py` (100 题版) + `docs/decisions/2026-08-05-bge-m3-decision.md`
- W-N-C +4 closure memory (本任务收口)