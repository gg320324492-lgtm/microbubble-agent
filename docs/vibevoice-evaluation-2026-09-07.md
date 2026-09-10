# VibeVoice 实测评估与"按需占显存"最佳方案

> **日期**: 2026-09-07（v2，含 GPU 恢复后全场实测）
> **测试环境**: RTX 5090 32GB / AMD Ryzen 9 9950X3D / Windows 11 / torch 2.14.0+cu130 / transformers 4.57.6
> **测试音频**: `data/asr_eval/normalized/meeting-083.webm`（20min16s 真实组会，人工校对 GT `meeting83_final.md`：王天志 97% / 杨慈 3 段插话）
> **声纹库**: 生产 DB 真实成员向量（清洗后 7 个干净向量，含 6 个 anchor）

---

## TL;DR

| 结论 | 内容 |
|---|---|
| **VibeVoice-ASR-7B 全场实测通过** | 20min 会议单次转写 **131 段全覆盖无幻觉**，自动分出 3 个说话人（主讲 117 段/88% vs GT 97% 结构吻合），热词 A/B **关键词召回 12/16 → 15/16**，RTF 0.53~0.97 |
| **显存生命周期实测成立** | 会议处理期峰值 22.7~29.2GB（吃满可用显存），worker 进程退出后显存**完全回落到桌面基线**，零残留 |
| **说话人识别的真正拦路虎是声纹库数据** | 清洗 11 个坏向量后，同一会议主讲人从"自信认错人(0.158→韩重阳)"变为**正确匹配王天志(0.360)且余量明显**；未录入声纹的说话人正确返回未知 |
| **BitNet CPU 版不适合会议** | 60s 起领域术语崩坏、300s 整段幻觉、无 Speaker 标签；仅适合 ≤60s 短语音兜底 |
| **最佳方案** | 会议生命周期 = 显存生命周期（子进程 worker 载 7B → 转写+声纹映射 → 进程退出）；60min+ 会议需分块或 vLLM |

---

## 0. 过程中的生产环境抢救（附带成果）

测试开始时发现本机 NVIDIA 驱动异常（NVML 失败 / Docker "no adapters"），sensevoice 容器 500。执行恢复过程中处理了三个问题：

1. **驱动恢复**：Windows 侧 nvidia-smi 自行恢复（616.64 / CUDA 13.4），但 Docker 的 WSL GPU 透传仍是旧状态 → `wsl --shutdown` + 重启 Docker Desktop 修复；
2. **PostgreSQL 数据卷故障**：硬杀 WSL 导致 bind mount 上 **12 个空目录丢失**（pg_notify、pg_logical/snapshots、pg_tblspc 等运行时瞬态目录）。症状：db 容器崩溃循环 `could not open directory "pg_notify"`。修复：WAL 自动回放 + 手工补建 12 个空目录，**数据零丢失**（members=32 等全量校验通过）；
3. **sensevoice 服务恢复**：重启后在 CUDA 上正常加载，`POST /transcribe` 实测 **200 OK**（转写正确）。

> 经验沉淀：Windows bind-mount 的 PGDATA 在 WSL 硬杀后，空目录会静默丢失；postgres 报 "could not open directory" 时按标准 PGDATA 目录清单补建即可。

## 1. 测试背景

上一轮分析确认 VibeVoice 家族与本项目"会议纪要 + 说话人识别"场景高度相关。本轮在真实组会音频上完成三轮测试并落地最佳方案。

## 2. 第一轮：VibeVoice-ASR-BitNet（CPU，1.58GB）— 排除

构建（Windows/MinGW）踩坑记录：架构检测失败需 `-DCMAKE_SYSTEM_PROCESSOR=x86_64`；SIMD 宏需全局 `-mavx2 -mfma -mssse3`；segfault 需 `-Wl,--stack,33554432`。

实测（meeting-083）：

| 切片 | RTF@16T | 结果 |
|---|---|---|
| 30s | 0.65~0.81 | ✅ 基本正确 |
| 60s | 0.53 | ⚠️ "UV臭氧纳米气泡"→"邮被加加too young, not too poor"、"养殖尾水"→"杨志辉" |
| 300s | — | ❌ 整段幻觉（输出无关"教育"主题长文） |

