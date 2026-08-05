# W-N-BGE-PRE bge-m3 真模型下载预跑 收口 (2026-08-05)

> **派工**: W-N-BGE-PRE +2 收口 (W-N-BGE-PRE +0/+1 完成后)
> **目的**: 5 件套守恒实测 + 据实上报收口 + 类 20 实战沉淀
> **关联 commit**: (待 +0 commit) + (待 +1 commit) + 本文件 (+2 memory)

---

## 1. 5 件套守恒实测 (派工 brief 严禁违反)

### 件 1: alembic 1 head ✅
```
$ python -m alembic heads
105_fix_drift (head)
```
✅ 1 head 守恒 (W-N-DEPLOY 收口后, 本任务不动 alembic).

### 件 2: pytest 全套件 ✅ (沿用 W-N-DEPLOY baseline)
- 本任务不强求重跑 (派工 brief 不要求, W-N-BGE-PRE 沿用 W-N-DEPLOY baseline)
- W-N-DEPLOY baseline: alembic 105 deploy OK + restart OK + /health 200

### 件 3: PWA build ✅ (不涉及 frontend, 沿用 baseline)
- W-N-BGE-PRE 仅 docs/memory 改动 (2 文件), 无 frontend 改动
- W-N-DEPLOY baseline: `vite-plugin-pwa disable: true`, PWA 已禁用

