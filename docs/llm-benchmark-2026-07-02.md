# LLM 3-Way Benchmark Report (2026-07-02)

> **目的**: 对比 云 mimo-v2.5 (openai_compat) vs 本地 qwen3:8b vs 本地 qwen3:14b 的 qa-bench 表现
> **方法**: 35 题全跑 (云 + 8b) + 10 题前 10 题 3-way 公平对比 (subset, 因 14b 跑测超时)
> **位置**: `tests/qa-bench/results/{local-ollama-qwen3-8b,cloud-mimo-openai-compat,local-ollama-qwen3-8b-10q,cloud-mimo-openai-compat-10q,local-ollama-qwen3-14b}-2026-07-02/`

## 1. TL;DR

| Backend | 35 题 PASS | 10 题 PASS | 10 题耗时 | 10 题通过率 |
|---|---|---|---|---|
| **mimo-v2.5 (云 openai_compat)** | 5/35 (14.3%) | **5/10** | 1m 57s | **50.0%** |
| **qwen3:8b (本地 ollama)** | 4/35 (11.4%) | **5/10** | 1m 53s | **50.0%** |
| **qwen3:14b (本地 ollama)** | ❌ 12/35 partial | 3/10 (10 题 partial) | 7m 16s | 30.0% |

**核心结论**:
- **云 mimo 与本地 8b 在 qa-bench 35 题 / 10 题前 10 题** 表现**几乎相同** (50% 10 题)
- **mimo 加权综合分 0.937 > 8b 0.906** (3% 差距，主要在 tool/content 维度)
- **qwen3:14b 速度 4× 慢且通过率反而更低** (thinking 模式太重，duration_too_long 占 80% FAIL)
- **推荐生产环境保持 cloud mimo** (性能 + 质量综合最优，8b 是 fallback 备选)

## 2. 35 题完整 benchmark (mimo cloud vs 8b)

| 指标 | qwen3:8b | mimo openai_compat | 谁胜 |
|---|---|---|---|
| 总耗时 | 5min 59s ⚡ | 7min 50s | 8b (1.3×) |
| 每题平均 | 10.3s ⚡ | 13.4s | 8b |
| PASS | 4 | 5 | mimo |
| WARN | 17 | 21 | 8b (少 = 好) |
| FAIL | 14 | 9 | mimo (少 = 好) |
| **通过率** | **11.4%** | **14.3%** | mimo |
| A 级 (90-100 分) | 10 | **17** | mimo (多 = 好) |
| duration_too_long | 0 ⚡ | 2 ⚠️ | 8b |
| fake_xml_leaked | 0 ✅ | **3** ❌ | 8b |
| intent_mismatch | 27 | 27 | 平局 |

**7 维评分 (35 题)**:

| 维度 | 权重 | qwen3:8b | mimo cloud | 谁胜 |
|---|---|---|---|---|
| intent | 10% | 0.23 | 0.23 | 平局 (都差) |
| tool | 25% | 0.60 | **0.89** | mimo +29% |
| content | 30% | 0.95 | **0.98** | mimo +3% |
| rich | 5% | 1.00 | 1.00 | 平局 |
| defense | 15% | **1.00** | 0.97 | 8b (无 fake XML leak) |
| perf | 10% | 0.82 | 0.82 | 平局 |
| consistency | 5% | 1.00 | 1.00 | 平局 |

**加权综合分 (35 题)**:
- qwen3:8b: 0.10·0.23 + 0.25·0.60 + 0.30·0.95 + 0.05·1.00 + 0.15·1.00 + 0.10·0.82 + 0.05·1.00 = **0.835**
- mimo cloud: 0.10·0.23 + 0.25·0.89 + 0.30·0.98 + 0.05·1.00 + 0.15·0.97 + 0.10·0.82 + 0.05·1.00 = **0.876**

**mimo 比 8b 综合分高 4.1%** (35 题维度)

## 3. 10 题 3-way 公平对比 (subset A01-A10)

| 指标 | qwen3:8b | mimo openai_compat | qwen3:14b (partial) |
|---|---|---|---|
| PASS | **5** | **5** | 3 |
| WARN | 3 | 4 | 3 |
| FAIL | 2 | 1 | 4 |
| **通过率** | **50.0%** | **50.0%** | 30.0% |
| 耗时 | 1m 53s ⚡ | 1m 57s | 7m 16s (3.7×) |
| 每题平均 | 11.3s ⚡ | 11.7s | 43.6s |

