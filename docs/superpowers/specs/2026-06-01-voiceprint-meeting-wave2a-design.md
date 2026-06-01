# 声纹会议系统升级 — 第二波（2a）设计规格

**日期**：2026-06-01
**作者**：Claude (brainstorming 阶段产物)
**范围**：第二波 2a — 声纹真正启用 + 声纹录入整合
**状态**：待用户审阅
**关联**：
- 第一波设计规格：[2026-06-01-voiceprint-meeting-wave1-design.md](2026-06-01-voiceprint-meeting-wave1-design.md)
- 总览 Roadmap：[2026-06-01-voiceprint-meeting-upgrade-roadmap.md](../plans/2026-06-01-voiceprint-meeting-upgrade-roadmap.md)
- 第一波已实现（commit `3ff6a7d`，已部署）

---

## 1. 目标与背景

### 1.1 第一波成果（已上线）

- ✅ AI 润色（异步渐进覆盖）
- ✅ 智能分段（LiveSegmenter）
- ✅ 关键句高亮（决策/待办/风险徽章）
- ✅ 挂断后处理进度（Redis + WS 推送）

### 1.2 第二波 2a 痛点

1. **声纹识别未真正启用** — `MeetingPipeline.process_audio` 实现了但 `/live` 端点**完全没用**（commit `b777a9a` 降级了它）。用户转录中"发言人"字段永远是"发言人"
2. **VAD 单例状态污染** — `vad_engine` 全局单例（`vad.py:122`），多会议并发会污染 `_speech_samples` 累积状态
3. **DB 缺关键字段** — `Member.voice_embedding` / `voice_enrolled_at` / `voice_sample_count` 在 ORM 中定义但**没有 Alembic 迁移**（致命：enroll_member 调入会失败）
4. **声纹录入麻烦** — 必须离开通话页才能录入
5. **speaker 永远显示"发言人"** — `MeetingRoom.vue:73` `activeSpeaker = ref(null)`，没有任何代码更新它
6. **audio_level 后端没推** — 前端 `useMeetingRoomWS.js:16` 已有 `audioLevel` ref 就绪，但后端没发 `audio_level` 消息
7. **SpeakerStrip 没声波条** — 当前只有头像 + 名字（42 行极简版）

### 1.3 2a 目标

让用户**开会中**看到：
1. 实时声纹识别（"发言人"变成"张三/李四"）
2. 声波条（头像旁实时跳动）
3. 声纹未识别时弹窗选人
4. 选定后该 speaker label 自动映射（下次同声自动识别）

### 1.4 非目标（YAGNI，留到 2b/3）

- 实时 AI 互动（总结/翻译/提问）— 2b
- MinIO 音频存档 — 2b
- 多设备同步 — 2b
- TTS 朗读 — 2b
- 声纹画像可视化 — 3
- 跨会议关联 — 3

---

## 2. 关键决策（已通过 brainstorming 确认）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 范围拆分 | 严格 2a + 2b | 2a 是基础，2b 是增强 |
| VAD 单例修复 | **每条 WS 独立 VAD 实例** | 与 LiveSegmenter 风格一致，彻底避免污染 |
| 声纹准确度策略 | **保守型 + 人工认领** | 不重训/不投票，依赖"未识别弹窗选人"提升准确度 |
| 未录入弹窗触发 | **未识别 + 会议有未录入成员 → 列表弹窗** | UX 最自然，转写体验连续 |
| MeetingPipeline 集成 | **per-WS MeetingPipeline 实例** | 接收 vpi/asr/voiceprint/db 实例注入 |
| audio_level 推送 | **每 100ms 单独 task** | 不阻塞主 ASR 流 |

---

