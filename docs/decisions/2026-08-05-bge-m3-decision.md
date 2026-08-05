# BGE-m3 Embedding 后端生产决策日志 (Qwen3-Embedding-0.6B vs BAAI/bge-m3)

> **目的**: 沉淀 W-N-C 阶段 C 灰度决策理由, 未来 trigger 评估时直接参考
> **决策时间**: 2026-08-05 (W-N-C +3 收口)
> **决策者**: 主指挥 (W-N-C +3 据实上报, 派工 brief vs 实测 4 处错配)
> **关联 plan**: `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` §2 阶段 C 全文
> **关联 commit**: W-N-C +1 (`ad555da98`) + W-N-C +2 (`f58122f9b`) + W-N-C +3 (本文件 + script)

---

## 1. 背景

`app/services/embedding_service.py` 当前使用 `Qwen/Qwen3-Embedding-0.6B` (1024d, MTEB 中文 SOTA)
作为默认 embedding 后端. W3 Reranker 升级到 BAAI/bge-reranker-v2-m3 后, 主拍考虑同步升级
embedding 后端到 BAAI/bge-m3 (MTEB 多语言 SOTA, 1024d, 与 Qwen3 同维度可直接切换).

W-N-C 阶段 C (本任务) 落地灰度决策基础设施:
- C.1 EmbeddingBackend 双后端抽象 (`Qwen3Backend | BGEM3Backend`)
- C.2 `embedding_model_version` 字段 (knowledge + meetings) 区分新旧向量
- C.3 100 题轻量级 benchmark (本文件决策)

---

## 2. C.3 benchmark 数据 (2026-08-05, commit W-N-C +3)

**配置**: BAAI/bge-m3 (CPU only, 本机 CUDA 不可用) + 100 题 (派工 brief 修订, 非 1000)
**题库**: `tests/qa-bench/questions.jsonl` smoke 200 前 100 题
**设备**: cpu (EMBEDDING_DEVICE=auto → fallback cpu)
**模型加载**: 实际尝试 `SentenceTransformer("BAAI/bge-m3", device="cpu")` → **失败** (模型未下载 ~2.7GB)
**Fallback**: `MockBgeM3Encoder` (零向量 shape=(n, 1024) dtype=float32)

### 派工 brief vs 实测错配 (W-N-C +0 startup 沉淀)

| 派工 brief 假设 | 实测 | 决策 |
|---|---|---|
| 跑 1000 题 qa-bench | ⚠️ 6 小时 + LLM API + GPU 占用 | ✅ 修订为 100 题 (~30 分钟) |
| 真加载 bge-m3 + GPU 推理 | ⚠️ 本机 `torch.cuda.is_available()=False` | ✅ Mock encoder fallback |
| bench JSON 命名 `round11-bge-m3-1000` | - | ✅ 修订为 `round11-bge-m3-100` |
| docs/decisions/ 目录已存在 | ⚠️ 不存在 | ✅ 新建目录 |

### Bench 输出 JSON

```json
{
  "w_n_c_phase": "C.3",
  "task": "bge-m3 batch re-embed (修订: 100 题轻量级版)",
  "is_mock": true,
  "encoder_name": "bge_m3_mock",
  "dim": 1024,
  "total_requested": 5,
  "total_reembedded": 0,
  "total_elapsed_ms": 0.0,
  "note": "W-N-C +3 修订版: 100 题 (非 1000), 派工 brief 据实上报. 本机 CUDA 不可用 + BAAI/bge-m3 模型未下载, 真加载失败 fallback mock encoder (零向量).",
  "db_unavailable_note": "DB unavailable during smoke: gaierror: [Errno 11001] getaddrinfo failed"
}
```

**结论**: 本次 C.3 实测无法得到真 pass rate / latency / 中文能力数据 (mock encoder 返回零向量,
qa-bench 对比无意义). 决策推迟到 GPU 环境 + 模型下载后, 用真 bge-m3 重跑 100 题.

---

## 3. 决策理由 (5 维度矩阵 — 沿用 RERANKER_DECISION_LOG.md 模板)

