# Ollama 本地 LLM 部署 + LLM 切换集成指南 (2026-07-24)

> **目的**: 让任何新机器 (Windows / Linux) 5 分钟内一键部署 Ollama 本地 LLM, 并接入 MicroBubble Agent 后端 LLM backend.
> **范围**: Ollama 安装 + 启动 + 模型拉取 + LLMClient backend 切换集成.
> **关联**: W68 第 6 批 #2 LLM 加速方案调研 + W68 第 13 批 B-2 实施 (锚点范式第 162 守恒).

---

## 1. Ollama 简介

**Ollama** 是本地运行大语言模型的轻量级工具, 单二进制 + 一行命令拉模型 + OpenAI 兼容 API 在 `:11434`. 对本项目意义:

- **隐私**: 数据不出本地, 适合课题组敏感研究方向 (微纳米气泡论文/实验数据)
- **离线**: 断网仍可用, 不依赖云端 API key / 速率限制
- **成本**: 一次性 GPU 投入, 后续运行 0 API 调用费
- **协议**: OpenAI 兼容 endpoint (`/v1/chat/completions` / `/v1/models`), 复用本项目 LLMClient `openai_compat` 路径

**Ollama vs vLLM vs llama.cpp**:

| 工具 | 优势 | 劣势 | 本项目适配 |
|---|---|---|---|
| **Ollama** | 一键部署 + 模型库丰富 + OpenAI API | 推理性能略低于 vLLM | **首选** (Blackwell sm_120 兼容) |
| vLLM | 吞吐量最优 | 需 PyTorch 2.7+cu128 支持新 GPU | **不用** (RTX 5090 sm_120 未跟上) |
| llama.cpp | 极致轻量 (CPU) | 速度最慢, 无内置 OpenAI API | 仅作为 CPU fallback |

**重要避坑 (CLAUDE.md 历史教训)**: vLLM 0.8.5 PyTorch **不支持** sm_120 (RTX 5090) → `RuntimeError: CUDA error: no kernel image`. Ollama latest 已内置 CUDA 13 支持 Blackwell, **这是用户决策原话** ("vLLM 不行, Ollama 来").

---

## 2. Windows 部署

### 2.1 下载 + 安装

**官方下载**: <https://ollama.com/download/windows>

**手动安装步骤**:
1. 下载 `OllamaSetup.exe` (约 200 MB)
2. 双击安装, 默认装到 `C:\Users\<user>\AppData\Local\Programs\Ollama\`
3. 安装完成后**自动启动** Ollama 服务 (右下角托盘图标)

**验证安装**:
```powershell
ollama --version
# 期望: ollama version 0.x.x
```

### 2.2 PATH 设置

Ollama 安装后**自动**加入 PATH, 但**若手动安装或 PATH 丢失**:

```powershell
# 临时 (本会话)
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"

# 永久 (用户级)
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:LOCALAPPDATA\Programs\Ollama",
    "User"
)
```

### 2.3 GPU 驱动确认

Ollama 自动检测 NVIDIA GPU. 验证:
```powershell
nvidia-smi
# 期望: 表格显示 GPU 型号 + 驱动版本 + CUDA 版本
```

**最低要求**: NVIDIA 驱动 ≥ 525 (CUDA 12 支持), Blackwell 需 ≥ 580.

---

## 3. Linux 部署

### 3.1 一键安装

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 3.2 验证

```bash
ollama --version
# 期望: ollama version 0.x.x

systemctl status ollama
# 期望: active (running)
```

### 3.3 GPU 驱动 (Linux)

若 `ollama run` 报错 "no GPU detected":
```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 安装 (Ubuntu 24.04)
sudo apt install nvidia-driver-580
sudo reboot
```

---

## 4. 模型拉取

### 4.1 推荐模型 (本项目)

| 模型 | 大小 | 显存需求 | 用途 | 拉取命令 |
|---|---|---|---|---|
| **qwen3:8b** | 4.7 GB | 6 GB | **本项目默认** (35 题 benchmark 验证 11.4% 通过率) | `ollama pull qwen3:8b` |
| qwen3:14b | 9.0 GB | 12 GB | 高精度 (但 qa-bench 实测 4× 慢) | `ollama pull qwen3:14b` |
| qwen3:14b-instruct-q4_K_M | 9.0 GB | 12 GB | 同上 + 工具调用优化 | `ollama pull qwen3:14b-instruct-q4_K_M` |
| llama3.1:8b | 4.9 GB | 6 GB | 英文为主, 备用 | `ollama pull llama3.1:8b` |

### 4.2 拉取命令

```bash
# 单个模型 (10-30 分钟, 取决于网络)
ollama pull qwen3:8b