关键事实：BitNet 实为 Qwen2.5-1.5B 量化版；**无 Speaker 标签输出**；无热词；官方基准 AISHELL4 中文会议 WER 27.45 也劣于 SenseVoice 22.52。**结论：仅作边缘兜底，不进会议链路。**

## 3. 第二轮：VibeVoice-ASR-7B（GPU 全场实测）— 通过 ✅

### 3.1 实测数据（meeting-083 真实组会）

| 指标 | 30s 冒烟 | 5min A/B | **20min 全场** |
|---|---|---|---|
| RTF | 0.77 | **0.53** | 0.97（1178s 推理 20min 音频） |
| 覆盖 | 30s 全 | 300s 全 | **1216s 全，无幻觉** |
| 段落数 | 3 | 29 | **131** |
| 说话人数 | 1 | 1 | **3**（Spk0 117 段/1072s，Spk1 6 段，Spk2 8 段） |
| 峰值显存 | 22.7GB | 27.1GB | **29.2GB**（贴近 32GB 上限） |
| 模型加载 | 9.7s | 9.7s | 10.0s |

转写质量抽样（全场，无需后处理即可读）：

> [27.8-38.2] 所以呢，我想，就是，这个，呃，**让同贺先做**，你呢，也要持续的在看这个，明白吧？因为你的方向基本上是定了。
> [53.4-63.8] 嗯，但是呢，这个机理这一块，**让同贺先干**，干呢，是有2个好处……
> [38.9-52.9] 就是，还是这个UV加，因为这个，这个**UV加加臭氧纳米气泡**……这个可能大概率是用在**养殖尾水**的处理上。

与人工校对 GT 对齐度：GT 的"让同学先做"（同贺=同学同音）、"基底/机理"、"臭氧纳米气泡"、"养殖尾水"、"ESG"、"国家奖"、"方老师"等领域内容几乎全部命中。CER 精确值受人工校对稿删口癖影响不可直接比（对齐伪影），采用关键词召回衡量。

### 3.2 热词 A/B（5min，context_info 机制）

| 关键词 | 无热词 | 有热词 |
|---|---|---|
| 臭氧 | ❌("除氧") | ✅ |
| 基底 | ❌("机理") | ✅ |
| 同贺(人名) | ❌("同赫") | ✅ |
| 纳米气泡/养殖尾水/ESG/方老师/实验系统/小组/国家奖/大项目/停滞/白费/超越/同济 | ✅ | ✅ |
| 花工 | ❌ | ❌ |
| **召回** | **12/16** | **15/16** |

### 3.3 工程参数与坑

- 部署：transformers 4.57.6 + torch cu130 + VibeVoice 官方仓库（`VibeVoiceASRForConditionalGeneration`，bf16 + sdpa），**无需 flash-attn**；huggingface_hub 必须 <1.0；tokenizer 用本地 Qwen2.5-7B 目录。
- **坑 1**：processor 对 numpy 输入不做重采样（target 24kHz），16kHz 音频必须先 `resample_poly` 到 24kHz，否则时长被压缩 2/3（30s 被当 20s）。
- **坑 2**：`max_new_tokens` 必须按时长估算（≈dur×18+384）。官方 demo 默认 512 只适合短音频；设 32K 会导致贪心解码跑满（30s 音频生成了 18 分钟）。
- **坑 3**：模型可能把 JSON 输出两遍，解析时时间轴回卷即截断。
- 长音频显存：20min 峰值 29.2GB 已贴 32GB 上限，**60min 会议建议按 15~20min 分块**（块间携带说话人上下文）或上 vLLM。

### 3.4 显存生命周期实测 ✅

推理期间 GPU 占用 22.7 → 27.1 → 29.2GB（90%+ 利用率）；进程退出后 `nvidia-smi` 回落到 **5.1GB 桌面基线，零残留**（对照：in-process 卸载 Whisper 残留 4.3GB，见项目基准报告）。"会议时占满显存、会后释放"由子进程退出保证。

### 3.5 分块压测（meeting-120_30min，900s 能量谷值分块）✅

