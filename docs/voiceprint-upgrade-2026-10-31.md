# 声纹系统换代调研与路线（2026-10-31）

> 起因：主指挥「去社区看一下与咱们这个相似的功能的成熟的项目、模型等等，能直接区分说话人的，
> 更好的声纹模型等等吧，看看咱们这个声纹会议能不能更新换代一轮」。
>
> **本文只写经核验的结论**。四路并行调研（说话人嵌入新代际 / 端到端 diarization 框架 /
> 重叠分离与 TSE / 评测方法学）＋ 本机在生产容器里的实测。
> 凡无法核实的都标了「⚠ 未核实」，不写"据说"。

---

## 0. 一句话结论

**先修 enrollment（数据），再换范式，最后才换模型 —— 顺序反了就是白做。**

我们的失败模式是「**逐段绝对匹配**」失败（同人跨场 0.50 vs 异人互距 0.25–0.40），
而社区在同一批中文会议、同样短的窗上拿到 **DER 10.30%**，靠的是
「**会议内先聚类 → 用簇质心/turn 级聚合 → 再命名**」。
⇒ 换代的**主体不是模型，是把「逐段最近邻 + 簇级投票」换成「diarization 聚类 + 簇质心命名」**。
**但聚类要换范式，就必须先有更好的嵌入** ⇒ 两者是配套的，不是二选一。

> ⚠️ **2026-10-31 本机实测又往前推了一步（§3.4）**：我们**每个成员的质心本身是坏的**
> —— 它是「若干个 1.5–8 秒片段的均值」（`voice_sample_count` 是段数不是秒数，
> 录入 API 的 docstring 明写「上传 3-5 秒语音」且**样本不留档**）。
> 实测：**同一人（贾琦）自比对只有 0.723，而异人（朱彤→王天志）是 0.685 —— 异人比同人还近**；
> 簇质心聚合只把距离收紧 7%（0.733→0.685）。
> ⇒ **命名是「簇质心 ↔ 成员质心」的比较；成员质心不对，比较就没有意义。**
> ⇒ **Phase 0 必须是「重建 enrollment」，不是「换模型」。**

---

## 1. 我们的实测基线（本项目的硬事实，不是论文数字）

| # | 事实 | 出处 |
|---|---|---|
| ① | 现役模型 `iic/speech_eres2net_sv_zh-cn_16k-common`（3D-Speaker ERes2Net，**192 维**），`HalfVector(192)` 存储 | `app/services/voiceprint_service.py:29` |
| ② | **跨场同一人距离基线 ≈ 0.50**（不是 0.20；0.10–0.19 是**同环境**留出） | 类 20.243 |
| ③ | 短插话型学生质心互距 **0.25–0.40**（比同人基线还近 ⇒ embedding 不可分） | 类 20.243 / 20.245 |
| ④ | 8 场 9336 段体检 ⇒ **一个声纹都建不出** | memory #54 |
| ⑤ | 判据是**逐段最近邻**（`MATCH_THRESHOLD=0.65`）+ 簇级投票（`vote_with_quality_gates`），**不是**端到端 diarization | `voiceprint_voting.py:285` |
| ⑥ | 重叠说话**完全不处理** | — |
| ⑦ | **成员库 36 人里只有 13 人有向量、12 人标了采样数、9 人是 anchor** | 2026-10-31 实测 |
| ⑧ | **生产路径的嵌入是串行的**：`batch_extract_embeddings` 用 ThreadPoolExecutor + **全局锁**包住模型调用 ⇒ 实测 **0.900 s/段** | 本轮实测 |

**新测（本轮，会议 263 外部讲座）**：
- 到王天志质心的距离**中位 0.732**，而 `MATCH_THRESHOLD=0.65` ⇒
  **那 1420 段根本不是靠阈值命中的，是簇级投票兜底**（类 20.249 ⑦ 的又一例）。
- **朱彤院士与王天志在声学上分不开**（簇内距离重叠）⇒
  一场外部讲座的**报告本体 1257 段被整体安到王天志名下**。
  ⇒ **这正是「逐段绝对匹配 + 兜底」的必然后果**，与模型强弱无关。

---

## 2. 社区调研结论

### 2.1 说话人嵌入：新代际只有一条路可走

