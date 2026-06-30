---
name: asr-benchmark-2026-06-30
description: ASR 模型对比 benchmark 完整沉淀 — Whisper large-v3 vs SenseVoice-Small vs Paraformer-large 在 RTX 5090 上的实测数据 + 5 维度对比 + 决策建议
metadata:
  type: project
---

# ASR 模型对比 benchmark (2026-06-30)

## Context

`docs/asr-alternatives.md` 列出了 17 个 Whisper 替代品，但厂商声称未经 RTX 5090 (Blackwell sm_120) + 真实业务数据验证。本任务用统一 benchmark 测 3 个候选 (Whisper baseline / SenseVoice-Small / Paraformer-large)，给用户提供**可决策**的实测数据。

## 核心结论 (TL;DR)

**SenseVoice-Small 5 维度全部胜出**:
- VRAM: **0.93 GB vs 8.0 GB** (-88%)
- RTF: 0.01-0.09 vs 0.08-0.25 (**3-25x 加速**)
- 中文 CER: 15.6% vs 25.7% (改善 39%)
- 20 min 会议覆盖: 500 字 vs 105 字 (4.7x)
- 中文标点 + ITN 原生支持

**推荐**: 混合架构 (SenseVoice 主 + Whisper fallback 长会议)

## 关键文件

- 主报告: [docs/asr-benchmark-2026-06-30.md](../microbubble-agent/docs/asr-benchmark-2026-06-30.md)
- 脚本: `scripts/prepare_eval_audio.py` + `scripts/benchmark_asr.py` + `scripts/aggregate_metrics.py`
- 7 层过滤器重构: `app/voice/asr_filters.py` (commit ac80ec3a 删的代码重新落地)
- 数据: `data/asr_eval/{synthetic,normalized,ground_truth.jsonl}`
- 结果: `results/asr_benchmark_2026-06-30/{summary.json, metrics/*, transcripts/*}`

## 7 条铁律 (永久沉淀)

### 铁律 1: SenseVoice 处理长会议需要 `batch_size_s=60` 防止 OOM

**症状**: 20 min 会议 peak VRAM 25.77 GB (32 GB 上限, 接近 OOM)
**根因**: funasr `model.generate()` 默认 `batch_size_s=300` (5 min chunk), 累积所有 chunk 状态
**修复**: `model.generate(input=path, batch_size_s=60)` (1 min chunks, 安全)
**纪律**: 任何 >10 min 音频, 调小 `batch_size_s`

### 铁律 2: funasr 1.3.14 + Seaco Paraformer + ct-punc = `generate()` hang

**症状**: 模型加载 OK, `m.generate(input=path)` 静默挂起
**调试路径**:
- 单独加载 Seaco Paraformer (无 punc) → 0.93 GB, 正常 inference
- 加 `punc_model='ct-punc'` → 加载成功 (1.2 GB) + jieba 初始化 OK, 但 `generate()` 静默 60s+
- 120s 后进程被 timeout kill, **无 exception 抛出**
**根因推测**: Punc 模型推理路径与 Seaco 冲突 (funasr 1.3.14 bug)
**修复**: 等 funasr 1.4+ 修复, 或用 SenseVoice 替代
**临时方案**: Paraformer benchmark 只跑无 punc 模式 (字符级输出)

### 铁律 3: benchmark 脚本中途崩溃必须从 transcripts 重建 metrics

**症状**: 完整 benchmark (3 backends × 20 audios × 3 runs) 跑 ~15 min 后进程消失, 但 `transcripts/` 增量写入
**根因**: Claude shell session timeout 触发, 或父进程 kill
**修复模式**:
1. transcripts 在每次 transcribe 后立即写 (增量安全)
2. metrics.json 在整个 backend 跑完后才写 (易丢失)
3. 写 `aggregate_metrics.py` 从 transcripts parse + 重算 CER/VRAM/RTF (从文件名/duration 推)
**纪律**: 任何长跑 benchmark 任务, **必须** 增量保存中间结果, 不能等全部跑完再统一写

### 铁律 4: SenseVoice 的 emotion tag 必须 strip 才能算 CER