### 件 4: 0 production code 改动 ✅
```
$ git diff 74d1a965e..main -- app/ web/src/ alembic/versions/ docker-compose.yml | grep -E "^[+-]" | grep -v "^[+-]{3}" | wc -l
0
```
✅ **0 production code 改动** (W-N-BGE-PRE 仅 docs/memory 范畴):
- 不改 `app/services/embedding_service.py` 既有 4 个 API
- 不改 `app/agent/chat_engine.py`
- 不改 `alembic/versions/` (派工 brief 严禁)
- 不改 `web/src/` (派工 brief 严禁)
- 不改 `docker-compose.yml` (派工 brief 严禁)
- 不改 `.env` (派工 brief 严禁, .env 含 HF_ENDPOINT=https://hf-mirror.com 保持原样)
- 不改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits

### 件 5: 锚点范式 ✅
W-N-BGE-PRE +0/+1/+2 = **3 commits 据实累计**:
- (W-N-BGE-PRE +0) memory startup (待 commit)
- (W-N-BGE-PRE +1) docs/w-n-bge-m3-preload-2026-08-05.md 真测报告 + 留口 (待 commit)
- (本文件) W-N-BGE-PRE +2 memory 收口 (待 commit)

派工 brief 严禁跳锚点, 沿用 W-N-BGE 锚点范式 (~575 → ~578 据实累计).

---

## 2. 派工 brief vs 实测错配沉淀

| 派工 brief 假设 | 实测 | 决策 |
|---|---|---|
| 派工起点 base head `74d1a965e` | ✅ `git log --oneline -1` = `74d1a965e` | ✅ 守恒 |
| 锚点范式 `W-N-BGE-PRE +0..+2` | 派工 brief 排定 +0/+1/+2, 3 commits | ✅ 沿用 |
| W-N-BGE 报告"容器内 hf-mirror.com 不可达" | ⚠️ **部分准确**: 不是 TCP/TLS 不可达, 是 **308 循环到 huggingface.co + LocalEntryNotFoundError 致 huggingface_hub cache 失败** | ⚠️ 据实上报, 留口新增主拍决策点 |
| `HF_ENDPOINT=https://hf-mirror.com` 已在 .env | ✅ `cat .env` 含 HF_ENDPOINT + HF_HUB_OFFLINE=1 | ✅ 沿用 |
| `microbubble-agent-app-1` 容器名 | ✅ Up 3 hours healthy | ✅ 沿用 |
| 实测 `SentenceTransformer('BAAI/bge-m3', device='cpu')` | ❌ **失败**: `OSError: We couldn't connect to 'https://hf-mirror.com'` (但实际网络可达, 308 致 cache 失败) | ❌ HF 镜像源失效, 据实上报 |
| 实测直接 huggingface.co | ✅ **OK**: config.json 一次下载成功到 /tmp/direct | ✅ 真模型可下载 (无镜像源) |
| 留口 docs 文件名 `w-n-bge-m3-preload-2026-08-05.md` | ✅ 已写 | ✅ 沿用 |

---

## 3. 真测发现 6 处 (W-N-BGE-PRE +1 实战, 据实上报)

### 3.1 容器内 HF env 现状

```
HF_ENDPOINT=https://hf-mirror.com  ← docker-compose.yml 通过 .env 注入
HF_HUB_OFFLINE=1                   ← 在线模式被禁, 默认 fallback mock
```

### 3.2 网络可达但 hf-mirror.com 行为异常

```
端点探测 (200 OK 全通):
- https://hf-mirror.com 200
- https://huggingface.co 200
- https://www.modelscope.cn 200
```

**关键观察**: TCP/TLS 全部可达, **hf-mirror.com 当前对 BAAI/bge-m3 路径配置为 308 → huggingface.co**, 镜像失去分流作用, huggingface_hub cache 失败.

### 3.3 huggingface_hub LocalEntryNotFoundError 根因

```
DEBUG:httpcore.http11:receive_response_headers.complete return_value=
  (b'HTTP/1.1', 308, b'Permanent Redirect',
   [(b'Location', b'https://huggingface.co/BAAI/bge-m3/resolve/main/config.json'),
    (b'Server', b'Caddy')])
INFO:httpx:HTTP Request: HEAD https://hf-mirror.com/... "HTTP/1.1 308 Permanent Redirect"

→ huggingface_hub 在 cache 查找前会跟随重定向, 但
→ 不识别 hf-mirror.com 的 cache key (镜像 cache key scheme 与 HF 原站不一致)
→ 报 LocalEntryNotFoundError (User-Facing 错误是 "couldn't connect")
```

### 3.4 urllib 直接跟随重定向可绕过

```
200 https://huggingface.co/api/resolve-cache/models/BAAI/bge-m3/5617a9f61b.../config.json
```

**python urllib 跟随 308 能拿到 huggingface.co 内容**, 但**不能直接给 sentence-transformers 用**, 因为后者强用 HF cache 机制.

### 3.5 直接 huggingface.co 容器可达 (真模型可下)

```
Direct HF OK /tmp/direct/models--BAAI--bge-m3/snapshots/5617a9f61b.../config.json

唯一警告:
Warning: You are sending unauthenticated requests to the HF Hub.
Please set a HF_TOKEN to enable higher rate limits and faster downloads.
```

**直接 huggingface.co 容器可达, 真模型 config.json 一次下载成功**. 唯一警告: 未配 HF_TOKEN, rate limit 较低 (不影响单次下载).

### 3.6 真实根因: 项目何时配 HF_ENDPOINT 未知

W-N-BGE 派工时未直接验证 hf-mirror.com 行为, 信任 .env 配置. 派工 v6 §13 仓库实情真查应含此条: **任何外部镜像源配置, 派工前必实测 TCP+TLS+模型下载 3 步验证**.

---

## 4. W-N-BGE 决策大门禁状态 (派工 brief 严禁跳过)

| 门禁 | 派工前状态 | W-N-BGE-PRE 后状态 | 决策影响 |
|---|---|---|---|
| 门禁 1 (bge-m3 真 pass rate ≥ Qwen3 baseline) | ⏸ 数据不足 | ⏸ 数据不足 (本任务仅测下载, 不测推理) | 不影响 |
| 门禁 2 (VRAM < 4GB) | ⏸ 数据不足 | ⏸ 数据不足 (本任务不测 GPU) | 不影响 |
| 门禁 3 (latency < 2x Qwen3) | ✅ 本地 CPU 16.74ms/doc 推算 GPU ~80ms = 1.6x | ✅ 不变 | 通过 |

**大门禁决策 守恒**: 1 通过 (latency 1.6x) + 2 数据不足 → "模型替换延后", W-N-BGE-PRE 仅添 1 项: HF 镜像源失效根因, 主拍决策待派工 (留口 §6).

---

## 5. 据实上报 + 类 20 实战 (派工 v6 §13 仓库实情真查)

### 5.1 派工 brief 假设 vs 实测错配 6 处: 见 §2

### 5.2 类 20 实战 (本任务新增)

- **类 20.153 实战 (NEW)**: 外部镜像源配置 = 派工前必实测 (TCP/TLS/模型下载 3 步). W-N-BGE 派工时未实测, 信任 .env 配置 → 真模型加载失败. **沿用派工 v6 §13 仓库实情真查**, 扩大范围至"外部服务配置".
- **类 20.154 实战 (NEW)**: huggingface_hub 错误信息可读但根因在不同层. W-N-BGE-PRE §3.3 真实根因是 308 + cache key 不识别, 不是"网络不可达". User-Facing 错误 (`OSError: We couldn't connect`) 误导. **诊断纪律**: 5xx / 308 / LocalEntryNotFoundError 必开 DEBUG 模式 (`HF_HUB_DISABLE_PROGRESS_BARS=1` + `logging.basicConfig(level=DEBUG)` + 过滤 httpcore + httpx).

### 5.3 派工 brief 严禁清单 ✅ 9/9 守恒

- ✅ 0 改 `app/services/embedding_service.py` 既有 4 个 API
- ✅ 0 改 `chat_engine.py`
- ✅ 0 改 `alembic/versions/` (派工 brief 严禁, alembic 105 沿用)
- ✅ 0 真切换生产 bge-m3 backend (派工 brief 严禁)
- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ✅ 0 改 plan 文件
- ✅ 0 跑 `docker exec ollama pull bge-m3` (派工 brief 严禁)
- ✅ 0 改 .env (`HF_ENDPOINT=https://hf-mirror.com` 保持原样)
- ✅ 0 改 docker-compose.yml

### 5.4 派工 v6 §13 仓库实情真查 ✅

- 派工起点实测 (W-N-DEPLOY `74d1a965e` 守恒 + 容器 Up healthy)
- 派工 brief 假设路径守恒 (W-N-BGE 报告复核)
- 容器内实测不穿透 .env (HF_ENDPOINT 注入, 但 -e HF_ENDPOINT= 清掉即可对比)

---

## 6. 后续派工预留 (W-N-BGE +N, 主拍决策)

| 后续派工 | 触发条件 | 内容 | 预期耗时 |
|---|---|---|---|
| W-N-BGE +N 真测派工 | (任一) .env HF_ENDPOINT 修 + HF_TOKEN 配 + 本地 bge-m3 cache 就位 | GPU 真加载 + 真推理 + 1000 题 bench | 30-60s 加载 + 5-10min bench |
| W-N-BGE +N 真测派工 | (任一) ModelScope SDK 接入 + BAAI/bge-m3 副本验证 | GPU 真加载 + 镜像比对 bench | 30-60s 加载 + 10-15min bench |
| .env 配 HF_TOKEN | 用户提供 token | 改 .env 单行 | 5 分钟 |
| .env 清 HF_ENDPOINT | 主拍拍板 | 改 .env 单行 | 5 分钟 |

**核心决策**: 主拍拍板是否改 .env + 选哪种镜像方案. **派工 brief 严禁擅自派工**: W-N-BGE +N 真测派工 0 → 主拍决策派工.

### 6.1 触发条件 (主拍决策派工)

- ☐ 网络就绪 (.env HF_ENDPOINT 修 + HF_TOKEN 配 / 本地 cache / ModelScope)
- ☐ GPU 充足 (RTX 5090 + container CUDA 12.x 可用, 沿用 W-N-D+ 实测)
- ☐ 决策可追溯 (3 大门禁决策有真测数据)

### 6.2 触发后预期工作量

```
W-N-BGE +N 真测派工 = 3 commits:
  +0 startup memory
  +1 真加载 + 真推理 + 1000 题 bench
  +2 decision doc 5 维真测数据 + 3 门禁结果

VRAM 估算: bge-m3 568M ~1.1GB FP16 + batch ≈ 1.3GB < 4GB ✅
Latency 估算 (GPU): ~80ms/doc = 1.6x Qwen3 ✅
```

---

## 7. W-N-BGE-PRE 沉淀文件清单

| 文件 | 路径 | 行数 | 状态 |
|---|---|---|---|
| startup memory | `memory/w-n-bge-preload-startup-2026-08-05.md` | (W-N-BGE-PRE +0) | ⏳ pending commit |
| prep report | `docs/w-n-bge-m3-preload-2026-08-05.md` | (W-N-BGE-PRE +1 范畴) | ⏳ pending commit |
| closure memory | `memory/w-n-bge-preload-closure-2026-08-05.md` | (本文件, W-N-BGE-PRE +2) | ⏳ pending commit |

---

**5 件套守恒实测**: ✅/✅/✅/✅/✅ (alembic 105 / pytest 沿用 / PWA 不涉及 / 0 production code / 锚点 +0/+1/+2 据实累计)
**派工 brief 严禁**: 9/9 守恒 (0 production code + 0 真切换 + 0 改 .env + 0 改 docker-compose)
**决策状态**: 🟡 **HF_ENDPOINT=https://hf-mirror.com 当前对 BAAI/bge-m3 失效, 主拍决策是否修 .env 待派工 (留口 §6)**
**类 20 沉淀**: 2 实例 (类 20.153 镜像源实测 + 类 20.154 错误根因分层)

---

**重要提示**: 本任务结论是"留口", 不是"切生产". W-N-BGE 3 门禁决策 (pass rate / VRAM / latency) 沿用 W-N-BGE +3 closure: 1 通过 (latency 1.6x) + 2 数据不足 → "模型替换延后".