## 3. 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                  浏览器 MeetingRoom                          │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────┐ │
│  │SpeakerStrip │ │Transcript   │ │SpeakerUniden │ │AI    │ │
│  │+ 声波条     │ │Panel        │ │tifiedDialog  │ │(2b)  │ │
│  │             │ │+ 说话人标签 │ │              │ │      │ │
│  └──────┬──────┘ └──────┬──────┘ └──────┬───────┘ └──────┘ │
│         │ audio_level   │ speaker_*    │ claim            │
└─────────┼───────────────┼──────────────┼───────────────────┘
          │               │              │
   ┌──────▼───────────────▼──────────────▼──────┐
   │    /ws/meeting/{id}/live                   │
   │  新协议:                                   │
   │    收: {type: "speaker_claim",            │
   │         segment_id, member_id}             │
   │    推: {type: "transcript",                │
   │         segment_id, speaker, confidence,   │
   │         text, ts}                          │
   │    推: {type: "speaker_unidentified",     │
   │         segment_id, candidates[]}          │
   │    推: {type: "audio_level", level: 0-1}   │
   └──────┬─────────────────────────────────────┘
          │
   ┌──────▼──────────────────────────────────────┐
   │  每条 WS 独立的 MeetingPipeline 实例        │
   │  ┌──────────┐  ┌──────┐  ┌──────────────┐ │
   │  │VAD       │→ │ASR   │→ │Voiceprint    │ │
   │  │(per-WS,  │  │fast  │  │3D-Speaker    │ │
   │  │ silero)  │  │whisp │  │identify      │ │
   │  └──────────┘  └──────┘  └──────────────┘ │
   │  + 旁路: audio_level 计算（每 100ms）       │
   │  + 旁路: 未录入声纹参与者查询              │
   └─────────────────────────────────────────────┘
