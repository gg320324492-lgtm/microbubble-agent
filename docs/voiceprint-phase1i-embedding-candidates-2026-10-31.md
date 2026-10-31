# Phase 1i 报告：嵌入候选 CAM++ 对比 + ERes2NetV2_w24s4ep4 的可获得性核查（2026-10-31）

> **一句话结论：这一格也关掉了 —— 嵌入候选里没有一个可用的目标。**
> ① **ERes2NetV2_w24s4ep4 在 ModelScope 上取不到**（三个变体全部 **404**）——
>    升级文档把它列为「中文数最好的候选」，**那条建议不可执行**；
> ② **CAM++ 可获得但实测更差**（跨场段级 0.5604 → **0.4815**，−7.9 点）；
> ③ 附带查出一件**影响前面所有轮次**的事：**我此前所有轮次的「段级归属准确率」都是悲观估计**，
>    生产形态（用库里的现役质心）实际高 7 个点。

---

## 0. 做了什么 / 没做什么

| 做 | 没做 |
|---|---|
| 核查 `ERes2NetV2_w24s4ep4` 的可获得性（ModelScope 三个变体 ID） | **没有改生产 `members.voice_embedding`**（SQL 回读 0 行差异） |
| 实测 **CAM++**（`damo/speech_campplus_sv_zh-cn_16k-common`）：11358 段嵌入 + 同口径评测 | 没有测「滑窗 + CAM++」（模型已判负 ⇒ 边际价值低） |
| 补了**第三档候选池 `prod`**（库里的现役生产质心）⇒ 修正了历史口径 | 没有改流水线代码、没有装新依赖（funasr 1.4.16 容器里已装） |

**脚本**：[scripts/voiceprint/phase1i_campplus.py](../scripts/voiceprint/phase1i_campplus.py)（嵌入）、
[scripts/voiceprint/phase1i_eval.py](../scripts/voiceprint/phase1i_eval.py)（评测）

**回归核对**：`ERes2Net|重建池` 的验证集段级 = **0.5970** = Phase 1g **逐位相同** ✅

---

## 1. 候选模型的可获得性核查（这一节本身就是一个发现）

| 候选（升级文档 §2.1 的「嵌入候选只剩两个没否掉的」） | ModelScope | 状态 |
|---|---|---|
| `iic/speech_eres2netv2_w24s4ep4_sv_zh-cn_16k-common` | — | ❌ **404** |
| `iic/speech_eres2netv2_w24s4ep4_sv_zh-cn_16k` | — | ❌ **404** |
| `iic/speech_eres2netv2_w24s4ep4` | — | ❌ **404** |
| `iic/speech_eres2netv2_sv_zh-cn_16k-common`（基础版） | ✅ | Phase 1 已实测**全面略差**（同族、192 维、CN-Celeb 4.32% vs 官方 3.28%） |
| `damo/speech_campplus_sv_zh-cn_16k-common`（CAM++） | ✅ | 本轮实测 ⇒ **更差** |
| `iic/speech_campplus_sv_zh-cn_16k-common` | — | ❌ 404 |
| `iic/speech_campplus_sv_en_16k-common` | — | ❌ 404 |

⇒ ⭐ **「中文数最好的嵌入候选」在模型仓库里根本不存在** ⇒ 那条建议不可执行。
⇒ ⇒ **嵌入候选这一格没有可达的高价值目标** ⇒ 嵌入这条路整体关掉。

---

## 2. CAM++ 实测（与现役 ERes2Net 同构造对比）

⚠️ **跨模型比较必须重建成员质心**（两个空间不相通，现役质心在 CAM++ 空间不可用）
⇒ 本节全部用**「重建池」**（在各自空间里、用该成员的**其它场**重建 13 人质心）⇒ 构造相同，只差模型。

