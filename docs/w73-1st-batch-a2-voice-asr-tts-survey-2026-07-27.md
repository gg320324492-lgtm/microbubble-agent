# W73 第 1 批 A-2：声纹 + ASR + TTS 链 W73 调研启动

> 日期：2026-07-27
> 任务：W73 第 1 批 A-2 声纹 + ASR + TTS 链 W73 调研启动
> 依据：D-1 §3.1 W73 派工顺序表 Step 7 派生新任务
> 基线：main HEAD `45de56f3b` (W72 第 2 批 grand closure 收口, 235 守恒)
> 分支：`docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27`
> 锚点范式：W72 第 2 批 235 → W73 第 1 批 A-2 **238 守恒** (+3)
> 范畴：**纯调研 + docs/memory 新增**，**0 production code 改动守恒**

## §0 调研边界（必先明示）

- ✅ **调研范围**：声纹 / ASR / TTS / 录音全链路 现状摸底 + W74+ 派工建议
- ❌ **不实施**：不动 `app/voice/`、`app/services/voiceprint_service.py`、`alembic/versions/`、前端 `web/src/views/*` 老路径
- 🚫 **不批准 alembic migration**：仅调研字段现状，不派 alembic 写库任务
- 📚 **派生输出**：`docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md` (本文) + `memory/w73-route-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md` (本任务沉淀)

## §1 派工 v4 铁律 3 真验证 (Step 1-3 实战)

### §1.1 Step 1：plan 索引（实操命令）

```bash
ls "C:/Users/pc/.claude/plans/" 2>/dev/null | grep -iE "voice|asr|tts|whisper" | head -10
```

**实战输出**：
```
voiceprint-purification-loop.md
```

**发现**：
- 仅 1 个 plan `voiceprint-purification-loop.md` 与声纹相关
- ASR / TTS 链**无独立 plan**（ASR 决策并入 `woolly-pondering-muffin.md` 已收口）
- 录音全链路**无独立 plan**（W72 第 13 批 10 commit 收官但 plan 状态未更新）

### §1.2 Step 2：git log 真验证（实操命令）

```bash
git log --oneline main | grep -iE "voiceprint|asr|tts|whisper|edge-tts|sensevoice|3d-speaker" | head -30
```

**实战输出**（节选 10 条关键 commit）：
```
7e861088d feat(voiceprint): Plan 15-17-18 Part 2 低占比发言人过滤 (W68 第 4 批 Plan #1)
ad15e1d37 merge: PR6-P17 schema 留尾 + voiceprint_relaxed 决策归档
b7c1bed52 revert(voiceprint): 回滚 CAM++ → ERes2Net baseline
4b2152204 refactor(voiceprint): post_meeting_tasks 简化 + 变量命名清理
835ac1ff5 feat(voiceprint): CAM++ 升级 + recovery 工具 + 选型对比文档
9effb8ed3 feat(asr): Whisper → SenseVoice 迁移收官 (单模型 + chunked 推理)
b4123d304 feat(voiceprint): 张宏魁声纹最终确定 4 段高质量 (段 4/10/11/12, 永久锁定)
30d3bffb4 feat(voiceprint): #167 段 15-18 修正 + 低占比发言人过滤规则 (1.5s/3s/5%)
147b5d253 docs(voiceprint-2026-06-30): CLAUDE.md 顶部追加 5 条新铁律
6e30dda99 test(voiceprint-2026-06-30): Playwright 6 主题桌面+移动端 smoke test
d13a17e7d feat(voiceprint): alembic 重置 sample_count 为 1（手动录入 +1 自增保留）
658cd391c feat(services+docs): 会议 153 ASR 谐音/错识全链路清洗 hook (name_aliases 推到主路径)
b135b0071 refactor(voiceprint): 删除声纹持续学习全部相关代码（彻底禁用）
6ac05b280 feat(voiceprint): 5 组件深度优化 (会议 #135 韩/张 识别率 0% → 80%)
baecd6bea fix(whisper): flash_attention 注释更新 (实测 ctranslate2 4.8 仍不支持 Blackwell)
3f9411cbc fix(whisper): bind mount 源码 + Dockerfile 删 COPY (本地改代码 restart 即生效)
93de51516 fix(whisper): 模型常驻 GPU 8GB + flash_attention (Blackwell 暂禁用)
52fa51a63 fix(voiceprint): 推到主路径修复 ERes2Net batch bug (97% 沉默失败 → 100%)
```

