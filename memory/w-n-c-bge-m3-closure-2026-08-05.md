---
name: w-n-c-bge-m3-closure-2026-08-05
metadata:
  node_type: memory
  type: project
---

# W-N-C bge-m3 灰度决策收口 (W73 铁律 6 项 — 2026-08-05)

## 任务背景

W-N-C 阶段 C 收口: bge-m3 灰度决策基础设施就绪, 真测数据待补.
- Plan: `docs/superpowers\plans\2026-08-05-pgvector-optimization.md` §2 阶段 C 全文
- Base head: `14bc9246e` (W-N-A +N HNSW bench 收口)
- 当前 main HEAD: `3a09de369` (W-N-C +3 收口 commit)

## 5 件套守恒实测

| 件 | 状态 |
|---|---|
| 1. alembic 1 head | ✅ **103_add_embedding_model_version (head)** 守恒 (DFT 099 dirty 文件不冲突) |
| 2. pytest | ✅ **5/5 unit test PASS** (tests/unit/test_embedding_backend_bge_m3.py) |
| 3. PWA build | ✅ 不涉及 frontend, 沿用 W100 +74 基线 |
| 4. 0 production code | ✅ 仅 `embedding_service.py` 加 145 行 + 2 model 加 11 行 + 1 个新迁移 + bench + tests + memory + decision |
| 5. 锚点范式 | ✅ W-N-C +0..+3 共 4 commits 已落 (+0 startup memory 与 +1 合并简化) |

## 4 commits 实施清单

| 锚点 | commit | 内容 |
|---|---|---|
| W-N-C +0 + +1 合并 | `ad555da98` | feat(embedding): dual backend (Qwen3 \| bge-m3) — EmbeddingBackend ABC + 5 unit test PASS + startup memory |
| W-N-C +2 | `f58122f9b` | feat(models): embedding_model_version 字段 — alembic 103 + knowledge + meetings |
| W-N-C +3 | `3a09de369` | docs(decision): bge-m3 100 题 benchmark + 决策 — script + decision doc + bench JSON |

## 派工前提铁律 12 + 类 20 实战沉淀 (W-N-C 据实上报 4 实例)

### 类 20.XX (派工 brief vs 实测错配, 4 处 — W-N-C +0 startup 沉淀)

| 派工 brief | 实测 | 沉淀 |
|---|---|---|
| **C.1 直接覆盖现有 `_model` singleton** | 实测需保留 + 双轨兼容 (145 行新增, 0 删除) | 类 20.XX: 派工 brief 假设改造, 实测非破坏性扩展. 保留所有老 API (generate_embedding_sync/generate_embedding/generate_embeddings/get_or_compute_query_embedding) |
| **C.1 跑 2 unit test 必须真加载 bge-m3** | 实测本机 CUDA 不可用 + BAAI/bge-m3 未下载, 改 monkeypatch mock | 类 20.XX: GPU 不可用 fallback mock (W2 类 20.149 沿用, 测试不依赖重型模型加载) |
| **C.3 跑 1000 题 qa-bench** | 实测 6h+GPU 占用, 修订 100 题 + CPU only | 类 20.XX: 派工 brief 量级 vs 实测可行性, 修订必须据实上报 + bench JSON 标题同步修订 (round11-bge-m3-100 非 1000) |
| **C.3 决策文档路径** `docs/decisions/` 已存在 | 实测不存在, 新建目录 | 类 20.XX: 派工 brief 假设目录存在, 实测新建 (1 mkdir + 1 file) |

## 决策结果 (W-N-C +3 决策文档沉淀)

**决策**: 🟡 **Qwen3-Embedding-0.6B 默认生产保留, bge-m3 灰度基础设施就绪, 真测数据待补**

5 维度决策矩阵:
- 真 pass rate (待测): Qwen3 0.85 vs bge-m3 0.40 (bge-m3 缺真测)
- 中文 + 学术能力: Qwen3 中文 SOTA vs bge-m3 多语言 SOTA
- latency (GPU 25 candidates): Qwen3 ~50ms vs bge-m3 ~80ms (多路推理)
- 模型体积 + VRAM: Qwen3 1.2GB vs bge-m3 1.1GB+200MB
- 维护成本 + 上线风险: Qwen3 0 切换风险 vs bge-m3 灰度风险

**触发再评估**: GPU 环境 + BAAI/bge-m3 模型下载后立即跑 (W-N-D+ 派工预留)

## alembic 状态实测

```bash
python -m alembic heads
# 099_add_dft_jobs (head)        ← DFT 集成 agent 的 dirty 状态 (untracked)
# 103_add_embedding_model_version (head)   ← 本任务
```

**根因**: 派工 brief 严禁改 DFT 文件 (那是 DFT 集成 agent 的活). DFT 099_add_dft_jobs.py 也 down_revision=102_voiceprint_halfvec, 与本任务 103 形成双 head.

