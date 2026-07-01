# #001 BGE m3 Reranker Upgrade — Benchmark Report (2026-07-01)

> **目标**：用 cross-encoder reranking (BGE m3) 取代 Self-RAG #009 judge 路径，提升 KB 检索质量。
>
> **状态**：代码改动 ✅ 完成；HF mirror 阻塞 ⚠️ 不能下载 BGE m3 真模型，graceful degradation 验证 pipeline。

## 1. Benchmark 数据

| Round | 配置 | Pass Rate | Avg Duration | rerank_score 字段 |
|---|---|---|---|---|
| **Round 1 OFF** | `enable_rerank=False` | **100/100 (100%)** | 9.3s | ❌ 无（三路检索） |
| **Round 2 ON** | `enable_rerank=True` (graceful) | **100/100 (100%)** | 10.5s | ✅ 有（=score fallback） |

**Delta**: pass rate 0% (天花板)，avg latency +1.2s（rerank code path 仍在跑，即使 graceful degrade）

## 2. Micro-test 直接验证 rerank pipeline

100 题 smoke benchmark 用 `run_qa4.py` 没收集 `tool_results` 字段（仅 `tools_called` + `content`）。
直接 chat 调用查证：

```bash
# "什么是 zeta 电位" 触发 search_knowledge
→ 1 tool_result events
→ docs returned: 5
→ [0] id=257 title=赵航佳研究方向 rerank_score=0.3668 score=0.3668 norm=1.0
→ [1] id=141 title=微纳米气泡+超细微气泡: UFB相关 rerank_score=0.2981 ...
```

✅ **rerank_score 字段被正确添加**（pipeline 正常，graceful 时 = original score）

## 3. 基础设施约束

### 3.1 HF mirror 阻塞

```bash
$ curl -sk --max-time 5 https://hf-mirror.com/  →  不可达 (no route / 403)
$ HF_HUB_OFFLINE=0 python -c 'huggingface_hub.snapshot_download("cross-encoder/ms-marco-MiniLM-L-6-v2")'
→ LocalEntryNotFoundError: cannot find in local cache + cannot reach remote
```

`app/config.py` line 88 `HF_HUB_OFFLINE=1` (CLAUDE.md 2026-06-24 教训：防止 SSL 握手抖动)
但加上 HF mirror (hf-mirror.com) 也不通 → **整个容器无法下载任何新 HF 模型**

### 3.2 ms-marco cache 不完整

`/root/.cache/huggingface/hub/models--cross-encoder--ms-marco-MiniLM-L-6-v2/` 仅有 `refs/main`，**无 snapshots 目录** = 模型从未真正下载

### 3.3 影响

| 阶段 | 状态 |
|---|---|
| `CrossEncoder(MODEL_NAME)` import | ✅ |
| `CrossEncoder(MODEL_NAME).predict(...)` | ❌ RuntimeError "We couldn't connect to hf-mirror.com to load the files" |
| Graceful degradation | ✅ 按原始 score 排序返回，pipeline 完整 |

## 4. 待网络恢复后实跑（roadmap）

网络恢复后 (`hf-mirror.com` 可达)：

```bash
# 1. 临时关 HF_HUB_OFFLINE 下载 BGE m3 (2.3GB)
docker exec -i microbubble-agent-app-1 bash -c "
  HF_HUB_OFFLINE=0 python -c '
  from huggingface_hub import snapshot_download
  snapshot_download(\"BAAI/bge-reranker-v2-m3\")
  '
"

# 2. 设置 BGE m3 模型 (改 container .env, 然后 docker restart)
docker exec -i microbubble-agent-app-1 bash -c "sed -i 's/RERANKER_MODEL_NAME=.*/RERANKER_MODEL_NAME=BAAI\/bge-reranker-v2-m3/' /app/.env"
docker compose restart app

# 3. 验证加载日志
docker logs microbubble-agent-app-1 --tail 30 2>&1 | grep "Cross-encoder"
# 期望: 加载 Cross-encoder 模型: BAAI/bge-reranker-v2-m3 on cuda
# 期望: Cross-encoder 模型加载完成

# 4. VRAM 检查
nvidia-smi --query-gpu=memory.used --format=csv,noheader
# 期望: 比 baseline + ~1.1GB (FP16)

# 5. 跑 Round 3 BGE m3 GPU
python /tmp/run_qa4.py "$TOKEN" tests/qa-bench/questions_smoke_200.jsonl \
  tests/qa-bench/results/reranker-benchmark/round3-bge-m3 100 2

# 6. 对比 3 round
# Round 1 (no rerank) vs Round 2 (graceful) vs Round 3 (BGE m3 GPU)
# 期望 Round 3: B 类别召回率提升 + 内容质量更准 (avg_duration 应 ~9s, 比 Round 2 的 10.5s 略快)
```