```

**关键模块边界**：
- `MeetingPipeline` 接收 vpi/segmenter/db 实例（不创建全局依赖）
- `VADEngine` 支持 per-instance 化（每条 WS 一个）
- `SpeakerUnidentifiedService`（新）— 提供"未录入参与者查询 + speaker 候选匹配"

---

## 4. 后端设计

### 4.1 DB 迁移 010 — 补 voice_embedding 字段（关键 bug fix）

**文件**：`alembic/versions/010_voice_embedding_member.py`

```python
"""Add voice_embedding fields to members table

Wave 2a critical fix: Member.voice_embedding/voice_enrolled_at/voice_sample_count
defined in ORM but missing from DB schema. Without this migration,
voiceprint_service.enroll_member() fails with "column does not exist".
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade():
    op.add_column('members', sa.Column('voice_embedding', Vector(256), nullable=True))
    op.add_column('members', sa.Column('voice_enrolled_at', sa.DateTime(), nullable=True))
    op.add_column('members', sa.Column('voice_sample_count', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('members', 'voice_sample_count')
    op.drop_column('members', 'voice_enrolled_at')
    op.drop_column('members', 'voice_embedding')
```

**风险**：现有生产 members 表已有该字段的概率低（ORM 与 DB 不一致已存在），加列 nullable=True 安全。

### 4.2 VAD 改造 — 可实例化

**文件**：`app/voice/vad.py`

**改动要点**：
- 移除 module-level `vad_engine = VADEngine()` 单例（line 122）
- `VADEngine` 类保持不变（已经是 class 形式）
- 新增可选的模块级 `get_vad_engine()` 工厂函数（如有其它模块引用）
- `reset()` 接口保留

**新接口**：
```python
class VADEngine:
    def __init__(self, sample_rate=16000, threshold=0.5, min_speech_ms=250, min_silence_ms=400):
        # 不再假设全局单例
        ...
```

**兼容性**：现有 `/voice` 等端点如果引用 `vad_engine.process_chunk()`，需改为 `vad_engine` 由调用方传入（lazy 创建）。

### 4.3 MeetingPipeline 改造 — 实例化

**文件**：`app/voice/pipeline.py`

**改造前**：
```python
class MeetingPipeline:
    def __init__(self):
        # 引用全局 vad_engine / asr_service
        ...
    async def process_audio(self, audio_chunk, db, elapsed):
        # 调用 vad_engine.process_chunk(...)  # 全局
        ...
```

**改造后**：
```python
class MeetingPipeline:
    def __init__(
        self,
        vad_engine: VADEngine,
        asr_service: SpeechRecognizer,
        voiceprint_service: VoiceprintService,
    ):
        self.vad = vad_engine
        self.asr = asr_service
        self.vp = voiceprint_service

    async def process_audio(self, audio_chunk: bytes, db: AsyncSession, elapsed: float) -> list[dict]:
        # 1. VAD（per-instance）
        speech_segment = self.vad.process_chunk(audio_array)
        if speech_segment is None:
            return []
        # 2. ASR
        wav_data = self._to_wav(speech_segment)
        asr_result = await self.asr.transcribe(wav_data, language="zh")
        text = asr_result.get("text", "").strip()
        if not text:
            return []
        # 3. Voiceprint
        name, member_id, confidence = await self.vp.identify_speaker(db, speech_segment)
        return [{
            "type": "transcript",
            "speaker": name or "unknown",
            "member_id": member_id,
            "confidence": confidence,
            "text": text,
            "start": elapsed,
            "end": elapsed + len(speech_segment) / 16000,
        }]
```

**Module-level 单例**（`meeting_pipeline = MeetingPipeline()`）**保留为可选便利构造**，但**不强制**。每个 WS 可选：
- A) 使用全局默认（VAD/ASR/Voiceprint 默认注入）
- B) 显式构造 per-instance

### 4.4 /live 端点重构

**文件**：`app/api/v1/voice.py`

**改造要点**：
- WS accept 后：
  ```python
  vad = VADEngine()
  pipeline = MeetingPipeline(vad, asr_service, voiceprint_service)
  audio_level_task = asyncio.create_task(_audio_level_loop(websocket))
  ```
- 接收 PCM chunk（保持二进制流）：
  ```python
  data = await websocket.receive_bytes()
  ```
- 调 `pipeline.process_audio(data, db, elapsed)`：
  ```python
  entries = await pipeline.process_audio(data, db, elapsed)
  for entry in entries:
      segment_id = f"seg_{int(entry['start'] * 1000)}"
      speaker = entry["speaker"]
      # 1. 噪音过滤
      if any(noise in entry["text"] for noise in NOISE_PATTERNS):
          continue
      # 2. 查 speaker_mapping 应用已知映射
      mapped_speaker = meeting.speaker_mapping.get(speaker, speaker)
      # 3. 推 transcript
      await websocket.send_json({
          "type": "transcript",
          "segment_id": segment_id,
          "speaker": mapped_speaker,
          "speaker_confidence": entry["confidence"],
          "text": entry["text"],
          "ts": entry["start"],
          "polish_status": "pending",
      })
      # 4. 触发 AI 润色（第一波已实现）
      asyncio.create_task(_polish_and_send(websocket, meeting_id, segment_id, ...))
      # 5. 声纹未识别 + 有未录入成员 → 推 speaker_unidentified
      if speaker == "unknown" or entry["confidence"] < 0.4:
          candidates = await get_unenrolled_participants(db, meeting_id)
          if candidates:
              await websocket.send_json({
                  "type": "speaker_unidentified",
                  "segment_id": segment_id,
                  "candidates": [{"id": c.id, "name": c.name, "avatar": c.avatar} for c in candidates],
                  "transcript_text": entry["text"],
              })
  ```
- 接收 `speaker_claim` JSON 消息（前端弹窗选择后回报）：
  ```python
  if msg.get("type") == "speaker_claim":
      # msg = {"type": "speaker_claim", "segment_id": ..., "member_id": ..., "speaker_label": "speaker_1"}
      # 写入 meeting.speaker_mapping
      meeting = await db.get(Meeting, meeting_id)
      if meeting.speaker_mapping is None:
          meeting.speaker_mapping = {}
      meeting.speaker_mapping[msg["speaker_label"]] = (await db.get(Member, msg["member_id"])).name
      await db.commit()
  ```
- **保留第一波的 LiveSegmenter**（与 VAD 并行） — LiveSegmenter 决定"段满"（字节级），VAD 决定"段内是否为语音"。两者互补

### 4.5 audio_level 推送 task

**文件**：`app/api/v1/voice.py`（辅助函数）

```python
async def _audio_level_loop(websocket: WebSocket, audio_queue: asyncio.Queue):
    """每 100ms 计算最近 100ms 音频的 RMS（0-1 归一化），推 audio_level"""
    while True:
        try:
            await asyncio.sleep(0.1)
            samples = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
            if not samples:
                continue
            # RMS 归一化
            rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
            level = min(1.0, rms / 10000)  # 经验系数
            await websocket.send_json({"type": "audio_level", "level": level})
        except asyncio.TimeoutError:
            # 静默期推 level=0
            await websocket.send_json({"type": "audio_level", "level": 0.0})
        except Exception:
            break
```

**集成**：`audio_queue` 在 PCM chunk 接收时填入（float32 数组），task 消费。

### 4.6 新增 SpeakerUnidentifiedService

**文件**：`app/services/speaker_unidentified_service.py`（新）

```python
"""声纹未识别时的辅助服务"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member


