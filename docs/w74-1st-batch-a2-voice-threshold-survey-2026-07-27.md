# W74 第 1 批 A-2：声纹 MATCH_THRESHOLD 0.7 vs 90% 门禁调研

> 日期：2026-07-27  
> 性质：纯调研，调研完成 ≠ 生产实施  
> 依据：W73 A-2 `a2243a650` 关键发现 #1  
> 锚点范式：W73 第 1 批 242 → W74 第 1 批 A-2 245 守恒（本任务 +1）

## 0. 真验证与 W74 起步纪律

先执行派工 v4 铁律 3：读原调研、查 git log、grep 当前代码。结果确认：

1. `app/services/voiceprint_service.py:26` 定义 `MATCH_THRESHOLD = 0.7`，而且注释明确其量纲是**余弦距离上限（越低越相似）**。
2. `identify_speaker`、`identify_speaker_by_embedding`、`identify_speaker_anchored` 均使用 `distance < 0.7`；`voiceprint_voting.py` 也默认 `match_threshold=0.7`。
3. 90% 永久规则位于 `docs/CLAUDE-history.md:5446-5496`，量纲是 strict merge 后的**跨会议段级识别率**，不是单段相似度。
4. 历史真实案例为王天志：跨会议加权识别率 88.1% < 90%，执行 rollback。
5. 当前树不存在 `memory/voiceprint-90-percent-gate-2026-06-28.md`、`voiceprint_research/bubble_speech_2026-06-28*.md` 或 `app/agent/tools/voiceprint*.py`；相关事实保存在 `docs/CLAUDE-history.md`、README/CHANGELOG 历史和用户级 memory 索引。这一缺失本身必须如实记录，不能伪造引用。
6. W74 起步纪律实战：基准 HEAD 真验证、来源 commit 真验证、git log 真验证、生产 grep 真验证、缺失文件显式报告、调研与实施边界锁定。

派工 v10 段 7 类 20 的本次落实：派生任务必须先完成 plan/source、git log、代码 grep 三证，再给 W75/W76 排期；不得以 memory 自报替代代码物证。

## 1. 现状：MATCH_THRESHOLD 0.7 代码层

### 1.1 定义、量纲和使用点

`app/services/voiceprint_service.py` 使用 ERes2Net 模型 `iic/speech_eres2net_sv_zh-cn_16k-common`，输出 192 维 embedding。主链为：

1. 音频转 float32、最低补齐 1 秒；
2. ERes2Net 提取 192 维 embedding；
3. PostgreSQL/pgvector 以 cosine distance 排序取最近成员；
4. 再以 numpy 计算 `cosine_dist`；
5. `confidence = 1 - min(cosine_dist, 1)`；
6. `cosine_dist < MATCH_THRESHOLD(0.7)` 才返回成员，否则 unknown。

因此 **0.7 是距离，不是 70% 通过率**。在该公式下，边界 `distance=0.7` 对应 confidence 约 0.3；把常量直接改成 0.9 反而会接受更远、更差的匹配，并非“提高到 90%”。若目标是单段 confidence ≥ 0.9，等价距离上限应接近 0.1。

跨文件使用：`voiceprint_voting.py` 默认 `match_threshold=0.7`，另有 cluster 合并 cosine similarity `merge_threshold=0.85`、质量门 `votes_ratio>=0.30`、`avg_conf>=0.30`，严格分配层另用 `conf>0.50` 与 votes ratio ≥0.5。多个阈值量纲不同，不能横向直接相减。

### 1.2 录入、anchor 与不可变语义

`enroll_member` 对多次样本加权平均并归一化，然后更新 `voice_embedding`、`voice_sample_count`、`voice_enrolled_at`。`Member.voice_confirmed_at` 在 `app/models/member.py` 和 migration `036_add_voice_confirmed.py` 中存在；非空表示 anchor。`get_anchor_members` 只选已确认成员，`identify_speaker_anchored` 仅与 anchor 比较。历史脚本和注释规定 anchor embedding 永不自动修改，strict 流程跳过。

### 1.3 KMeans、sil_floor、cluster_centers

`post_meeting_tasks.py` 对全部转录段批量提 embedding，`smart_select_k` 聚类，再计算代表 embedding并匹配。`voiceprint_voting.py` 记录 083 实战：cluster centers cosine similarity >0.85 时使用 union-find 合并，防止同一说话人被强分簇。低 silhouette 质量由 sil_floor/质量门参与决策；最后还需 votes ratio、平均置信度、上下文成员、歧义和低占比过滤。这些是聚类质量控制，不会把 0.7 自动“校正成 90%”。

## 2. 90% 门禁：MEMORY/历史层

仓库当前没有派工所点名的独立 gate memory 和 bubble_speech 文件，故以仍在仓库的永久历史锚点作为一手物证：

- `docs/CLAUDE-history.md:5446-5452`：strict merge 后必须跨会议验证；<90% rollback，90–95% 用户决定，≥95% 接受。
- `docs/CLAUDE-history.md:5459-5464`：验证脚本按段计算 `cos_dist <= 0.55` 的命中率，最终对全部会议加权。
- `docs/CLAUDE-history.md:5483-5492`：王天志 #135 94.6% + #151 83.5%，整体 88.1%，回滚 sample_count 583→384。
- `README.md:148` 与 `docs/CHANGELOG-history-2026-07-23.md` 保留 #151 rollback 摘要。
- `docs/voiceprint-anchor-scripts.md` 仍将 strict 90% 门禁列为后续 anchor 脚本要求。

所以 90% 是**一次 embedding 变更能否保留的回归验收门禁**；它并非线上逐段识别常量，也不是模型返回的确认概率。所谓“12 会议音频 reprocess+strict 长期迭代”属于声纹净化项目的跨会议回归样本池；真实 rollback 已证明门禁执行过，但当前代码并未把它嵌入在线 matcher。

