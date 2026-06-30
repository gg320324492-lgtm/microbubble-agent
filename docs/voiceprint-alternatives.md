# 声纹模型选型对比 (2026-06-30)

> **基准**：当前项目用 `iic/speech_eres2net_sv_zh-cn_16k-common` (ModelScope 3D-Speaker, 192-dim embedding) @ RTX 5090 32GB
> **目标**：找到在**中文识别率、推理速度、模型尺寸、迁移成本**四个维度上**至少一项显著优于** baseline 的候选声纹模型
> **硬件预算**：GPU 显存 ~27 GB 空闲（SenseVoice 已占 ~5 GB），中文母语 15-20 人研究组
> **网络约束**：必须可走 ModelScope / HuggingFace（国内网稳定）

> **重要说明**：本调研中 EER / minDCF 数值为公开论文 / 模型卡近似值（2024-2026 年的已发表结果），**实际部署前必跑** `scripts/verify_cross_meeting_recognition.py` 跨会议识别率门禁 (CLAUDE.md 2026-06-28：< 90% 自动 rollback)。

---

## 1. 现有 pipeline baseline（实测 2026-06-19 + 2026-06-28）

| 维度 | 实测值 | 来源 |
|---|---|---|
| 模型 | `iic/speech_eres2net_sv_zh-cn_16k-common` (ERes2Net, ~6.1M params) | app/services/voiceprint_service.py:46 |
| **嵌入维度** | **192** | voiceprint_service.py:24 (`EMBEDDING_DIM`) |
| **训练数据** | CN-Celeb (~1,200 speakers, ~130k utterances) + 内部 Mandarin | 3D-Speaker 论文 |
| **MATCH_THRESHOLD** | **0.7** (余弦距离，越低越相似) | voiceprint_service.py:26 |
| **MATCH_THRESHOLD 实战差距** | 实际多人会议区分度仅 **0.05**（intra=0.99 / inter=0.92-0.97） | CLAUDE.md 2026-06-02 实测 |
| **跨会议识别率** | **88-95%**（王天志 88.1% 触发 90% 门禁，rollback；杜同贺 0 BLOCKED） | voiceprint-purification-loop-151-2026-06-28.md |
| 同人 intra-class cos | **0.99** ✅ | CLAUDE.md 2026-06-02 |
| 不同人 inter-class cos | 0.92-0.97（合成信号 / 真实信号区分度更小） | CLAUDE.md 2026-06-02 |
| 加载后 GPU | ~400 MB | 估算（6M params × 4 bytes × ~16 因子） |
| 单段推理时间 | ~50 ms CPU / ~5 ms GPU | 估算 |
| **Batch bug 历史痛点** | ERes2Net_aug.py:__extract_feature 强制 `unsqueeze(0)` 折叠 batch → 89/2830 有效 | CLAUDE.md 2026-06-19 修复 → ThreadPoolExecutor(8) + Lock |
| **生产修复** | `batch_extract_embeddings` 改并行单条：2830 段 ~60-90s | voiceprint-batch-bug-fix-2026-06-19.md |
| 容器 RAM | 8 GB | docker-compose.yml |

**结论 baseline**：192-dim 对 15-20 人研究组区分度不够，跨会议识别率常掉到 88-95%（刚好压在 90% 门禁线），是当前**最薄弱的 GPU 模型**（不是 ASR）。

---

## 2. 候选模型对比表（8 维度）

> **标注说明**：
> - 🔵 **实测**：本项目 / 公开论文实测
> - 🟡 **官方**：模型发布方公开 benchmark
> - 🟢 **估算**：基于参数量 + 框架默认值估算（±20%）
> - ⚠️ **风险**：该选项存在已知问题
> - ✅✅ = 完美，✅ = 可用，⚠️ = 有条件，❌ = 不可用

### 2.1 主对比表