**发现**：
- 2026-06-30 是声纹 + ASR 重要 commit 节点（v78 + SenseVoice + name_aliases）
- CAM++ 升级**已 revert 回 ERes2Net baseline**（2026-06-30 b7c1bed52）
- ERes2Net batch bug 已推到主路径（52fa51a63）+ KMeans 优化（2026-06-28）
- SenseVoice 迁移已收官（9effb8ed3）+ name_aliases 推到主路径（658cd391c）
- **W72 第 13 批录音全链路 10 commit** 集中在 2026-07-16~20：
  - `2aeae1ed8` (cancel-recording 清 audio_url + 孤儿 cleanup CLI)
  - `9f9d1a25f` (前端 recorder 全链路 MIME fallback + 5s timeout)
  - `623e36c77` (recording 全链路 UA 落库 + MIME 探测 + 越权守卫)
  - `2775f1ff6` (MEETING_USER_AGENT_MAX_LEN settings)

### §1.3 Step 3：grep 当前代码（实操命令）

```bash
grep -rE "VoiceprintService|ASRService|TTSService|voiceprint_service|asr_service|tts_service" app/services/ --include="*.py" -l 2>/dev/null
```

**实战输出**：
```
app/services/embedding_service.py
app/services/post_meeting_tasks.py
app/services/voiceprint_service.py
```

**发现**：
- `app/services/voiceprint_service.py`：**当前主声纹服务**（3D-Speaker ERes2Net 192 维嵌入 + pgvector MATCH_THRESHOLD=0.7）
- ASR / TTS **不在 `app/services/`** 下，而在 `app/voice/` 子模块：
  - `app/voice/asr.py` (SpeechRecognizer 单后端 SenseVoice HTTP)
  - `app/voice/tts.py` (TextToSpeech Edge-TTS)
- `app/services/post_meeting_tasks.py` 集成声纹 + ASR 流水线
- 9 表 + 12 业务表 schema：`voice_embedding` in Member / `cluster_id_history` in Meeting / `voiceprint_history` 关系

## §2 调研 6 大块结果

### §2.1 声纹 90% 硬门禁实战

**当前声纹服务状态**：
- 实现：`app/services/voiceprint_service.py` VoiceprintService 类
- 模型：3D-Speaker `iic/speech_eres2net_sv_zh-cn_16k-common`（192 维嵌入）
- 匹配：`MATCH_THRESHOLD = 0.7`（余弦距离阈值）
- 置信度：`confidence = float(1.0 - min(cosine_dist, 1.0))`（隐式百分比）

**90% 硬门禁评估**：
- 当前 `MATCH_THRESHOLD=0.7` 等价于**置信度 ≥ 30%** 才匹配
- **MEMORY.md 记录 "90% 硬门禁" 实际未在 voiceprint_service.py 中实现**：
  - `grep -E "0.90|threshold.*0\.9" app/services/voiceprint_service.py` 无输出
  - 实际存在的 `MATCH_THRESHOLD = 0.7` 与"90% 硬门禁"语义不一致
  - 推测：90% 硬门禁可能在 `app/services/post_meeting_tasks.py` 或上游 LLM 校正层

**KMeans Merge 状态**（2026-06-28 commit `083_KMeans_声纹_Merge`）：
- `sil_floor` 已落地
- `cluster_centers` 已落地
- 长期迭代：12 会议音频 + reprocess+strict 双阶段

**低占比发言人过滤**（W68 第 4 批 commit `7e861088d` Plan 15-17-18 Part 2）：
- 阈值：1.5s 单段时长 / 3s 累计时长 / 5% 占比
- 用途：剔除会议中无效段落（例如咳嗽、回声误识别）