| 集合 | 指标 | ERes2Net(现役) | **CAM++** | 差 |
|---|---|---|---|---|
| 选参数集 | 跨场 EER | **0.1391** | 0.1549 | +0.0158 ❌ |
| 选参数集 | 跨场段级 | **0.5364** | 0.5329 | −0.0035 ≈ |
| **验证集** | 跨场 EER | 0.1504 | **0.1250** | −0.0254 ✅ |
| **验证集** | 跨场段级 | **0.5970** | **0.4030** | **−0.1940** ❌❌ |
| 全 9 场 | 跨场 EER | **0.1484** | 0.2527 | +0.1043 ❌❌ |
| 全 9 场 | 跨场段级 | **0.5604** | **0.4815** | **−0.0789** ❌ |
| 全 9 场 | 簇纯度 | 0.8535 | 0.8446 | −0.0089 |
| 全 9 场 | 主导簇占比 | 0.8053 | 0.7920 | −0.0133 |
| 全 9 场 | 命名天花板 | **0.8252** | 0.8165 | −0.0087 |

⇒ ⭐ **CAM++ 更差**，尤其是**验证集的段级**（−19.4 点）⇒ **不通过**。

⚠️ **两个必须标出来的异常**（都说明这些数不可靠，不能只看单点）：
1. **验证集 EER 反而更好（0.1250），段级却极差（0.4030）** ⇒ 两个指标**方向相反**
   ⇒ 说明 CAM++ 的簇质心「可分性」尚可，但**命名**极差 ⇒ 又是同一个瓶颈（命名）。
2. **EER 的 minimax 值在样本集变化时不稳定**：CAM++ 验证集 EER **0.1250** 而全 9 场 **0.2527**
   ⇒ FAR/FRR 曲线有跳变 ⇒ **单点 minimax EER 不是稳定指标**（类 20.229 的同族：
   报告一个数不等于报告了结论）。⇒ 后续应同时报 FAR/FRR 与曲线。

⚠️ **第三档候选池 `prod` 对 CAM++ 无效**：现役生产质心只存在于 **ERes2Net 空间**
⇒ 拿它去比 CAM++ 的向量是**空间混用** ⇒ CAM++ 的 `prod` 档（实测 0.000–0.019）
**不是"CAM++ 很差"，是"这个口径对 CAM++ 没有意义"** ⇒ **跨模型比较只能用 `strict` 档**。

---

## 3. ⚠️⚠️ 附带查出的口径订正：**此前所有轮次的「段级归属准确率」都是悲观估计**

本轮补了第三档候选池 `prod`（**库里的现役生产质心**）：

| 候选池 | 含义 | 验证集段级（ASR段聚类） | 全 9 场 |
|---|---|---|---|
| `strict`（Phase 1b~1h 一直用的） | 该成员的质心**留出该场**、只用别的场重建 | 0.5970 | 0.5604 |
| **`prod`**（**库里的现役生产质心**） | 用全部素材跨场混合建（**含被识别的那一场**） | **0.8201** | **0.6350** |

⇒ **生产上的成员质心含被识别场次的素材** ⇒ 此前一直用「留出该场」的严格口径
⇒ ⇒ **此前所有轮次的段级数字都系统性偏低**：全 9 场真实水平是 **0.6350** 而不是 0.5604。

⚠️ **两条必须一起说的限制**：
1. **prod 口径的场次波动很大**（验证集 0.8201 vs 选参数集 0.5139）
   ⇒ **现役质心对目标场的适配度不稳定** ⇒ 与 Phase 1f 的扩池发现互相印证：
   **「成员侧参照物」的质量有很大的运气成分**。
2. **Phase 1h 的滑窗提升在 prod 口径下变小**：strict +5.6 点（验证集）⇒ prod **+0.7 点**；
   全 9 场 strict +3.3 点 ⇒ prod **+2.3 点** ⇒ **滑窗仍有效，收益比 strict 显示的小**。

⇒ ⇒ **读历史报告里的「段级归属」时，一律按「严格跨场口径」理解**；
生产预期看 `prod` 那一档。

---

## 4. 结论：换代路线的三格已关，只剩一格

