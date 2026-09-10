# VibeVoice 部署与项目变更完整报告

> **日期**: 2026-09-08
> **范围**: microsoft/VibeVoice 开源项目在本机（RTX 5090 32GB）的部署全貌 + microbubble-agent 项目的全部代码/数据/配置变更
> **配套文档**: 评测数据详见 [vibevoice-evaluation-2026-09-07.md](./vibevoice-evaluation-2026-09-07.md)，本报告聚焦部署与变更

---

## 1. 一页总结

| 维度 | 结论 |
|---|---|
| **采用了什么** | VibeVoice-ASR-7B（离线会议转写，生产就绪）+ ASR-Streaming-7B（实时转写，已接线）+ 热词机制（context_info） |
| **排除了什么** | BitNet CPU 版（长音频幻觉）、Realtime TTS（无中文音色，试听判定）、vLLM（暂缓）、LoRA 微调（三轮实验未超基线，关闭） |
| **部署形态** | host 侧 2 个 GPU 服务 + Docker 容器零改动（代码 volume 挂载 + 配置开关） |
| **显存策略** | 会议 worker 按需加载（会毕归零）；Streaming 服务常驻 16GB（flag 门控）；并发冲突自动安全降级 SenseVoice |
| **项目侵入度** | 低：新增 7 个文件 + 4 处小修改，全部 flag 门控，失败自动回退旧链路 |
| **当前生产状态** | ✅ 已生效（app 容器已重启加载）——新会议 ≥180s 自动走 7B 转写 |

---

## 2. 部署架构

```
┌─ Docker 容器（未改镜像，仅重启加载代码）──────────────────────┐
│  app-1 (healthy)                                              │
│   ├─ post_meeting_tasks: 会议≥180s → gpu_asr_client ──────────┼──┐
│   │   失败/短音频 → SenseVoice 逐段链路（原逻辑不变）          │  │
│   └─ voice.py 实时接口: asr_service.transcribe_stream ─────────┼──┤
│       GPU_STREAMING_ASR_ENABLED → gpu_streaming_client ───────┼──┤
│       失败 → SenseVoice（原逻辑不变）                          │  │
└──────────────────────────────────────────────────────────────┘  │
                                   host.docker.internal            │
┌─ Windows host（GPU 侧，无 Docker）────────────────────────────▼──┐
│  :8005 GPU ASR 守护服务 (app/gpu_worker/server.py)               │
│   · 常驻但显存 0；每场会议 spawn meeting_worker 子进程           │
│   · 子进程: 加载 7B(~17GB) → 分块转写 Who/When/What+热词 → 退出  │
│   · 子进程退出 = 显存归零（实测验证，零残留）                    │
│  :8006 Streaming-7B 服务 v2 (streaming_server.py)                │
│   · 服务常驻但模型按需加载：首次请求加载(~20s)                   │
│   · 空闲 600s 自动卸载显存归零；会话中不卸载                      │
│   · POST /transcribe（无状态整段）+ /ws/asr（真流式）            │
│  ⚠ 二者同时满载 >32GB → meeting worker OOM 自动回退 SenseVoice  │
└──────────────────────────────────────────────────────────────────┘
```

**端口/服务清单**

| 端口 | 服务 | 显存 | 生命周期 | 自启动 |
|---|---|---|---|---|
| 8005 | GPU 会议转写守护（spawn 子进程） | 0（任务时 22-29GB） | 常驻进程 | ✅ 启动文件夹 bat |
| 8006 | Streaming-7B 实时服务 v2 | 0（会话期 16GB，空闲 600s 卸载） | 常驻进程 | ✅ 启动文件夹 bat（与 8005 同一 bat） |
| 8002 | Whisper（旧） | — | 已退役 | — |
| 8003 | SenseVoice 容器 | 1GB | 常驻（回退链路） | ✅ docker |

---

## 3. 模型资产（全部本地化，无外网依赖）

| 资产 | 位置 | 大小 | 用途 |
|---|---|---|---|
| VibeVoice-ASR-7B 权重 | `.workbuddy/vibevoice-test/models-vv/`（8 分片） | 17GB | 会议离线转写 |
| ASR-Streaming-7B 权重 | `.workbuddy/vibevoice-test/streaming-model/`（8 分片） | 17GB | 实时转写 |
| Qwen2.5-7B tokenizer | `.workbuddy/vibevoice-test/qwen-tokenizer/` | 11MB | 两者共用的文本分词器 |
| LoRA adapters（存档） | `.workbuddy/vibevoice-test/lora_output{,_v2,_v3}/` | ~450MB | 微调实验存档（未上线） |
| 代码仓库 | `.workbuddy/vibevoice-test/VibeVoice/`（官方，含 6 处兼容补丁） | — | 推理/训练代码 |

