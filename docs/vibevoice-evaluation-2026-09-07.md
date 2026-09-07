# VibeVoice 实测评估与"按需占显存"最佳方案

> **日期**: 2026-09-07
> **测试环境**: RTX 5090 32GB (当前 GPU 驱动异常，见 §2) / AMD Ryzen 9 9950X3D 16 核 / Windows 11
> **测试音频**: `data/asr_eval/normalized/meeting-083.webm` (20min 真实组会，有人工校对 GT `meeting83_final.md`：王天志 97% / 杨慈 3 段)
> **声纹库**: 生产 DB 17 名成员真实录入的 192 维 ERes2Net embedding

---

## TL;DR

| 结论 | 内容 |
|---|---|
| **BitNet CPU 版** | ❌ 不适合会议场景。30s 短音频可用（RTF 0.53@16T），60s 起领域术语大面积崩坏（"UV臭氧纳米气泡"→"邮被加加too young"），300s 直接整段幻觉跑题，且**无 Speaker 说话人标签输出** |
| **VibeVoice-ASR-7B** | ⏳ 官方中文会议数据好（AISHELL4 cpWER 24.99 / AliMeeting DER 10.92），但本机 GPU 驱动当前故障无法实测；按 16GB 显存 + 会议期按需加载设计 |
| **说话人识别真正的拦路虎** | ❗ **不是模型，是声纹库数据质量**：17 份 embedding 里 4 份是同一坏向量、6 份未归一化（norm 488~859）、只有 6 个 anchor 可信；实测王天志本人的会议音频匹配到韩重阳（dist 0.158）而非自己（0.359） |
| **最佳方案** | **会议生命周期 = 显存生命周期**：会议开始 → 子进程 worker 载入 VibeVoice-ASR-7B + 声纹 → 会后进程退出显存归零；配合声纹库数据清洗 3 步 |

---

## 1. 测试背景

上一轮分析确认 VibeVoice 家族（ASR-7B / ASR-Streaming-7B / BitNet / Realtime-0.5B）与本项目"会议纪要 + 说话人识别"场景高度相关。本轮在真实组会音频上做了三轮测试。

## 2. 环境事实（重要，两个生产隐患）

1. **本机 GPU 驱动当前异常**：`nvidia-smi` 报 `Failed to initialize NVML`，Docker 报 `WSL environment detected but no adapters were found`。2 天前 sensevoice 容器还能正常加载 CUDA，现在无法新建任何 GPU 负载。**需要重启 NVIDIA 驱动/主机后重测 7B 模型**。
2. **SenseVoice 服务正在报 500**：`microbubble-agent-sensevoice-1` 日志显示 `POST /transcribe 500 Internal Server Error`——GPU 驱动故障导致其 CUDA 上下文失效。驱动恢复后需要重启该容器。
3. **Ollama 常驻模型**：qwen3.5:9b (6.6GB) / qwen3:14b-q4 (9.3GB) / gemma4:12b (7.6GB) / qwen2.5vl:7b (6GB)。显存预算必须把 ollama 算进去（建议会议处理期 `keep_alive=0` 卸载）。

## 3. 第一轮：VibeVoice-ASR-BitNet（CPU，1.58GB）

### 3.1 构建过程（Windows / MinGW GCC，官方支持）

源码：`microsoft/VibeASR.cpp`（ggml/llama.cpp 内核）。本机踩坑记录：

| 问题 | 现象 | 修复 |
|---|---|---|
| 架构检测失败 | CMake 报 `Unknown architecture`，误编译 aarch64 内核，`VAE_ROW_BLOCK_SIZE` 等宏未定义 | `-DCMAKE_SYSTEM_PROCESSOR=x86_64` |
| SIMD 宏未启用 | `lm-config.h`/`vae-config.h` 只在 `__AVX2__` 定义时才给块大小宏 | 全局加 `-mavx2 -mfma -mssse3` |
| 运行期 segfault | Step 7 LM prefill 阶段崩（gdb 下能跑完，裸跑 6/6 崩） | `-Wl,--stack,33554432` + gdb 包裹运行（根因未完全定位，见 §3.4） |

产物：`build/bin/asr_infer.exe`（模型：`vibeasr-lm-i2_s-embed-q6_k.gguf` 993MB + `vibeasr-vae-encoder-i8_s.gguf` 703MB，hf-mirror 3 分钟下载完）。

### 3.2 实测结果（meeting-083 真实组会）

| 切片 | RTF@16T | 结果 |
|---|---|---|
| 30s | 0.65~0.81 | ✅ 转写基本正确（与 GT 段落 1-2 对齐） |
| 60s | 0.53 | ⚠️ 流利但领域术语崩坏：**"UV臭氧纳米气泡"→"邮被加加too young, not too poor"、"养殖尾水"→"杨志辉"、"基底"→"激励"** |
| 300s | — | ❌ **整段幻觉**：输出与会议完全无关的"教育"主题长文，模型自由发挥 |