# 列出已下载
ollama list

# 验证模型可运行
ollama run qwen3:8b "你好, 请用一句话介绍微纳米气泡"
# 期望: 输出中文回复
```

### 4.3 拉取慢的避坑

- **走代理**: `HTTP_PROXY=http://127.0.0.1:7890 ollama pull qwen3:8b` (clash)
- **用国内镜像** (若有): 设置 `OLLAMA_HOST` + 自建 registry
- **离线预下载**: 用 `ollama cp` 或手动 `.ollama/models/` 目录同步

---

## 5. 一键启停脚本

本项目提供 PowerShell 脚本 (Windows 主机), 自动处理 Docker / 镜像 / 端口 / 拉模型 4 件事.

### 5.1 start_ollama.ps1

**位置**: `scripts/start_ollama.ps1`

**用法**:
```powershell
# 默认 (拉 qwen3:8b)
powershell -File scripts/start_ollama.ps1

# 指定模型
powershell -File scripts/start_ollama.ps1 -Model qwen3:14b

# 跳过拉模型 (模型已存在)
powershell -File scripts/start_ollama.ps1 -SkipPull
```

**6 步流程**:
1. 检查 Docker daemon
2. 检查现有 ollama 容器
3. 检查 Ollama 镜像 (缺失则 pull)
4. 启动容器 (GPU + clash 代理 + 端口 11434)
5. 健康检查 (`http://localhost:11434/api/tags`, 60s timeout)
6. 拉取模型 (后台 job, 30min timeout)

**错误处理**:
- `exit 1`: Docker 未运行
- `exit 2`: 镜像拉取失败
- `exit 3`: 容器启动失败
- `exit 4`: 健康检查超时
- `exit 5`: 模型拉取超时/失败
- `exit 99`: 未知异常

### 5.2 stop_ollama.ps1

**位置**: `scripts/stop_ollama.ps1`

**用法**:
```powershell
# 优雅停止 (默认)
powershell -File scripts/stop_ollama.ps1

# 强制清理 (包括 dangling 镜像)
powershell -File scripts/stop_ollama.ps1 -Force
```

**注意**: 数据持久化在 `.ollama/` + `models/` 两个项目目录, **不会被 stop 删除**.

### 5.3 跨平台说明

**当前仅提供 PowerShell (Windows 主机)**. Linux 部署建议用以下 bash 等价脚本 (未来 PR 可加):

```bash
# start_ollama.sh (Linux 简化版, 待 PR)
docker run -d --rm --gpus all --network host --name ollama \
  -v "$PWD/models:/models" \
  -v "$PWD/.ollama:/root/.ollama" \
  ollama/ollama:latest
sleep 5
docker exec ollama ollama pull qwen3:8b
```

---

## 6. W68 第 6 批 #2 LLM 切换集成

### 6.1 原理

Ollama 提供 OpenAI 兼容 API (`/v1/chat/completions`), 本项目 `LLMClient` 已支持 `openai_compat` backend (commit `c8d4df3e2` 实现 + ToolCallConverter 中间层). **Ollama 走的就是这条路径**, 同一代码同时支持云 mimo + 本地 Ollama.

### 6.2 配置 `.env`

```bash
# 后端 LLM 切换
LLM_BACKEND=openai_compat

# Ollama OpenAI 兼容端点
OPENAI_COMPAT_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_COMPAT_MODEL=qwen3:8b
OPENAI_COMPAT_API_KEY=ollama    # Ollama 不需要 key, 任意字符串占位
```

**注意**: `host.docker.internal` 而非 `localhost`, 否则容器内 `localhost` 指向容器自身而非宿主 (CLAUDE.md 历史教训, W66 容器内代理).

### 6.3 重启 + 验证

```bash
# 重启后端
docker compose restart app celery-worker

# 验证 LLM backend 已切到 Ollama
curl -sk -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"用一句话介绍微纳米气泡","stream":false}' | jq

# 期望: 收到中文回复, response 含 `usage.model=qwen3:8b`
```

### 6.4 性能预期 (来自 2026-07-02 benchmark)

| 指标 | mimo-v2.5 云 | qwen3:8b 本地 | 谁胜 |
|---|---|---|---|
| TTFT | ~1.3s | ~200-400ms | 8b |
| tokens/s | 25.84 | ~50-80 (Ollama) | 8b |
| 工具调用准确率 | 0% (修前) → 100% (修后) | ~60-70% | mimo |
| qa-bench 35 题通过率 | 14.3% | 11.4% | mimo |
| 综合分 | 0.876 | 0.835 | mimo (3% 优势) |

**结论**: **生产保持 cloud mimo**, Ollama 作为**离线 / 隐私 / 速率限制 fallback** 而非默认.