环境：`venv-gpu`（Python 3.12 + torch 2.14.0+cu130 + transformers 4.57.6 + peft + librosa + uvicorn/fastapi；huggingface_hub 必须 <1.0）。

---

## 4. microbubble-agent 项目变更清单

### 4.1 新增文件（7 个代码 + 1 脚本 + 1 配置）

| 文件 | 职责 |
|---|---|
| `app/gpu_worker/__init__.py` | 包说明 |
| `app/gpu_worker/meeting_worker.py` | 会议转写子进程（7B 分块推理 + 热词 + 显存归零退出）；`--selftest` |
| `app/gpu_worker/manager.py` | 子进程管理（spawn/超时/退出码/显存回落断言） |
| `app/gpu_worker/server.py` | :8005 守护服务（单并发队列；POST /transcribe raw-PCM → GET /jobs/{id}） |
| `app/gpu_worker/streaming_server.py` | :8006 Streaming-7B 实时服务（POST /transcribe + /ws/asr） |
| `app/gpu_worker/hotwords.txt` | 热词配置（领域术语 + 成员名单，随会议更新） |
| `app/services/gpu_asr_client.py` | 会议转写客户端（健康缓存 + 提交 + 轮询，失败抛异常供回退） |
| `app/services/gpu_streaming_client.py` | 实时转写客户端（/transcribe + healthy） |
| `scripts/start_gpu_asr_daemon.bat` | 守护服务启动脚本（已复制到 `shell:startup`，登录自启） |
| `scripts/prepare_asr_finetune_data.py` | LoRA 数据准备（md 人工稿 × 7B 时间锚 difflib 对位） |
| `scripts/prepare_asr_finetune_data_db.py` | LoRA 数据准备（DB polished ts 直切版，**主力**） |
| `scripts/consistency_filter_v2.py` | 双引擎一致性过滤（v2 数据集生成） |
| `scripts/convert_finetune_to_official.py` | 训练对 → 官方 finetune 格式合并 |
| `scripts/cleanup_voiceprint_embeddings_2026-09-07.py` | 声纹库清洗（已执行，dry-run 默认） |
| `.workbuddy/vibevoice-test/eval_finetune.py` | 微调前后对比评测 |

### 4.2 修改文件（4 个）

| 文件 | 变更 | 效果 |
|---|---|---|
| `app/config.py` | 新增 `GPU_ASR_ENABLED/URL/MIN_SEC(180)/TIMEOUT` + `GPU_STREAMING_ASR_ENABLED/URL` | 全部 flag 门控 |
| `app/services/post_meeting_tasks.py` | 阶段 1 加 GPU 7B 分支（≥180s 且守护健康 → 整场转写；失败回退 SenseVoice）；两处 `identify_speaker` → `identify_speaker_anchored` | 会议转写主力切换 |
| `app/voice/asr.py` | `transcribe_stream` 加 Streaming-7B 分支（flag + 健康检查，失败回退） | 实时链路可切 |
| `app/services/voiceprint_service.py` | ①提取嵌入强制 L2 归一化 ②拒绝全零录入 ③识别过滤 `voice_sample_count=0` ④`MATCH_THRESHOLD 0.7→0.65` | 修复"自信认错人" |

### 4.3 数据变更

| 项 | 内容 |
|---|---|
| 声纹库清洗 | **11 名成员**坏向量置 NULL（4 人同一坏向量 + 7 人未归一化），7 个干净向量保留；**待 11 人重录** |
| 声纹备份 | `backups/voiceprint/members_voice_embedding_backup_2026-09-07.tsv`（18 条全量，可完全恢复） |
| LoRA 数据集 | `data/asr_finetune/`：v1 全量 4133 对/3.35h（db{64..151}+meeting083）、v2 一致性过滤 558 对（v2db*、train_v2） |

### 4.4 基础设施事件（过程中修复）

| 事件 | 处置 | 教训沉淀 |
|---|---|---|
| NVIDIA 驱动 NVML 间歇性失败（当日 3 次，曾自愈） | Windows 侧自愈；Docker 侧需 `wsl --shutdown` + 重启 Docker Desktop | 驱动不稳期网络栈会连带异常 |
| WSL 硬杀 → **PGDATA bind-mount 丢失 12 个空目录**（pg_notify 等） | 按标准目录清单补建 + WAL 回放，**数据零丢失** | postgres 报 "could not open directory" 时的标准修复法 |
| sensevoice 容器 500/无法启动 | 随 GPU 恢复 + Docker 重启后正常（/transcribe 200 实测） | 依赖 GPU 的容器在驱动故障后会硬挂 |

