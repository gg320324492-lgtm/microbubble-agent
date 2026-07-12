# GPU 功能 02: 本地大模型部署 — 详细实施计划

> 预计周期: **2-3 周** | 优先级: 🔴 高 | GPU 需求: ~14-28GB

## 功能概述

在 5090 32GB 上部署本地大语言模型（Qwen-14B），实现隐私保护、低延迟、离线可用的 AI 对话能力。

---

## 2.1 模型选型与评估

### 2.1.1 候选模型评估
| 模型 | 参数量 | 显存需求 | 中文能力 | 推理速度 | 推荐度 |
|------|--------|----------|----------|----------|--------|
| Qwen-7B-Chat | 7B | ~14GB | ⭐⭐⭐⭐⭐ | 快 | ⭐⭐⭐⭐ |
| Qwen-14B-Chat | 14B | ~28GB | ⭐⭐⭐⭐⭐ | 中 | ⭐⭐⭐⭐⭐ |
| ChatGLM3-6B | 6B | ~12GB | ⭐⭐⭐⭐ | 快 | ⭐⭐⭐ |
| Yi-34B-Chat | 34B | ~68GB | ⭐⭐⭐⭐⭐ | 慢 | ❌ 超出显存 |
| Llama-3-8B | 8B | ~16GB | ⭐⭐⭐ | 快 | ⭐⭐⭐ |

**推荐**: Qwen-14B-Chat（中文能力强，32GB 显存刚好够用）

### 2.1.2 量化方案
| 量化方式 | 显存占用 | 精度损失 | 推荐度 |
|----------|----------|----------|--------|
| FP16 | ~28GB | 无 | ⭐⭐⭐⭐⭐ |
| INT8 | ~14GB | 极小 | ⭐⭐⭐⭐ |
| INT4 | ~7GB | 小 | ⭐⭐⭐ |
| GPTQ-4bit | ~8GB | 小 | ⭐⭐⭐⭐ |
| AWQ-4bit | ~8GB | 小 | ⭐⭐⭐⭐ |

**推荐**: FP16（32GB 显存足够）或 INT8（留显存给其他模型）

---

## 2.2 推理框架部署

### 2.2.1 vLLM 部署（推荐）
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| vLLM 安装 | pip install vllm | 0.5d |
| 模型下载 | 从 ModelScope/HuggingFace 下载 | 1d |
| 服务启动 | vLLM OpenAI 兼容 API | 1d |
| 性能调优 | 调整 batch_size/gpu_memory_utilization | 1d |
| 健康检查 | 添加健康检查端点 | 0.5d |

```bash
# 启动 vLLM 服务
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen-14B-Chat \
  --gpu-memory-utilization 0.85 \
  --max-model-len 8192 \
  --port 8003 \
  --trust-remote-code
```

**验收标准**: 本地模型 API 可正常调用，响应延迟 < 1s

### 2.2.2 Ollama 部署（备选）
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| Ollama 安装 | curl 安装脚本 | 0.5d |
| 模型拉取 | ollama pull qwen:14b | 1d |
| 服务启动 | ollama serve | 0.5d |
| API 测试 | 测试 OpenAI 兼容 API | 0.5d |

```bash
# 安装 Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 拉取模型
ollama pull qwen:14b

# 启动服务
ollama serve
```

**验收标准**: Ollama 服务正常运行，API 可调用

### 2.2.3 Docker 容器化
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| Dockerfile | 编写 LLM 服务 Dockerfile | 1d |
| GPU 支持 | 配置 NVIDIA Container Toolkit | 0.5d |
| docker-compose | 添加 llm 服务到 compose | 0.5d |
| 卷挂载 | 模型文件持久化 | 0.5d |

```yaml
# docker-compose.yml
services:
  llm:
    build:
      context: .
      dockerfile: Dockerfile.llm
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "8003:8003"
    volumes:
      - llm_models:/root/.cache
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - MODEL_NAME=Qwen/Qwen-14B-Chat
      - GPU_MEMORY_UTILIZATION=0.85
      - MAX_MODEL_LEN=8192
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  llm_models:
```

**验收标准**: LLM 服务通过 Docker 正常运行

---

## 2.3 模型路由与切换

### 2.3.1 智能路由
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 路由策略 | 根据任务类型选择模型 | 2d |
| 本地优先 | 优先使用本地模型 | 1d |
| 降级策略 | 本地不可用时降级到 API | 1d |
| 负载均衡 | 多模型负载均衡 | 2d |

```python
# 路由策略
ROUTING_STRATEGY = {
    "简单问答": "local",           # 本地 7B
    "复杂推理": "local_14b",       # 本地 14B
    "代码生成": "local_14b",       # 本地 14B
    "学术写作": "claude",          # Claude API
    "多模态": "claude",            # Claude API
    "实时对话": "local",           # 本地（低延迟）
    "批量处理": "local_14b",       # 本地（成本低）
}
```