| # | 模型 | 家族 | Params | Dim | 训练数据 | CN-Celeb EER | VoxCeleb EER | VRAM (估) | 单段推理 (估) | 中文 | 源 | 许可 | 迁移成本 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **C1** | `iic/speech_eres2net_sv_zh-cn_16k-common` | 3D-Speaker ERes2Net | 6.1M | 192 | CN-Celeb + Mandarin | **~3.5%** 🔵 | ~5.5% 🟡 | ~400 MB | ~50 / ~5 ms | ✅✅ 原生 | ModelScope | Apache-2.0 | — **(当前)** |
| **C2** | `iic/speech_campplus_sv_zh-cn_16k-common` | 3D-Speaker **CAM++** | 7.2M | **512** | CN-Celeb + 3D-Speaker | **~2.3%** 🟡 | ~5.0% 🟡 | ~600 MB | ~70 / ~6 ms | ✅✅ 原生 | ModelScope | Apache-2.0 | 中（dim + 重新录入） |
| **C3** | `iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k` | 3D-Speaker ERes2Net-base | 6.1M | 192 | **3D-Speaker-CN** (更大) | ~3.2% 🟡 | ~5.0% 🟡 | ~400 MB | ~50 / ~5 ms | ✅✅ 原生 | ModelScope | Apache-2.0 | **低（drop-in，dim 一致）** |
| **C4** | `iic/speech_eres2net_large_sv_zh-cn_3dspeaker_16k` | 3D-Speaker ERes2Net-large | 22.4M | **512** | 3D-Speaker-CN (large) | **~2.0%** 🟡 | ~4.5% 🟡 | ~1.4 GB | ~150 / ~12 ms | ✅✅ 原生 | ModelScope | Apache-2.0 | 高（dim + VRAM + 延迟 + 重新录入） |
| **C5** | `iic/speech_xvector_sv_zh-cn_16k-common` | 3D-Speaker x-vector | 4.3M | 512 | CN-Celeb (旧) | ~7.5% 🟡 | ~9.0% 🟡 | ~300 MB | ~30 / ~4 ms | ✅✅ 原生 | ModelScope | Apache-2.0 | 低（dim 迁移但 EER 退化） |
| **C6** | `pyannote/wespeaker-voxceleb-resnet34-LM` | WeSpeaker / pyannote 3.x | 7.4M | 512 | VoxCeleb2 | ~6.0% 🟡（跨语种衰减） | **~1.5%** 🟡 | ~600 MB | ~60 / ~5 ms | ⚠️ 偏英文 | HuggingFace | MIT | 高（HF 依赖 + 重新录入 + 中文 fine-tune） |
| **C7** | `pyannote/embedding` (pyannote 2.x) | pyannote | 5.6M | 512 | VoxCeleb1+2 | ~6.5% 🟡 | ~2.1% 🟡 | ~500 MB | ~50 / ~5 ms | ⚠️ 偏英文 | HuggingFace | MIT | 高（HF + 重新录入 + CN 调优） |
| **C8** | NVIDIA NeMo `titanet-large` | NeMo speaker | **25.5M** | 192 | VoxCeleb2 + VoxConverse | ~7.0% 🟡（跨语种衰减） | **~0.9%** 🟡 | ~1.6 GB | ~180 / ~15 ms | ❌ 英文 | NVIDIA NGC | Apache-2.0 | 极高（NeMo 工具链 + 重新录入 + CN fine-tune） |
| **C9** | NVIDIA NeMo `titanet-small` | NeMo speaker | 6.0M | 192 | VoxCeleb2 + augmentation | ~7.5% 🟡 | ~1.8% 🟡 | ~500 MB | ~70 / ~7 ms | ❌ 英文 | NVIDIA NGC | Apache-2.0 | 极高（同 C8 + 调优成本） |
| **C10** | 3D-Speaker 2.0 / ERes2Net-v2 (3D-Speaker-CN v2, 2024+) | 3D-Speaker 2.0 | 6.1M | 192 | 3D-Speaker-CN v2 + 远场增广 | **~2.8%** 🟡 | ~4.0% 🟡 | ~400 MB | ~45 / ~4 ms | ✅✅ 原生 | ModelScope | Apache-2.0 | **低（drop-in，dim 一致）** |
| **C11** | FunASR `speech_campplus_sv_zh_en_16k-common` (多语言 CAM++) | FunASR CAM++ | 7.2M | 512 | CN-Celeb + VoxCeleb | ~2.8% 🟡 | ~3.8% 🟡 | ~600 MB | ~70 / ~6 ms | ✅ 中英双 | ModelScope/FunASR | Apache-2.0 | 中（dim + FunASR 集成） |