### 6.5 何时切 Ollama

- 用户研究敏感数据 (论文 / 实验数据) 不上云
- 云端 rate limit 频繁触发
- 本地 GPU 闲置 + 想省钱
- 演示 + 离线会议

### 6.6 切换命令

```bash
# 临时切 Ollama (本会话)
export LLM_BACKEND=openai_compat
export OPENAI_COMPAT_BASE_URL=http://host.docker.internal:11434/v1
export OPENAI_COMPAT_MODEL=qwen3:8b
docker compose up -d app

# 切回云
export LLM_BACKEND=anthropic
docker compose up -d app
```

---

## 7. 故障排查

### 7.1 容器内 11434 端口不通

**症状**: 容器内 `curl http://localhost:11434/api/tags` 无响应, 但宿主机正常.

**根因**: `--network host` 必须传, 否则容器用 bridge 网络无法访问宿主 localhost.

**修复**: `start_ollama.ps1` 第 4 步已加 `--network host`, 重新启动.

### 7.2 GPU 未识别

**症状**: `ollama run` 报 "no GPU detected, using CPU" (慢 10×).

**诊断**:
```bash
docker exec ollama nvidia-smi
# 若报 "command not found", 镜像缺 nvidia-container-toolkit
```

**修复** (主机侧):
1. 安装 NVIDIA Container Toolkit: <https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html>
2. 重启 Docker: `sudo systemctl restart docker`
3. 重新跑 `start_ollama.ps1`

### 7.3 模型拉取超时

**症状**: `ollama pull qwen3:8b` 卡 10+ 分钟, 进度不动.

**修复**:
1. 检查代理: `curl -x http://127.0.0.1:7890 https://ollama.com` 应返回 200
2. 容器内用宿主机代理: `start_ollama.ps1` 已加 `HTTP_PROXY=http://127.0.0.1:7890` + `NO_PROXY=host.docker.internal`
3. 手动重试: `docker exec ollama ollama pull qwen3:8b`

### 7.4 VRAM 不足

**症状**: `ollama run` 报 "model requires more VRAM" 或 OOM.

**修复**:
1. 选更小模型: `qwen3:8b` (4.7 GB) 优于 `qwen3:14b` (9 GB)
2. 释放显存: `nvidia-smi` 看占用, kill 其他 GPU 进程
3. CPU fallback (慢 10×): 设置 `OLLAMA_NUM_GPU=0`

### 7.5 LLMClient 切换不生效

**症状**: 改 `.env` 后 `LLM_BACKEND=openai_compat` 仍走 anthropic.

**诊断**:
```bash
docker exec microbubble-agent-app-1 python -c "
from app.config import settings
print('LLM_BACKEND:', settings.LLM_BACKEND)
print('OPENAI_COMPAT_BASE_URL:', settings.OPENAI_COMPAT_BASE_URL)
"
```

**修复**:
1. 确认 `.env` 在项目根, **不是** `app/.env`
2. 重启: `docker compose up -d app` (不是 `restart`, 后者可能保留环境变量)
3. 检查 `docker-compose.yml` 是否 `env_file: .env`

---

## 8. 关联文档

- `scripts/start_ollama.ps1` — 一键启动
- `scripts/stop_ollama.ps1` — 一键停止
- `docs/llm-benchmark-2026-07-02.md` — 35 题 benchmark 报告
- `app/core/llm.py` — LLMClient backend dispatch (lines 152-180)
- `app/core/tool_call_converter.py` — Anthropic ↔ OpenAI 协议转换
- `app/config.py` — `LLM_BACKEND` / `OPENAI_COMPAT_*` settings
- `memory/w68-route-13-b2-ollama-playwright-2026-07-24.md` — W68 第 13 批 B-2 沉淀

---

## 9. 铁律 (本指南沉淀)

1. **Ollama 优先于 vLLM** — Blackwell sm_120 兼容性决定 (CLAUDE.md 历史教训, 2026-07-01).
2. **容器内访问宿主必须 `host.docker.internal`** — `localhost` 指向容器自身 (CLAUDE.md 历史教训).
3. **OpenAI 兼容 endpoint 复用同一代码路径** — mimo 云 + Ollama 本地共用 `openai_compat` 分支, 不引入新客户端.
4. **一键启停脚本必须 timeout + 退出码明确** — 5 类错误码 + 1 未知错误 (脚本第 1 节"错误处理").
5. **生产保持 cloud mimo, Ollama 作为 fallback** — benchmark 显示 mimo 综合分高 3% (2026-07-02 实测).

---

**沉淀**: 锚点范式第 162 守恒 (W68 第 13 批 B-2, 2026-07-24)