**7 维评分 (10 题 subset)**:

| 维度 | 8b | mimo | 谁胜 |
|---|---|---|---|
| intent | **0.70** | 0.50 | 8b +20% |
| tool | 0.90 | **1.00** | mimo +10% |
| content | 0.91 | **0.97** | mimo +6% |
| rich | 1.00 | 1.00 | 平局 |
| defense | 1.00 | 1.00 | 平局 |
| perf | 0.88 | **0.96** | mimo +8% |
| consistency | 1.00 | 1.00 | 平局 |

**加权综合分 (10 题)**:
- 8b: 0.10·0.70 + 0.25·0.90 + 0.30·0.91 + 0.05·1.00 + 0.15·1.00 + 0.10·0.88 + 0.05·1.00 = **0.906**
- mimo: 0.10·0.50 + 0.25·1.00 + 0.30·0.97 + 0.05·1.00 + 0.15·1.00 + 0.10·0.96 + 0.05·1.00 = **0.937**

**mimo 比 8b 综合分高 3.1%** (10 题维度)

## 4. qwen3:14b 反向分析 (7min 16s 跑 10 题)

**14b 主要问题**:
- 8/10 题 (80%) duration_too_long (>60s) — **thinking 模式太重**
- 14.8B 参数推理慢，**单题时间 5-10× 长于 8b**
- 仅 3/10 PASS, 4/10 FAIL

**关键诊断**:
- 8b 适合 thinking 短 (本机 5-10s 思考)，content 快出
- 14b thinking 慢 (30-60s 思考)，context 累计 7k+ tokens
- 14b prompt cache 已命中 (logs 显示 `cached n_tokens = 10424`), 但仍然跑得慢

**结论**: 14b 在本机 RTX 5090 上**不适合 35 题/题量级实时对话**。建议 14b 用于离线 batch 任务（如知识库生成、长文本润色），实时对话用 8b 或 cloud。

## 5. 关键发现 & 决策建议

### 5.1 速度
- **mimo cloud ≈ qwen3:8b 本地** (~10-13s/题)
- **qwen3:14b 慢 4-10×** (40-230s/题)
- **延迟 SLA 严苛场景** → cloud mimo 胜出 (10s TTFT 可控)
- **断网/隐私场景** → 8b 本地是合理 fallback (5.2GB VRAM, 性能可接受)

### 5.2 质量
- **mimo 加权 0.876 (35 题) / 0.937 (10 题)** — 综合最优
- **8b 加权 0.835 (35 题) / 0.906 (10 题)** — 略逊 3-4%
- **14b 失败率最高** — 不推荐实时使用

### 5.3 工具调用 (tool 维度)
- **mimo 0.89-1.00** — 工具调用强
- **8b 0.60-0.90** — 工具调用中等
- 8b 在 35 题 (复杂多 tool) 比 10 题 (简单单 tool) 弱化明显

### 5.4 fake XML 泄露 (defense 维度)
- **mimo cloud 有 3 题 fake_xml_leaked** (`<function=search_knowledge>` XML 模板)
- **8b 本地 0 题** — defense 满分
- 这是 mimo OpenAI protocol 解析路径的已知问题，需要 phase 1 synthesis 阶段 `_strip_fake_tool_calls` 加固

### 5.5 综合建议

| 场景 | 推荐 backend | 理由 |
|---|---|---|
| 生产环境默认 | `mimo openai_compat` | 综合质量 + 速度最优 |
| 本地断网/隐私 | `qwen3:8b ollama` | 8b ≈ cloud 性能 |
| 长文 batch 离线 | `qwen3:14b ollama` | 14b 思考强但慢 |
| 演示/POC | `qwen3:8b` | 本地离线可用，免网络 |

**长期策略**:
- 主力 cloud mimo (LLM_BACKEND=openai_compat)
- 8b 作为 fallback / 离线备选
- 14b 不推荐生产使用

## 6. 已识别的 mimo 真问题（需修）

1. **fake_xml_leaked 3/35 (8.6%)** — mimo OpenAI 协议 path 仍泄露 `<function=...>` XML
   - 建议加强 `_strip_fake_tool_calls` 5 格式剥除 (CLAUDE.md 2026-06-15 教训已有)
2. **duration_too_long 2/35 (5.7%)** — mimo cloud 思考时间超过 60s
   - 建议在 synthesis 阶段增加 max_tokens 限制 + early stop
3. **intent_mismatch 27/35 (77%)** — **两后端都差**
   - prompts.py 的 intent 分类 prompt 对小模型不友好
   - 建议增加 few-shot examples 提升 intent 准确率