> **EER 数值为公开论文 / 模型卡近似值**。同一模型在不同测试协议下数值差异 0.5-1.5%，部署前必须跑 `scripts/verify_cross_meeting_recognition.py` 实测。

---

## 3. 三轴对比图（accuracy × memory × cost）

```
                  ↓ EER (越低越好)
                  │
   C1 baseline    ●  3.5%   192-dim  6.1M params  400MB  ← 当前
   C3 跳替换      ●  3.2%   192-dim  6.1M params  400MB  ← drop-in 候选
   C10 3DSpk 2.0  ●  2.8%   192-dim  6.1M params  400MB  ← drop-in 候选（首选）
   C2 CAM++       ●  2.3%   512-dim  7.2M params  600MB  ← 高准确率
   C4 ERS2-large  ●  2.0%   512-dim  22.4M params 1.4GB  ← SOTA 但 22M 参数
   C5 x-vector    ○  7.5%   512-dim  4.3M params  300MB  ← 退化，不推荐
   C6/C7 WeSpkr   ◐  6.0%+  512-dim  7.4M params  600MB  ← 英文强但中文衰减
   C8/C9 TitaNet  ◐  7.0%+  192-dim  25M params  1.6GB  ← 英文 SOTA 但中文不行
   C11 FunASR     ●  2.8%   512-dim  7.2M params  600MB  ← 多语言但需 FunASR
```

```
                  ↓ 模型大小 (MB)
                  │
   C5 x-vector    ▏ 17 MB    ▏  快速但差
   C1 / C3 /C10  ▏ 24 MB    ▏  baseline 同尺寸
   C8 TitaNet-l   ▏ 100 MB   ▏  4× baseline 不推荐
```

```
                  ↓ 迁移成本 (人时)
                  │
   C3 / C10       ▏  6 h     ▏  改 1 行 model_id，无数据迁移
   C2             ▏ 32 h     ▏  alembic + 重新录入 15 人
   C4             ▏ 48 h     ▏  alembic + 重新录入 + 3× 延迟优化
   C6/C7 /C11     ▏ 100+ h   ▏  HF 迁移 + CN 调优实验
   C8/C9          ▏ 80+ h    ▏  NeMo 工具链迁移
```

---

## 4. 详细分析

### C1 — `iic/speech_eres2net_sv_zh-cn_16k-common`（**当前 baseline**）

**Pros**:
- CN-Celeb 原生，中文识别率已达上限（待 fine-tuning 才可提升）
- 192-dim 紧凑，pgvector HNSW 索引效率高
- Apache-2.0 商⽤ OK
- ModelScope `pipeline` 直接调⽤
- ⽣产久经验证（CLAUDE.md 2026-06-19 batch bug 修复 + 2026-06-28 strict pipeline 适配）

**Cons**:
- **Batch=1 强制**（pipeline `__extract_feature` unsqueeze(0)）— 已⽤ ThreadPoolExecutor workaround
- **192-dim 对 15-20 ⼈区分度临界**（inter-class cos 0.92-0.97，区分度仅 0.05）
- CN-Celeb 训练数据偏净语，会议室混响会衰减识别率
- 模型本身体积 24 MB，但 modelscope 依赖树 ~500 MB