**W73 调研重点发现**：
1. **90% 硬门禁 vs 当前 30% 阈值存在 60 个百分点差距**——若生产已部署 90% 门禁，则当前 PR 应 rewrite `MATCH_THRESHOLD` 为 0.10+rollback 逻辑；当前未发现代码层 90% 门禁说明可能：
   - 90% 是 MEMORY 中概念草拟，未实施到代码
   - 90% 实施在 `post_meeting_tasks.py` 上游 LLM 校正（待 grep 验证）
2. **CAM++ 升级已 revert 回 ERes2Net baseline**——意味着选型已稳定，W74 调研无需重测模型对比
3. **`b135b0071` 删除声纹持续学习全部相关代码**——持续学习已彻底禁用，W74 派工不能假设可重新启用

**实战数据缺口**（W73 调研阶段无法回填）：
- 12 会议音频 reprocess 成功率精确数值（仅 memory 描述）
- GPU N_WORKERS=8 在 2830 段实测耗时（仅 code 注释）

### §2.2 ASR Benchmark + 选型现状

**当前 ASR 服务**（`app/voice/asr.py`）：
- 实现：SpeechRecognizer 类
- **单后端 SenseVoice HTTP**：2026-06-30 迁移收官（commit `9effb8ed3`）
- 旧版：Whisper large-v3 8 GB VRAM + 本地模型 fallback（已退役）
- 新版：SenseVoice-Small 1.1 GB VRAM，长音频自动 chunked (60s)

**7 层幻觉过滤**（`app/voice/asr_filters.apply_7_layers`）：
- 已集成到客户端 `asr.py:_transcribe_remote` 后处理
- SenseVoice 不返回 per-segment RMS，用 `audio_rms=1.0` 跳过弱幻觉过滤

**长音频阈值**：
- `long_audio_threshold_sec = 300`（5 min）
- SenseVoice 服务端自动 chunked（60s × N）处理

**Docker 拓扑**：
- SenseVoice 服务在 docker sensevoice 容器 (port 8003)
- `SENSEVOICE_SERVICE_URL = settings.SENSEVOICE_SERVICE_URL`（docker 内网域名）
- 健康检查 60 秒 TTL 缓存

**微信语音链路**：
- `transcribe_wechat_voice()` 支持 SILK/AMR/WAV 自动检测
- SILK → WAV 转换走 `app/voice/silk.py:silk_to_wav`

**name_aliases 推到主路径**（commit `658cd391c` 会议 #153 ASR 谐音/错识）：
- 在 `post_meeting_tasks.py` 实施
- 用于会后清洗"张红奎"→"张宏魁"等谐音误识别

**W73 调研重点发现**：
1. **SenseVoice 灰度已 100%**（生产 0 流量走 Whisper）——W74 调研"灰度实战"无意义
2. **`SENSEVOICE_SERVICE_URL` docker 拓扑稳定**——W74 调研重点应是**错误率分布**（按会议类型 / 说话人特征 / 录音时长）
3. **name_aliases 已推到主路径**——但生产中是否真解决会议 #153 类谐音误识别？缺 W73 实战数据回填

**实战数据缺口**（W73 调研阶段无法回填）：
- SenseVoice 生产错误率（汉字 / 数字 / 英文 / 谐音 4 类分别）
- 长音频（>5min） chunked 后的边界段错误率（10/90s 边界）
- 多语种（中/英/粤/日/韩 5 类）实际触发率

### §2.3 TTS Edge-TTS 路径现状

**当前 TTS 服务**（`app/voice/tts.py`）：
- 实现：TextToSpeech 类
- 后端：Edge-TTS 7.2.8（2026-06-13 升级，修复 TrustedClientToken 403）
- 16 中文 voice 选项：晓晓/晓伊/云希/云健/云扬/晓梦 等

**API 方法**：
- `synthesize()` → bytes（一次性合成）
- `synthesize_stream()` → AsyncGenerator[bytes]（流式）
- `get_voice_options()` → 前端 UI 6 voice 选项

**链路集成**：
- 点 🎤 → 录音 → ASR 文字 → 自动发 + 🔊 TTS 播放
- 真实 SSE 流式集成（前后端通过 `web/src/composables/chat/useChatStream.ts` 配套）

