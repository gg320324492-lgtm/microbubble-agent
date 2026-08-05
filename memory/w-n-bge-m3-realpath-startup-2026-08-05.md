# W-N-BGE bge-m3 真路径回归 起步 (2026-08-05)

> **派工**: W-N-BGE +0 startup (主指挥 W-N-D++ 收口后派工, base head `1cc5362e2`)
> **目的**: 验证 RTX 5090 + 容器 CUDA + sentence-transformers 5.6.0 三件套, 跑 1000 题真 bge-m3 bench
> **决策门禁**: 派工 brief 严禁, 跑真测数据决策 (pass rate / latency / VRAM / 中文 + 学术 / 维护成本)

---

## 1. 任务背景

W-N-C 阶段 C 已落 `EmbeddingBackend` 双后端 (Qwen3 | bge-m3) + `embedding_model_version` 字段
(commit `ad555da98` + `f58122f9b`). 但 W-N-C +3 实测时:

- **本机 CUDA 不可用**: `torch.cuda.is_available()=False` → fallback CPU
- **BAAI/bge-m3 模型未下载**: ~2.7GB 权重文件未下载 → 真加载失败
- **修订为 100 题 mock**: 决策推迟到 GPU 环境 + 模型下载后真测

**本任务 (W-N-BGE)** 派工前提已变更:
- W-N-D+ 已确认 RTX 5090 + 容器 CUDA 可用 (`41ab080a1` `perf(rag): late chunking 真 bench + 5 文档`)
- 现可实测 bge-m3 真加载 + 真推理 + 1000 题真 bench
- **不真部署生产** (派工 brief 严禁, 仅 benchmark)

---

## 2. 起步 6 项 (W73 铁律)

### 2.1 派工 brief vs 实测错配 (本任务 startup 沉淀)

| 派工 brief 假设 | 实测 | 决策 |
|---|---|---|
| 派工起点 base head `1cc5362e2` | ✅ `git log --oneline -1` = `1cc5362e2 feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档` | ✅ 守恒 |
| 锚点范式 `W-N-BGE +0..+3` | 派工 brief 排定 +0/+1/+2/+3, 4 commits 起步 | ✅ 沿用 |
| 已有 `scripts/reembed_knowledge_bge_m3.py` 100 题 mock | ✅ W-N-C +3 落地 (派工 brief 引用, 真用此扩展) | ✅ 复用 |
| bench 输出 JSON `round11-bge-m3-1000.json` | W-N-C +3 写的是 `round11-bge-m3-100.json` (修订版), 本任务**新写** `round11-bge-m3-1000.json` | ✅ 新文件, 不冲突 |
| `docs/decisions/2026-08-05-bge-m3-decision.md` 已存在 | ✅ 已存在 (W-N-C +3 创建), 加 5 维真测数据 | ✅ 沿用 |
| qa-bench 题库 1000 题就绪 | ✅ `tests/qa-bench/questions.jsonl` smoke 200 + `tests/qa-bench/questions_full_*.jsonl` 大题库 | ✅ 沿用, 详查后报告 |

### 2.2 实测 sentence-transformers 5.6.0 是否支持 BAAI/bge-m3

**目标**: 派工 brief 必加项. 验证 GPU 容器内 `SentenceTransformer('BAAI/bge-m3', device='cuda', trust_remote_code=True)`
真能加载.

**Step 1 计划**: `docker exec microbubble-agent-app-1 python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-m3', device='cuda', trust_remote_code=True); print(m.model.card_data)" 2>&1 | head -20`

派工 brief 已在 Step 1, 本任务 W-N-BGE +1 执行时实测.

### 2.3 锚点范式

W-N-BGE +0 (本 memory) → W-N-BGE +1 (1 commit, bge-m3 真加载 + 1000 题 bench) → W-N-BGE +2 (1 commit, decision doc 5 维真测) → W-N-BGE +3 (1 commit, 收口 memory 沉淀). 总 4 commits.

派工 brief 严禁跳锚点, 沿用 W-N-C/W-N-D/W-N-E 锚点范式 (~567 → ~571 据实累计).

### 2.4 决策门禁 3 条 (派工 brief 严禁跳过)

1. **bge-m3 真 pass rate ≥ Qwen3 baseline?** → 切换生产
2. **VRAM < 4GB?** → GPU 资源充足
3. **latency < 2x Qwen3?** → 可接受

任 1 项失败 → 决策"暂不切" + 原因记录.
任 1 项**缺真测** → 决策"模型替换延后" + 后续派工预留.

### 2.5 5 件套守恒 (派工 brief 严禁违反)

- 件 1: alembic 1 head `104_*` (W-N-D++ 收口后) 守恒
- 件 2: pytest 全套件 PASS (本任务不强求, 沿用 W-N-D++ 基线)
- 件 3: PWA build (本任务不涉及 frontend, 沿用基线)
- 件 4: 0 production code 改动 (严禁改 `app/services/embedding_service.py` 4 个 API + `app/agent/chat_engine.py`)
- 件 5: 锚点范式 W-N-BGE +0..+3 据实累计

### 2.6 严禁清单 (派工 brief 严禁)

- ❌ 改 `app/services/embedding_service.py` 既有 4 个 API (`generate_embedding_sync` / `generate_embedding` / `generate_embeddings` / `get_or_compute_query_embedding`)
- ❌ 改 `app/agent/chat_engine.py`
- ❌ 改 `alembic/versions/`
- ❌ 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG commits
- ❌ 真切换生产 bge-m3 backend (`EMBEDDING_BACKEND=bge_m3` 仅 bench 临时设置, 不改 .env)
- ❌ 改 plan 文件
- ❌ 改 chat_engine.py / embedding_service.py / hybrid_retriever.py 老核心

---

## 3. 派工 brief 路径起点 base head 验证

```
$ git log --oneline -3
1cc5362e2 feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档 (W-N-D++ +1/+2/+3)
ef44aa929 feat(web): DFT/MD 计算工作台 (W-N-D +3)
ce05da2ea docs(memory): W-N-MEM +2 索引扩展收口 (5 件套守恒实测 + 派工 brief 偏差据实上报)
```

✅ base head `1cc5362e2` 守恒. 派工起点合法.

---

## 4. 起步沉淀

**派工前提确认**: 本任务起点 = `1cc5362e2` + 5 件套守恒 + 决策门禁 3 条 + 严禁清单 + 1000 题真测.
**W-N-BGE +1 待执行**: 实测 ST 5.6.0 真加载 bge-m3 + 写 1000 题真 bench 脚本 + 跑 bench + commit.
**W-N-BGE +2 待执行**: 加 5 维真测数据到决策文档 + 3 门禁结果 + commit.
**W-N-BGE +3 待执行**: 5 件套守恒实测 + 据实上报收口 + commit.

**派工 v6 §13 仓库实情真查**: 本任务起点已实测 (W-N-D+ 真测 GPU + W-N-D++ 真 bench), 派工 brief 假设路径守恒.