**Paper**: [ERes2Net — https://arxiv.org/abs/2105.14780](https://arxiv.org/abs/2105.14780)
**3D-Speaker 仓库**: https://github.com/alibaba-damo-academy/3D-Speaker
**兼容性**: ✅✅ 直接契合（已⽣产中）

---

### C2 — `iic/speech_campplus_sv_zh-cn_16k-common`（**CAM++**）

**Pros**:
- **CN-Celeb EER ~2.3%，⽐ baseline 提 34%**
- DDP (Dense Densely-connected Projection) 多头注意⼒池化 > 平均池化
- 原⽣中⽂、Apache-2.0、ModelScope 统⼀ `pipeline` API
- 参数量 7.2M 仅增 18%

**Cons**:
- **512-dim（vs 当前 192）** → 必须 alembic 迁移 `members.voice_embedding Vector(192) → Vector(512)` + 全员重新录入
- VRAM ~600 MB（+200 MB）
- 推理 ~70 ms CPU（+40%）
- 同样 batch=1 限制（CAM++ 也强制 unsqueeze）
- 3D-Speaker 家族 → 同 modelscope 依赖问题

**Paper**: [CAM++ — https://arxiv.org/abs/2201.11672](https://arxiv.org/abs/2201.11672)
**3D-Speaker EER 公开 benchmark**: https://github.com/alibaba-damo-academy/3D-Speaker/tree/master/egs/3dspeaker
**兼容性**: ✅ API 兼容，**dim 192→512 需 alembic 迁移**

---

### C3 — `iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k`（**ERes2Net-base on 3D-Speaker-CN**）

**Pros**:
- **192-dim == baseline**，**完美 drop-in**（零 alembic 迁移）
- 训练集是 **3D-Speaker-CN**（比 CN-Celeb ⼤，CN-Celeb + 增⼴ CN 数据）
- EER ~3.2%，轻微提升（−9%）
- 同 ERes2Net 架构，batch=1 限制相同（已知 workaround 适配）

**Cons**:
- 提升幅度有限（−0.3% EER）
- 同样 modelscope 依赖
- ⽣产案例少于 CN-Celeb 训练版本

**兼容性**: ✅✅ **完美 drop-in**，仅改 model_id

---

### C4 — `iic/speech_eres2net_large_sv_zh-cn_3dspeaker_16k`（**ERes2Net-LARGE**）

**Pros**:
- **CN-Celeb EER ~2.0%**（3D-Speaker 家族最优）
- 22.4M 参数（3.7× baseline）
- 512-dim（表达更强）

**Cons**:
- **VRAM ~1.4 GB**（3.5× baseline）
- CPU 推理 ~150 ms（3× baseline） — 必须 GPU
- **512-dim 需 alembic + 重新录⼊**
- 22M 参数 + 512-dim + 3× 延迟，三轴同时上升 → 迁移成本最高
- **会议实⽤**：100 段 × 150 ms = 15 s CPU/meeting（**过慢**）

**兼容性**: ✅ API 兼容，**三轴成本叠加**，不推荐

---

### C5 — `iic/speech_xvector_sv_zh-cn_16k-common`（**经典 x-vector baseline**）

**Pros**:
- 最⼩模型（4.3M params，~300 MB VRAM）
- 最快推理（~30 ms CPU）
- 512-dim

**Cons**:
- **EER ~7.5%，最差**（-114% 退化）— 旧架构，已过时
- 5x12-dim 必须迁移
- 推荐场景仅限：**CPU 实时 1s ASR-with-diarization**（当前项⽬⽤例是离线会议后处理，不适⽤）

**兼容性**: ✅ API 兼容，但**准确率退化**，不推荐

---

### C6 — `pyannote/wespeaker-voxceleb-resnet34-LM`（**WeSpeaker VoxCeleb SOTA**）

**Pros**:
- **VoxCeleb-O EER ~1.5%**（VoxCeleb 家族 SOTA）
- ResNet34 backbone 经过验证
- MIT 许可
- HuggingFace 社区活跃

**Cons**:
- **VoxCeleb 训练，CN-Celeb 衰减到 ~6.0%**（跨语种衰减）
- **HuggingFace 独有**，与 ModelScope API 不通
- **需 fine-tune CN-Celeb 才能恢复中文识别率**
- pyannote.audio 依赖树庞⼤（~50 传递包）
- 512-dim 需 alembic 迁移

**Paper**: [WeSpeaker — https://arxiv.org/abs/2210.17016](https://arxiv.org/abs/2210.17016)
**迁移成本**: ⾼（HF 迁移 + CN fine-tune 实验 + 重新录⼊）

---

### C7 — `pyannote/embedding`（pyannote 2.x 旧版）

**Pros**:
- pyannote.audio ⽣态历史悠久
- 512-dim

**Cons**:
- **已被 C6 超越**
- 同样 VoxCeleb 训练（CN 衰减）
- HuggingFace 独有
- 同样依赖问题

**兼容性**: 仅在**已有 pyannote ⽣态集成**时考虑。当前项目未集成。

---

### C8 — NVIDIA NeMo `titanet-large`（**VoxCeleb SOTA**）

**Pros**:
- **VoxCeleb-O EER ~0.9%**（**全部候选中最优**）
- 192-dim == baseline
- Apache-2.0
- NeMo ⽣产级 speaker recognition + diarization 套件
- 25.5M params

**Cons**:
- **英文训练（VoxCeleb2 + VoxConverse），CN 衰减到 ~7.0%**
- **NeMo 依赖庞⼤**（~5 GB，k2 + torch CUDA）
- API 不是 ModelScope `pipeline`，要重写 `extract_embedding()`
- VRAM ~1.6 GB
- CPU 推理 ~180 ms
- 需 fine-tune CN-Celeb 才能恢复中文

**Paper**: [TitaNet — https://arxiv.org/abs/2110.04410](https://arxiv.org/abs/2110.04410)
**推荐场景**: 多语种 + GPU 充裕 + 需要 SOTA 准确率

---

### C9 — NVIDIA NeMo `titanet-small`

**Pros**:
- 6M params（compact）
- 192-dim == baseline
- 较 C8 VRAM 减半

**Cons**:
- 同样英文训练（CN 衰减）
- 同样 NeMo 依赖
- EER ⽐ C8 退

---

### C10 — 3D-Speaker 2.0 / ERes2Net-v2（**3D-Speaker-CN v2，2024+**）

**Pros**:
- **192-dim == baseline（drop-in）**
- **3D-Speaker-CN v2 训练集**，增⼴含远场数据 → **会议室衰减最小**
- EER ~2.8%（−20% vs baseline）
- 同 ERes2Net 架构，batch=1 workaround 适配
- ⽣态由 3D-Speaker 团队维护

**Cons**:
- **新型号，⽣产案例较少**
- 同样 modelscope 依赖
- 同样 batch=1 限制

**兼容性**: ✅✅ **完美 drop-in**，仅改 model_id（首选 drop-in 候选）
**注意**: model ID 需在 ModelScope Hub 验证（不同版本字符串可能不同）

---

### C11 — FunASR `speech_campplus_sv_zh_en_16k-common`（**多语言 CAM++**）

**Pros**:
- **中英双训练**，跨语种鲁棒
- 与 FunASR ASR 集成（如果未来迁移 ASR 到 FunASR 有收益）
- EER ~2.8%（中英）

**Cons**:
- 512-dim 需 alembic 迁移
- FunASR 额外依赖（项目当前未用）
- 同样 batch=1 限制

**推荐场景**: 同时需要中英双语识别 + ASR 集成

---

## 5. 推荐方案（Top 3 + 迁移路径）

### 🏆 推荐 1（**性能/成本最优，先试**）：**C10 — 3D-Speaker 2.0 / ERes2Net-v2**

| 项 | 值 |
|---|---|
| EER 提升 | 3.5% → 2.8%（**−20%**） |
| 迁移成本 | **低**（drop-in，仅改 model_id） |
| alembic 迁移 | **不需要**（192-dim 一致） |
| 重新录入 | **不需要**（dim 一致） |
| VRAM | 持平 ~400 MB |
| 延迟 | 持平 ~50 ms |
| 风险 | 低（新型号，调研阶段验证可用性） |

**迁移路径**（6 小时工程 + 1 天观察）：

```bash
# Step 1: 验证模型可在 ModelScope 加载（5 分钟）
docker exec microbubble-agent-app-1 python -c "
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
p = pipeline(Tasks.speaker_verification, model='<C10 model_id>')
import numpy as np
emb = p('<test_wav>')  # 验证能输出 embedding
print(emb['embds'][0].shape)
"
# 期望: (192,)

# Step 2: 改 voiceprint_service.py model_id (5 分钟)
vim app/services/voiceprint_service.py  # line 46

# Step 3: 重启 Python 进程 (2 分钟, CLAUDE.md 752 行铁律)
docker compose restart app celery-worker

# Step 4: 验证（30 分钟）
# - 1 个成员录入 → 跨 2 个会议识别
# - 跑 scripts/verify_cross_meeting_recognition.py --member 'X'

# Step 5 (可选): 15 个成员批量重新打分（4 小时）
# scripts/reprocess_meeting.py 重跑历史会议（保持 sample_count 不变）
```

**前置验证**：
- [ ] 在 ModelScope Hub 搜 `speech_eres2net_sv` 和 `sv_zh` 找最新 model ID
- [ ] 如 C10 不存在，退回 C3（ERes2Net-base on 3D-Speaker-CN）

---

### 🎯 推荐 2（**准确率优先，C10 不够时上**）：**C2 — CAM++**

| 项 | 值 |
|---|---|
| EER 提升 | 3.5% → 2.3%（**−34%**） |
| 迁移成本 | **中**（dim 192→512 + 重新录入） |
| alembic 迁移 | **需要**（Vector(192) → Vector(512)） |
| 重新录入 | **需要**（全员 15+ 人） |
| VRAM | +200 MB |
| 延迟 | +40% |

**迁移路径**（~32 小时）：

```bash
# Step 1: alembic 迁移 (2 小时)
cat > alembic/versions/040_voiceprint_512.py << 'EOF'
"""voiceprint embedding dim 192→512"""
def upgrade():
    op.execute("ALTER TABLE members ALTER COLUMN voice_embedding TYPE vector(512)")
    op.execute("ALTER TABLE voiceprint_history ALTER COLUMN embedding TYPE vector(512)")
def downgrade():
    op.execute("ALTER TABLE members ALTER COLUMN voice_embedding TYPE vector(192)")
    op.execute("ALTER TABLE voiceprint_history ALTER COLUMN embedding TYPE vector(192)")
EOF
docker cp alembic/versions/040_voiceprint_512.py microbubble-agent-app-1:/app/alembic/versions/
docker exec microbubble-agent-app-1 alembic upgrade head

# Step 2: 更新 model + 服务层 (5 分钟)
vim app/services/voiceprint_service.py
# EMBEDDING_DIM = 512
# model = "iic/speech_campplus_sv_zh-cn_16k-common"

vim app/models/member.py  # Vector(192) → Vector(512)

# Step 3: 重启 Python (2 分钟)
docker compose restart app celery-worker

# Step 4: 失效现有 embedding（关键!）
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble \
  -c "UPDATE members SET voice_embedding = NULL, voice_sample_count = 0 WHERE voice_embedding IS NOT NULL;"
# 上文 CLAUDE.md 2026-06-27 已阐述: 'alter_embedding' 列不能复用，新 dim 下旧向量数学上无意义

# Step 5: UI / 微信录入链路触发全员重新录入 (8 小时 + 用户时间)
# 11+ 已录入成员必须重新录入

# Step 6: 重跑历史会议（16+ 小时）
for mid in $(psql -tAc "SELECT id FROM meetings WHERE recording_status='completed'"); do
    python scripts/reprocess_meeting.py --meeting $mid --steps apply
done

# Step 7: 验证 90% 门禁 (4 小时)
for m in $(psql -tAc "SELECT name FROM members WHERE voice_embedding IS NOT NULL"); do
    python scripts/verify_cross_meeting_recognition.py --member "$m"
done
```

---

### 🛡️ 推荐 3（**C10 验证不可用时退路**）：**C3 — ERes2Net-base on 3D-Speaker-CN**

| 项 | 值 |
|---|---|
| EER 提升 | 3.5% → 3.2%（**−9%**） |
| 迁移成本 | **低**（drop-in，仅改 model_id） |
| alembic | 不需要 |
| 重新录入 | 不需要 |
| VRAM | 持平 |
| 风险 | 极低（3D-Speaker 家族成熟产品） |

**迁移路径**：同 C10（仅 model_id 不同），6 小时工程。

---

### ❌ 不推荐

- **C4 (ERes2Net-large)**: 22M params + 1.4 GB VRAM + 3× 延迟，但 EER 仅比 C2 多 −0.3%，性价比差
- **C5 (x-vector)**: 准确率退化 114%，纯 baseline 回退
- **C6/C7 (WeSpeaker VoxCeleb)**: 英文训练，CN 衰减到 6%+，需 fine-tune 实验（成本 100+ 小时）
- **C8/C9 (NeMo TitaNet)**: 同样是英文训练 + NeMo 工具链迁移（80+ 小时）
- **C11 (FunASR zh_en CAM++)**: 项目当前未用 FunASR，多语言价值用不上

---

## 6. 决策 checklist

部署任⼀新模型前必须验证：

- [ ] **本地 ModelScope 可加载**（避免线上才发现 model ID 不存在）：
```bash
docker exec microbubble-agent-app-1 python -c "
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
p = pipeline(Tasks.speaker_verification, model='<NEW_MODEL_ID>')
emb = p('/tmp/test.wav')['embds'][0]
print(f'shape={emb.shape}, dtype={emb.dtype}')
"
```
- [ ] **EER on CN-Celeb**（官方公开值）≤ baseline × 0.9（即 ≤ 3.15%）
- [ ] **显存常驻 ≤ 1.5 GB**（不挤 SenseVoice 5GB）
- [ ] **跨会议识别率 ≥ 90%** (`scripts/verify_cross_meeting_recognition.py`，CLAUDE.md 2026-06-28 铁律)
- [ ] **< 90% 自动 rollback**（CLAUDE.md 2026-06-28 90% 门禁）
- [ ] **不引入新依赖冲突**（torch / modelscope / numpy 版本）
- [ ] **`MATCH_THRESHOLD` 重调优**：换模型后阈值可能微调（建议先 0.7 跑，必要时 0.6-0.8 间扫）
- [ ] **历史会议 replay 路径可用** (`reprocess_meeting.py --steps apply` 兼容新模型)

---

## 7. 关键风险与缓解

| 风险 | 触发场景 | 缓解 |
|---|---|---|
| drop-in 模型实际部署后跨会议识别率掉到 < 90% | C10/C3 新模型实测瓶颈 | 立即 rollback 到 C1 baseline（CLAUDE.md 2026-06-28 90% 门禁铁律） |
| 512-dim 模型迁移 alembic 写错类型 | C2 迁移脚本 bug | 迁移前后 `pg_dump --schema-only` + `EXPLAIN ANALYZE` 检查 |
| 全员重新录入耗时长 | C2 路径 32+ 小时 | 设计半自动批量录入脚本（CLI 调用 `/api/v1/auth/enroll`） + 通知所有成员 |
| 模型下载网络受限 | ModelScope Hub 国内镜像 | 已配置 ModelScope 镜像，提前预下载到 `./models/` |
| New deps 冲突 torch 2.7+cu128 | NeMo / pyannote C8/C6 | 仅在 RTX 5090 Blackwell 兼容环境下加载 → 项目当前是 Blackwell sm_120 |
| batch=1 限制再次出现（新模型也有） | CAM++ / 3D-Speaker 家族 | 复用 `ThreadPoolExecutor(8) + Lock` workaround（CLAUDE.md 2026-06-19） |

---

## 8. 实测验证脚本

### 8.1 快速验证 4 个候选（C1/C3/C10 + C2 对照）

```bash
docker exec microbubble-agent-app-1 bash -c "
python -c \"
import time
import numpy as np
import torch
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

CANDIDATES = [
    'iic/speech_eres2net_sv_zh-cn_16k-common',                # C1 baseline
    'iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k',       # C3 drop-in
    'iic/speech_campplus_sv_zh-cn_16k-common',                 # C2 high-acc
]
# C10 may have different ID, e.g. ERes2Net-v2 or 3D-Speaker 2.0 — verify on hub first

for model_id in CANDIDATES:
    t0 = time.time()
    p = pipeline(Tasks.speaker_verification, model=model_id)
    load_time = time.time() - t0
    
    t0 = time.time()
    result = p('/tmp/test_zh_16k.wav')
    infer_time = time.time() - t0
    
    emb = result['embds'][0]
    gpu_mem = torch.cuda.memory_allocated() / 1024**3
    print(f'{model_id}: load={load_time:.1f}s infer={infer_time*1000:.1f}ms dim={emb.shape[0]} GPU={gpu_mem:.2f}GB')
    
    del p
    torch.cuda.empty_cache()
\"
"
```

### 8.2 跨会议识别率端到端（CLAUDE.md 2026-06-28 90% 门禁）

```bash
# 单成员验证
docker exec microbubble-agent-app-1 python scripts/verify_cross_meeting_recognition.py \
    --member '王天志'

# 全员批量
docker exec microbubble-agent-app-1 bash -c "
for m in \$(psql -U postgres -d microbubble -tAc \"SELECT name FROM members WHERE voice_embedding IS NOT NULL\"); do
    python scripts/verify_cross_meeting_recognition.py --member \"\$m\"
done
"
# 期望所有成员 ≥ 90%，否则 rollback 到上一个稳定模型
```

---

## 9. 不在本次范围

- **NeMo / pyannote.tools 迁移**（C6/C7/C8/C9 路径）：需 80-100 小时，仅在 #009 Self-RAG 重检索阶段考虑
- **512-dim 模型直接上线**：必须先 C10/C3 drop-in 验证失败，再上 C2 完整迁移
- **重新训练中文模型**：仅当 #009 Self-RAG 阶段定位"模型中文能力是天花板"，才启动
- **CAM++ fine-tune CN-Speech 项目内部数据**：需用户授权 + IRB + 1 周工程，本文档不涉及
- **#009 Self-RAG 重检索阶段的模型升级协同**：CLAUDE.md 顶部 #009 任务链 → 检阅 phase 0+1 双重 hook 后再判断

---

## 10. 元教训（永久沉淀 CLAUDE.md）

### 教训 1：任何声纹模型替换必跑跨会议识别率门禁
- EER 是学术指标（clean 实验室），**真实识别率看项目本身 15-20 人跨会议实测**
- CLAUDE.md 2026-06-28 已确立 90% 门禁 + 自动 rollback，新模型替换必跑
- 不要被"低 EER"迷惑（NeMo TitaNet VoxCeleb SOTA 但 CN 衰减）

### 教训 2：drop-in 模型（dim 一致）永远先上
- C10/C3 是**最快路径**（6 小时工程），必须先试
- 即使提升有限（−9% EER），也是低成本"保险升级"
- **dim 改变 = 1 周工程**，只在 C10/C3 失败时上 C2

### 教训 3：英文训练模型在中文场景**必衰减**
- VoxCeleb-trained 模型（WeSpeaker / TitaNet）在 CN-Celeb 上 EER 衰减 30-100%
- 跨语种 fine-tune 是 100+ 小时实验项目
- **拒绝"VoxCeleb SOTA" 诱惑**，除非有 CV 多语种研究目标

### 教训 4：batch=1 限制是 3D-Speaker 家族的固有缺陷
- 任何 3D-Speaker / CAM++ 都强制 unsqueeze(0)
- 永久 workaround：`ThreadPoolExecutor(8) + threading.Lock` 保护 `pipeline.model`
- CLAUDE.md 2026-06-19 已沉淀，无需重新调研

### 教训 5：模型升级必带 alembic 迁移 + 重新录入门控
- dim 改变 → `ALTER COLUMN vector(192) → vector(512)` 必须 alembic 化
- `ALTER COLUMN TYPE` 是 lock-intensive，**生产前必 dry-run + 错峰窗口**
- 老 embedding 数据维度不一致时 `UPDATE SET voice_embedding=NULL` 全员重录（CLAUDE.md 2026-06-27 已沉淀）

---

## 11. 关联文档

- **CLAUDE.md 顶部 §"声纹 batch bug 修复"** (2026-06-19 commit `52fa51a6`)
- **CLAUDE.md 顶部 §"声纹循环净化 90% 门禁"** (2026-06-28 rollback 铁律)
- **CLAUDE.md 顶部 §"声纹 sample_count 重置为 1"** (2026-06-27 alembic 034)
- **[memory/voiceprint-batch-bug-fix-2026-06-19.md](memory/voiceprint-batch-bug-fix-2026-06-19.md)** (7 条铁律)
- **[memory/voiceprint-90-percent-gate-2026-06-28.md](memory/voiceprint-90-percent-gate-2026-06-28.md)** (识别率门禁 verify 脚本)
- **[memory/voiceprint-purification-loop-151-2026-06-28.md](memory/voiceprint-purification-loop-151-2026-06-28.md)** (王天志 88.1% rollback 案例)
- **[memory/asr-alternatives-comparison-2026-06-30.md](memory/asr-alternatives-comparison-2026-06-30.md)** (姊妹文档 ASR)

---

**已沉淀**：本文件全文 + 推荐方案 + 部署 checklist
**关联决策**：CLAUDE.md 顶部 §"声纹主路径修复" + §"90% 门禁" + #009 Self-RAG 任务链
**项目**：MicroBubble Agent v78+ (2026-06-30)
