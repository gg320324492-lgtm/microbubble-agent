# late chunking 真 bench 触发条件 (bge-m3 路径留口)

> W-N-D+ +2 沉淀. 真 bench 已用 **Qwen3-Embedding-0.6B (生产默认)** 跑通,
> 本文档只记录 **`BAAI/bge-m3` 路径**尚未跑的触发条件, 留 future PR.
> 已跑结果: `results/late_chunking_real_bench_2026-08.json` (8192) +
> `results/late_chunking_real_bench_32k_2026-08.json` (32768).
> 能力验证: `docs/capability/gpu-bge-m3-2026-08-05.md`.

## 1. 已完成 (不需再派工)

| 项 | 状态 | 物证 |
|----|------|------|
| GPU 能力验证 | ✅ | RTX 5090, 容器内 `torch.cuda.is_available()=True` |
| `token_embeddings` 接口验证 | ✅ | shape `(1, 281, 1024)`, `max_seq_length=32768` |
| 真 bench 脚本 | ✅ | `scripts/run_late_chunking_realbench.py` |
| 真 bench 执行 (Qwen3, 生产默认) | ✅ | chunk 胜率 85% @ 8192 与 32768 两组 |

结论: **late chunking 相比 parent 单向量确有召回增益** (delta_mean +0.041 ~ +0.054),
且该结论在两种 context 长度下一致.

## 2. 未完成: bge-m3 路径

`BAAI/bge-m3` 是 `EMBEDDING_BACKEND=bge_m3` 的灰度候选 (`app/services/embedding_service.py:43`
`BGEM3Backend`). 本轮**未**用它跑 bench, 原因:

- HF 缓存中**不存在** `models--BAAI--bge-m3` (仅有同名易混的 `bge-reranker-v2-m3`, 是 reranker)
- 需下载 **~2.7GB** — 派工 brief 明令禁止 (`禁止: 跑 ollama pull bge-m3 (2.7GB 太大)`)

### 2.1 触发条件 (全部满足才跑)

| # | 条件 | 校验命令 | 当前 |
|---|------|---------|------|
| 1 | GPU 可用 | `docker exec microbubble-agent-app-1 python -c "import torch;print(torch.cuda.is_available())"` | ✅ True |
| 2 | `BAAI/bge-m3` 已缓存 | `docker exec microbubble-agent-app-1 ls /root/.cache/huggingface/hub \| grep -x 'models--BAAI--bge-m3'` | ❌ 未缓存 |
| 3 | 主拍显式批准 2.7GB 下载 | 派工 brief 或主拍指令 | ❌ 当前明令禁止 |
| 4 | 磁盘余量 ≥ 5GB | `df -h` | 待查 |

条件 2 与 3 是当前唯一缺口。**条件 3 是硬门禁** — 即便模型碰巧被别的任务下载了,
也不得在未获批准时自行触发下载。

### 2.2 满足后的执行命令

```bash
# 脚本已支持 --model, 无需改代码
docker exec microbubble-agent-app-1 python scripts/run_late_chunking_realbench.py \
    --model BAAI/bge-m3 --device cuda --n-docs 5 --max-length 8192 \
    --output results/late_chunking_real_bench_bgem3_2026-08.json
```

注: 脚本非 bind-mount 进容器, 需先
`docker cp scripts/run_late_chunking_realbench.py microbubble-agent-app-1:/app/scripts/`
(类 20.142 同款纪律)。

### 2.3 预期与验收

- bge-m3 同为 1024d, 预期同样暴露 `token_embeddings` (**未实测**, 属推断)
- 验收: 与 Qwen3 组对比 `summary.chunk_win_rate` 与 `delta_mean`
- 若 bge-m3 胜率显著高于 Qwen3 → 可作为 `EMBEDDING_BACKEND` 灰度切换的**新增**依据
  (但切换本身仍是独立决策, 不由本 bench 单独决定)

## 3. 其他留口 (本轮据实发现, 均非阻塞)

### 3.1 语料规模偏小

`--n-docs 5` 实际只取到 **4** 篇 — DB 中 `length(content) >= 8000` 的 knowledge 恰好只有 4 条
(实测 `SELECT count(*)` = 4)。20 个 (doc, query) 对足以看出方向 (85% 胜率),
但样本量不足以做显著性检验。

触发条件: knowledge 库长文档 ≥ 20 篇时, 重跑并加统计检验。
放宽 `--min-chars 3000` 可得 50 篇 (实测), 是更快的替代路径。

### 3.2 未接 DB 真实召回链路

本 bench 比较的是**向量空间中的 cosine**, 未经过 `hybrid_retriever._chunk_late_recall()`
的真实 SQL 召回 (pgvector `<=>` + HNSW)。即测的是"late chunking 向量本身更好",
而非"端到端召回更好"。

触发条件: `knowledge_chunks.late_embedding` 列 (alembic 104) 在生产**已回填数据**后,
才能跑端到端 recall@k。当前该列为空 → 端到端 bench 属 future PR。

### 3.3 未做 prod 配置变更

本轮**0 prod 配置改** (`EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME` 均未动),
符合派工 brief "即使 GPU 可用, 不改 prod 配置 (留 future PR)"。

late chunking 是否启用于生产, 需独立派工决策, 依据至少包含:
本 bench (向量质量) + 端到端 recall (§3.2) + 回填成本 + 存储开销 (每文档 N 个 1024d 向量)。

## 4. 不要做的事

- ❌ 不得为"凑齐 5 篇文档"而合成/复制文档 — 4 篇是 DB 真实情况, 据实报
- ❌ 不得在未获批准时 `SentenceTransformer('BAAI/bge-m3')` — 该调用会静默触发 2.7GB 下载
- ❌ 不得因 bench 结果好看就直接改 `EMBEDDING_BACKEND` — 见 §3.3
- ❌ 不得把 `bge-reranker-v2-m3` 当作 `bge-m3` — 不同模型, 不可互换