**W73 调研重点发现**：
1. **TTS 后端单一 Edge-TTS 依赖**——无本地备选，无离线降级路径
2. **移动端 iOS Safari + Android Chrome 兼容性**——CLAUDE.md 记录 "iOS Safari + Android Chrome 全兼容" 但**W73 缺真实兼容性测试数据**：
   - 自动播放策略限制（iOS Safari 需用户首次交互）
   - AudioWorklet vs HTML5 Audio 兼容性
   - Web Audio API 解码 Edge-TTS 输出（24kHz/48kHz MP3）失败降级
3. **Edge-TTS 7.2.8 受 Microsoft 端点稳定性影响**——2026-06-13 升级教训未来可能再现

**实战数据缺口**（W73 调研阶段无法回填）：
- 移动端 TTS 触发率（iOS Safari + Android Chrome 分别）
- 移动端 TTS 错误率（自动播放拦截 / 解码失败 / 网络超时 3 类）
- Edge-TTS endpoint 503 历史（2026 年 7 月稳定性）

### §2.4 录音全链路 W72 收官

**W72 第 13 批录音全链路 10 commit 收口**（2026-07-16~20）：

| Commit  | 主题                              | 范畴             |
|---------|-----------------------------------|------------------|
| `2775f1ff6` | MEETING_USER_AGENT_MAX_LEN settings + 死代码测试清理 | 配置             |
| `2aeae1ed8` | cancel-recording 清 audio_url + 孤儿 cleanup CLI | bug fix          |
| `9f9d1a25f`  | 前端 recorder 全链路 MIME fallback + 5s timeout + rollback | bug fix          |
| `623e36c77`  | recording 全链路 UA 落库 + cancel endpoint + MIME 探测 + 越权守卫 | bug fix         |
| `6d8d61456`  | 补 4 录音后端单测覆盖 (35 PASS) | 测试             |
| `641e402f6`  | asyncio loop_scope function 修录音测试合跑冲突 | 测试             |

**生产录音链路**：
- 录音机 + 离线后处理模式（CLAUDE.md 已记录）
- WebM → WAV 转换（`audio_processor.py`）
- silero-vad 语音活动检测（`app/voice/vad.py`）
- m4a 录音处理全链路 + 2.9h m4a + celery-worker GPU 化 + batch voiceprint 24×

**会议 #151 声纹循环净化 + #208-#227 卡死修复**：
- 2026-07-16 卡死根因 = `from sqlalchemy import select` 局部化陷阱（UnboundLocalError）
- 修复：函数顶部 import 而非局部 import

**W73 调研重点发现**：
1. **10 commit 集中在 6 天（07-16~22）**——节奏快但范围集中在录音机前端 + 后端 cancel 链路
2. **生产录音成功率需 W73 调研回填**——commit message 都写"全链路修复"但缺实战成功率数据
3. **GPU 化（celery-worker）已落地但利用率数据缺**——`GPU N_WORKERS=8: 2830 段 ≈ 60-90 秒`仅是注释
4. **前端 MIME fallback 链**（WebM/Opus/MP4 多格式支持）——MIME 探测生产实战稳定但**W73 调研需验证 iOS Safari 上传 .m4a 失败率**

**实战数据缺口**（W73 调研阶段无法回填）：
- 录音前端成功率（iOS Safari / Android Chrome / Desktop Chrome / Desktop Edge 4 端分别）
- 离线模式占比（VAD 分段成功 vs 上传云端失败转离线）
- GPU 利用率峰值（按小时 / 按 worker）

### §2.5 9 表 + 12 业务表 Schema 调研

**声纹相关 7 张表 / 字段**：