| 杠杆 | 状态 | 依据 |
|---|---|---|
| 换**聚类算法** | 🔴 关 | Phase 1g：18 组无一超过 KMeans+固定 k=6；自动估人数全失败 |
| 换**嵌入模型** | 🔴 关 | Phase 1i：V2_w24s4ep4 **取不到**；V2 基础版 Phase 1 已否；CAM++ 本轮更差 |
| 改 **enrollment 长度** | 🔴 关 | Phase 0：长段质心无增益，「只取最长一段」显著更差 |
| ✅ 改**聚类的输入单元** | 🟢 **活着** | Phase 1h：滑窗在两个口径下都改善（strict +5.6 / prod +0.7 ~ +2.3 点） |

⇒ ⇒ **下一步该在滑窗这条线上继续**，具体三件事（按性价比）：
1. **窗口长度 / 重叠率敏感性**（1.0s / 2.0s、25% / 75%，每档约 30 分钟重嵌）
2. **生产接入**：把「滑窗聚类 → 簇质心 → 簇命名」做成流水线里的一步
   （人工纠正走 Phase 1f 已落地的 `cluster_naming_service`，默认关）
3. **shadow evaluation**：在生产跑一轮对比再切换

---

## 5. 限制

1. **CAM++ 只测了段级**（11358 段）；「滑窗 + CAM++」未测（模型已判负 ⇒ 边际价值低）。
2. ⚠️ **CAM++ 的官方前端是 `WavFrontend`**，本脚本复刻了 funasr 的
   `extract_feature` 的 fbank + 逐条减均值（**逐行一致**），但**没有走**
   `load_audio_text_image_video`（它可能做音量归一）⇒ 若官方路径含幅度归一，
   本轮结果会与官方推理有细微差异。**方向性结论不受影响**（差 8–19 点）。
3. **CAM++ 的批量是零 padding 的**（按帧数分桶）⇒ 与官方 `extract_feature` 的
   `pad_list` 行为不同（官方会 pad）⇒ 本轮**比官方更干净**，但也因此与官方不完全等价。
4. **单点 minimax EER 不稳定**（见 §2）⇒ 本报告的 EER 只能当方向看。

---

## 6. 复现

```bash
# 1) CAM++ 嵌入 (容器内; 段级 ~25 分钟, 滑窗再 ~25 分钟)
docker cp scripts/voiceprint/phase1i_campplus.py <container>:/tmp/vp/
docker exec -w /app <container> python /tmp/vp/phase1i_campplus.py \
    --phase1 /tmp/vp/phase1 --sw /tmp/vp/phase1h --out /tmp/vp/phase1i
# 2) 评测
docker cp scripts/voiceprint/phase1i_eval.py <container>:/tmp/vp/
docker exec -w /app <container> python /tmp/vp/phase1i_eval.py \
    --phase1 /tmp/vp/phase1 --camp /tmp/vp/phase1i --out /tmp/vp/phase1i
```

**产物**：`data/vp_phase1i/eval.json`

---

## 7. 关联

- Phase 1h：[docs/voiceprint-phase1h-sliding-windows-2026-10-31.md](voiceprint-phase1h-sliding-windows-2026-10-31.md)（滑窗，唯一活着的方向）
- Phase 1g：[docs/voiceprint-phase1g-cluster-algos-2026-10-31.md](voiceprint-phase1g-cluster-algos-2026-10-31.md)（聚类算法关）
- Phase 1：[docs/voiceprint-model-swap-2026-10-31.md](voiceprint-model-swap-2026-10-31.md)（V2 基础版略差）
- Phase 1f：[docs/voiceprint-phase1f-product-shape-2026-10-31.md](voiceprint-phase1f-product-shape-2026-10-31.md)（产品形态数字）
- 升级文档 [docs/voiceprint-upgrade-2026-10-31.md](voiceprint-upgrade-2026-10-31.md)（V2_w24s4ep4 那一行的可获得性需订正）
- CLAUDE.md 类 20.226（双指标）、**20.229**（验证纪律必须同时写"那该信什么"）、
  **20.243**（先量基线）、**20.249 ⑧**（锁死输入）、**20.252**（参照集≠候选池）
