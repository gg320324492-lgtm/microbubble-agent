---
name: llm-benchmark-2026-07-02
description: 2026-07-02 云 mimo vs 本地 qwen3:8b/14b 3-way qa-bench benchmark 结果 — 推荐保持 cloud mimo，8b 离线 fallback
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2f289a0b-325f-44ba-9800-0497bc3a25ac
---

# LLM 3-Way Benchmark (2026-07-02)

## Context

v2 网盘 PR6 收官后，用户要求对比云 mimo-v2.5 (openai_compat) vs 本地 qwen3:8b/14b 在 qa-bench 35 题上的表现，决定生产环境 LLM_BACKEND 切到哪个。

## 端到端执行

1. 切 `.env` LLM_BACKEND=ollama + docker compose stop+up 重启（`docker compose restart` 不重读 env_file，**必须 stop+up**）
2. 拉 qwen3:8b (5.2GB) + qwen3:14b (9.27GB, 16.7min)，**走 clash 代理** (registry.ollama.ai 直连 GFW 阻断 0KB/s)
3. docker cp 容器内代码 + 切 backend + 跑 35 题 benchmark
4. 用 --limit 10 重跑做 3-way 公平对比 (14b 跑测超时只完成 10 题)

## 结果

| Backend | 35 题 | 10 题 subset | 加权综合分 (10 题) |
|---|---|---|---|
| mimo openai_compat (云) | 14.3% PASS | 50% (5/10) | **0.937** ⭐ |
| qwen3:8b (本地) | 11.4% PASS | 50% (5/10) | 0.906 |
| qwen3:14b (本地) | ❌ partial 12/35 | 30% (3/10) | N/A (太慢) |

详细报告 [docs/llm-benchmark-2026-07-02.md](../../microbubble-agent/docs/llm-benchmark-2026-07-02.md)

## 7 大铁律

### 铁律 1：clash 代理必需 + 走 OLLAMA Go client HTTP_PROXY env

GFW 阻断 `registry.ollama.ai` 直连（0KB/s, 5min 下载 130KB）。但**加 `HTTP_PROXY=http://host.docker.internal:7890` env 到 ollama 容器后 9MB/s**。

CLAUDE.md 之前说"Ollama Go client 不读 HTTP_PROXY"，但实测 **0.31.1 + HTTP_PROXY env 工作**（2026-07-02 验证）— 上游可能后来修了。

### 铁律 2：docker run 路径必须 `MSYS_NO_PATHCONV=1`

Git Bash 把 `E:\microbubble-agent\.ollama` 翻译成 `C:\Program Files\Git\.ollama`，导致 bind mount 失败，ollama pull 实际写到容器内 `/root/.ollama`（5GB 数据丢失风险）。

```bash
# ✅ 正确
MSYS_NO_PATHCONV=1 docker run -d --rm --gpus all \
  -p 11434:11434 \
  -v "E:/microbubble-agent/.ollama:/root/.ollama" \
  -e HTTP_PROXY=http://host.docker.internal:7890 \
  ollama/ollama:latest

# ❌ 错误（Git Bash 翻译 Windows 路径）
docker run -d -v E:\microbubble-agent\.ollama:/root/.ollama ...
```

### 铁律 3：Ollama `--network host` 在 Docker Desktop Windows bind IPv6 only

`--network host` + `ollama/ollama` 容器默认只 bind `[::]:11434` (IPv6)，Windows `localhost:11434` 走 IPv4 → connection refused。

**Workaround**: 用 `-p 11434:11434` 强制 IPv4 NAT 转发（CLAUDE.md 2026-06-13 已有此教训）。

### 铁律 4：`docker compose restart` 不重读 env_file，必须 stop+up

`restart` 复用容器进程，env vars 保留上次启动时的值。**必须 `docker compose stop X && docker compose up -d X`** 才能让 `LLM_BACKEND` 切换生效。

### 铁律 5：qwen3:8b 是 cloud 备选，不是替代品

- 8b 速度 ≈ mimo cloud（10-13s/题）
- 8b 通过率 50%（10 题） = mimo cloud 50%（10 题）— **平局**
- 8b defense 维度 1.00 > mimo 0.97（无 fake XML leak）
- 8b tool 维度 0.60-0.90 < mimo 0.89-1.00（工具调用弱）
- 8b 5.2GB VRAM, 16GB 显卡可装（生产环境 32GB 充足）

### 铁律 6：qwen3:14b 慢 4× 且通过率反而低，**不适合实时对话**

- 14b 思考模式消耗 200+ tokens 思考，单题 40-230s
- 80% 题 duration_too_long (>60s)
- PASS rate 反而 30% (10 题) < 8b 50%
- 推荐场景：离线 batch（知识库生成 / 长文润色），**不推荐实时聊天**

### 铁律 7：mimo openai_compat 有 3 大待修问题

跑 35 题发现：
1. **fake_xml_leaked 3/35 (8.6%)** — `<function=search_knowledge>` XML 泄露给用户
2. **duration_too_long 2/35 (5.7%)** — mimo thinking 超过 60s
3. **intent_mismatch 27/35 (77%)** — prompts.py intent 分类对所有 LLM 都不友好

**修法 (CLAUDE.md 2026-06-15 教训已有)**:
- 加固 `_strip_fake_tool_calls` 5 格式剥除
- synthesis 阶段 max_tokens 限制 + early stop
- prompts.py intent 分类加 few-shot examples

## 部署必做

```bash
# 1. 启动 ollama (clash 代理 + 正确 mount + 8b/14b 拉测)
MSYS_NO_PATHCONV=1 docker run -d --rm --gpus all \
  -p 11434:11434 \
  -v "E:/microbubble-agent/.ollama:/root/.ollama" \
  -e HTTP_PROXY=http://host.docker.internal:7890 \
  -e HTTPS_PROXY=http://host.docker.internal:7890 \
  --name ollama \
  ollama/ollama:latest

curl -X POST http://localhost:11434/api/pull -d '{"name":"qwen3:8b"}' --max-time 1500
curl -X POST http://localhost:11434/api/pull -d '{"name":"qwen3:14b"}' --max-time 1800

# 2. 切 .env + stop+up (restart 不重读 env)
# .env: LLM_BACKEND=ollama + OLLAMA_MODEL=qwen3:8b
docker compose stop app celery-worker
docker compose up -d app celery-worker
sleep 8

# 3. 验证
docker exec microbubble-agent-app-1 python -c "
import os; os.environ['SKIP_DB_SETUP']='1'
from app.core.llm import LLMClient
c = LLMClient()
print(c.backend, c.models[0])
"

# 4. 跑 5 题 smoke
TOKEN=$(curl -sk -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

python tests/qa-bench/runner.py \
  --token "$TOKEN" --limit 5 --concurrency 3 \
  --output tests/qa-bench/results/smoke-$(date +%s)
```

## 与 CLAUDE.md 其他教训的关联

- **2026-06-15 prompts.py 元话语 + JSON 剥除**：mimo fake_xml_leaked 8.6% 来源
- **2026-06-30 KB 数据清洁**：3 个 chart 跨 v2 PR6 收官
- **2026-07-01 ToolCallConverter**：openai_compat 路径已稳定
- **2026-07-02 reranker-upgrade Phase I**：BGE m3 + 7 铁律 + 同步本地 LLM 部署