**验收标准**: 根据任务类型自动选择最优模型

### 2.3.2 模型切换 UI
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 模型选择器 | 前端模型切换组件 | 2d |
| 状态显示 | 显示当前使用的模型 | 1d |
| 性能监控 | 显示推理延迟和吞吐量 | 2d |
| 手动切换 | 支持手动切换模型 | 1d |

**验收标准**: 用户可手动切换模型并查看状态

---

## 2.4 性能优化

### 2.4.1 推理优化
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| KV Cache | 优化 KV Cache 管理 | 1d |
| Continuous Batching | 连续批处理 | 1d |
| Speculative Decoding | 投机解码 | 2d |
| Flash Attention | Flash Attention 2 | 1d |

**验收标准**: 推理速度提升 30%+

### 2.4.2 缓存优化
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| Prompt Cache | 相同 prompt 缓存 | 1d |
| 响应缓存 | 相同问题缓存响应 | 1d |
| Redis 集成 | Redis 存储缓存 | 1d |
| 缓存失效 | 缓存过期和失效策略 | 1d |

**验收标准**: 重复问题响应时间 < 100ms

### 2.4.3 并发优化
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 异步推理 | 异步推理请求 | 1d |
| 请求队列 | 请求排队和优先级 | 2d |
| 并发控制 | 控制并发数量 | 1d |
| 超时处理 | 请求超时和重试 | 1d |

**验收标准**: 支持 10+ 并发请求

---

## 2.5 与现有系统集成

### 2.5.1 Agent 工具集成
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| LLM 客户端 | 统一 LLM 调用接口 | 2d |
| 工具调用 | 本地模型支持工具调用 | 3d |
| 上下文管理 | 管理对话上下文 | 2d |
| 流式输出 | 支持流式输出 | 1d |

```python
# 统一 LLM 接口
class LLMClient:
    def __init__(self):
        self.local_client = OpenAI(base_url="http://llm:8003/v1")
        self.claude_client = Anthropic()
    
    async def chat(self, messages, model="auto", **kwargs):
        if model == "auto":
            model = self._select_model(messages)
        
        if model.startswith("local"):
            return await self._call_local(messages, **kwargs)
        else:
            return await self._call_claude(messages, **kwargs)
    
    def _select_model(self, messages):
        # 智能选择模型
        ...
```

**验收标准**: 本地模型可作为 Agent 的 LLM 后端

### 2.5.2 知识库集成
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| RAG 增强 | 本地模型 + 知识库检索 | 2d |
| 摘要生成 | 本地模型生成知识摘要 | 1d |
| 分类标签 | 本地模型自动分类 | 1d |
| QA 问答 | 本地模型回答知识库问题 | 2d |

**验收标准**: 本地模型可基于知识库回答问题

### 2.5.3 会议系统集成
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 实时转录 | 本地模型润色转录文本 | 2d |
| 会议摘要 | 本地模型生成会议摘要 | 1d |
| 要点提取 | 本地模型提取讨论要点 | 1d |
| 任务生成 | 本地模型生成待办任务 | 1d |

**验收标准**: 本地模型可处理会议相关任务

---

## 2.6 监控与运维

### 2.6.1 性能监控
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| GPU 监控 | 监控 GPU 使用率/显存/温度 | 1d |
| 推理监控 | 监控推理延迟/吞吐量 | 1d |
| 请求监控 | 监控请求成功率/错误率 | 1d |
| 告警机制 | 异常时发送告警 | 1d |

**验收标准**: 实时监控模型服务状态

### 2.6.2 日志与审计
| 任务 | 技术方案 | 工时 |
|------|----------|------|
| 请求日志 | 记录所有请求和响应 | 1d |
| 错误日志 | 记录错误和异常 | 0.5d |
| 性能日志 | 记录性能指标 | 0.5d |
| 审计日志 | 记录敏感操作 | 1d |

**验收标准**: 完整的日志记录和审计能力

---

## API 设计

```python
# 模型状态
GET /api/v1/llm/status
# 响应: {models: [{name, status, gpu_usage, latency}], current_model}

# 模型切换
POST /api/v1/llm/switch
# 请求: {model: "local|local_14b|claude"}
# 响应: {success, model}

# 聊天补全（OpenAI 兼容）
POST /v1/chat/completions
# 请求: {model, messages, stream, ...}
# 响应: OpenAI 格式响应

# 性能指标
GET /api/v1/llm/metrics
# 响应: {requests_per_second, avg_latency, gpu_utilization, ...}
```

---

## 实施步骤

### Week 1: 模型部署
- 模型下载和验证
- vLLM/Ollama 部署
- Docker 容器化
- 基础 API 测试

### Week 2: 系统集成
- 智能路由实现
- Agent 工具集成
- 知识库集成
- 会议系统集成

### Week 3: 优化与监控
- 推理性能优化
- 缓存优化
- 监控告警
- 压力测试