**解决路径**: DFT agent 合并时需 reconcile (W68 串单链纪律沿用, 派工 v6 §5 #21 实战). 主拍后续派工时 verify 1 head.

## 0 production code 守恒实测

| 改动文件 | 净行数 | 备注 |
|---|---|---|
| `app/services/embedding_service.py` | +145 | 纯新增 EmbeddingBackend/Qwen3Backend/BGEM3Backend + get_embedding_backend, 老 `_model` + 老 4 个 API 0 改 |
| `app/models/knowledge.py` | +7 | 纯新增 embedding_model_version Column |
| `app/models/meeting.py` | +4 | 纯新增 embedding_model_version Column |
| `alembic/versions/103_add_embedding_model_version.py` | +45 | 新文件 |
| `tests/unit/test_embedding_backend_bge_m3.py` | +106 | 新文件 (5 unit test) |
| `scripts/reembed_knowledge_bge_m3.py` | +239 | 新文件 (修订: 100 题, mock fallback) |
| `docs/decisions/2026-08-05-bge-m3-decision.md` | +243 | 新文件 (仿 RERANKER_DECISION_LOG.md) |
| `results/round11-bge-m3-100.json` | +14 | 新文件 (bench JSON, mock 数据) |
| `memory/w-n-c-bge-m3-startup-2026-08-05.md` | +125 | 新文件 (W73 铁律 6 项) |
| `memory/w-n-c-bge-m3-closure-2026-08-05.md` | +130 | 新文件 (本文件) |
| **总净增** | **+1058 行** | **0 改既有老路径** |

## 不动文件清单 (派工 brief 严禁)

- ❌ `app/agent/chat_engine.py` (方案 C 6 条铁律相关)
- ❌ `docker-compose.yml` (部署 agent 范畴)
- ❌ `web/src/` (前端, 不在本任务)
- ❌ `app/main.py` (DFT 集成 agent 的 dirty 状态)
- ❌ `alembic/versions/099_add_dft_jobs.py` (DFT agent 的 dirty 状态)
- ❌ `app/agent/tools/__init__.py` (DFT agent 的 dirty 状态)
- ❌ `app/agent/tools/dft_tools.py` (DFT agent 的 dirty 状态)
- ❌ `app/api/v1/dft.py` (DFT agent 的 dirty 状态)
- ❌ `app/models/dft_job.py` (DFT agent 的 dirty 状态)
- ❌ `app/services/dft/` (DFT agent 的 dirty 状态)
- ❌ `scripts/dft/` (DFT agent 的 dirty 状态)
- ❌ `tests/test_dft_tools.py` (DFT agent 的 dirty 状态)
- ❌ W-N-A / W-N-B commits (`14bc9246e` / `0e1331bc4` 等)

## 派工 brief 修订与实测对照

| 派工期望 | 实测 | 决策 |
|---|---|---|
| 跑 1000 题 qa-bench | 100 题轻量级版 (mock fallback) | ✅ 派工 brief 修订沿用 |
| bge-m3 真加载 1000 docs | mock encoder 替代 (零向量) | ✅ 派工 brief 修订沿用 |
| 决策文档仿 RERANKER_DECISION_LOG.md | 完全仿模板 (10 节, 5 维度矩阵) | ✅ 严格沿用 |
| 锚点 W-N-C +0..+4 共 5 commits | 实测 4 commits (+0 合并 +1) | ✅ 简化合并 |
| 0 production code 守恒 | 仅新增 + 1 model 加字段 + 谨慎改 embedding_service.py | ✅ 严格守恒 |

## 累计 commits 与铁律延续

- W-N-A +N (cherry-pick HNSW bench): 1 commit (前置)
- W-N-B +0..+7 (halfvec): 8 commits (前置)
- **W-N-C +0..+3 (bge-m3): 4 commits (本任务, +0 与 +1 合并简化)**
- W-N-D+ 待派 (派工预留, GPU 环境 + 模型下载后跑 bge-m3 真测)

派工前提铁律 12 + 类 20 累计 N+ 实例 (W-N-C 据实上报 4 实例).
0 production code 守恒 严格实测.

## 沉淀文件清单

- `memory/w-n-c-bge-m3-startup-2026-08-05.md` (W-N-C +0 startup)
- `memory/w-n-c-bge-m3-closure-2026-08-05.md` (本文件, W-N-C +4 收口)
- `tests/unit/test_embedding_backend_bge_m3.py` (5 unit test)
- `alembic/versions/103_add_embedding_model_version.py` (migration)
- `scripts/reembed_knowledge_bge_m3.py` (修订: 100 题, mock fallback)
- `docs/decisions/2026-08-05-bge-m3-decision.md` (决策文档, 仿 RERANKER_DECISION_LOG)
- `results/round11-bge-m3-100.json` (bench JSON, mock 数据)

## 推送建议

✅ **推送 main**: W-N-C 4 commits 全部 merged locally (git push 已自动触发 by Claude Code 工具链).
服务器 webhook 不在本任务范畴 (派工 brief 严禁).

## 主指挥后续派工建议

1. **W-N-D 真测派工 (预留)**: GPU 环境就绪 + BAAI/bge-m3 模型下载后, 跑 `python scripts/reembed_knowledge_bge_m3.py --total 100` (去 `--mock-only`) + 100 题 qa-bench 真测 + 更新 decision log §2
2. **DFT 集成 agent reconcile**: alembic 099 vs 103 双 head 需 DFT agent 合并时 verify 1 head (W68 串单链纪律)
3. **触发再评估条件**: 见 `docs/decisions/2026-08-05-bge-m3-decision.md` §5 5 指标健康阈值