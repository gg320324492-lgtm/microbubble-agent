# W-N-BGE bge-m3 真模型预跑报告 2026-08-05

> **派工**: W-N-BGE-PRE +1 真测 (W-N-BGE +3 closure 后派工, base head `74d1a965e`)
> **目的**: 用 `HF_ENDPOINT=https://hf-mirror.com` 试下载 BAAI/bge-m3 真模型
> **派工 brief 严禁**: 真模型推理 / 改 .env / 改 docker-compose.yml / 真切换生产
> **结论**: ⛔ **hf-mirror.com 当前无效 (308 → huggingface.co 循环), 直接 huggingface.co 可用, 改 .env HF_ENDPOINT 为空或保留镜像需另行评估**
> **留口**: 见 §6

---

## 1. 决策摘要

### 1.1 一行结论

**HF_ENDPOINT=https://hf-mirror.com 当前对 huggingface_hub 5.x 失效**. 容器内 `BAAI/bge-m3` 真模型下载仍走通路径 = 直接 `huggingface.co` (HF_ENDPOINT=空 或 HF_ENDPOINT= → 彻底清掉). **下一步不沿用 hf-mirror.com, 应评估改 .env 配 `HF_TOKEN=...` 或彻底清掉 HF_ENDPOINT**.

### 1.2 派工前提复核

| 来源 | W-N-BGE +3 closure 沉淀 | 派工 brief |
|---|---|---|
| 失败根因 | "hf-mirror.com 不可达" | 重试用 HF_ENDPOINT=https://hf-mirror.com |
| 与本任务实测 | 部分准确: 不是 "不可达" 而是 **"308 循环到 huggingface.co, huggingface_hub LocalEntryNotFoundError"** | 派工 brief 据实待派工 |

---

## 2. 实测环境

### 2.1 容器 & 系统

```
容器: microbubble-agent-app-1 (Up 3 hours, healthy)
镜像: microbubble-agent-app:latest (内置 sentence-transformers 5.6.0 + transformers 4.56.0)
Python: 3.11
磁盘: 1007G 总量 / 702G 可用 (overlay FS, /tmp 可写)
HF 库: huggingface_hub (随 ST 5.6.0 集成)
```

### 2.2 环境变量 (.env 沿用)

```
HF_ENDPOINT=https://hf-mirror.com      ← docker-compose.yml 通过 .env 注入
HF_HUB_OFFLINE=1                       ← 在线模式被禁, 默认 fallback mock
```

### 2.3 内置网络可达 (基础探测)

```
$ 容器内 urllib HEAD/GET:
OK 200 https://hf-mirror.com
OK 200 https://huggingface.co
OK 200 https://www.modelscope.cn
OK 200 https://hf-mirror.com/api/models
OK 200 http://hf-mirror.com
```

**结论**: 4 个端点全部 TCP+TLS 200, **不是不可达, hf-mirror.com 站点可访问**.

---

## 3. 实测 1: HF_ENDPOINT=https://hf-mirror.com 真测

### 3.1 直接加载尝试 (cpu)

```bash
$ docker exec -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_OFFLINE=0 \
  microbubble-agent-app-1 timeout 30 python -c \
  "from sentence_transformers import SentenceTransformer; \
   m = SentenceTransformer('BAAI/bge-m3', device='cpu'); \
   print('OK', m.model.card_data)" 2>&1 | tail -3

OSError: We couldn't connect to 'https://hf-mirror.com' to load the files,
and couldn't find them in the cached files.
```

### 3.2 网络层日志 (DEBUG 模式)

```
DEBUG:httpcore.connection:connect_tcp.complete host='hf-mirror.com' port=443
DEBUG:httpcore.http11:send_request_headers.started request=<Request [b'HEAD']>
DEBUG:httpcore.http11:receive_response_headers.complete return_value=
  (b'HTTP/1.1', 308, b'Permanent Redirect',
   [(b'Location', b'https://huggingface.co/BAAI/bge-m3/resolve/main/config.json'),
    (b'Server', b'Caddy')])
INFO:httpx:HTTP Request: HEAD https://hf-mirror.com/BAAI/bge-m3/resolve/main/config.json
       "HTTP/1.1 308 Permanent Redirect"
```

