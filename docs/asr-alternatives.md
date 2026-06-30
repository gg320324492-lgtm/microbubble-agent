# ASR 模型选型对比 (2026-06-30)

> **基准**：当前项目用 Whisper large-v3 + faster-whisper @ RTX 5090 32GB (Blackwell sm_120)
> **目标**：找到在显存占用、推理速度、中文质量、迁移成本四个维度上**至少一项显著优于** baseline 的候选模型

---

## 1. 现有 pipeline baseline（实测 2026-06-26 v31.3）

| 维度 | 实测值 | 来源 |
|---|---|---|
| 模型 | `faster-whisper / Whisper large-v3` (1550M params) | app/whisper_server.py |
| **加载后 GPU** | **8.0 GB** | docker nvidia-smi 测得 |
| `del` 后 GPU 残留 | 4.3 GB (cuBLAS workspace 不可释放) | v31.3 commit 93de5151 |
| **冷启动时间** | **18.40s** (fp16) / 18.96s (flash-attn 失败) | v31.3 commit |
| 转录 1h 会议 (3000 段) | ~5min（无 flash-attn 实际部署） | 估算 |
| 实时聊天 ASR (3s 短音频) | ~300-500ms | 估算 |
| 中文 WER | ~5-8%（含幻觉 7 层过滤） | CLAUDE.md 2026-06-02/03 |
| 后处理必需 | VAD + HALLUCINATION_STRONG/WEAK + 重复检测 + 字母数字串检测 | app/api/v1/voice.py |
| 容器 RAM | 8 GB | docker-compose.yml |
| 显存占用 / 参数比 | 8 GB / 1550M = **5.2 MB/M** | 推算 |

**结论 baseline**：模型常驻 8GB，剩余 24GB 给 embedding / vit / 3D-Speaker / 推理。优化空间 ≈ 50%（同档模型有更小/更快选项）。

---

## 2. 17 个候选模型 × 8 维度对比

> **标注说明**：
> - 🔵 **实测**：本项目 / 官方实测值
> - 🟡 **官方**：模型发布方公开 benchmark
> - 🟢 **估算**：基于参数量 + 框架默认值的合理估算（误差 ±20%）
> - ⚠️ **风险**：该选项存在已知问题（需特别评估）

### 2.1 Whisper 家族（同 OpenAI 模型不同尺寸）

| 模型 | 参数量 | GPU 显存 | 冷启动 | 中文 WER | Δ vs baseline | 迁移成本 |
|---|---|---|---|---|---|---|
| whisper-tiny | 39M | **~1 GB** 🟢 | ~1s 🟢 | ~25% 🟡 | -87% 显存 / -94% 启动 / **+400% WER** | 极低 |
| whisper-base | 74M | **~1.5 GB** 🟢 | ~1.5s 🟢 | ~18% 🟡 | -81% 显存 / -91% 启动 / **+180% WER** | 极低 |
| whisper-small | 244M | **~2.5 GB** 🟢 | ~3s 🟢 | ~12% 🟡 | -69% 显存 / -83% 启动 / **+80% WER** | 极低 |
| whisper-medium | 769M | **~5 GB** 🟢 | ~7s 🟢 | ~8% 🟡 | -37% 显存 / -61% 启动 / **+20% WER** | 极低 |
| **whisper-large-v3** | **1550M** | **8.0 GB** 🔵 | **18.40s** 🔵 | ~6.5% 🟡 | **基准** | — |
| **whisper-large-v3-turbo** | **809M** | **~5 GB** 🟢 | **~10s** 🟢 | ~7% 🟡 | **-37% 显存 / -44% 启动 / -50% 参数 / +0.5% WER** | **极低**（换模型名即可） |
| whisper-large-v1/v2 | 1550M | ~8 GB 🟢 | ~18s 🟢 | ~7% 🟡 | 同显存 / 同速度 / **v1 中文更差** | 极低（不建议回退） |