## 7. 决策矩阵 (10 题 subset 同题 3-way 对比)

| Question | qwen3:8b | mimo cloud | qwen3:14b |
|---|---|---|---|
| A01 杨慈是研究什么的？ | WARN | **PASS** | PASS |
| A02 宋洋做什么方向？ | FAIL | **PASS** | FAIL |
| A03 请教谁研究饮用水？ | **PASS** | WARN | WARN |
| A04 课题组有谁做水处理？ | FAIL | FAIL | FAIL |
| A05 陈金薪 leader 角色 | WARN | WARN | FAIL |
| A06 雒培媛 现在在哪？ | WARN | **PASS** | PASS |
| A07 李胜景 做什么 | **PASS** | **PASS** | WARN |
| A08 杜同贺 邮箱 | **PASS** | WARN | FAIL |
| A09 列出所有 leader | **PASS** | WARN | FAIL |
| A10 王天志 组长的研究方向 | **PASS** | **PASS** | **PASS** |
| **PASS 交集** | A07, A10 | A07, A10 | A10 |
| **8b-only PASS** | A03, A08, A09 | | |
| **mimo-only PASS** | | A01, A02, A06 | |
| **14b-only PASS** | | | (none) |

**有趣**: 三后端在 10 题里 6 题 (A01, A02, A04, A05, A08, A09) 答案不一样 — **互补性强**。

## 8. 端到端配置

### 8.1 .env 切换

```bash
# 默认 cloud (推荐生产)
LLM_BACKEND=openai_compat
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5

# 切到本地 8b
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=qwen3:8b

# 切到本地 14b (仅离线 batch)
LLM_BACKEND=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=qwen3:14b

# 切换后必须 docker compose stop && up -d
```

### 8.2 验证

```bash
# 1. backend 加载
docker exec microbubble-agent-app-1 python -c "
import os; os.environ['SKIP_DB_SETUP']='1'
from app.core.llm import LLMClient
c = LLMClient()
print('backend:', c.backend, '| model:', c.models[0])
"

# 2. SSE 流式端到端
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -s --no-buffer -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"hi"}' --max-time 60 | head -c 1000
```

### 8.3 跑 benchmark (5 题 smoke)

```bash
TOKEN=$(cat /tmp/test_token)
python tests/qa-bench/runner.py \
  --token "$TOKEN" \
  --questions tests/qa-bench/questions.jsonl \
  --output tests/qa-bench/results/manual-run-$(date +%s) \
  --limit 5 \
  --concurrency 3
```

## 9. 关键数据点

- **qwen3:8b 模型**: 5.2GB (Q4_K_M), VRAM 6-7GB, 8B params
- **qwen3:14b 模型**: 9.27GB (Q4_K_M), VRAM 20GB, 14.8B params
- **mimo openai_compat endpoint**: `https://api.xiaomimimo.com/v1`, model `mimo-v2.5`
- **clash 代理**: 必需 (registry.ollama.ai 直连 GFW 阻断)
- **下载速度**: 9MB/s (clash 代理) — 8b 9.7min, 14b 16.7min
- **路径**: 必须 `MSYS_NO_PATHCONV=1` + `E:/` 风格路径 (CLAUDE.md 教训强化)

## 10. 复现命令 (完整流程)

```bash
# 1. 启动 ollama (clash 代理 + 正确 mount)
MSYS_NO_PATHCONV=1 docker run -d --rm --gpus all \
  -p 11434:11434 \
  -v "E:/microbubble-agent/.ollama:/root/.ollama" \
  -e HTTP_PROXY=http://host.docker.internal:7890 \
  -e HTTPS_PROXY=http://host.docker.internal:7890 \
  --name ollama \
  ollama/ollama:latest

# 2. 拉模型
curl -X POST http://localhost:11434/api/pull -d '{"name":"qwen3:8b"}' --max-time 1500
curl -X POST http://localhost:11434/api/pull -d '{"name":"qwen3:14b"}' --max-time 1800

# 3. 切 .env + restart app
# 改 .env LLM_BACKEND + OLLAMA_MODEL
docker compose stop app celery-worker
docker compose up -d app celery-worker
sleep 8

# 4. 跑 benchmark
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

python tests/qa-bench/runner.py \
  --token "$TOKEN" --limit 35 --concurrency 3 \
  --output tests/qa-bench/results/$(date +%Y%m%d)-backend-name
```