| 指标 | 结果 |
|---|---|
| 覆盖 | **1800s 全覆盖无幻觉**（last end = 1800.0），207 段 |
| RTF | 0.77（1387s 推理 30min 音频） |
| **峰值显存** | **22.2GB**（分块方案 vs 单次 20min 的 29.2GB，**-7GB**，60min 会议可行性实证） |
| 分块 | 3 块，能量谷值切点在 ±30s 搜索窗内自动选静音处 |
| 边界质量 | 切点附近语义连贯（"50克臭氧发生器"等），个别短句被切（对话密集区无长静音，可接受） |
| 说话人标签 | 跨块碎片化（c0/c1/c2 共 13 个标签，主讲人 c0s0 566s / c1s0 681s 占比稳定）——**设计预期**，由应用侧声纹聚类统一映射真名 |

### 3.6 ASR-Streaming-7B 首测（实时通话候选）✅

官方流式 demo（transformers 直推，无需 vLLM）跑 slice30.wav：

- **11 个增量块实时输出**（[1/11]→[11/11]，边转边出），Speaker 标签保留
- **RTF 0.107**（30s 音频仅 3.21s 生成，比离线快 7 倍）
- 质量与离线同级（"UVA 家格外的"≈"UV加紫外"）
- 结论：**达到接入实时通话链路的判定标准**（增量首包远小于 2s）；下一步与 silero-VAD/声纹流水线做兼容联测

## 4. 第三轮：声纹说话人识别（清洗前后对照）

### 4.1 清洗前的问题（实测）

- 聚类本身正确：301 段 → 2 簇，与 GT 参会人结构吻合；
- 但名字映射**自信认错**：主讲人（GT=王天志）匹配到韩重阳 dist=0.158，本人 anchor 反而 0.359。

### 4.2 根因与清洗执行

生产库 vector_norm 普查发现三类污染：4 人同一坏向量（norm 全等 13.2603）、7 人未归一化（norm 488~859，含普查新发现的余歆睿 546）、仅 6 个 anchor norm=1.0。已执行（用户确认）：

- `scripts/cleanup_voiceprint_embeddings_2026-09-07.py --execute`：**UPDATE 11 名成员**（置 NULL + 采样数清零），7 个干净向量保留，备份在 `backups/voiceprint/members_voice_embedding_backup_2026-09-07.tsv`；
- `voiceprint_service.py` 加固：嵌入提取出口强制 L2 归一化、拒绝录入全零向量、识别查询过滤 `voice_sample_count=0` 残留。

### 4.3 清洗后：7B 说话人标签 × 声纹映射（全场 131 段）

| 7B 说话人 | 段数/时长 | 映射结果 | 依据 |
|---|---|---|---|
| Speaker 0（主讲） | 113 段嵌入 | **王天志** (dist=0.360) ✅ | 第二名杜同贺 0.56，余量明显 |
| Speaker 2（插话） | 7 段 | 贾琦 0.676（弱匹配，接近阈值） | GT 认为是杨慈——其声纹已被清洗待重录 |
| Speaker 1（插话） | 1 段有效嵌入 | **None（正确拒识）** | 杨慈未重录，不乱猜符合"禁止误认"规则 |

**结论**：数据清洗后，"自信认错人"现象消除；主讲人正确识别；未录入者正确返回未知（符合项目"声纹无法确认时使用发言人A/B"的硬规则）。**说话人准确率的瓶颈在声纹库治理，不在模型**。建议：重录 11 人声纹（每人 ≥3 次采样 + anchor 确认），并把弱匹配阈值收紧到 ~0.65。

## 5. 最佳方案：会议生命周期 = 显存生命周期

```
┌─ 平时（无会议）────── 显存 ≈ 0（仅桌面基线）─────────┐
│  聊天短语音 ASR → SenseVoice(CPU/GPU 1GB) 或 BitNet 兜底 │
└────────────────────────────────────────────────────┘
        │ 会议开始 / 录音上传
        ▼
┌─ 会议处理期 ────────── 峰值 22~29GB ─────────────────┐
│  gpu_worker（独立子进程，app/gpu_worker/）             │
│   1. 载入 VibeVoice-ASR-7B (~17GB, 加载仅 10s)        │
│      → 单次转写 Who/When/What + context_info 热词      │
│   2. ERes2Net 声纹：逐段嵌入 → 簇质心 → anchor 匹配    │
│      → Speaker N → 真名（清洗后的 anchor 库）          │
│   3. >20min 音频按 15min 分块（防 32GB OOM）           │
│  完成 → 进程退出 → 显存归零（已实测验证）              │
└────────────────────────────────────────────────────┘
```

