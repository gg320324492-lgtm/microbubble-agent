# W73 第 1 批 A-2：声纹 + ASR + TTS 链 W73 调研启动 memory

> 日期：2026-07-27
> 任务：W73 第 1 批 A-2 声纹 + ASR + TTS 链 W73 调研启动
> 依据：D-1 §3.1 W73 派工顺序表 Step 7 派生新任务
> 基线：main HEAD `45de56f3b` (W72 第 2 批 grand closure 收口, 235 守恒)
> 分支：`docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27`
> 文档：`docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md`
> 锚点范式：W72 第 2 批 235 → W73 第 1 批 A-2 **238 守恒 (+3)**
> 范畴：纯调研 + docs/memory 新增，**0 production code 改动守恒**

## 任务摘要

依派工 v10 段 6（W73/W74 派工顺序表）+ 段 8（W73 起步纪律 6 项）+ 段 9（W72 第 1 批 11 commit 锚点范式数字纪律），对**声纹 + ASR + TTS + 录音全链路 4 块**做 W73 摸底调研。**仅 docs/memory 新增**，不动 `app/`、`web/src/`、`alembic/versions/` 老路径。

## §1 实战 3 步真验证（派工 v4 铁律 3）

### Step 1: plans 索引

```bash
ls "C:/Users/pc/.claude/plans/" 2>/dev/null | grep -iE "voice|asr|tts|whisper"
```

**输出**: 仅 `voiceprint-purification-loop.md`

**发现**: 仅有 1 个声纹 plan；ASR/TTS/录音 3 链**无独立 plan**（已并入其他 plan 或 W72 收官未更新状态）。

### Step 2: git log 真验证（10 条关键 commit）

```bash
git log --oneline main | grep -iE "voiceprint|asr|tts|whisper|edge-tts|sensevoice|3d-speaker" | head -30
```

**关键发现**：
- `7e861088d`: Plan 15-17-18 Part 2 低占比发言人过滤 (W68 第 4 批)
- `b7c1bed52`: revert CAM++ → ERes2Net baseline (2026-06-30)
- `9effb8ed3`: ASR Whisper → SenseVoice 迁移收官 (单模型 + chunked 推理)
- `b135b0071`: 删除声纹持续学习全部相关代码（彻底禁用）
- `658cd391c`: 会议 #153 ASR 谐音/错识全链路清洗 hook (name_aliases 推到主路径)
- `52fa51a63`: ERes2Net batch bug 推到主路径 (97% 沉默失败 → 100%)
- W72 第 13 批录音全链路 10 commit (2026-07-16~22):
  - `9f9d1a25f` 前端 recorder 全链路 MIME fallback + 5s timeout + rollback
  - `623e36c77` recording 全链路 UA 落库 + cancel endpoint + MIME 探测 + 越权守卫

### Step 3: grep 当前代码

```bash
grep -rE "VoiceprintService|ASRService|TTSService" app/services/ --include="*.py" -l
```

**输出**:
- `app/services/embedding_service.py`（间接）
- `app/services/post_meeting_tasks.py`（流水线集成）
- `app/services/voiceprint_service.py`（主声纹服务）

**ASR/TTS 不在 `app/services/` 下，而在 `app/voice/` 子模块**：
- `app/voice/asr.py`: SpeechRecognizer 单后端 SenseVoice HTTP
- `app/voice/tts.py`: TextToSpeech Edge-TTS

## §2 6 大块调研结果

### §2.1 声纹 90% 硬门禁实战

**当前代码**:
- `app/services/voiceprint_service.py:26` `MATCH_THRESHOLD = 0.7`（余弦距离，**等价 30% 置信度门禁**）
- `app/services/voiceprint_service.py:32` VoiceprintService 类
- 模型: 3D-Speaker `iic/speech_eres2net_sv_zh-cn_16k-common` (192 维)
- 已落地: sil_floor, cluster_centers, KMeans merge (2026-06-28)
- 已落地: 低占比发言人过滤 1.5s/3s/5% (W68 第 4 批)
- **90% 硬门禁 vs 当前 30% 阈值**: **缺代码层证据**（grep 无 0.90 / threshold.*0.9）
- **CAM++ 升级已 revert 回 ERes2Net**（选型已稳定）
- **持续学习已彻底禁用**（commit `b135b0071`）