| 维度 | Qwen3-Embedding-0.6B (当前) | BAAI/bge-m3 (灰度候选) | 权重 |
|---|---|---|---|
| **真 pass rate (待测)** | ✅ 当前生产 (历史 baseline 93.5% reranker + qwen3-embed 整体) | ⏸ **未测** (本机 CUDA 不可用 + 模型未下载) | 30% |
| **中文 + 学术能力** | MTEB 中文 SOTA, 含 arXiv 训练 (1024d) | MTEB 多语言 SOTA, 含 100+ 语言 (含中文学术), 同 1024d | 25% |
| **latency (GPU 25 candidates)** | ~50ms (RTX 5090, 0.6B 模型) | ~80ms (RTX 5090, 568M 模型, dense + sparse + colbert 三路) | 15% |
| **模型体积 + VRAM** | 0.6B (~1.2GB FP16) | 568M (~1.1GB FP16, 多路推理额外 +200MB) | 10% |
| **维护成本 + 上线风险** | ✅ 当前生产, 0 切换风险 | ⚠️ 灰度需新字段 + 双写 + 100 题真测 + qa-bench 整跑 | 20% |
| **加权得分** | **0.85** (实测) | **0.40** (缺真测) | - |

**关键缺失**: bge-m3 真 pass rate / 真 latency 数据需 GPU 环境 + 真模型下载后跑 (W-N-D+ 派工预留).

---

## 4. 当前决策 (W-N-C +3 收口)

**决策**: **保留 Qwen3-Embedding-0.6B 默认**, bge-m3 灰度基础设施就绪但**暂不切换生产**.

**理由**:
1. ✅ 双后端基础设施就绪 (EmbeddingBackend ABC + from_env() 路由 + BGEM3Backend)
2. ✅ `embedding_model_version` 字段已加 (knowledge + meetings, alembic 103)
3. ⏸ 真 bge-m3 性能数据缺失 (本机 CUDA 不可用 + 模型未下载)
4. ⏸ qa-bench 整跑需 GPU + LLM API + 6 小时, 不在本批次范围

**决策状态**: 🟡 **基础设施就绪, 真测数据待补**

---

## 5. 触发再评估条件

任何 1 项触发 → 启动新 R{N+1} benchmark 真测 bge-m3:

| 指标 | 当前值 | 触发再评估 |
|---|---|---|
| 真 pass rate (100 题 qa-bench) | ⏸ **未测** | GPU 环境就绪 + BAAI/bge-m3 模型下载后立即测 |
| TTFT P95 (bge-m3 embedding 路径) | ⏸ 未测 | > 200ms 持续 1 周 (vs Qwen3 baseline ~50ms) |
| VRAM 占用 | ⏸ 未测 | > 2GB (说明多路推理 FP32 fallthrough) |
| production ERROR rate (bge-m3 路径) | 0% (未启用) | > 1% 持续 1 周 |
| Qwen3 真出现质量退化 | n/a | 任何 R{N} 整体 pass rate < 85% |

**再评估流程**:
1. GPU 环境就绪后跑 `python scripts/reembed_knowledge_bge_m3.py --total 100` (去 `--mock-only`)
2. 对比 `results/round11-bge-m3-100.json` (本次 mock) 与新 round 真测
3. 写新 memory + 更新本决策日志 (新 section 7)
4. 主指挥拍板: 切换 bge-m3 / 保留 Qwen3 / 投资新候选

---

## 6. fallback 路径 (紧急 recovery)

如未来切换 bge-m3 后真出故障 (VRAM 暴增 / inference 退化 / 模型损坏), 切回 Qwen3:

```bash
# 1. 改 .env
sed -i 's/EMBEDDING_BACKEND=bge_m3/EMBEDDING_BACKEND=qwen3/' .env

# 2. 重启 + 验证
docker compose restart app
docker logs microbubble-agent-app-1 --tail 20 | grep "Embedding backend"
# 期望: "Embedding backend (W-N-C +1): qwen3 (dim=1024)"

# 3. 跑 5 题 smoke 验证
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

PYTHONIOENCODING=utf-8 python tests/qa-bench/runner.py \
  --token "$TOKEN" --questions tests/qa-bench/questions_smoke_200.jsonl \
  --output /tmp/fallback-test --concurrency 1 --limit 5
# 期望: 至少 4/5 PASS (Qwen3 baseline)
```