已交付的代码（本轮实现并验证）：

- `app/gpu_worker/meeting_worker.py` — **v2 已校准**：与实测脚本完全一致的推理路径（bf16+sdpa / 24kHz 重采样 / max_new_tokens 估算 / 去重解析）+ **能量谷值分块**（>chunk_sec 自动切，块边界±30s 找 1s 能量最低点）；selftest 通过；
- `app/gpu_worker/server.py` — **host 守护服务**（stdlib HTTP :8005，单并发队列）：POST /transcribe(raw PCM) → 202 job_id → GET /jobs/{id} 轮询；子进程逐会议拉起，**服务本身常驻但显存为零**；
- `app/gpu_worker/hotwords.txt` — 热词配置（领域术语+成员名单，按会议更新）；
- `app/services/gpu_asr_client.py` — 容器侧异步客户端（健康探测 60s 缓存 + 提交 + 轮询），失败一律抛 GPUASRError 供回退；
- `app/config.py` — `GPU_ASR_ENABLED/URL/MIN_SEC(180s)/TIMEOUT`；
- `app/services/post_meeting_tasks.py` — **阶段 1 已接入**：音频 ≥180s 且守护服务健康 → 整场 PCM 交 7B 转写（自带 Who/When/What）；失败自动回退 SenseVoice 逐段链路；阶段记录带 backend 标签；
- `app/services/voiceprint_service.py` — `MATCH_THRESHOLD 0.7→0.65`（实测 0.676 擦线误配）；
- `post_meeting_tasks.py` 两处识别调用切换 `identify_speaker_anchored`（只与已确认 anchor 比较）；
- `scripts/prepare_asr_finetune_data.py` — **LoRA 微调数据准备**：人工校对稿 × 7B 时间锚 difflib 字符级对位 → 官方 finetuning-asr 数据格式（{n}.wav+{n}.json）；meeting-083 试跑导出 10 对/148s（跑完全部有校对稿的会议即可攒够训练集）。

端到端验证记录：
- worker/manager selftest ✅（分块点 [0, 270.5, 541, 811.5, 1000] 符合预期）
- 守护服务健康：host `localhost:8005` ✅ + 容器内 `host.docker.internal:8005` ✅
- **5min 会议 HTTP 全链路** ✅：提交 9.6MB PCM → 25 段结构化结果，RTF 0.519，热词生效（"臭氧"命中），进程退出后显存回落 5012MB 基线
- **anchored 识别容器内验证** ✅：meeting-083 三个时间点（60/200/700s）全部正确识别王天志（conf 0.53~0.62 < 0.65 阈值）
- 30min 分块压测（meeting-120_30min，900s 分块）：进行中/结果见 §3.5

### 显存预算（实测值）

| 状态 | 显存 |
|---|---|
| 平时 | 桌面基线 ~5.1GB（无任何模型驻留） |
| 30s~5min 会议 | 22.7~27.1GB |
| 20min 会议 | 29.2GB（vram_loaded 21.9 + KV/激活增长） |
| 60min 会议 | 需分块或 vLLM（单次会 OOM） |

## 6. 可选增强与所需测试