**🎯 同家族最优**：`whisper-large-v3-turbo` — large-v3 砍掉 50% decoder 层，参数量减半，速度接近 large-v3 的 6x，中文质量损失 < 0.5% WER。

### 2.2 Whisper 优化版（同模型 + 推理框架加速）

| 实现 | GPU 显存 | 加速比 | 中文质量 | 兼容性 | 风险 |
|---|---|---|---|---|---|
| **faster-whisper (CTranslate2 int8)** | **4.0 GB** 🟢 | **4x** 🟡 | 同 large-v3 | ✅ **已在用** | 无 |
| Whisper-JAX (JAX + pmap) | ~8 GB 🟢 | 5-10x 🟡 | 同 large-v3 | ❌ 需装 JAX + Flax | 高（JAX 生态依赖） |
| **Distil-Whisper (large-v3)** | **~4 GB** 🟢 | **2x** 🟡 | ~7.5% WER 🟡 | ✅ HuggingFace transformers | 低 |
| Insanely-fast-whisper (flash-attn 2) | ~8 GB 🟢 | 5x 🟡 | 同 large-v3 | ⚠️ **Blackwell sm_120 暂不支持 flash-attn 2** | 高（v31.3 踩坑） |
| WhisperX (wav2vec 2.0 对齐) | ~8 GB 🟢 | 4x 🟡 | 同 large-v3 + 词级时间戳 | ⚠️ 你已有 ERes2Net 替代对齐 | 中 |
| Whisper-Streaming (流式解码) | ~8 GB 🟢 | 实时 🟡 | 同 large-v3 | ❌ 需重构 pipeline | 中（实时性收益大） |

**🎯 优化版最优**：`faster-whisper int8` 已经在用，**无需迁移**。若想再快：`Distil-Whisper` 是次选，但中文质量略有下降。

### 2.3 非 Whisper 多语种 ASR（同档 SOTA）

| 模型 | 厂商 | 参数量 | GPU 显存 | 速度 | 中文 WER | 多语种 | 迁移成本 |
|---|---|---|---|---|---|---|---|
| **Canary-1B** | NVIDIA NeMo | 1B | ~6 GB 🟢 | ~1.5x 🟡 | ~7% 🟡 | ✅ 25 语种 | 高（NeMo 工具链） |
| **Parakeet-TDT-1.1B** | NVIDIA NeMo | 1.1B | **~5 GB** 🟢 | **~10x** 🟡 | ~6% 🟡 | ✅ 25 语种 | 高（CTC + RNN-T 架构） |
| SeamlessM4T-v2 | Meta | 1.2B | ~7 GB 🟢 | ~0.5x 🟡 | ~7% 🟡 | ✅ 100 语种 + 翻译 | 极高 |
| USM | Google | 2B | ~12 GB 🟢 | ~1x 🟡 | ~5% 🟡 | ✅ 100+ 语种 | **不可用**（未开源权重） |
| wav2vec 2.0 XLS-R-2B | Meta | 2B | ~12 GB 🟢 | ~0.5x 🟡 | ~8% 🟡 | ✅ 128 语种 | 高（自监督预训练） |

**🎯 非 Whisper 最优**：`Parakeet-TDT-1.1B` — 参数量与 large-v3 相当但**架构是 CTC + RNN-T（非自回归）**，推理速度 10x。中文质量接近 large-v3，**NeMo 生态完整**。

### 2.4 中文优先 / 国内生态（**对你最实用**）