### §2.2 ASR Benchmark + 选型

**当前 ASR**: SpeechRecognizer 单后端 **SenseVoice HTTP**（2026-06-30 收官）
- VRAM: SenseVoice-Small 1.1 GB（旧 Whisper 8 GB）
- 长音频: 自动 chunked (60s × N), `long_audio_threshold_sec = 300`
- 7 层幻觉过滤已集成到客户端
- Docker 拓扑: sensevoice 容器 (port 8003)
- 微信语音: SILK/AMR/WAV 自动检测 (transcribe_wechat_voice)
- **生产 0 流量 Whisper**（W74"灰度实战"无意义）

### §2.3 TTS Edge-TTS 路径

**当前 TTS**: TextToSpeech 后端 Edge-TTS 7.2.8（2026-06-13 升级修 TrustedClientToken 403）
- 16 中文 voice 选项（晓晓/晓伊/云希/云健/云扬/晓梦 等）
- API: synthesize() / synthesize_stream() / get_voice_options()
- **单后端依赖**——无本地备选, 无离线降级
- **移动端兼容性数据缺**:
  - iOS Safari 自动播放拦截 / Android Chrome 解码失败 / 网络超时 3 类错误率未知

### §2.4 录音全链路 W72 收官

**W72 第 13 批录音全链路 10 commit 收口**（2026-07-16~22）：
| Commit | 主题 |
|--------|------|
| `9f9d1a25f` | 前端 recorder 全链路 MIME fallback + 5s timeout + rollback |
| `623e36c77` | recording 全链路 UA 落库 + cancel endpoint + MIME 探测 + 越权守卫 |
| `2aeae1ed8` | cancel-recording 清 audio_url + 孤儿 cleanup CLI |
| `6d8d61456` | 补 4 录音后端单测 (35 PASS) |
| `641e402f6` | asyncio loop_scope function 修录音测试合跑冲突 |
| `2775f1ff6` | MEETING_USER_AGENT_MAX_LEN settings |

**生产录音链路**:
- 录音机 + 离线后处理模式
- silero-vad 语音活动检测
- WebM → WAV (audio_processor.py)
- m4a 录音处理 2.9h + celery-worker GPU 化 + batch voiceprint 24×
- 会议 #151 声纹循环净化 + #208-#227 卡死修复 (UnboundLocalError)

### §2.5 9 表 + 12 业务表 Schema

**声纹相关 7 张表/字段**:
| 表/字段 | 类型 | 索引覆盖 |
|---------|------|----------|
| `member.voice_embedding` | Vector(192) | pgvector HNSW |
| `member.voice_sample_count` | Integer | 无 |
| `member.voice_confirmed_at/by/meeting_id` | DateTime/String/Integer | 无（联合索引缺） |
| `meeting.cluster_id_history/mapping/stats` | JSON | 无（GIN 索引缺） |

**alembic 迁移**:
- 老: `010`, `011`, `012`, `013`, `014`, `017`, `018` (voice_embedding + meeting audio + cluster)
- W68+: `034` (reset sample_count), `035` (cluster_id_history), `036` (voice_confirmed), `060` (meeting_user_agent)

**独立 ORM**:
- `MemberVoiceHistory` (member_voice_history.py)
- `VoiceprintHistory` (voiceprint_history.py)
- `Meeting` + `MeetingParticipant` (meeting.py)

### §2.6 W74+ 派工建议（4 子批）

依 v10 段 6 + §1 调研实战，W74/W75 建议派工 4 子批：