| 增强 | 状态 | 需要的测试 | 判定标准 |
|---|---|---|---|
| **LoRA 领域微调** | ❌ 两轮实验均未通过，**LoRA 线关闭**：v1（3.35h 弱监督全量，2 epochs）15/19 vs 基线 16/19 轻微回退；v2（双引擎一致性过滤 558 对/0.76h，3 epochs）**崩溃性失败 0/19**（灾难性遗忘，lr 1e-4 过猛）→ 不上线，基线服役；adapter 存档 `lora_output/`、`lora_output_v2/` | 若未来重试：lr 2e-5、1 epoch、rank 8、数据 ≥3h 经 `consistency_filter_v2.py` 去噪（已就绪） | 重训后召回 >16/19 且 RTF 不劣化才重新评估 |
| **vLLM 加速** | 未采用（transformers 版 RTF 0.53~0.97 已够用；vLLM 不支持 Windows 原生，需改 Linux GPU 容器部署） | 60min 会议单次 vs 分块的吞吐/显存对比；多会议并发压测 | 单次 RTF <0.5 且显存 <30GB 才值得改部署形态 |
| **ASR-Streaming-7B** | ✅ **已上线（flag 门控）**：1h 漂移测试通过（Speaker 0 全程无漂移）；`app/gpu_worker/streaming_server.py`（:8006，常驻 ~16GB，2.9s 增量块）+ `POST /transcribe` 无状态端点；`asr.py transcribe_stream` 已接后端开关（`GPU_STREAMING_ASR_ENABLED`），失败回退 SenseVoice；容器端到端实测通过 | 已知取舍：常驻显存与 meeting_worker 并发会 OOM→自动回退；生产启用需 `docker restart microbubble-agent-app-1` | 达标 |
| **Realtime-0.5B TTS** | ❌ 试听判定（2026-09-07 用户实测）：中文样本**有声但不通顺、不像地道中国话**，英文样本流利——与官方"English only"声明一致；数据支持：25 音色无中文，中文段 RTF 0.42（样本见桌面/附件） | 维持 Edge-TTS；触发重开条件：官方发布中文 voice，或评估 CosyVoice 等中文开源 TTS 做本地化替代 | 出现地道中文 voice 且听感接近 Edge-TTS 才替换（RAG 语音问答集成点已确认可行，随时可接） |

## 7. 风险与待办

- [x] ~~GPU 驱动修复 + WSL 重置~~（已完成，sensevoice 已恢复 200）
- [x] ~~声纹库清洗~~（已执行，11 人待重录）
- [x] ~~VibeVoice-ASR-7B 全场实测~~（本报告 §3）
- [x] ~~worker 校准 + 守护服务 + 会议流接入 + anchored/阈值 0.65~~（§5，端到端验证通过）
- [ ] **重录 11 人声纹**（≥3 次采样/人 + anchor 确认；杨慈重录后 Speaker 1/2 即可定名）
- [ ] **重启 app 容器使新代码生效**（post_meeting_tasks/voiceprint_service 已改，volume 挂载，`docker restart microbubble-agent-app-1` 即加载）
- [ ] 补齐 LoRA 训练数据（其余有校对稿会议跑 `prepare_asr_finetune_data.py`，目标 ≥2h 音频）
- [ ] ASR-Streaming-7B 兼容联测（首测达标，见 §3.6；权重在 `.workbuddy/vibevoice-test/streaming-model`）
- [ ] gpu_worker 守护服务注册为 Windows 自启动服务（当前手动 `python -m app.gpu_worker.server`）
- [ ] 能量 VAD → silero-VAD（models/torch_hub 已有，仅测试脚本内）

## 8. 测试产物

| 文件 | 说明 |
|---|---|
| `docs/vibevoice-evaluation-2026-09-07.md` | 本报告 |
| `app/gpu_worker/{meeting_worker,manager}.py` | worker 子进程 + 管理器（selftest 通过） |
| `scripts/cleanup_voiceprint_embeddings_2026-09-07.py` | 声纹清洗脚本（已执行） |
| `app/services/voiceprint_service.py` | 归一化/防零向量/采样数过滤加固 |
| `backups/voiceprint/members_voice_embedding_backup_2026-09-07.tsv` | 清洗前全量备份 |
| `.workbuddy/vibevoice-test/test_vibevoice_7b.py` | 7B 实测脚本（含 24kHz 重采样与 max_new_tokens 修复） |
| `.workbuddy/vibevoice-test/r_7b_{30s,300s,300s_hw,full}.json` | 各轮转写原始结果 |
| `.workbuddy/vibevoice-test/result_speakermap.json` | 全场声纹映射结果 |
| `.workbuddy/vibevoice-test/{test_voiceprint_container,test_speakermap_7b}.py` | 声纹测试脚本（容器版） |
| `.workbuddy/vibevoice-test/VibeASR.cpp/`, `VibeVoice/` | 两个引擎源码与构建产物 |

**测试人**: WorkBuddy Agent | 2026-09-07