| 模型 | 维度 | 官方 Vox1-O EER | **短时长(2s/3s)** | 中文 | 许可 | 结论 |
|---|---|---|---|---|---|---|
| **ERes2Net**（现役） | 192 | 0.84% | 3.28% / 1.89% | ✅ 200k | Apache-2.0 | 基准 |
| **ERes2NetV2** ★ | **192** | 0.61% | **1.48% / 0.98%（−55%/−48%）** | ✅ 200k | Apache-2.0 | **首选** |
| ERes2NetV2_w24s4ep4 | 192 | — | 同族 | ✅ | Apache-2.0 | CN-Celeb 2.31%（更好，但参数量 ⚠ 未核实） |
| CAM++ | 192 | 0.65% | ⚠ 无短时长专项数据 | ✅ | Apache-2.0 | 最轻（RTF 0.013），但短段无证据 |
| ECAPA-TDNN | 192 | 0.82% | 1.95% | ❌ 英文为主 | Apache-2.0 | 中文差（CN-Celeb 8.01%） |
| WavLM-SV / UniSpeech-SAT | 768 | 0.617–0.84% | ⚠ | ❌ | ⚠ MIT | 维度变了 ⇒ 质心全废 |
| RDINO | 192 | Cross-Device **20.41%** | ⚠ | ✅ | Apache-2.0 | **最差** |
| Resemblyzer | 256 | 0.83% | ❌ | ❌ | MIT | 2019 年后未更新，**已过时** |

- **`iic/speech_eres2netv2_sv_zh-cn_16k-common`** —— 同 3D-Speaker 家族、**同 192 维**
  ⇒ **pgvector `HalfVector(192)` 表结构不用改**；官方 `yesOrno_thr=0.360`（相似度）
  ⇒ 距离阈值 0.64，**但阈值必须在我们自己的数据上重标**（我们自己的 0.50 基线
  远高于官方 0.635 ⇒ 这正是「建不出声纹」的结构性原因之一）。
- **CAMoE 查无实据**（ModelScope 4639 个 speech_* 模型全量枚举 + 两个 GitHub 仓 + OpenAlex
  三路检索均无）⇒ 勿据传闻立项。**ClearerVoice-Studio 只有降噪/分离/超分/TSE，没有 SV 模型**
  ⇒ 它的价值在**前端降噪**，不是嵌入。

### 2.2 端到端 diarization 框架：只有一个能进主镜像

| 方案 | 中文 DER | 重叠 | 能直接绑定已有声纹库 | 依赖风险 | 许可 | 结论 |
|---|---|---|---|---|---|---|
| **3D-Speaker 自带 recipe** | AISHELL-4 **10.30%**（含重叠）/ 23.04%（不含）<br>AliMeeting 19.73% | ✅(需 HF token) | ✅ **192 维 ERes2Net＝我方同款 ⇒ 30+ 质心零重录** | recipe 钉 `numpy==1.23.5`/`numba==0.56.2`/`datasets==3.1.0` ⇒ **都要放宽**；`pyannote.audio` 未钉会拉 4.x | Apache-2.0 | **唯一推荐** |
| pyannote.audio 3.3.2 | AISHELL-4 12.2% / AliMeeting far **24.4%（最差）**<br>Mandarin **19.8%（六模型最差）** | ✅ | ✅ | core 5.0 numpy>=1.10 ✅；引 speechbrain/lightning | MIT / 模型 CC-BY-4.0 | 次选，中文最弱 |
| pyannote.audio 4.0.7 | 同上 | ✅ | ✅ | 🔴 `pyannote.core>=6.1` ⇒ **numpy>=2.0** ⇒ 撞死我们 `numpy==1.26.2` | MIT | **排除** |
| NeMo Sortformer v1 | Mandarin 13.1% | ✅ | 需自取 embedding | ⚠ Python 3.12+ / lightning 钉 2.4.0 | 🔴 **CC-BY-NC-4.0 禁商用** | **排除** |
| NeMo Sortformer v2 / Nemotron-3 | Mandarin **9.2%** | ✅ | 需自取 embedding | 同上 | v2 商用可 / Nemotron-3 openmdw-1.1 可商用 | 可用但重（比 pyannote 慢 4–10×） |
| DiariZen | AISHELL-4 **10.1%** / AliMeeting **10.8%**（中文开源最优） | ✅ | ❌ **WavLM 空间 ⇒ 30+ 质心全废** | 中 | MIT | 中文最好但**要重录所有人** |
| FunASR `--spk` | — | ❌ | ⚠ 匿名簇 | ✅ 已在依赖内 | MIT | 可作基线 |
| sherpa-onnx 2.0.1 | — | ⚠ | ❌ 不吐 embedding | ✅ 单依赖零冲突 | ⚠ **端到端 diarization 模型禁商用** | 排除 |
| WhisperX 3.8.6 | — | ✅ | ✅ | 🔴 numpy>=2.1.0 | BSD-2 | **排除** |