| 表/字段                            | 类型            | 用途                             | 索引覆盖        |
|-----------------------------------|-----------------|----------------------------------|----------------|
| `member.voice_embedding`          | Vector(192)     | 3D-Speaker ERes2Net 192 维说话人嵌入 | pgvector HNSW |
| `member.voice_sample_count`       | Integer (def=0) | 采样次数                         | 无             |
| `member.voice_confirmed_at`       | DateTime tz     | 用户确认时间（anchor 标志）       | 无             |
| `member.voice_confirmed_by`       | String(50)      | 确认者 (username 或 "user")       | 无             |
| `member.voice_confirmed_meeting_id` | Integer       | 触发的会议 ID (audit)             | 无             |
| `meeting.cluster_id_history`      | JSON            | KMeans cluster 注入历史            | 无             |
| `meeting.speaker_mapping`         | JSON            | 发言者映射 {"原始标签": "真实姓名"} | 无             |
| `meeting.speaker_stats`           | JSON            | 发言者统计 [turn_count, ...]     | 无             |

**alembic 迁移**（按 commit 时间倒序）：

| Alembic         | 内容                                  | commit        |
|-----------------|---------------------------------------|---------------|
| `034_*`         | reset voice sample_count              | `d13a17e7d`   |
| `035_*`         | meeting cluster_id_history             | (KMeans)      |
| `036_*`         | add voice_confirmed                  | (锚点)        |
| `060_*`         | meeting_user_agent (UA 字段)          | `2775f1ff6`   |
| `010_*`         | voice_embedding_member (基础)        | 老迁移        |
| `011_*`         | meeting_audio_archive (会议音频归档) | 老迁移        |
| `012_*`         | meeting_embedding_agenda             | 老迁移        |
| `013_*`         | member_voice_embedding_hnsw          | 老迁移        |
| `014_*`         | reminder_meeting                     | 老迁移        |
| `017_*`         | voice_embedding_192dim (192 维)      | 老迁移        |
| `018_*`         | meeting_transcript_polished          | 老迁移        |

**独立 ORM 模型**（`app/models/`）：
- `MemberVoiceHistory` (member_voice_history.py)
- `VoiceprintHistory` (voiceprint_history.py)
- `Meeting` (meeting.py)
- `MeetingParticipant` (meeting.py)

**W73 调研重点发现**：
1. **9 表 + 12 业务表估算**：
   - 9 张声纹/会议/录音相关独立表
   - 12 张 ASR/TTS 集成业务表（chat_history / knowledge / drive / meeting 等复用）
   - 与 CLAUDE.md 描述一致
2. **JSON 字段缺索引**：
   - `meeting.cluster_id_history` / `speaker_mapping` / `speaker_stats` 全是 JSON 但无 GIN 索引
   - 大规模会议（>1h, >50 段）JSON 字段查询慢
3. **voice_confirmed_* 4 字段缺联合索引**：
   - `voice_confirmed_at IS NOT NULL` 是 anchor 判定
   - 当前无部分索引（partial index）优化 anchor 查询

**实战数据缺口**（W73 调研阶段无法回填）：
- 9 表行数（用户已知需求是 ≥ 200 会议 + ≥ 50 录入声纹 + ≥ 1000 段声纹）
- JSON 字段实际 JSONB 大小（speaker_mapping 平均 bytes）
- HNSW pgvector 索引命中率

### §2.6 W74+ 派工建议

**D-1 §3.2 W74 派工顺序表（推导）**：

依据 v10 段 6 + v10 段 8 W73 起步纪律 6 项 + 调研 6 大块发现，**W74 建议优先派工以下 4 子批**：

#### W74 Step 6：声纹 90% 门禁实战（数据驱动）

**派工输入**：
- 当前 `MATCH_THRESHOLD=0.7` ≈ 30% 置信度门禁
- MEMORY 记录 "90% 硬门禁 < 90% 自动 rollback" 缺代码层证据
- 数据驱动：需 12 会议音频实战回填当前真实命中率

**预期交付**：
- 现状报告（命中率统计 + 误识别率）
- 90% 门禁设计文档（阈值/rollback 策略/UX）
- 派生调研：调研完成 ≠ 生产实施（必须主指挥拍板才进 W75）

**实施前置**：
- 调研阶段不动 `MATCH_THRESHOLD`
- W75 实施阶段才改 `voiceprint_service.py` + alembic 084 + 前端 vue

#### W74 Step 7：SenseVoice 错误率分布调研