W68 第 12/13 批提交检索未发现把 voice matcher 改为 0.9 的提交；W68 第 13 批相关 `c6932a946` 是通知系统 voice-alert，不是声纹识别阈值。不得把“voice alert”误当“voiceprint”。

## 3. LLM 校正层真验证

- `app/services/llm_analysis_service.py` 未发现声纹匹配、speaker mapping 或阈值校正逻辑。
- `app/agent/tools/voiceprint*.py` 不存在。
- `post_meeting_tasks.py` 的第二阶段先声纹提取/聚类/投票，再通过 `correct_speaker_name` 做成员姓名字符串校对，随后更新 `speaker_mapping`；这不是 LLM 对相似度重评分。
- `meeting_analysis_service.py` 负责会议结构化分析，未成为 0.7→0.9 的阈值桥。
- 后续“AI 润色转录文本”接收已生成的 speaker 信息，不能视为声纹置信度硬门禁。

结论：候选解释“LLM 校正层将 0.7 提到 90%”缺乏代码证据，当前应判否。

## 4. “60 百分点差距”根因四候选

| 候选 | 代码证据 | 判定 |
|---|---|---|
| (a) 0.7 宽松阈值、90% 严格门禁 | 在线 matcher 用 distance<0.7；strict merge 回归用跨会议识别率≥90% | 部分正确，但二者量纲不同，不能称简单 60 点差 |
| (b) 0.7 匹配相似度、90% 确认概率 | 代码明示 0.7 是 cosine distance；90% 文档明示是段命中率 | “量纲不同”方向正确，但 0.7 甚至不是 similarity；应表述为距离上限 vs 回归成功率 |
| (c) LLM 校正层将 0.7 提到90% | 未找到 LLM 重评分；姓名校对只规范字符串 | 否决 |
| (d) MEMORY 描述不准确 | 若 MEMORY 把“90%硬门禁”描述成在线 MATCH_THRESHOLD，则不准确；历史锚点本身明确是 strict merge 跨会议门禁 | 最可能是 W73 摘要压缩时丢失量纲，而不是永久规则错误 |

**根因结论**：这不是同一指标的 0.7 vs 0.9 冲突，而是三层指标被混写：单段 cosine distance（0.7）、strict 验证段命中条件（distance≤0.55）、跨会议总体识别率（90%）。因此“60 百分点差距”是口径错误。真实风险仍存在：在线 0.7 较宽松，且 90% 回归门禁只在修改 embedding 后由脚本/流程执行，并非在线强制。

## 5. W75+ 修复路径与主拍

### 方案 A：直接改 `MATCH_THRESHOLD=0.9`

破坏性最高，且按距离语义方向错误：0.9 会更宽松。若方案 A 的真实意图是 confidence≥0.9，应设计为 distance≤0.1，并对 12 会议音频全部 reprocess、统计 unknown/误识别率、逐成员 rollback。不能按派工字面直接落 0.9。

### 方案 B：增加渐进校正/门禁层

保留老 matcher 兼容性，在候选识别后增加可配置的质量层：单段距离、top1-top2 margin、cluster votes、anchor 状态、跨会议回归门禁分别记录；新 embedding 写入或确认前自动跑 ≥90% 回归，否则 rollback。这里应是确定性质量门，不建议依赖 LLM 修改数值；LLM最多解释歧义，不得越过门禁。

### 方案 C：只修 MEMORY 描述

最低成本：明确“0.7=distance 上限；0.55=跨会议验证单段命中；90%=变更后跨会议总体识别率”。它可消除假冲突，但不能改善线上宽松匹配与流程门禁未自动化问题。

### 主拍必拍

建议主拍 **B + C 组合**，拒绝字面 A：先修口径，再将 90% strict 回归门禁自动化且可观测；保持在线老路径，通过 shadow report 比较新门规则，达到覆盖率/误拒率基线后再决定 matcher 阈值。主拍必须明确：距离阈值目标、回归数据集、unknown 上限、误识别上限、rollback 资产和 feature flag。此为派工 v6 段 5 反馈 #6：调研 agent只给证据与选项，主指挥拍板后才能生产实施。

## 6. W75/W76 四子批建议

1. **W75 Step 6：声纹阈值修复**：采用主拍后的 B+C；先补指标命名与离线 shadow benchmark，再决定阈值，必须覆盖 12 会议音频及 #151 rollback 重演。
2. **W75 Step 7：9 表 2 索引缺口修复**：由 W74 B-1 结果驱动；保持与声纹阈值变更独立提交、独立回滚。
3. **W76 Step 8：Edge-TTS 移动端兼容性**：分别验证 iOS Safari/Android Chrome 的 autoplay、音频格式、后台切换和中断恢复。
4. **W76 Step 9：SenseVoice 错误率三维分布**：至少按噪声/SNR、说话人或性别、片段时长三维统计，输出置信区间与失败样本，不能只报平均 WER。

每个派生子批启动前重复 git log + git show + grep 三证，先验证前一批是否真实落地。

## 7. 边界、守恒与结论

- 调研 ≠ 生产：未修改 `app/services/voiceprint*.py`、`app/voice/`、模型、数据库或 migration。
- 0 production code 改动铁律守恒：仅新增本调研文档与 memory 沉淀。
- 核心结论：所谓 60 百分点差距是指标量纲混淆；在线 0.7 distance gate 与 strict merge 后 90% cross-meeting acceptance gate 可同时成立。真正待修的是命名/文档口径和 90% 门禁自动化，而不是把常量机械改成 0.9。
- 锚点范式：W73 第 1 批 242 → W74 第 1 批 A-2 245 守恒（+1）。