- **AlSense 查无实据**（GitHub 全库 + ModelScope + arXiv + 两份最全清单均无）⇒
  推测是 SenseVoice/阿里 Speech Lab 的记忆混淆，**勿据此立项**。
- 3D-Speaker recipe 的关键机制：**FSMN-VAD → 1.5s 滑窗/0.75s shift(50%重叠) →
  CAM++(192d) → spectral 聚类（pval=0.012, min_cluster_size=4, `mer_cos=0.8` **作用在簇中心**）**
  ⇒ **它不是逐段最近邻，是聚类 ⇒ 这正是我们要换的范式**。
- **CPU RTF 0.03**（pyannote 0.19 / DiariZen 0.3）⇒ 不增加 GPU 压力，符合 2026-10-26「按需启动」铁律。

### 2.3 重叠分离与 TSE：对我们的边际收益低

- **重叠分离**（TF-GridNet / MossFormer2 / TIGER）：社区基准都是重叠语音任务，
  而我们**轮流发言为主** ⇒ 收益小；且要跑两遍音频。
  ⚠️ 但 **3D-Speaker README 自己写明**：「端到端 diarization 的优势是能处理多人同时说话，
  分段-聚类在训练/测试不匹配、说话人过多、长音频场景表现不佳」
  ⇒ 若将来出现真重叠场景再上。
- **TSE（目标说话人抽取）**：WeSep 是**训练包**（v0.1 明写 production not yet supported）；
  X-TF-GridNet **仓库无 license**（商用风险）⇒ 工具链不成熟。
  ⇒ **更关键的是前置条件**：TSE 需要每人一段**长而干净**的 enrollment，
  而我们现在的质心是**短段算出来的**（本身就是坏的）⇒ **拿不到长 enrollment 时，TSE 只是换个网络继续用坏质心**。
- **说话人条件 VAD**：只改「切多碎」，**不改变短段 embedding 不可分**这一事实 ⇒ 边际收益低。

### 2.4 评测方法学：**社区给不了我们的核心指标 —— 但给了两把关键的钥匙**

> ⚠️ 本节同时**订正了本仓此前引用的三处社区说法**（都是我们自己在文档里沿用的）：

| 此前沿用的说法 | 实测真相 |
|---|---|
| 「VoxCeleb1-H/E = clean/noisy 两档」 | ❌ **错**。H/E 是**难度集**（hard / extended），不是干净/噪声。真三档 = **Vox1-O original（40人/37,611对）/ Vox1-E extended（1251人/579,818对）/ Vox1-H hard（1251人/550,894对）**（arXiv:2406.02167 Table 2） |
| 「NIST 的 C=0.01 归一化常数」 | ❌ **错**。SRE24 的成本函数里 0.01 是**先验 PTarget**（SRE24 取 {0.01, 0.005} 两档），不是归一化常数 |
| 「有 NIST 的 3 秒短语音条件」 | ❌ **不存在**。SRE21 最短测试 10s、SRE24 最短 5s ⇒ **我们的 1.5–3s 在 NIST 里没有对应标准条件**（最新是 **SRE24**） |

#### ⭐ 钥匙一：**DER 测不出「认错人」** ⇒ 我们的核心指标社区确实是空白
`pyannote.metrics` 源码实测（`identification.py:60` + `diarization.py:134`）：
先做**匈牙利一对一匹配**再算分 ⇒ **把两个正确的簇换个名字，DER 一点不变**。
⇒ **DER 永远只测「切错段」，测不出「切对了但叫错名字」。**
⇒ 我们的「重标 / 改名」工作**必须另建指标** —— 社区在 closed-set 侧没有现成的
（只有开放集 OSI 那侧的 DIR@FAR）。
⇒ ⚠️ 而**社区也没有「验证集标注错误」的评测协议** —— 所有标签噪声论文针对的都是
*训练*标签 ⇒ **这是空白，也是我们可以原创的地方**。

#### ⭐ 钥匙二：**社区对长音频/短语音的标准解法，正是我们 Phase 0 要做的事**
`arXiv:2211.00815` 原文实测：
> "**We average all the embeddings belonging to each enrollment speaker to get the final speaker embedding.**"
> "Because there are many short utterances less than 2s in CN-Celeb dataset, we first
> **concatenate the short utterances from the same genre and same speaker to make them longer than 5s.**"