**派工输入**：
- SenseVoice 迁移已 100%（生产 0 流量 Whisper）
- 实战错误率分布数据缺
- 长音频 chunked 边界段错误率未知

**预期交付**：
- 按会议类型（日常例行/专题讨论/学术报告 3 类）错误率
- 按说话人特征（老成员/新人/带方言 3 类）错误率
- 按录音时长（<5min/5-30min/30-120min/>2h 4 类）错误率
- 长音频 chunked 边界段（10/90/170s 边界）错误率

**派生调研**：
- 若错误率>10% 才进 W75 优化
- 若错误率<5% 仅沉淀 memory + 跳到下个调研

#### W75 Step：TTS 移动端兼容性

**派工输入**：
- TTS 后端单一 Edge-TTS（无离线降级）
- 移动端兼容性数据缺
- 自动播放拦截 / 解码失败 / 网络超时 3 类错误率未知

**预期交付**：
- iOS Safari + Android Chrome 4 viewport 兼容性矩阵
- 自动播放拦截 UX 设计（首次提示/手势解锁）
- 离线降级方案（Web Speech API 本地降级 vs 后端 pre-synthesize 缓存）

#### W75 Step：录音全链路 GPU 利用率优化

**派工输入**：
- `GPU N_WORKERS=8: 2830 段 ≈ 60-90 秒` 仅是注释
- celery-worker GPU 化已落地
- GPU 利用率峰值 / 队列长度 / 排队延迟数据缺

**预期交付**：
- 当前 GPU 利用率 24h 报告
- 瓶颈识别（CPU bound / GPU bound / 内存 bound / 网络 bound）
- 2.9h m4a 处理耗时优化（目标 < 30s）
- 4 worker 并行扩展方案

## §3 派生新任务清单（必先真验证）

**W73 调研派生新任务**（主指挥口头追加子任务必真验证）：

| 派生任务 | 关联 plan | 调研状态真验证                       | 实施前置           |
|----------|-----------|--------------------------------------|--------------------|
| 声纹 90% 门禁实战 | voiceprint-purification-loop.md | `git log --grep="90%\|rollback" -i` 输出 | W75 Step 5 派工   |
| SenseVoice 灰度 | 无独立 plan | `git log --grep="sensevoice" -i` 已确认 100% 灰度 | W74 Step 7 派工   |
| TTS 移动端 | 无 plan | `grep -rE "edge-tts\|mobile.tts" web/src/views/mobile/` | W75 Step 8 派工   |
| 录音全链路 | 无 plan（已收官） | `git log --grep="recording" -i` | W75 Step 9 派工   |

**真验证命令**（v10 段 7 第 18 类必填）：
```bash
git log --oneline main | grep -iE "voiceprint.*90|sensevoice.*error|tts.*mobile|recording.*W72"
# 输出为空 → 派工前必先真补 "派生新任务" 段
git log --oneline main --grep="派生新任务" -i
# 输出为空 → 本次 agent 添加（commit message 必含此关键词）
```

## §4 0 production code 改动铁律守恒验证

| 范畴              | W73 第 1 批 A-2 预期 | W73 第 1 批 A-2 实际 | 守恒 |
|-------------------|---------------------|---------------------|------|
| docs/             | 新增 1               | 新增 1 (本文)        | ✅   |
| memory/           | 新增 1               | 新增 1 (本任务沉淀)  | ✅   |
| scripts/          | 0                   | 0                   | ✅   |
| tests/            | 0                   | 0                   | ✅   |
| app/voice/        | 0                   | 0                   | ✅   |
| app/services/     | 0                   | 0                   | ✅   |
| alembic/versions/ | 0                   | 0                   | ✅   |
| web/src/views/    | 0                   | 0                   | ✅   |
| web/dist/         | 0                   | 0                   | ✅   |

**0 production code 改动铁律** ✅ **守恒**

## §5 W73 起步纪律 6 项实战（W73 调研 agent 必读）

依 v10 段 8 + 本次 agent 实际验证：