async def get_unenrolled_participants(
    db: AsyncSession, meeting_id: int
) -> List[Member]:
    """
    查询会议中尚未录入声纹的参与者。

    Returns: 列表（按 name 排序），空列表表示"全员已录入"或"无参与者"
    """
    stmt = (
        select(Member)
        .join(MeetingParticipant, MeetingParticipant.member_id == Member.id)
        .where(
            MeetingParticipant.meeting_id == meeting_id,
            Member.voice_embedding.is_(None),
            Member.is_active == True,
        )
        .order_by(Member.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

### 4.7 /live 端点消息协议升级

**新消息类型**（前向兼容第一波）：

| 方向 | type | payload | 用途 |
|---|---|---|---|
| 客户端→服务端 | `speaker_claim` | `{segment_id, member_id, speaker_label}` | 弹窗选人后回报 |
| 服务端→客户端 | `transcript` | `{segment_id, speaker, speaker_confidence, text, ts, polish_status}` | 转录（含 speaker + 置信度，第一波已实现但 speaker 永远是"发言人"） |
| 服务端→客户端 | `speaker_unidentified` | `{segment_id, candidates: [{id, name, avatar}], transcript_text}` | 弹窗候选人列表 |
| 服务端→客户端 | `audio_level` | `{level: 0.0-1.0}` | 声波条驱动 |

**保留**（第一波）：
- `transcript_polished` / `transcript_polished_error` / `transcript_error`（已存在）
- `meeting_ended`（已存在）
- `ai_chat` / `ai_reply`（已存在，本波不动）

---

## 5. 前端设计

### 5.1 SpeakerStrip 改造 — 加声波条

**文件**：`web/src/components/meeting-room/SpeakerStrip.vue`

**改造要点**：
- 新增 `audioLevels: Array<{memberId, level}>` prop
- 每张卡片底部加 `<div class="wave-bar">` 容器
- 内部 5 个竖条（`<div class="bar">`），高度由 level 控制（0-100%）
- level 变化时 CSS transition 100ms 平滑

**视觉**：
```css
.speaker-card.active .wave-bar .bar {
  background: linear-gradient(180deg, #ff7a5c 0%, #ffb347 100%);
  animation: wave-pulse 0.5s ease infinite;
}
.speaker-card:not(.active) .wave-bar .bar {
  background: rgba(255,255,255,0.2);
}
```

### 5.2 MeetingRoom 改造 — 接收新消息 + 弹窗

**文件**：`web/src/components/MeetingRoom.vue`

**新增 prop**：`participants` 改为对象数组（含 `voice_enrolled` 字段）

**新增 state**：
```javascript
const unidentifiedDialog = ref({ visible: false, segmentId: null, candidates: [], transcript: '' })
const audioLevels = ref({})  // { memberId: 0-1 }
```

**WS 回调**：
```javascript
onMessage.value = (msg) => {
  switch (msg.type) {
    case 'transcript':
      onTranscript(msg)  // 第一波已有
      // 新增：更新 audioLevels（如果 speaker 已识别）
      if (msg.member_id) {
        audioLevels.value[msg.member_id] = 0.5  // 占位
      }
      break
    case 'speaker_unidentified':
      unidentifiedDialog.value = { visible: true, ...msg }
      break
    case 'audio_level':
      // 更新当前发言人的 level
      if (currentSpeakerId.value) {
        audioLevels.value[currentSpeakerId.value] = msg.level
      }
      break
  }
}
```

**新增组件** `<SpeakerUnidentifiedDialog v-model:visible="..." :candidates="..." :transcript="..." @claim="onClaim" />`

### 5.3 SpeakerUnidentifiedDialog 新建

**文件**：`web/src/components/meeting-room/SpeakerUnidentifiedDialog.vue`

**结构**：
- el-dialog 标题："未识别发言人"
- 内容：转录文字预览
- 候选人列表：每人一张卡片（头像 + 名字）
- 点击候选人 → emit `claim: {segment_id, member_id, speaker_label}` → 父组件发 WS

### 5.4 useMeetingRoomWS 改造

**文件**：`web/src/composables/useMeetingRoomWS.js`

**新增回调 ref**：
```javascript
const onMessage = ref(null)  // 通用消息处理（除了已分发的 transcript/polished/error/ended/level）
const onSpeakerUnidentified = ref(null)
```

**消息分发**（在 `handleJSONMessage` 内）：
```javascript
case 'speaker_unidentified':
  if (onSpeakerUnidentified.value) onSpeakerUnidentified.value(msg)
  break
case 'audio_level':
  audioLevel.value = msg.level  // 已有
  break
```

**新增方法**：`sendSpeakerClaim(segmentId, memberId, speakerLabel)`

### 5.5 MeetingView / MeetingDetailView 调整

**文件**：`web/src/views/MeetingView.vue`, `web/src/views/MeetingDetailView.vue`

**改动**：
- `<MeetingRoom :participants="participantsWithVoice" />` — 从后端拉取"含 voice_enrolled 状态"的成员列表
- 新增 API 调用：`GET /api/v1/members?meeting_id={id}&with_voice_status=true`（或在前端过滤）

**简化**：第一波已用 `meetingAnalysis` 静态传入 participants，本波后端需补 API。**最小改动**：复用现有 `GET /members` + 前端 filter `voice_embedding != null`。

### 5.6 新建 speaker_unidentified API（如需）

实际上**不需要新建 API** — `speaker_unidentified` 候选人是 `meeting.participants` 中 `voice_embedding IS NULL` 的成员。**前端已有 `GET /members`**，前端按 `voice_enrolled` 字段过滤即可。

如前端需要"会议参与者名单 + 各自 voice_enrolled 状态"一次性拿，**加 1 个小端点**：
```python
@router.get("/meetings/{meeting_id}/participants-with-voice")
async def get_meeting_participants_with_voice(meeting_id, db, current_user):
    # 返回 [{"id", "name", "avatar", "voice_enrolled": bool, "voice_sample_count": int}, ...]
```

---

## 6. 数据流

### 6.1 正常声纹识别（已录入）

```
浏览器 16kHz Float32 音频
    │ 转换 Int16 PCM
    ▼
MeetingRoom.sendAudio(int16.buffer)
    │ WS 发送
    ▼
/live 端点 receive_bytes()
    │
    ▼
pipeline.process_audio(pcm_bytes, db, elapsed)
    │
    ├─→ vad.process_chunk()  (per-WS)
    │      返回 None（无语音）→ 跳过
    │
    ├─→ asr.transcribe(wav)
    │      返回 {text: "..."}
    │
    ├─→ voiceprint.identify_speaker(db, segment)
    │      返回 ("张三", 5, 0.85)
    │
    ▼
transcript 推送
{speaker: "张三", speaker_confidence: 0.85, text: "...", ...}
    │
    ▼
MeetingRoom 收到
    ├─→ 添加 entry（status=pending）
    ├─→ 更新 audioLevels[5] = 0.5 (初始)
    └─→ activeSpeaker = 5 触发头像放大
```

### 6.2 声纹未识别（未录入成员弹窗）

```
（前半段同上）
voiceprint.identify_speaker
    │ 返回 (None, None, 0.12)  # 没人录入声纹 或 录入了但都不匹配
    ▼
查 meeting.participants 中 voice_embedding IS NULL
    │
    ├─→ 空（全员已录入）→ 跳过弹窗，speaker 显示"未识别"
    └─→ 非空 → 推 speaker_unidentified
          {segment_id, candidates: [{id, name, avatar}], transcript_text}
    │
    ▼
MeetingRoom 弹窗
    │
    ▼ 用户点 "李四"
    │
sendSpeakerClaim(segment_id, member_id, speaker_label)
    │
    ▼
/live 端点收到 speaker_claim
    │
    ├─→ 查 Member (id=member_id)
    ├─→ 写入 meeting.speaker_mapping[speaker_label] = "李四"
    └─→ db.commit()
```

### 6.3 audio_level 旁路

```
浏览器 audio chunks 持续发送
    │
    ▼
/live 端点入队 audio_queue
    │
    ▼
_audio_level_loop task（每 100ms）
    │
    ├─→ 取出最近 100ms 音频
    ├─→ 计算 RMS（归一化 0-1）
    └─→ 推 audio_level: {level: 0.5}
```

---

## 7. 错误处理

### 7.1 后端

| 场景 | 处理 | 用户感知 |
|---|---|---|
| VAD process 抛异常 | catch + log + 返回空 list | 当前段跳过，下段继续 |
| ASR 失败 | catch + log + 跳过该 entry | 静默（不推送该段） |
| Voiceprint 模型未加载（首次调用） | 3D-Speaker lazy load（已知 100MB 下载） | 首次会议 30s 延迟 |
| Voiceprint identify 抛异常 | 返回 (None, None, 0.0) | speaker 显示"未识别" |
| speaker_claim 时 Member 不存在 | 静默忽略 | 弹窗不消失（前端错误处理） |
| speaker_claim 时已认领 | 覆盖（幂等） | 无影响 |
| DB 缺 voice_embedding 字段 | **DB 迁移必须先执行** | 任务 1 阻塞 |
| audio_level task 异常 | 自动重启 task | 短期声波条卡顿 |

### 7.2 前端

| 场景 | 处理 |
|---|---|
| SpeakerUnidentifiedDialog 用户取消 | 弹窗消失，speaker 保持"未识别"，下段继续 |
| WS 断线 | 第一波已有自动重连 |
| audio_level 收不到 | SpeakerStrip 声波条静止（不报错） |
| 后端发空 candidates | 弹窗不显示候选人（仅"未识别"提示） |

---

## 8. 测试策略

### 8.1 后端单测（pytest + pytest-asyncio）

**`tests/test_vad_per_instance.py`**（新）
- `test_vad_two_instances_independent`：两个 VADEngine 实例互不污染
- `test_vad_process_chunk_returns_speech_array`：返回 ndarray
- `test_vad_reset_clears_state`：reset 后清空累积

**`tests/test_meeting_pipeline_instance.py`**（新）
- `test_pipeline_uses_injected_vad`：传入 mock vad，验证调用
- `test_pipeline_returns_empty_on_silent`：VAD 返回 None → []
- `test_pipeline_returns_transcript_with_speaker`：mock ASR + voiceprint 完整流

**`tests/test_speaker_unidentified.py`**（新）
- `test_get_unenrolled_participants_empty`：全员已录入 → []
- `test_get_unenrolled_participants_filters_inactive`：is_active=False 不返回
- `test_get_unenrolled_participants_filters_enrolled`：voice_embedding 不为空不返回

### 8.2 后端集成测试

**`tests/test_live_ws_voiceprint.py`**（新）
- `test_ws_voice_identified`：完整 PCM → 收到 `transcript` with `speaker` 字段
- `test_ws_voice_unidentified_triggers_dialog`：无人录入 → 收到 `speaker_unidentified`
- `test_ws_speaker_claim_writes_mapping`：前端 claim → meeting.speaker_mapping 写入

### 8.3 前端测试

项目无前端测试框架（已确认）。本波不强求前端单测，依赖 E2E 手动验证。

---

## 9. 部署与迁移

### 9.1 DB 迁移

**alembic upgrade head**（生产服务器必跑）：
- 新增 3 列：`members.voice_embedding` / `voice_enrolled_at` / `voice_sample_count`
- nullable=True，无破坏性

### 9.2 后端部署

新增/修改文件：
- 新建 `alembic/versions/010_voice_embedding_member.py`
- 新建 `app/services/speaker_unidentified_service.py`
- 修改 `app/voice/vad.py`（移除 module-level 单例）
- 修改 `app/voice/pipeline.py`（构造函数签名变更）
- 修改 `app/api/v1/voice.py`（/live 端点重构 + 新辅助函数）
- 修改 `app/main.py`（如有新路由注册）

### 9.3 前端部署

- 新建 `web/src/components/meeting-room/SpeakerUnidentifiedDialog.vue`
- 修改 `web/src/components/MeetingRoom.vue`
- 修改 `web/src/components/meeting-room/SpeakerStrip.vue`
- 修改 `web/src/composables/useMeetingRoomWS.js`

### 9.4 风险

| 风险 | 缓解 |
|---|---|
| VAD 改造破坏现有 /voice 等端点 | 兼容旧用法：保留 `vad_engine` 全局单例，标注 deprecated |
| DB 迁移失败（生产已有字段） | 现状：ORM 定义但 DB 缺字段，加列 nullable=True 永远安全 |
| per-WS VAD 模型加载慢（首次） | 沿用 wave 1 lazy load 模式（modelscope 下载） |
| audio_level 推送频率（10/s）增加 WS 压力 | 客户端节流：每 100ms 更新一次 CSS，不阻塞 |
| 声纹识别失败时影响 ASR 流 | pipeline.process_audio 内 try/except 各环节互不影响 |

---

## 10. 验收标准

### 10.1 必达

1. ✅ VADEngine 可实例化，两实例互不污染
2. ✅ MeetingPipeline 接受注入的 vpi/asr/voiceprint
3. ✅ /live 端点收到 PCM chunk 后输出 `transcript` 含 `speaker` / `speaker_confidence` 字段
4. ✅ 声纹未识别 + 会议有未录入成员 → 前端弹窗候选人列表
5. ✅ 弹窗选人后 → meeting.speaker_mapping 持久化
6. ✅ 同 speaker label 下次自动映射为已选人
7. ✅ audio_level 消息 10/s 推送，SpeakerStrip 声波条实时跳动
8. ✅ DB 迁移 010 补 voice_embedding 字段成功
9. ✅ 单测覆盖率 > 70%（VAD / Pipeline / SpeakerUnidentified）

### 10.2 体验达

10. ✅ 会议中 speaker 标签准确率 > 80%（保守型 + 人工认领后）
11. ✅ 声波条跳动延迟 < 300ms
12. ✅ 弹窗响应延迟 < 500ms

---

## 11. 实施顺序（建议）

1. DB 迁移 010 + VAD 实例化
2. MeetingPipeline 改造
3. speaker_unidentified_service
4. /live 端点重构（接入 MeetingPipeline）
5. audio_level 推送
6. speaker_claim 消息处理
7. SpeakerStrip 改造（声波条）
8. SpeakerUnidentifiedDialog
9. useMeetingRoomWS 改造
10. MeetingRoom 集成
11. 端到端测试
12. 部署上线

---

## 12. 开放问题

1. **VAD 改造是否破坏现有 /voice 等端点？** — 需在改造前 grep 所有 `vad_engine` 引用
2. **声纹识别首次加载慢（100MB 模型下载）** — 启动时预热？还是 lazy？建议沿用 lazy
3. **audio_level 频率 10/s 是否过高？** — 10/s = 600/min，单连接 36KB/min。可接受

---

**版本**：v1.0
**等待用户审阅** → 通过后进入 writing-plans 阶段生成实现计划