⇒ ① 长音频社区做法是**池化 embedding**（不是池化分数）⇒ 直接支持「每成员一个池化质心」；
② 短语音社区解法是**把同一说话人的短段拼接变长** ⇒ **这就是我们 Phase 0**，
而且要同时试「拼接」与「整段嵌入」两种变体（我们的 Phase 0 brief 里已写明）。

#### 我们的 7 个坑 ↔ 社区标准判据（逐条对照）

| 我们的坑 | 社区标准做法 | 出处 |
|---|---|---|
| 拍脑袋定阈值 | 阈值**从分数分布导出**，且**报多个操作点**（FRR@FAR=0.5% / FAR@FRR=5% / DIR@FAR），不报单点 | VoxWatch `arXiv:2307.00169`；⚠ `arXiv:2606.21584` 证明 in-domain EER 0.21% 可对应跨域 HTER 39.5% ⇒ **EER 单独报 = 骗自己** |
| 验证集本身标错 | **双人独立标注 + 仲裁 + 报 IAA**（κ/α/γ），且**按段长分层** | Seshat `arXiv:2003.01472`；Mathet γ `10.1162/coli_a_00227` |
| 只报认回率 | **coverage–selective-risk 曲线**（coverage ρ=接受率，selective risk=错误率/接受率） | Geifman `arXiv:1705.08500` |
| 验证粒度≠生产粒度 | 评测粒度必须=部署粒度；短语音有标准集 **Vox1-S（0.5–2s）/ Vox1-M** | `arXiv:2401.08342` |
| 分母含取不到样本的段 | 分母 = 实际参与计算的样本（类 20.250 已修） | — |
| 无跨场基线 | 用**分布 + bootstrap CI**（非参数 two-sample bootstrap），不报单点 | NIST IR 7722 `10.6028/NIST.IR.7722` |
| 候选池变化漂移判据 | **VoxWatch 的 "false-alarm problem"**：池从 50 人涨到 500 人，FAR@FRR=5% 从 2.4% → **16.1%（近 7 倍）** ⇒ **池变大 ⇒ margin 阈值必须重标定，且用冻结的验证集标** | VoxWatch §6.1；Sculley NeurIPS'15 §3/§7（**冻结 + 版本化输入**） |

> ⭐ **最后一条正面解释了我们「两次重跑差 787 段 = 候选池变了」的根因** ——
> 社区的诊断（Sculley：不稳定数据依赖 ⇒ 冻结并版本化）与我们的实测完全一致。

#### 短语音的社区量级（为什么说这是「信号不足」区间）
- 3D-Speaker ERes2NetV2（`arXiv:2406.02167`）Vox1-O：**全长 0.61% / 3s 0.98% / 2s 1.48%**
- DAME（`arXiv:2601.13999`）Vox1-O：**1s 3.89%**；VOiCES 远场 1s **17.09%**
⇒ **1 秒语音最佳 EER ≈ 3–5%（同域）/ ≈17%（远场）** ⇒ 我们的 1.5–3s 落在 1s 与 3s 之间，
**社区普遍视为「信号不足」区间，不是工程问题** ⇒ 换模型的期望收益要按这个量级估，
而不是拿全长 0.61% 去想象。