关键事实：
- BitNet 实为 **Qwen2.5-1.5B 量化版**（不是 7B），官方承认 1-4% WER 退化；
- CLI 支持 `[Start-End] Speaker N: Content` 结构化输出，但实测 **BitNet 模型不输出 Speaker 标签**（说话人分离能力未带到量化版）；
- 不支持热词（7B transformers 版才支持）；
- 官方 WER 基准也印证：AISHELL4 中文会议 BitNet 27.45 vs SenseVoice 22.52 vs FunASR 20.41。

### 3.3 结论

BitNet 定位是**边缘设备/零显存兜底**：适合 ≤60s 的单条语音（如聊天 ASR 降级、离线笔记），**不适合 20-60min 会议**（质量悬崖 + 无说话人 + 无热词）。

### 3.4 遗留问题

裸跑（不经 gdb）在 prefill 阶段 segfault，gdb 下稳定复现成功，疑似 MinGW 线程栈或 ggml 内核内存问题。若未来采用 BitNet 做兜底，建议在 Linux/MSVC 官方推荐环境重建验证。

## 4. 第二轮：VibeVoice-ASR-7B（GPU）

**因 GPU 驱动故障本轮无法实测**。设计输入采用官方数据 + 代码架构分析：

| 项 | 数值 | 来源 |
|---|---|---|
| 显存 | ~16GB (FP16)；vLLM 加速支持 | 官方 README / HF |
| 中文会议 | AISHELL4: DER 6.77 / cpWER 24.99；AliMeeting: DER 10.92 / cpWER 29.33 | 官方报告 |
| 输出 | 单次 60min，Who + When(时间戳) + What，结构化 JSON | 官方文档 |
| 热词 | 原生支持（人名 + 术语注入） | 官方文档 |
| 微调 | LoRA finetuning 代码开放 | finetuning-asr/ |
| 依赖 | transformers（注意 5.0.0 暂不兼容）、flash-attn | 官方 docs |

**驱动恢复后的实测清单**（30 分钟可完成）：
1. `meeting-064`（1min）冒烟：加载耗时、峰值显存、Speaker 标签格式；
2. `meeting-083`（20min）：转写 CER vs `meeting83_final.md`（5448 字 GT）、说话人段落数 vs GT（王天志 55 段/杨慈 3 段）、热词注入 A/B；
3. 卸载后 `nvidia-smi` 显存归零验证（见 §6.3）。

## 5. 第三轮：声纹说话人区分（ERes2Net，CPU）

用生产库 17 份真实 embedding + meeting-083 全会议（能量 VAD 切 301 段 → 全部提嵌入 → 余弦聚类 → 簇质心 vs 成员向量）。

### 5.1 聚类本身是好的

- 301 段 → **2 个簇**，与 GT 参会人（王天志主导 + 杨慈简短插话）完全吻合；
- 簇 0：300 段 / 846.5s（97% 时长占比，与 GT 97% 一致）；簇 1：1 段 / 1.1s（对应杨慈级别的短插话被吸收）；
- 簇内相似度中位数 0.62，前两大簇质心相似度 0.484 —— 有区分度但不大（能量 VAD 粗切 + 单模型所致）。

### 5.2 名字映射坏了（核心发现）

| 现象 | 数据 |
|---|---|
| 主簇（真正的王天志）匹配到 **韩重阳** | dist **0.158**（远小于阈值 0.7，会自信地认错人） |
| 王天志自己的 anchor（121 次采样）反而排第三 | dist **0.359**（真人与自己 anchor 距离偏大） |
| DB 库内区分度 | 全库两两余弦距离 min **0.0** / median 0.831 |

### 5.3 根因：声纹库数据污染（vector_norm 实测）

| 问题 | 成员 | 证据 |
|---|---|---|
| **同一坏向量复制 4 份** | 耿嘉栋(0次)、关小未(3)、宋洋(1)、刘莫菲(0) | norm 全部 = 13.2603，两两 dist=0.0 |
| **未归一化向量** | 赵航佳(531)、张懿(745)、李胜景(488)、王书馨(526)、韩重阳(705)、杨慈(859) | 2026-06-28 的归一化修复只对"多次录入取均值"生效，单次录入的老向量没归一化 |
| **可信 anchor 仅 6 个** | 王天志/杜同贺/陈金薪/张宏魁/贾琦/周之超 | norm=1.0 且 `voice_confirmed_at` 非空 |

韩重阳 dist 0.158 的最可能解释：**单次录入样本方向性不可靠**（甚至可能是传错音频），而识别接口 `identify_speaker` 与全部 enrolled 成员比较（含污染向量），阈值 0.7 过松 → 自信认错。

### 5.4 结论

"准确区别说话人是谁"当前**被数据质量卡住，不是被模型卡住**。3D-Speaker ERes2Net 模型本身 + 聚类方法够用，需要的是治理。

## 6. 最佳方案：会议生命周期 = 显存生命周期

### 6.1 架构