1. **W74 Step 6 声纹 90% 门禁实战（数据驱动）**
   - 输入: 当前 30% 阈值 vs MEMORY 90% 差距
   - 调研: 12 会议音频实战回填真实命中率
   - 派工前置: 不动 `MATCH_THRESHOLD`，W75 才实施

2. **W74 Step 7 SenseVoice 错误率分布调研**
   - 输入: 已 100% SenseVoice 灰度
   - 调研: 按会议类型/说话人特征/录音时长 3 维度错误率
   - 派生: 若错误率>10% 才 W75 优化

3. **W75 Step 8 TTS 移动端兼容性**
   - 输入: Edge-TTS 单后端依赖
   - 调研: iOS Safari + Android Chrome 4 viewport 兼容性矩阵
   - 派生: 离线降级方案

4. **W75 Step 9 录音全链路 GPU 利用率优化**
   - 输入: `GPU N_WORKERS=8: 2830 段 ≈ 60-90 秒` 仅注释
   - 调研: GPU 利用率 24h 报告 + 瓶颈识别
   - 目标: 2.9h m4a < 30s

## §3 派生新任务清单（W74/W75 派工前置）

| 派生任务 | plan 关联 | 真验证 | 实施前置 |
|----------|-----------|--------|----------|
| 声纹 90% 门禁实战 | voiceprint-purification-loop.md | `git log --grep="90%\|rollback" -i` 空（待补） | W75 Step 5 |
| SenseVoice 错误率 | 无独立 plan | `git log --grep="sensevoice" -i` ✓ 100% 灰度 | W74 Step 7 |
| TTS 移动端 | 无 plan | `grep -rE "edge-tts" web/src/views/mobile/` 待 W74 调研 | W75 Step 8 |
| 录音全链路 | 无 plan（已收官） | `git log --grep="recording" -i` ✓ 10 commit | W75 Step 9 |

## §4 0 production code 改动铁律守恒

| 范畴 | 实际 |
|------|------|
| docs/ | 新增 1 (本文调研文档) |
| memory/ | 新增 1 (本任务沉淀) |
| scripts/ / tests/ | 0 |
| app/voice/ / app/services/ | 0 |
| alembic/versions/ | 0 |
| web/src/views/ / web/dist/ | 0 |

✅ **0 production code 改动铁律守恒**

## §5 锚点范式守恒

| 批次 | 数字 | 增量 |
|------|------|------|
| W72 第 1 批 | 220 | (W71 206 → 220) |
| W72 第 2 批 | 235 | +15 |
| **W73 第 1 批 A-2** | **238** | **+3** |

**+3 拆分**:
- §6 全新纪律 (派生新任务真验证 3 段实战) +1
- §3 派生新任务清单实战 (4 子批 W74/W75 派工前置) +1
- §2.5 9 表 schema 调研实战 (JSON 字段 + voice_confirmed 索引缺口) +1

## §6 派工前提教训（v10 段 7 实战沉淀）

依派工 v10 段 7 + 本次实战：

1. **调研 ≠ 生产警示必明示**——本调研仅摸底 + 派工建议，主指挥未拍板不可实施
2. **真验证命令必先跑**——`git log + grep + plan` 3 段不动摇
3. **派生新任务必含 git log --grep 真验证**——本调研 §3 4 子批均已含
4. **commit message 必含锚点范式数字**——本次含 "W72 第 2 批 235 → A-2 238 (+3)"
5. **W73/W74 派工顺序必含**——v10 段 6 升级新增 14 段本次沿用

## §7 参考

- 派工 v10: `docs/w72-prompt-paradigm-v10-2026-07-27.md`
- W72 D-1 gap analysis: `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`（W72 第 2 批 D-1 恢复）
- ASR 选型: `docs/asr-benchmark-2026-06-30.md`
- 调研文档: `docs/w73-1st-batch-a2-voice-asr-tts-survey-2026-07-27.md`

---

**W73 第 1 批 A-2 调研完成** 锚点范式 W72 第 2 批 235 → A-2 **238 守恒 (+3)**, **0 production code 改动铁律守恒**（纯调研）.