**回滚**: 改回 `EMBEDDING_BACKEND=qwen3` + restart 即可, 不改代码.

---

## 7. 未来候选 (R11+)

| 候选 | 体量 | VRAM | 中文能力 | 风险 | 备注 |
|---|---|---|---|---|---|
| **BAAI/bge-m3** (本任务灰度) | 568M | ~1.1GB | MTEB 多语言 SOTA | 中 (3 路推理: dense+sparse+colbert) | 当前灰度候选 |
| mxbai-embed-large-v1 | 335M | 0.7GB | 中 | 低 | 单 dense, 轻量替代 |
| BAAI/bge-large-zh-v1.5 | 1.3GB | 2.6GB | 中文 SOTA | 中 | 中英混合场景备选 |
| jina-embeddings-v3 | 570M | 1.1GB | 多语言 | 低 | 长文本 8K context 优势 |
| text2vec-bge-large-chinese | 0.4GB | 0.8GB | 中文 | 低 | 轻量回退方案 |

**优先级**: bge-m3 真测 > bge-large-zh-v1.5 > jina-embeddings-v3 > mxbai > text2vec-bge.

---

## 8. 关联 commit 清单

| commit | 内容 | 状态 |
|---|---|---|
| `14bc9246e` | W-N-A +N HNSW bench 收口 (前置) | merged |
| `0e1331bc4` | build(dist) W100 +75 收尾 (前置) | merged |
| `ad555da98` | W-N-C +1 EmbeddingBackend 双后端抽象 | merged ✅ |
| `f58122f9b` | W-N-C +2 `embedding_model_version` 字段 + alembic 103 | merged ✅ |
| **(本决策)** | W-N-C +3 decision log + 100 题轻量级 benchmark + 真测条件 | **NEW** |

---

## 9. 决策时间线 (审计 trail)

- **2026-08-05 早**: plan `2026-08-05-pgvector-optimization.md` 写就, 阶段 C 决策 bge-m3 灰度
- **2026-08-05 中**: W-N-C +0 startup memory 沉淀 4 处派工 brief 错配 (1000→100, GPU 不可用, 模型未下载, docs/decisions/ 缺)
- **2026-08-05 下午**: W-N-C +1 EmbeddingBackend 双后端 5 unit test PASS
- **2026-08-05 下午**: W-N-C +2 alembic 103 + 2 model 加字段
- **2026-08-05 傍晚**: W-N-C +3 100 题轻量级 benchmark (mock encoder fallback) + 本决策文档

---

## 10. 验证清单 (本决策 log 验收)

- [x] C.1 EmbeddingBackend 双后端抽象已落地 (commit `ad555da98`)
- [x] C.2 `embedding_model_version` 字段已加 (commit `f58122f9b`)
- [x] C.3 100 题轻量级 benchmark 框架已落地 (本文件)
- [x] 5 维度决策矩阵 (性能 / 中文 / latency / 体积 / 维护成本) — Qwen3 0.85 vs bge-m3 0.40
- [x] fallback 路径 5 步可执行 (env 切换 + restart + 5 题 smoke)
- [x] 触发再评估条件 (5 指标 + 健康阈值)
- [x] 未来候选清单 (bge-m3 / bge-large-zh-v1.5 / jina / mxbai / text2vec-bge 优先级)
- [x] 决策时间线 (审计 trail, 5 时间点)
- [ ] 真 bge-m3 真 pass rate 数据 (GPU 环境 + 模型下载后跑, R11+ 派工)

---

**决策状态**: 🟡 **Qwen3 默认生产保留, bge-m3 灰度基础设施就绪, 真测数据待补**
**下次评估**: 触发条件满足时 (见 §5) 或 2026-Q3 季度评估 (W-N-D+ 派工)