## 5. 关键发现与改进

### 5.1 ✅ 完成的代码改动

1. **`app/services/reranker_service.py` 全面重写**：
   - env var 配置 (RERANKER_MODEL_NAME/DEVICE/MAX_LENGTH/BATCH_SIZE)
   - device 检测 (`_detect_device()` mirror embedding_service.py 模式)
   - GPU 推理 (CrossEncoder 加 `device=` 参数)
   - async wrapper (`rerank_async` 用 run_in_executor 不阻塞 event loop)
   - warmup API (避免首次 rerank 8-10s 冷启动)
   - is_loaded/model_name/device properties
   - graceful degradation 保留 (model 加载失败/预测失败时按原始 score 排序)

2. **`app/services/hybrid_retriever.py`**：
   - `candidate_k = top_k * 5` (从 3 → 5，更大候选池给 rerank)
   - `rerank_async(query, normalized, top_k=top_k)` (从 sync → async)

3. **`tests/qa-bench/detectors/retrieval_recall.py` 新建** (P1)：
   - 用 `ground_truth_refs` (kb://a/a1-x1 格式) 算 recall@5 + MRR
   - 集成到 `tests/qa-bench/runner.py` (line 580-588)

4. **`.env` + `docker-compose.yml`**：4 个 env var 接入 (app + celery-worker)

5. **`app/agent/tools/knowledge_tools.py`**：`enable_rerank` 通过 `RERANKER_BENCHMARK_ENABLED` env var 控制（benchmark 专用）

### 5.2 ⚠️ Graceful Degradation 验证（无真模型情况下）

- Model load 失败 → graceful degradation 返回原序（pipeline 完整）
- 100 题 PASS 率 100% = 改代码未引入回归
- micro-test 直接调 chat/stream → rerank_score 字段正确添加
- 端到端 `Cross-encoder 不可用，按原始 score 排序` 日志符合预期

### 5.3 ❌ 待办（网络恢复后）

- [ ] 下载 BGE m3 (2.3GB) + 实跑 Round 3
- [ ] 对比 Round 1/2/3 三轮 pass_rate + avg_duration + retrieval_recall detector 命中率
- [ ] Round 3 PASS → 标记为生产默认
- [ ] Round 3 召回率 < Round 2 → 调 candidate_k 5 → 7 或换 jina-reranker

## 6. 沉淀

### 6.1 已知约束

- **HF mirror 必须可达才能下载模型** (CLAUDE.md 2026-06-24 升级 sentence-transformers 时的隐患)
- `HF_HUB_OFFLINE=1` 是"防止抖动"的安全网，但加上 mirror 不通 = 完全离线
- 解决路径：网络恢复后再下 BGE m3

### 6.2 Graceful Degradation 价值

- 即使新模型加载失败，旧行为（按 score 排序）仍 100% pass
- **新增 `enable_rerank` 开关**允许运营即时切回 fallback（不用改代码）
- pipeline 改动是**纯增量**，不影响其他 3 路检索

### 6.3 Run Qa4.py 局限

- 只收集 `tools_called` (names) 和 `content` (text concat)，没收集 `tool_results` 完整 dict
- 改进方向：加 `tool_results: List[dict]` 字段 + `rerank_score_present: bool` 字段
- 短期绕过：用 micro-test 直接调 chat/stream 验证 rerank_score 字段

## 7. 风险与回滚

| 风险 | 缓解 |
|---|---|
| Round 3 (BGE m3) 召回率反而下降 | 改 `RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2` 回退 (CPU 英文) |
| Round 3 与 Qwen3-Embedding 共存 OOM | RTX 5090 32GB 充足，理论峰值 18GB，BGE m3 FP16 1.1GB + Qwen3 1.2GB = 2.3GB |
| 真模型加载延迟 (8-10s) | `warmup()` 在 app lifespan startup 调一次 |
| 5x 候选集 (25 docs) 检索时间变长 | GPU 推理 30ms << 三路检索 ~500ms，可忽略 |

**回滚**：单 commit `Revert "feat(reranker): ..."` 或 `.env RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2`