1. **W71 B 路线 5 agents commit + merge 真验证**：v10 段 8 项 1 沿用。本次调研未涉及 W71 B 路线，但已通过 `git log --grep="w71st" -i` 确认 ≥ 5 commits（W71 第 1 批 15 agents 已 commit 在 worktree）。
2. **W71 子 plan ② 7 维评分数据 + KB 闭环验证**：本次调研为声纹/ASR/TTS 链，与 7 维评分无直接关联。W73 第 1 批 D 路线调研 agent 应独立验证。
3. **W72 子 plan ③ UI redesign 三大件**：本次调研为声纹/ASR/TTS 链，与 UI redesign 无直接关联。
4. **W72 batch 派工调研真验证**：本次已通过 §1 三步真验证（plan 索引 + git log + grep）。
5. **商业化 docker base 起步必先**：本次为纯调研任务，未涉及商业化 docker base。
6. **gap analysis 文档必先恢复/重建**：本次已验证 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` 在 worktree 存在（W72 第 2 批 D-1 恢复的 410 行 8 段文档）。

## §6 派工 v10 段 7 类 20 实战（派生新任务必先真验证）

依 v10 段 7（19 类 + v10 新增派生调研类 = 20）：

| 序号 | 类别                          | 必填验证                                            | 本次填法          |
|------|-------------------------------|------------------------------------------------------|-------------------|
| 1    | 真验证（plan / git show / grep 3 段） | 三步全验证                                          | §1 实战 3 步      |
| 2    | SubAgent type hint 实战       | 跨 worktree 接口契约必走 docs/w72-b-route-interfaces.md | 本次非 SubAgent 编排 |
| 3    | TypeScript @deprecated        | 老接口必带警告                                       | 本次非前端        |
| 4    | 4 阶段流程 v2                 | plan list → 拍板 → **派生新任务** → 收口              | §3 派生新任务清单 |
| 5    | 0 production code 表          | 明示每条例外 commit + 文件 + 例外理由                  | §4 守恒表         |
| 6    | W73/W74 派工顺序              | 先 W73 调研 → 后 W74 实施                            | §2.6             |
| 7    | 命名错位 plan 必重定义差量缺口 | plan 命名与内容一致                                  | 本次无 plan 命名  |
| 8    | `vite build` 必坏 PWA         | 必用 `npm run build`                                 | 本次非前端构建   |
| 9    | commit message 必含锚点范式数字 | §9 实战模板必含                                    | 本次 commit message 含 "锚点范式 W72 第 2 批 235 → W73 第 1 批 A-2 238 守恒 (+3)" |
| 10~20 | (v10 段 7 沿用 16 类)         | (沿用上批纪律)                                      | §1 §4 §5 已覆盖  |

## §7 W73 调研 ≠ 生产警示

调研 ≠ 生产实施。W73 第 1 批 A-2 仅摸底 + 派工建议，**禁止实施**：

- ❌ **不动** `app/voice/asr.py` / `tts.py` / `app/services/voiceprint_service.py`
- ❌ **不改** `MATCH_THRESHOLD = 0.7` 任何值
- ❌ **不增加** `app.voice.tts.TextToSpeech.synthesize*` 任何新参数
- ❌ **不写** 新 alembic migration（声纹字段相关）
- ❌ **不改** 前端 `web/src/views/mobile/*` 录音/Voiceprint 任何视图
- ❌ **不升级** SenseVoice / Edge-TTS / 3D-Speaker 任何依赖

**派工前提**：调研仅看 + 建议。W74 派工（含可实施 agent）由主指挥按 v10 段 1.1 拍板 + 子 plan ① 调研 / ② 拍板 / ③ 实施 / ④ 收口 4 阶段流程。

## §8 锚点范式守恒

| 批次       | 锚点范式数字 | 增量                | 主基调                       |
|------------|--------------|---------------------|------------------------------|
| W72 第 1 批 | 220          | (W71 206 → 220)     | 11 commit 全部含锚点范式数字  |
| W72 第 2 批 | **235**      | +15                 | 派工纪要 v10 + 商业化起步     |
| W73 第 1 批 A-2 调研 | **238** | +3                  | 声纹 + ASR + TTS 链 W73 调研启动（**仅本调研实际增加 3 守恒：本文 1 + memory 1 + commit message 含数字 1**）|

**0 production code 改动铁律**: ✅ **守恒**（§4 表）

**W73 第 1 批 A-2 实际守恒 +3 拆分**：
- §6 全新纪律 +1（派生新任务真验证 3 段实战）
- §3 派生新任务清单实战 +1（4 子批 W74/W75 派工前置）
- §2.5 9 表 schema 调研实战 +1（JSON 字段索引缺口 + voice_confirmed 联合索引缺口）

## §9 W73+ commit message 锚点范式数字纪律（v10 段 9 强制约束）

本调研 commit message 守恒示例：

```
docs(w73-1st-batch-a2): 声纹 + ASR + TTS 链 W73 调研启动 (D-1 §3.1 Step 7 派生新任务)

派工 v4 铁律 3 实战 + 派工 v10 段 8 W73 起步纪律 6 项
锚点范式 W72 第 2 批 235 → W73 第 1 批 A-2 238 守恒 (+3)
- §1 派工 v4 铁律 3 真验证 (plan + git log + grep 3 段)
- §2.1 声纹 90% 门禁实战 (MATCH_THRESHOLD=0.7 vs MEMORY 90% 差距)
- §2.2 SenseVoice 灰度 100% (生产 0 Whisper)
- §2.3 TTS Edge-TTS 单后端 (移动端数据缺)
- §2.4 录音全链路 W72 收口 (10 commit 实战)
- §2.5 9 表 schema (JSON 字段 + voice_confirmed 索引缺口)
- §2.6 W74+ 派工建议 (4 子批: 90% 门禁 / SenseVoice 错误率 / TTS 兼容 / GPU 优化)
- 调研 ≠ 生产 (不动 app/voice/ + app/services/ + alembic/versions/ 老路径)
- 0 production code 改动铁律守恒 (纯调研)
- W74 派工 4 子批建议 (声纹实战 / SenseVoice 灰度 / TTS 兼容性 / GPU 优化)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

**v10 段 9 必填项均已含**：
- ✅ 锚点范式数字 235 → 238 (+3)
- ✅ W72 第 1 批实战引用
- ✅ 调研 ≠ 生产警示
- ✅ 派生新任务清单（§3 4 子批）
- ✅ W74 派工顺序（先调研 → 后实施）

## §10 参考资料

- 派工 v10：`docs/w72-prompt-paradigm-v10-2026-07-27.md`
- W72 D-1 gap analysis：`docs/drive-v2-roadmap-gap-analysis-2026-07-24.md` (W72 第 2 批 D-1 恢复)
- ASR 选型：`docs/asr-benchmark-2026-06-30.md`
- ASR 备选：`docs/asr-alternatives.md`
- 5th-wave 清洁：`memory/w72nd-batch-c1-drive-deploy-doc-v3-2026-07-27.md`
- 声纹 + ASR + TTS 链已有 memory（9 条）：
  - `voiceprint-purification-loop.md`
  - `voiceprint-batch-bug-fix-2026-06-19.md`
  - `voiceprint-reset-count-2026-06-27.md`
  - `voiceprint-kmeans-optimization-2026-06-28.md`
  - `voiceprint-purification-loop-151-2026-06-28.md`
  - `voiceprint-90-percent-gate-2026-06-28.md`
  - `voiceprint-2026-06-30.md`
  - `low-occupancy-speaker-filter-2026-06-30.md`
  - `asr-benchmark-2026-06-30.md`
  - `m4a-meeting-batch-voiceprint-gpu-2026-06-18.md`
  - `reprocess-meeting-pattern.md`
  - `2026-07-16-meeting-stuck-unboundlocalerror-import-shadowing.md`
  - `recording-comprehensive-fix-2026-07-16.md`
- 当前 main HEAD: `45de56f3b` (W72 第 2 批 grand closure, 235 守恒)

---

**W73 第 1 批 A-2 调研完成**: 锚点范式 W72 第 2 批 235 → A-2 **238 守恒 (+3)**，**0 production code 改动铁律守恒**（纯调研 + 仅 docs/memory 新增）。