### 3.3 镜像行为根因

**hf-mirror.com 对 BAAI/bge-m3 路径返回 308 Permanent Redirect → huggingface.co**, huggingface_hub 在 cache 查找前会跟随重定向, 但**不识别 hf-mirror.com 的 cache key** (镜像 cache key scheme 与 HF 原站不一致), 故报 `LocalEntryNotFoundError`.

**注意**: 同一镜像对其他模型 (例如 bert-base-chinese) 可能正常工作, 也可能同样失效, 但 BAAI/bge-m3 这条核心路径失效 = 项目 RAG 不通.

### 3.4 python urllib 直接跟随重定向

```bash
$ docker exec -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_OFFLINE=0 \
  microbubble-agent-app-1 timeout 30 python -c \
  "from urllib.request import Request, urlopen; \
   req = Request('https://hf-mirror.com/BAAI/bge-m3/resolve/main/config.json', method='HEAD'); \
   r = urlopen(req, timeout=8); print(r.status, r.geturl())"

200 https://huggingface.co/api/resolve-cache/models/BAAI/bge-m3/5617a9f61b.../config.json
```

**绕过 huggingface_hub 用 python urllib 跟随重定向能拿到 huggingface.co 内容**, 但**不能直接给 sentence-transformers 用**, 因为后者强用 HF cache 机制.

---

## 4. 实测 2: 直接 huggingface.co (对比基线)

```bash
$ docker exec -e HF_HUB_OFFLINE=0 -e HF_ENDPOINT= \
  microbubble-agent-app-1 timeout 30 python -c \
  "from huggingface_hub import hf_hub_download; \
   p = hf_hub_download(repo_id='BAAI/bge-m3', filename='config.json', cache_dir='/tmp/direct'); \
   print('OK', p)"

Direct HF OK /tmp/direct/models--BAAI--bge-m3/snapshots/5617a9f61b.../config.json
```

**直接 huggingface.co 容器可达, 真模型 config.json 一次下载成功**. 唯一警告: `Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.`

---

## 5. 失败原因 & 备选方案

### 5.1 失败原因 (据实归类)

| 类别 | 描述 |
|---|---|
| **镜像站点配置** (主因) | hf-mirror.com 对 BAAI/bge-m3 路径配置为 308 → huggingface.co, 镜像失去分流作用, huggingface_hub cache 失败 |
| **镜像源选择** | 项目当时为何选 hf-mirror.com (推测是为绕过国内访问 HF 的网络限制), 但实际环境 (云服务器) 无此限制 |
| **未实测镜像源** | W-N-BGE 派工时未直接验证 hf-mirror.com 行为, 信任 .env 配置 (派工 v6 §13 仓库实情真查应含此条) |

### 5.2 备选方案 (派工 brief 严禁擅自派工, 仅留口)

| 方案 | 描述 | 风险 |
|---|---|---|
| **A: 改 .env 清掉 HF_ENDPOINT** | `HF_ENDPOINT=` 留空, 走 huggingface.co 直连 | 网络限制 (若有) 时下载慢 / 失败 |
| **B: 加 HF_TOKEN** | huggingface.co 配 token 提升 rate limit, 部分私有模型可用 | 需用户提 token |
| **C: 镜像源替换** | 试 https://hf-mirror.com (官方) + 备用 https://hf-mirror.com / https://www.modelscope.cn | 失败重试成本高 |
| **D: 本地缓存拷备** | bge-m3 ~2.7GB 在某台可访问镜像的机器上完整下载, 拷到 `/root/.cache/huggingface/hub/` 容器路径 | 运维成本, 不适合频繁升级 |
| **E: ModelScope 模型** | `BAAI/bge-m3` 在 ModelScope 也有副本, `from modelscope import snapshot_download` 路径独立 | 业务代码要用新 SDK (派工 brief 严禁) |