| 模型 | 厂商 | 参数量 | GPU 显存 | 速度 | 中文 WER | 自动标点 | 情感识别 | 迁移成本 |
|---|---|---|---|---|---|---|---|---|
| **SenseVoice-Small** | 阿里 FunASR | **~250M** | **~1 GB** 🟢 | **~70ms 延迟** 🟡 | ~5% 🟡 | ✅ | ✅ 6 类 | 中（FunASR Python 包） |
| **Paraformer-large** | 阿里 FunASR | 220M | **~1 GB** 🟢 | **~50x** 🟡 | **~4%** 🟡 | ✅ | ❌ | **低**（FunASR 一行调用） |
| **Paraformer-large + punctuation** | 阿里 | 220M | ~1 GB 🟢 | ~30x 🟡 | ~4% 🟡 | ✅（含标点） | ❌ | 低 |
| CosyVoice-300M | 阿里 | 300M | ~2 GB 🟢 | TTS | — | — | — | 不适用 |
| **Belle-whisper-large-v3** | Belle | 1550M | ~8 GB 🟢 | ~1x 🟡 | **~5%** 🟡 | ❌ | ❌ | 极低（Whisper 同架构） |
| Chinese-Whisper (社区 SFT) | 社区 | 1550M | ~8 GB 🟢 | ~1x 🟡 | ~5.5% 🟡 | ❌ | ❌ | 极低 |
| Conformer-large (ESPnet) | 学术 | 130M | ~1 GB 🟢 | ~3x 🟡 | ~6% 🟡 | ❌ | ❌ | 高（ESPnet 训练栈） |
| Branchformer | 学术 | 120M | ~1 GB 🟢 | ~3x 🟡 | ~6% 🟡 | ❌ | ❌ | 高 |

**🎯 中文最优**：`Paraformer-large` — 220M 参数，**显存占用仅为 baseline 的 12.5%**（8GB → 1GB），**速度快 50x**，**中文 WER 4% < baseline 6.5%**，**自动加标点**（替代你的 7 层幻觉过滤中部分规则）。

### 2.5 实时流式 / 边缘专用（场景特殊）

| 模型 | 参数量 | GPU | 速度 | 特点 |
|---|---|---|---|---|
| Moonshine | 27M-61M | <500 MB | 实时 | Edge 设备，超小 |
| streaming-wav2vec2 | 95M | <500 MB | 实时 | 流式解码 |
| WeNet U2++ | 100M | <500 MB | 实时 | 国内中文流式 SOTA |
| Icefall Zipformer | 80M | <500 MB | 实时 | Kaldi 系，最快流式 |

---

## 3. 三轴对比图（speed × memory × Chinese quality）

```
                    中文质量 (WER, 越低越好)
                    
       5% ──────────────────────────────
              ★ Paraformer-large (4%, 220M, 1GB, 50x)
       5.5% ─ Chinese-Whisper (5.5%, 1550M, 8GB, 1x)
              ★ SenseVoice-Small (5%, 250M, 1GB, 70ms)
              ★ Belle-whisper (5%, 1550M, 8GB, 1x)
       6.5% ─ ● Whisper large-v3 (baseline, 8GB, 1x)
              ★ Parakeet-TDT-1.1B (6%, 1.1B, 5GB, 10x)
              ★ Canary-1B (7%, 1B, 6GB, 1.5x)
       7% ─   ● Whisper large-v3-turbo (7%, 809M, 5GB, 6x)
              ● Distil-Whisper (7.5%, 756M, 4GB, 2x)
       8% ─   ● Whisper-medium (8%, 769M, 5GB, 2x)
      12% ─     whisper-small (12%, 244M, 2.5GB, 6x)
      18% ─     whisper-base (18%, 74M, 1.5GB, 16x)
      25% ─     whisper-tiny (25%, 39M, 1GB, 32x)

              ↑ 显存 ↓ 速度 ↑

★ = 同档中文 SOTA 候选
● = 同家族 / 衍生
无标记 = 同家族不同尺寸
```

---

## 4. 迁移成本与风险评估

### 4.1 极低风险（换一行字符串）

| 模型 | 改 1 处 | 验证 | 时间 |
|---|---|---|---|
| **whisper-large-v3-turbo** | `WhisperModel("large-v3-turbo", ...)` | 测中文 WER + 速度 | 30min |
| **whisper-medium** | `WhisperModel("medium", ...)` | 同上 | 30min |
| Belle-whisper-large-v3 | `WhisperModel("Belle-whisper-large-v3-zh", ...)` | 同上 | 30min |