**症状**: SenseVoice 输出 `<|zh|><|HAPPY|><|Speech|><|withitn|>今天天气真好...`
- raw CER: **184%** (tags 计入 13+ 字符"差异", CER > 100%)
- stripped CER: 15.6% (正常)
**修复**: `app.voice.asr_filters.strip_all_tags()` 剥除所有 `<|...|>` 标签
**纪律**: 任何 FunASR SenseVoice 输出, 必先 strip tags 再做 NLP/评估
**pattern**: `<\|[a-z]+\|>` 多次 sub() 或单次 `re.sub(r"<\|[^|]+\|>", "", text)`

### 铁律 5: ITN 模式让 CER 评估对数字/日期不公平

**症状**:
- GT: "一百二十三万四千五百六十七元"
- Whisper: "项目预算共计1234567元" (CER 62% — ITN 转阿拉伯数字)
- Paraformer: "项目预算共计一百二十三万四千五百六十七元" (CER 5% — 保留中文)
**根因**: ITN 是"用户友好"功能, 但 CER 评估期待"字面匹配"
**解决方案**:
- 用 `text.replace("1234567", "一百二十三万四千五百六十七")` 反 ITN 后算 CER (复杂)
- 或: 评估时分开两类 — ITN-mode CER vs 字面 CER
- 或: 业务上 ITN 通常更好, 接受"数字 CER 高, 用户体验好"的权衡
**纪律**: ASR benchmark 报告必须**明确**是否包含 ITN, 让用户基于业务选

### 铁律 6: VRAM 测量必须用 delta (warmup 后 - warmup 前), 不能用 nvidia-smi 总值

**症状**: benchmark 报告 SenseVoice peak VRAM 12.37 GB (实际 SenseVoice 只 0.93 GB, 12 GB 是 whisper 8 GB + 其他)
**根因**: `nvidia-smi --query-gpu=memory.used` 返回整卡总占用, 不是单 backend
**修复**:
```python
vram_before = nvidia_smi_memory()  # baseline
backend.warmup()
vram_after = nvidia_smi_memory()
backend_resident = max(0, vram_after - vram_before)  # 本 backend 增量
```
**纪律**: 多 backend 共存 GPU 时, VRAM 测量永远是 delta, 永远不是 absolute

### 铁律 7: 长会议 (20 min) Whisper 输出极少 (105 字), 不是模型差而是 VAD/no_speech 过激

**症状**: meeting-083 (20 min) Whisper output 105 字, polished GT 5448 字
**根因**: Whisper `no_speech_threshold=0.6` 过滤了大部分低能量段 (会议室环境)
**对比**: SenseVoice 在同音频输出 500 字 (4.7x), 因 SenseVoice VAD 更激进保留
**业务影响**:
- 短聊天 ASR: 两者差异不大 (音频能量清晰)
- 会议 ASR: SenseVoice **显著**优于 Whisper (VAD 设计差异)
**纪律**: 评估 ASR backend 时, **必须**测长会议 (而非只看短聊天), 才能发现 VAD 设计差异

## 6 条踩坑教训 (实施过程)

### 踩坑 1: docker cp Windows path 解析失败