---

## 5. 实测数据摘要（详见评估报告）

| 指标 | 数值 |
|---|---|
| 7B 会议转写（20min 实测） | 131 段全覆盖无幻觉，3 说话人（主讲 88% vs GT 97%），RTF 0.53~0.97，峰值 29.2GB |
| 热词 A/B | 领域关键词召回 **12/16 → 15/16** |
| 分块压测（30min） | 1800s 全覆盖，峰值显存 **22.2GB**（分块省 7GB），60min 可行 |
| Streaming（1h 漂移） | RTF 0.107（首测）/ 2136s 处理 1h，**Speaker 0 全程零漂移** |
| 显存生命周期 | 子进程退出后回落桌面基线（~5GB），**零残留**（对照：in-process 卸载残留 4.3GB） |
| 声纹清洗效果 | 主讲人从"认错人(0.158)"→"正确王天志(0.360, 第二名 0.56)"；未录入者正确返回未知 |
| LoRA 三轮 | v1 15/19、v2 崩溃 0/19、v3 15/19 —— 均未超基线 16/19，**线关闭** |

---

## 6. 运维手册

### 6.1 日常启停

```bash
# 守护服务（登录自启；手动重启）
E:\microbubble-agent\scripts\start_gpu_asr_daemon.bat

# Streaming 服务（按需，常驻 16GB）
cd E:\microbubble-agent
E:\microbubble-agent\.workbuddy\vibevoice-test\venv-gpu\Scripts\python.exe -m app.gpu_worker.streaming_server

# 健康检查（host / 容器内）
curl http://localhost:8005/health
curl http://localhost:8006/healthz
docker exec microbubble-agent-app-1 python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:8005/health', timeout=5).read())"
```

### 6.2 热词更新

编辑 `app/gpu_worker/hotwords.txt`（会议 worker）即可，无需重启（每次任务读取）；Streaming 服务热词在 `/ws/asr` 的 config 消息里传。

### 6.3 故障排查速查

| 症状 | 处置 |
|---|---|
| 会议走了 SenseVoice（想确认是否走了 7B） | 查 `post_meeting_tasks` 阶段记录 `backend` 标签 + `:8005/health` |
| 容器连不上 8005/8006 | Docker Desktop 的 host-gateway 路由故障 → 重启 Docker Desktop |
| GPU OOM | 检查 8006 是否常驻 + ollama keep_alive；会议 worker OOM 自动回退不阻塞 |
| postgres "could not open directory" | bind-mount 空目录丢失（WSL 硬杀后），按标准 PGDATA 清单补建 |
| 训练/推理脚本缺 vibevoice 模块 | `PYTHONPATH` 指向 VibeVoice 仓库；tokenizer 用本地 `qwen-tokenizer`；`HF_ENDPOINT=https://hf-mirror.com` |

### 6.4 回滚方案

- **代码回滚**：`post_meeting_tasks.py` / `asr.py` 的 GPU 分支由 `GPU_ASR_ENABLED` / `GPU_STREAMING_ASR_ENABLED` 开关控制，置 False 即回旧链路（无需改代码）
- **声纹回滚**：TSV 备份可全量恢复 18 条原始向量
- **模型回滚**：删除 8005/8006 进程即回到纯 SenseVoice 时代，零残留

---

## 7. 移交清单

| # | 事项 | 归属 |
|---|---|---|
| 1 | 11 人声纹重录（≥3 次/人 + anchor 确认） | 用户手动 |
| 2 | Streaming 服务如需常开：注册自启并接受 16GB 常驻（或维持按需手动） | 用户决策 |
| 3 | LoRA 若重试：lr 2e-5 / 1 epoch / rank 8 + 一致性过滤数据 ≥3h（当前 v2 仅 0.76h，可对剩余 9 场无本地音频会议补转写） | 可选实验 |
| 4 | meeting-120 完整 3h 分块转写压测（当前只压了 30min） | 可选 |
| 5 | 声纹重录后复测 anchored 识别准确率 | 建议验收 |

---

**报告人**: WorkBuddy Agent
**关联**: [评估报告](./vibevoice-evaluation-2026-09-07.md) | 声纹备份 `backups/voiceprint/` | 全部测试产物 `.workbuddy/vibevoice-test/`