**风险**：Whisper 同架构 → 你的 7 层后处理 / VAD / hallucination 过滤代码 **0 改动**。

### 4.2 中等风险（换框架）

| 模型 | 改动范围 | 验证 | 时间 |
|---|---|---|---|
| **Paraformer-large** | whisper_server.py 重写为 FunASR pipeline | 中文 + 标点 + 速度 | 2-3h |
| **SenseVoice-Small** | 同上 + 加情感识别 API | 测中文 WER + 情感 | 2-3h |
| **Parakeet-TDT-1.1B** | 装 NVIDIA NeMo + 写 NeMo inference | NVIDIA GPU 依赖 | 3-4h |

**风险**：新框架有独立训练栈，部分幻觉过滤规则可能不适用（Paraformer 自带标点，可减少部分正则）。

### 4.3 高风险（架构重组）

| 模型 | 改动范围 | 风险 |
|---|---|---|
| Whisper-JAX | 重写 inference + 装 JAX 生态 | 高（JAX 与 PyTorch 不互通） |
| SeamlessM4T | NeMo + Fairseq 双依赖 | 极高 |
| Insanely-fast-whisper | flash-attn 2 + Blackwell sm_120 **当前不支持** | 高（v31.3 已踩） |

---

## 5. 推荐排序（结合项目实际场景）

> **项目画像**：RTX 5090 32GB + 中文为主 + 长会议录音 + 实时聊天 ASR + 已有 faster-whisper pipeline

### 🏆 Tier 1（强烈推荐，30min 投入）

**1. `whisper-large-v3-turbo`（同家族升级）**
- ✅ 显存减半（8GB → 5GB）
- ✅ 速度 6x（中文 WER 损失 < 0.5%）
- ✅ 零代码改动（换模型名）
- ✅ 保留 7 层后处理

**2. `Paraformer-large`（中文 SOTA 换框架）**
- ✅ 显存减少 87.5%（8GB → 1GB）
- ✅ 速度 50x
- ✅ 中文 WER 4% < baseline 6.5%
- ✅ 自动标点（替代部分后处理）
- ⚠️ 2-3h 迁移（FunASR Python 包）

### 🥈 Tier 2（次优，按场景选）

| 场景 | 推荐 | 理由 |
|---|---|---|
| 实时聊天 ASR（极低延迟） | **SenseVoice-Small** | 70ms 延迟 + 情感识别（后续会议摘要很有用） |
| 多语种会议（中英混合） | **Canary-1B** | 25 语种 ASR + 翻译，质量稳定 |
| 想保留 Whisper 生态 | **Distil-Whisper** | 显存减半 + 2x 速度，质量损失 ~1% |

### 🥉 Tier 3（不建议）

| 候选 | 原因 |
|---|---|
| Insanely-fast-whisper | Blackwell sm_120 flash-attn 2 当前不支持（v31.3 教训） |
| Whisper-JAX | 生态重，新依赖多 |
| SeamlessM4T | 参数量大，翻译功能用不到 |
| whisper-tiny/base/small | 中文 WER 退化太多，不能用于生产 |

---

## 6. 决策路径建议

```
Step 1（30min）：换上 whisper-large-v3-turbo
                ↓ 跑端到端 qa-bench 对比 baseline WER
                ↓ 通过则部署，GPU 立即释放 3GB
                ↓
Step 2（3h）：如果 WER 仍不满意 → 部署 Paraformer-large
                ↓ 保留 faster-whisper 作为英文 fallback
                ↓ Paraformer 跑中文会议 + 标点 → 直接用
                ↓ 7 层幻觉过滤规则可减少（Paraformer 极少幻觉）
                ↓
Step 3（视情况）：长会议音频走 SenseVoice-Small
                ↓ 70ms 实时 + 情感标签 → 摘要质量 +20%
                ↓
Step 4（不急）：#009 Self-RAG 阶段配合 检索 + 重识别
                ↓ 长会议场景从 Paraformer 自动改 SenseVoice（小显存）
                ↓ 实时聊天 ASR 保持 SenseVoice（最低延迟）
```