```
┌─ 平时（无会议）──────── 显存占用 0 GB ────────────────┐
│  ollama 按需加载（keep_alive 管控）                       │
│  聊天短语音 ASR → SenseVoice-CPU 或 BitNet 兜底          │
└──────────────────────────────────────────────────────┘
          │ 会议开始（实时通话）或录音上传
          ▼
┌─ 会议处理期 ──────────── 峰值 ~18-26 GB ──────────────┐
│  gpu-meeting-worker（独立子进程/容器）：                  │
│   1. 载入 VibeVoice-ASR-7B (~16GB)                      │
│      → 60min 单次转写 Who/When/What + 热词注入           │
│   2. ERes2Net 声纹 (~0.5GB)：逐段嵌入 → 聚类             │
│      → 簇质心 ↔ anchor 向量 匹配 → Speaker N → 真名      │
│   3. （可选）Realtime-0.5B (~2GB) 实时语音回复           │
│  处理完成 → worker 进程退出 → 显存释放                    │
└──────────────────────────────────────────────────────┘
```

**为什么用"子进程退出"而不是 in-process 卸载**：项目自己的基准报告（`docs/asr-benchmark-2026-06-30.md` §2.1）实测 Whisper 卸载后仍有 **4.3GB residual 显存不可释放**（CTranslate2 CUDA 上下文残留）。进程退出是唯一能保证归零的方式。

### 6.2 显存预算

| 状态 | 显存 |
|---|---|
| 平时 | **0**（worker 不存在；ollama 空闲卸载；SenseVoice 聊天 ASR 可驻留 CPU） |
| 会议处理 | VibeVoice-ASR-7B 16GB + 声纹 0.5GB + Realtime-0.5B 2GB ≈ **18.5GB**；若 ollama qwen3:14b 同时驻留 +9.3GB → 27.8GB < 32GB ✅（建议会议期 `keep_alive=0`） |

### 6.3 说话人准确性保障（数据治理 3 步 + 机制 2 步）

**数据治理（一次性 SQL + 重新录入）**：
1. 清除 4 份相同坏向量：`耿嘉栋/关小未/宋洋/刘莫菲`（norm 全等 13.2603）→ 置 NULL 重新录入；
2. 重新录入 6 个未归一化向量：`赵航佳/张懿/李胜景/王书馨/韩重阳/杨慈`（norm 488~859）；
3. 入库前强制 L2 归一化 + norm 校验（`abs(norm-1) < 0.01`），并加"同 norm 不同人"重复检测。

**机制（代码改动小）**：
4. 识别只用 anchor（`identify_speaker_anchored` 已实现！）替代 `identify_speaker`，杜绝污染向量干扰；
5. 会议级说话人归属改为**逐段投票**：每个 VibeVoice Speaker 聚合其全部段落嵌入的质心再匹配，而不是单段匹配（本测试已验证 300 段质心的稳定性）。

### 6.4 决策矩阵

| 方案 | 显存 | 说话人 | 中文会议质量 | 建议 |
|---|---|---|---|---|
| **VibeVoice-ASR-7B + 声纹映射（按需加载）** | 会议期 16-18.5GB，平时 0 | ✅ 模型自带 diarization + 声纹定名 | 官方 cpWER 24.99（AISHELL4），待本机复测 | **主方案**（驱动修复后先跑 §4 清单再切换） |
| SenseVoice（现状）+ 声纹映射 | 1GB 常驻 | ❌ 无 diarization，纯靠声纹 | CER 15.6%（项目基准） | 保留为聊天 ASR / fallback |
| BitNet CPU | 0 | ❌ 无 Speaker 标签 | 60s+ 崩坏、300s 幻觉 | 仅边缘兜底，不推荐会议 |
| Whisper large-v3（已下线） | 8GB 常驻，卸载残留 4.3GB | ❌ | CER 25.7% | 维持下线 |

## 7. 风险与待办

- [ ] **P0** 重启 NVIDIA 驱动/主机 → 恢复 GPU；重启 sensevoice 容器（当前 500）
- [ ] **P0** 声纹库数据清洗（§6.3 步骤 1-3）
- [ ] **P1** 驱动恢复后按 §4 清单实测 VibeVoice-ASR-7B（含热词 A/B：注入"微纳米气泡/空化/UV臭氧/养殖尾水 + 17 人名单"）
- [ ] **P1** 实现 gpu-meeting-worker 子进程生命周期（任务队列 + 进程退出 + 显存归零断言）
- [ ] **P2** VibeVoice-ASR-Streaming-7B 评测（实时通话场景，9 月 3 日刚发布）
- [ ] **P2** 能量 VAD → silero-VAD（models/torch_hub 已有），降低过切/欠切

## 8. 测试产物

| 文件 | 说明 |
|---|---|
| `.workbuddy/vibevoice-test/VibeASR.cpp/` | 引擎源码 + 构建产物 asr_infer.exe |
| `.workbuddy/vibevoice-test/models/*.gguf` | BitNet 量化模型 ×2 (1.58GB) |
| `.workbuddy/vibevoice-test/test_voiceprint_container.py` | 声纹说话人区分测试脚本（容器版） |
| `.workbuddy/vibevoice-test/result_speakerid.json` | 声纹测试完整结果 |
| `.workbuddy/vibevoice-test/bitnet_{30,60,300}s.txt` | BitNet 各切片原始输出 |

**测试人**: WorkBuddy Agent | 2026-09-07