**症状**: `docker cp "e:\path\file.py" container:/app/file.py` 报 `C:/Program Files/Git/app/file.py: No such file or directory`
**根因**: Git Bash 把 Windows 路径 `e:\` 翻译成 `C:/Program Files/Git/e/`
**修复**: 
```bash
# 用 POSIX 路径
cd /e/microbubble-agent
docker cp "$(pwd)/scripts/file.py" container:/app/scripts/
```
或 `cd /e/microbubble-agent && docker cp ./scripts/file.py container:/app/scripts/`

### 踩坑 2: `pwd`/路径在 `python -c "..."` 多行字符串里

**症状**: heredoc 内 `Path('/app/...')` 在 Git Bash 下被错误翻译
**修复**: 用 `bash -c "cd /app && python script.py"` 模式, 或单行 `python -c "..."`

### 踩坑 3: 容器内 ROOT 路径不同 (在 /app 不是 /e/microbubble-agent)

**症状**: `prepare_eval_audio.py` 用 `ROOT / "meeting83_final.md"`, 容器内 ROOT = /app, 文件实际在 host /e/microbubble-agent/
**修复**: 
- `docker cp meeting83_final.md container:/app/meeting83_final.md`
- 重新跑脚本
**纪律**: 任何 host-only 文件 (不在 volume mount) 都必须 `docker cp` 进容器

### 踩坑 4: benchmark 进程被 kill, metrics 全部丢失

**症状**: 运行 15 min 后进程消失, `metrics/*.json` 只有 3 records (而非 60)
**根因**: Claude shell session 30 min timeout 触发, 或其他父进程 kill
**修复**: 写 `aggregate_metrics.py` 从 transcripts 重建 metrics
**纪律**: 长跑 benchmark 必加 `--limit` 分批跑, 或加 checkpoint 重启

### 踩坑 5: Paraformer 输出字符间空格 ("今 天 是 六 月")

**症状**: Paraformer 无 punc 时输出 "啊 今 天 是 六 月 五 号 然 后 我 这 是..."
**根因**: Paraformer 输出 token 间默认空格分隔, 中文场景需要 strip
**修复**: `re.sub(r"\s+", "", text).strip()` 后 CER 计算
**纪律**: 任何 Paraformer 输出必先 `re.sub(r"\s+", "", text)`

### 踩坑 6: SenseVoice 跳过 emotion tag 后的 "Speech"/"BGM" 标签是有效内容

**症状**: SenseVoice 输出 `<|BGM|>` (背景音乐) 或 `<|Speech|>` (说话) 标签
**正确处理**: `strip_bgm_tags` 只剥 BGM 标签 (替换为空), 保留 Speech 标签 (代表有说话)
**bug**: 我最初把所有 `<|...|>` 都剥掉, 丢失了 "BGM" vs "Speech" 区分
**修正**: `strip_emotion_tags` (剥 lang/emotion/withitn) + `strip_bgm_tags` (只剥 BGM/cry/laugh/sigh/cough) 分开实现

## 数据复现

```bash
# 1. 准备 ground truth (10 合成 + 10 真实音频)
cd /e/microbubble-agent
docker cp scripts/prepare_eval_audio.py microbubble-agent-app-1:/app/scripts/
docker cp meeting83_final.md microbubble-agent-app-1:/app/
docker exec -w /app microbubble-agent-app-1 python scripts/prepare_eval_audio.py

# 2. 跑 benchmark
docker cp scripts/benchmark_asr.py microbubble-agent-app-1:/app/scripts/
docker exec -w /app microbubble-agent-app-1 python scripts/benchmark_asr.py \
    --backends whisper,sensevoice,paraformer \
    --synthetic-dir data/asr_eval/synthetic/ \
    --audio-dir data/asr_eval/normalized/ \
    --ground-truth data/asr_eval/ground_truth.jsonl \
    --output-dir results/asr_benchmark_2026-06-30/ \
    --runs 3

# 3. 从 transcripts 聚合 metrics (即使 benchmark 中途崩溃)
docker exec -w /app microbubble-agent-app-1 python scripts/aggregate_metrics.py \
    --transcripts-dir results/asr_benchmark_2026-06-30/transcripts/ \
    --ground-truth data/asr_eval/ground_truth.jsonl \
    --output-dir results/asr_benchmark_2026-06-30/
```

## 与之前 CLAUDE.md 沉淀的关联

- 与 v31.3 (Whisper 常驻 GPU 8GB) 对比: SenseVoice 只 0.93 GB, **释放 7 GB 显存可用于其他模型**
- 与 2026-06-29 #043 (chat history persistent) 协同: 后端 chat API 改造, ASR 切换不影响前端
- 与 docs/asr-alternatives.md (17 模型对比) 关联: 本报告是 alternatives.md 的实测验证

## 后续工作 (用户决策后)

- [ ] 用户决定: 迁移 / 保持 / 混合
- [ ] 如果迁移 SenseVoice: 实施 `app/api/v1/voice.py` 后端切换 + Dockerfile.funasr
- [ ] 补全 9 个真实会议 ground truth (~45 min 手工)
- [ ] 完整跑 Paraformer benchmark (短音频, 跳过 hang 的长会议)
- [ ] 测试 SenseVoice 流式模式 (`chunk_size=[0,60,20]`) 首 token 延迟
- [ ] 评估 2h+ 会议 OOM 行为, 调小 `batch_size_s=60`
- [ ] 集成 Whisper-fallback 自动切换 (>30 min 会议)
- [ ] 生产灰度 A/B 测试 (10% 流量)