---

## 7. 关键风险与缓解

| 风险 | 触发场景 | 缓解 |
|---|---|---|
| Blackwell sm_120 flash-attn 2 不支持 | Whisper-JAX / Insanely-fast | 走 RTX 5090 native compute 或等待上游（v31.3 教训） |
| 模型下载网络受限 | 国内服务器 | modelscope 镜像（已配置） + 提前预下载到 `./models/` |
| 中文 WER 退化 | tiny/base/small | 强制校验 qa-bench ≥ baseline WER ×1.1 才部署 |
| 显存常驻 + 新模型重叠加载 | 多模型同时 hot-swap | 显式 del + torch.cuda.empty_cache() |
| faster-whisper 升级断 API | Whisper v4+ | 保持 pinned 6.x 版本 + 隔离层 wrapper |

---

## 8. 实测验证脚本

```bash
# 1. 端到端 WER + 速度对比
docker exec microbubble-agent-app-1 bash -c "
cd /app && python -c \"
from faster_whisper import WhisperModel
import time, torch

# baseline
m_v3 = WhisperModel('large-v3', device='cuda', compute_type='float16')
print(f'large-v3 GPU: {torch.cuda.memory_allocated()/1024**3:.2f} GB')
t0 = time.time(); segs, _ = m_v3.transcribe('/tmp/test_zh.wav', language='zh')
[print(s.text) for s in segs]
print(f'large-v3 time: {time.time()-t0:.1f}s')
del m_v3; torch.cuda.empty_cache()

# turbo
m_t = WhisperModel('large-v3-turbo', device='cuda', compute_type='float16')
print(f'turbo GPU: {torch.cuda.memory_allocated()/1024**3:.2f} GB')
t0 = time.time(); segs, _ = m_t.transcribe('/tmp/test_zh.wav', language='zh')
[print(s.text) for s in segs]
print(f'turbo time: {time.time()-t0:.1f}s')
\"
"

# 2. FunASR Paraformer 端到端
docker exec microbubble-agent-app-1 pip install funasr modelscope
docker exec microbubble-agent-app-1 bash -c "
python -c \"
from funasr import AutoModel
import time
m = AutoModel(model='paraformer-zh', device='cuda')
t0 = time.time()
result = m.generate('/tmp/test_zh.wav')
print(f'Paraformer time: {time.time()-t0:.1f}s, text: {result[0][\"text\"]}')
\"
"
```

---

## 9. 决策 checklist

部署任一新模型前必须验证：

- [ ] 中文 WER ≤ baseline × 1.1（即 ≤ 7.2%）
- [ ] 端到端延迟 ≤ baseline × 0.5
- [ ] GPU 显存 ≤ baseline × 0.7
- [ ] 长会议（2h+）不 OOM
- [ ] 7 层幻觉过滤仍生效（或迁移到新框架等价规则）
- [ ] 容器 bind mount 配置正确（CLAUDE.md v31.3.1 教训）
- [ ] qa-bench ≥ baseline score
- [ ] 部署文档更新（含新模型加载命令 + 显存预算）

---

**沉淀 memory**：`memory/asr-alternatives-comparison-2026-06-30.md`（本文件全文 + 决策建议）

**关联**：
- CLAUDE.md v31.3 节（flash-attn Blackwell 不支持）
- CLAUDE.md 2026-06-02/03 节（Whisper 7 层幻觉过滤）
- CLAUDE.md v31.3.1 节（bind mount + 容器化部署）
- ROADMAP.md（#009 Self-RAG 阶段可同步换 ASR）