#### 可直接抄的工具
`BUTSpeechFIT/VBx`（ARD 先验收缩）· `NVIDIA-NeMo/Speech` 的
`offline_clustering.py`（`SpeakerClustering`/`SpectralClustering`/**`NMESC`**/`estimateNumofSpeakers`）
与 `md_eval.py`（DER）· `pyannote/pyannote-audio` 的 `AgglomerativeClustering`
（cosine + centroid）· `fgnt/meeteval`（cpWER/tcpWER/ORC-WER/**DER**）·
**`fgnt/speaker_reassignment`**（`arXiv:2406.03155`，Interspeech 2024 — 「会议转写后人工改说话人」的现成工具）
· `speechbrain` 的 `EncoderClassifier` + EER/minDCF · `pygamma-agreement`（IAA）·
`sklearn` 的 `adjusted_rand_score`/`normalized_mutual_info_score`/`silhouette_score`。
⚠️ 簇数选择有四条互不等价的社区路线（VBx 的 ARD / eigengap（NeMo 的 NME-SC）/ ELBO+复杂度惩罚 / 经典 GMM-BIC），
**「VBx 用 eigengap」是常见误解** —— VBx 用 ARD，eigengap 是另一支。
⚠️ **DIALOKA 无法核实**（arXiv/Crossref/OpenAlex 全 0 命中，GitHub 账号本身不存在）⇒ **不要引用**。
⚠️ **`fgnt/diarization-kit` 不存在**；真实是 `fgnt/meeteval` 与 `fgnt/speaker_reassignment`。

---

## 3. 可行性实测（本轮在生产容器里真跑出来的）

> 这一节全是**本机实测**，不是论文复述。

### 3.1 依赖与现成件：不用 vendor 任何东西

- ✅ 容器里装的 `modelscope 1.40.2` **已包含**：
  - `models/audio/sv/ERes2NetV2.py`（**ERes2NetV2 的实现**）
  - `models/audio/sv/cluster_backend.py`（**`SpectralCluster` + `merge_by_cos`**
    —— 就是 3D-Speaker recipe 用的那套聚类）
  - 一批 `speaker_diarization_*` 模块
  ⇒ **不需要 pip install 任何新包，不需要 vendor 3D-Speaker 的 `speakerlab`**。
- ⚠️ `speakerlab` 本身**不在** pip 包里（它是 GitHub 仓）⇒ 走上面这条路就绕开了它。
- **依赖冲突实测**（类 20.224：冲突结论必须自己 dry-run，禁止 `--quiet`）：
  | 试装 | 结果 |
  |---|---|
  | `pyannote.audio==3.3.2` + `numpy==1.26.2` | ✅ 可解（pyannote.core 5.0.0） |
  | `pyannote.audio`（不钉）+ `numpy==1.26.2` | ✅ 可解 —— pip **回退到 3.4.0**（不是 4.0.7）⇒ **numpy 钉版才是真护栏**，不是「必须钉 pyannote」 |
  | `numba>=0.59` + `numpy==1.26.2` | ✅ 已满足（容器里 numba **0.68.0**）⇒ recipe 那个 `numba==0.56.2` 的钉版要**放宽**，不是冲突 |
  | pyannote 4.x / whisperx / nemo | 🔴 numpy>=2.0 ⇒ 排除 |

### 3.2 ERes2NetV2 可用性：已实测跑通

| 项 | 实测结果 |
|---|---|
| 模型下载 | `iic/speech_eres2netv2_sv_zh-cn_16k-common`（71.8 MB ckpt）→ `/root/.cache/modelscope/` |
| `configuration.json` | `embed_dim: 192`、`baseWidth: 26`、`scale: 2`、`expansion: 2`、`yesOrno_thr: 0.360`（相似度） |
| **直连 nn.Module 加载** | ✅ **`load_state_dict: missing=0 unexpected=0`** |
| modelscope pipeline 路径 | ❌ **不可用** —— modelscope 1.40.2 **没给 `eres2netv2-sv` 注册 preprocessor**（与现役 ERes2Net 同病）⇒ 生产只能直连底层 model（我们现状正是这么绕的） |
| **真批量推理** | ✅ `(6, 112000)` 音频 → `(6, 192)` 输出 ⇒ **batch>1 可用** |
| 速度 | **0.095 s/段**（真批量）vs 现役生产路径 **0.900 s/段** ⇒ **≈9.5×** |
| 嵌入空间兼容性 | ❌ 同一段音频，现役 ERes2Net 与 ERes2NetV2 的余弦相似度 **−0.1621** ⇒ **两个模型空间无关 ⇒ 换模型必须重算全部成员质心，不能混用** |

### 3.3 ⚠️ 两个必须写进实现的坑

1. **batch=1 的坑换模型后原样存在**：
   `modelscope/models/audio/sv/ERes2NetV2.py:335` 的 `__extract_feature` 与现役
   `ERes2Net_aug.py:337` **一字不差**（`feature.unsqueeze(0)`）⇒
   **「换到 ERes2NetV2 就自动有批量」是错的**。
   ⇒ 必须绕过 `__extract_feature`，**直驱 `ERes2NetV2` 这个 nn.Module**
   （它的 `forward` 吃 `(B, T, 80)` fbank 特征 ⇒ 天然可批量）。
2. **padding 会静默改变嵌入**：
   实测「批量(pad 到最长)」与「逐条(不 pad)」的嵌入**最大差 3.10e+01**（192 维、
   范数 ~150 ⇒ 这是**灾难级**差异）⇒ 因为 stats pooling 把补零帧也算进去了。
   ⇒ **朴素批量化会静默掉精度，且不会报错**（类 20.220 的完整形态）。
   ⇒ 必须按每条的真实帧数**裁剪**（3D-Speaker `speakerlab` 的做法），
   或改用 attention mask ⇒ **这是实现时的第一号验收点**。
   ⇒ 顺带：`torchaudio.compliance.kaldi.fbank` **严格只吃 2D (channel, time)**
   ⇒ 批量做法是**逐条算 fbank（便宜）+ 特征拼 batch 喂模型**（瓶颈在模型不在 mel）。

---

## 3.4 ⭐ 决定性实验：**根因是 enrollment 太短，不是模型不够强**

> 这一节是本轮**自己测出来的**，且把结论从社区报告的「换范式」**再往前推了一步**。
> 数据：会议 263 的 1464 段嵌入 + KMeans(6) 的簇 + 现有成员质心。

| 簇 | 段数 | 单段→王天志(中位) | **簇质心→王天志** |
|---|---|---|---|
| 朱彤(主讲) | 1257 | 0.733 | **0.685**（**只收紧 7%**） |
| 王天志(主持，**本人**) | 97 | ~0.65 | **0.512**（自比对） |
| **贾琦(听众，**本人**)** | 44 | 0.795 | **0.723**（自比对） |
| 朱彤(主讲)→贾琦 | — | 0.866 | 0.843 |

**三个致命的读数**：
1. **簇质心只把距离收紧 7%**（0.733 → 0.685）⇒ 社区暗示的「簇中心上 0.2 级阈值」
   在我们这里**不成立**。
2. **同一个人（贾琦）自比对只有 0.723**，**异人（朱彤→王天志）却是 0.685**
   ⇒ **异人比同人还近** ⇒ 任何「簇质心 ↔ 成员质心」的比较都不可能可靠。
3. ⇒ **问题不在聚类层，在「成员质心本身是坏的」**。

### 质心为什么是坏的 —— provenance 查证

`member_voice_history.source` 的分布：

| source | 次数 | 含义 |
|---|---|---|
| `recover_from_meeting` | **28** | **从会议片段里捞回来的** |
| `anchor_confirmed` | 7 | 来自会议 151/68/70/71 的片段 |
| `rebuild_20261030` | 5 | 从台账块重建（块本身也是 1.5–8 秒的段） |

而 `members.voice_sample_count`（59 / 68 / 56 …）是「**平均了多少个段**」，**不是多少秒音频**。
录入入口 `app/api/v1/voiceprint.py` 的 docstring 写的是「**上传 3-5 秒语音**」
（只拒 <1 秒），且**样本不留档**（`member_voice_history` 只存嵌入，不存音频）。

⇒ **每个成员的质心 = 若干个 1.5–8 秒片段的均值**。
⇒ 短段噪声在均值里**没有互相抵消**（不同段的环境/内容差异 > 单段噪声的随机抵消）
⇒ 这就是「同一人自比对 0.72、异人 0.69」的物理来源。

### ⛔ 社区报告里那条「前置条件」被本实验独立证实

`sep-tse` 报告写：「**前置条件（不做就白做）**：先把每个成员的 enrollment 改成
『用同样 1.5s 滑窗从其**干净长音频**聚合出的簇质心』。否则簇质心无处可对，TSE 也救不了。」
⇒ **社区结论与本机实测两条独立来源指向同一个前置条件。**

### ⇒ 换代路线必须重排（见 §4）

**先修 enrollment，再谈范式，最后才是换模型。** 理由：命名是「簇质心 ↔ 成员质心」的比较，
**成员质心不对，比较就没有意义** —— 换成 ERes2NetV2 也只是把一个坏质心算得更精确。

---


## 4. 换代路线（分阶段，每阶段有硬判据）

> ⚠️ **顺序被 §3.4 的实测重排过**：原路线是「先测模型 → 再换范式」，
> 实测证明**成员质心本身是坏的**（同一人自比对 0.723 < 异人 0.685）
> ⇒ **必须先修 enrollment**，否则后面两步都在拿坏质心做比较。

### Phase 0 —— ⭐ 重建 enrollment（**数据，不是代码；且不必等用户决策**）
**做什么**：给每个成员建一段**长而连续、同一说话人**的质心。两条来源，**优先第二条**：
- ①（需用户配合）改录入入口：docstring 现在写「3-5 秒语音」，应改到 **≥30 秒连续**；
  并且**样本要留档**（现在不留 ⇒ 无法审计、无法重建、无法重新标定）。
- ② ⭐ **从已有会议音频里收割连续长段**（不用任何人重录）：
  会议 262 里吴孟铨/韩重阳各有 400–800 秒的报告；259 里王天志的长独白；
  台账里每个人的最长连续段可直接从转录切。
  ⇒ 对每个成员，取其**最长的一段连续发言**（≥30 秒）建质心。

**硬判据**：重建后的质心 ⇒ **同一人跨场距离显著低于 0.50**（现役基线）。
**否决条件**：若不降 ⇒ 说明连「同一个人」都不可分 ⇒ 后续范式/模型全部无意义
⇒ 只能转向「更长 enrollment（≥2 分钟）+ 降噪前端」或「放弃自动识别、只做人工台账」。

### Phase 0.5 —— ⭐ 评测基建（**没有它，后面的数字都不可信**）
四份调研里最可执行的一份（按性价比排序）：

| 优先级 | 做什么 | 时长 | 抄谁 |
|---|---|---|---|
| **P0** | **冻结评测集 + 候选池快照**：每次评测产出 (segments, 台账, 裁决表, **候选池成员名单**, 质心 hash) 的**不可变快照**并版本化 | 0.5–1 天 | Sculley NeurIPS'15 §3/§7；VoxSRC 回顾「报条件集」 |
| **P0** | **coverage–selective-risk 曲线取代单一百分比**：margin 扫一遍，画 coverage / selective-risk / **绝对错名数**三条曲线 + bootstrap CI | 2–3 天 | Geifman `arXiv:1705.08500`；NIST IR 7722 |
| **P0** | **台账 IAA 审计**：双人重标 200–300 段，**按段长分层**报 κ/α/γ；IAA 低的层直接标「不可用」 | 3–5 天（人工为主） | Seshat `arXiv:2003.01472` |
| **P1** | **生产粒度评测集**：按 1.5–3s 生产段直接构造（Vox1-S 的裁剪思路），从此所有数字按此粒度报 | 2–3 天 | `arXiv:2401.08342` |
| **P1** | **pool-size 敏感性扫描**：同一场在候选池 3/6/9/12 人下各跑一遍 | 1–2 天 | VoxWatch §6.1 |
| **P1** | **Shadow 模式跑新判据**：新旧并行、只返旧答案，逐段/逐簇 diff | 3–5 天 | Fowler *Dark Launching*；SR 11-7 |
| **P2** | **自建「命名正确率」指标**（DER 测不出认错人 ⇒ 社区没现成的） | 2–3 天 | —— 这是**我们可以原创**的地方 |
| **P2** | **改用聚类后人工命名 + 交互式纠正**（人工只改错名不改全标） | 5–8 天 | `fgnt/speaker_reassignment`（`arXiv:2406.03155`；实测 DER −32%、替换错误 −53%） |
| **P2** | **成员池化质心替代逐段最近邻**（逐段最近邻只作诊断） | 2–4 天 | `arXiv:2211.00815` |
| **P3** | **统计检验落地**：McNemar（配对二元）+ paired bootstrap CI，别只比百分比 | 1 天 | Dror et al. ACL'18（ACL'17 180 篇仅 63 篇做显著性检验、6 篇用错检验） |

**为什么必须先做 P0 的「冻结」**：我们「两次重跑差 787 段」的根因是候选池变了，
社区的诊断（Sculley：不稳定数据依赖 ⇒ 冻结并版本化）与我们的实测**完全一致** ⇒
不做冻结，后面每次评测都在跟一个会漂的输入比较。

### Phase 1 —— 同口径模型对比（零生产改动，1–2 天）
**做什么**：现役 ERes2Net vs **ERes2NetV2** vs CAM++，**同一批 8 场 9336 段**
（**用 Phase 0 重建后的质心**），每条都跑**留一认回率 + 抢走率（绝对数）**（类 20.226），
并**按段长分档**（类 20.245）。阈值**在我们的数据上重标**（不沿用官方 0.64，也不沿用现役 0.65）。

**硬判据**：出「候选模型 × 我们数据」的认回/抢走对照表。

### Phase 1b —— 簇质心 vs 单段基线（Phase 0 之后才做）
**做什么**：跑 diarization 聚类 → **簇质心**（几十上百窗的均值）与成员质心比对
⇒ 命名一次，而不是逐段命名。
- ⚠️ 社区**没有先例**（0.2 级的社区阈值作用在**簇中心**上 ⇒ 暗示聚合层远比单段紧，
  但**这是推断不是证据**）⇒ **这一条只能自己量**。
- ⚠️ **§3.4 已给出同场预判**：只收紧 7%、且同人 0.723 仍差于异人 0.685
  ⇒ **Phase 0 不做，这一项几乎肯定不达标**。

**硬判据**：簇质心的跨场同人距离**显著低于**单段基线。


### Phase 2 —— 生产切换（只在 Phase 0 与 Phase 1 都通过后）
- 嵌入换成 ERes2NetV2（**批量路径 + 帧数裁剪**，按 3.3 的两个坑）；
- 识别流程换成「VAD → 重叠滑窗 → 嵌入 → 聚类 → 簇质心命名」；
- 投票与门控**沿用现有的五闸**（A/B1/B2/C/D，类 20.249），**不另造指标**；
- 成员质心**全部重算**（空间不兼容），备份表带判据版本号；
- 阈值**在生产数据上重新标定**，并按类 20.244 走三道安全闸。

**硬判据**：五闸全过 + 「台账真值判对数不降」+「全局未识别段数不升」+「换名(A→B)条数为 0」。

### Phase 3 —— 可选：重叠说话
只在真出现重叠场景时再上 `pyannote/segmentation-3.0`（**必须钉 `pyannote.audio==3.3.2`**，
且**做成独立可选进程，绝不进主 app 镜像的默认依赖**）。

### 明确不做
- ❌ 主镜像里装 pyannote.audio 4.x / nemo_toolkit / whisperx（numpy 2 冲突 + 商用许可风险）
- ❌ 为了「换框架」**重录 30+ 人声纹**（3D-Speaker recipe 同空间 ⇒ 零重录）
- ❌ 重叠分离 / TSE（边际收益低 + 工具链不成熟 + 缺长 enrollment）
- ❌ 任何**只报认回率不报抢走率**的「改进」
- ❌ 换模型但**沿用旧阈值**或**沿用旧质心**

---

## 5. 风险与未决

| 项 | 状态 |
|---|---|
| 簇质心是否真的把 0.50 降下来 | ⚠ **社区无先例，Phase 1 自己量**（决定整条链成立与否） |
| ERes2NetV2_w24s4ep4 参数量/FLOPs | ⚠ 未核实（仅由 ckpt 字节推算） |
| WavLM-SV / UniSpeech-SAT 的确切许可 | ⚠ 未逐条读 LICENSE |
| 「ERes2NetV2 能把 0.50 压到 0.42 量级」 | ⚠ **论文外推，我们数据上零证据** |
| ClearerVoice-Studio 后续版本是否加 SV | ⚠ 未核 |
| 中文 DER 基准的可比性 | 各家测的集子/口径不同（AliMeeting far vs AISHELL-4 vs 内部集），**不可直接横比** |
| **长 enrollment 的最长连续段到底有多长** | ⚠ **未量** —— 质心样本没留档，只能从转录反推；这是 Phase 0 的第一个待办 |
| **重建后同人跨场基线能否低于 0.50** | ⚠ **未量**（Phase 0 的硬判据，也是整条链成立与否的总闸） |
| **VoxCeleb3** | ⚠ **疑似不存在正式论文**（OpenAlex/Crossref/arXiv 检索均 0 命中）⇒ 勿引用 |
| VoxCeleb 官方 `voxtest_s_clean/noisy` 列表文件 | ⚠ 未核实（voxceleb.org 本机不可达） |
| **DIALOKA** | ⚠ **无法核实**（GitHub 账号本身不存在）⇒ **不要引用** |
| **「fgnt/diarization-kit」** | ⚠ **不存在**；真实是 `fgnt/meeteval` 与 `fgnt/speaker_reassignment` |
| Amelio & Pizzuti 的 B³ 论文 DOI | ⚠ 未核实 |

---

## 6. 关联

- CLAUDE.md 类 20.243（跨场基线/净增益/阈值不能自造）、20.245（短段内容优先）、
  20.246（空档单独审计）、20.247（没有声纹的人只会被兜底）、20.248（验证集本身可能是错的）、
  20.249（margin 弃权是簇级雪崩 + 五闸判定矩阵）、20.244（重标三道安全闸）、20.226（留一双指标）
- memory #54（会议 259 整场汇报被污染锚池吞掉）、#55（会议 262 四位汇报者都没声纹）、
  #56（margin 0.05 存量重标 + 四道新闸）