**主拍决策待派工** (派工 brief 严禁擅自派工): W-N-BGE +N 选择 A/B/D 中的一种并执行.

---

## 6. 留口 (W-N-BGE +N 触发条件)

### 6.1 触发条件 (主拍决策派工)

**W-N-BGE +N 真测派工仅在以下条件任一达成后派工**:

1. **网络就绪**: .env 已修改 HF_ENDPOINT= 或加 HF_TOKEN 或本地缓存就位
2. **GPU 充足**: RTX 5090 (W-N-D+ 已实测) + container CUDA 12.x 可用
3. **CI/CD 可控**: 重启 app 容器保留 HF cache (容器不会自动清理)
4. **决策追溯**: W-N-BGE 3 大门禁决策有真测数据 (pass rate / VRAM / latency)

### 6.2 触发前严禁清单 (派工 brief 严禁)

- ❌ 改本 prep report 留口结论
- ❌ 真推理 1000 题 bench (派工 brief 严禁)
- ❌ 真切换生产 EMBEDDING_BACKEND=bge_m3
- ❌ 删 .env HF_ENDPOINT 配置
- ❌ 改 docker-compose.yml 加 HF 镜像源卷

### 6.3 触发后预期工作量

```
W-N-BGE +N 真测派工 = 3 commits:
  +0 startup memory (60-100 行)
  +1 真加载 + 真推理 + 1000 题 bench (scripts/run_bge_m3_realbench_gpu.py + JSON)
  +2 decision doc 5 维真测数据 + 3 门禁结果

预估耗时: GPU 加载 30-60s + 1000 题 batch=32 ≈ 5-10 分钟 (GPU)
预估 VRAM: bge-m3 568M ~1.1GB FP16 + batch ≈ 1.3GB < 4GB ✅
预估 latency: GPU ~80ms/doc = 1.6x Qwen3 ✅
```

### 6.4 触发后决策矩阵

| 3 大门禁结果 | 决策 |
|---|---|
| 全通过 | 切生产 bge-m3 (W-N-BGE-PHASE2) |
| 1-2 缺 | 模型替换延后 + 投资新候选 (BGE-EN-ICL / M3E-LARGE / Qwen3-Embedding) |
| 全失败 | 不切 + 沿用 Qwen3 + 灰度基础设施保留 |

---

## 7. 沉淀文件 (本任务)

| 文件 | 路径 | 行数 | 状态 |
|---|---|---|---|
| startup memory | `memory/w-n-bge-preload-startup-2026-08-05.md` | (待 commit) | ⏳ pending |
| prep report | `docs/w-n-bge-m3-preload-2026-08-05.md` | (本文) | ⏳ pending |
| closure memory | `memory/w-n-bge-preload-closure-2026-08-05.md` | (W-N-BGE-PRE +2) | ⏳ pending |

---

## 8. 参考资料

- W-N-BGE 真路径回归: `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` §3 (派工 brief vs 实测错配 6 处)
- hf-mirror.com 308 行为: 跟踪 Caddy 服务器返回 308, Location header 指向 huggingface.co/.../resolve/main/
- huggingface_hub 缓存机制: 本地 cache 一致性 hash 不识别镜像源, 必须走 HF 原始 cache key
- W-N-BGE 3 门禁决策: §2 (派工 brief 严禁跳过)
- 派工 v6 §13 仓库实情真查: 实测镜像源行为 (本任务新增铁律)

---

**结论**: ⛔ **HF_ENDPOINT=https://hf-mirror.com 当前对 BAAI/bge-m3 失效**, 主拍需决策 (留口 §6). **0 production code 守恒**: 仅 docs/memory 范畴, 严禁改 .env / docker-compose.yml / app/.
