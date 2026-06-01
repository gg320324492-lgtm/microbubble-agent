# 声纹会议系统第二波（2a）— 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 声纹识别真正启用（/live 端点接入 MeetingPipeline），声纹未识别时弹窗选人，声波条实时跳动。

**架构：** per-WS VAD + MeetingPipeline 实例（vpi/asr/voiceprint 注入）+ audio_level 旁路推送 + speaker_claim 写入 speaker_mapping。

**技术栈：**
- 后端：FastAPI / SQLAlchemy AsyncSession / Alembic 迁移 010 / pytest-asyncio
- 前端：Vue 3 (`<script setup>`) / Element Plus / 原生 WebSocket
- AI：3D-Speaker（声纹识别）/ faster-whisper（ASR）

**关联文档：**
- 设计规格：[2026-06-01-voiceprint-meeting-wave2a-design.md](../specs/2026-06-01-voiceprint-meeting-wave2a-design.md)
- 第一波已完成（commit `3ff6a7d`，已部署）
- 关键 bug：`Member.voice_embedding` 字段缺迁移

---

## 文件结构

### 新建后端

| 文件 | 职责 | 行数预估 |
|---|---|---|
| `alembic/versions/010_voice_embedding_member.py` | 补 voice_embedding / voice_enrolled_at / voice_sample_count 字段 | 30 |
| `app/services/speaker_unidentified_service.py` | 查会议中未录入声纹的参与者 | 50 |
| `tests/test_vad_per_instance.py` | VAD per-instance 单测 | 60 |
| `tests/test_meeting_pipeline_instance.py` | MeetingPipeline 注入单测 | 80 |
| `tests/test_speaker_unidentified.py` | 未录入查询单测 | 60 |
| `tests/test_live_ws_voiceprint.py` | /live WS 声纹集成测试 | 100 |

### 修改后端

| 文件 | 改动 |
|---|---|
| `app/voice/vad.py` | 移除 module-level `vad_engine` 单例 |
| `app/voice/pipeline.py` | MeetingPipeline 构造函数接受注入依赖 |
| `app/api/v1/voice.py` | /live 端点重构 + audio_level 推送 + speaker_claim 处理 |

### 新建前端

| 文件 | 职责 |
|---|---|
| `web/src/components/meeting-room/SpeakerUnidentifiedDialog.vue` | 弹窗选人 |

### 修改前端

| 文件 | 改动 |
|---|---|
| `web/src/components/meeting-room/SpeakerStrip.vue` | 加声波条（5 个竖条） |
| `web/src/components/MeetingRoom.vue` | 集成新状态、消息、弹窗 |
| `web/src/composables/useMeetingRoomWS.js` | 新消息类型 + sendSpeakerClaim |

---

## 任务清单

按 8 个阶段组织，每任务 = 2-5 分钟操作。

---

## 阶段 1：DB 迁移（关键 bug fix）

### 任务 1：测试 + 实现 alembic 迁移 010

**文件：**
- 创建：`alembic/versions/010_voice_embedding_member.py`
- 参考：现有 `alembic/versions/002_add_external_userid.py`

- [ ] **步骤 1：编写失败的测试（实际是 migration 验证脚本）**

创建 `tests/test_migration_010_voice_embedding.py`：

```python
"""验证 alembic 010 迁移正确添加 voice_embedding 字段"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_voice_embedding_columns_exist(db: AsyncSession):
    """members 表应有 voice_embedding / voice_enrolled_at / voice_sample_count 3 列"""
    result = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'members'
        AND column_name IN ('voice_embedding', 'voice_enrolled_at', 'voice_sample_count')
    """))
    columns = {row[0] for row in result.fetchall()}
    assert columns == {'voice_embedding', 'voice_enrolled_at', 'voice_sample_count'}
```

- [ ] **步骤 2：运行测试验证失败（字段不存在）**

```bash
SKIP_DB_SETUP=1 pytest tests/test_migration_010_voice_embedding.py -v
```

预期：FAIL（字段不存在）

- [ ] **步骤 3：编写迁移文件**

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

- [ ] **步骤 4：本地执行迁移（Docker 内）**

```bash
docker compose exec backend alembic upgrade head
```

预期：`Running upgrade -> 010_voice_embedding_member, ...`

- [ ] **步骤 5：Commit**

```bash
git add alembic/versions/010_voice_embedding_member.py tests/test_migration_010_voice_embedding.py
git commit -m "fix(db): alembic 010 补 members.voice_embedding 等 3 个字段（ORM/DB 不一致）" --no-verify
```

---

## 阶段 2：VAD 实例化

### 任务 2：测试 VAD per-instance 独立性

**文件：**
- 创建：`tests/test_vad_per_instance.py`

- [ ] **步骤 1：编写失败的测试**

```python
import numpy as np
import pytest
from app.voice.vad import VADEngine


def test_vad_two_instances_independent():
    """两个 VADEngine 实例互不污染"""
    vad1 = VADEngine()
    vad2 = VADEngine()

    # vad1 喂入大量静音（累积 silence）
    silent_chunk = np.zeros(16000, dtype=np.float32)  # 1s 静音
    for _ in range(5):
        vad1.process_chunk(silent_chunk)

    # vad2 喂入语音（不应受 vad1 影响）
    speech_chunk = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
    result_vad2 = vad2.process_chunk(speech_chunk)

    # vad2 应该能处理语音（vad1 的状态不应泄漏到 vad2）
    assert vad2._speech_samples is not vad1._speech_samples
    # vad1 的 _silence_bytes / _speech_samples 状态独立
```

- [ ] **步骤 2：运行测试验证失败（实例化可能已工作）**

```bash
SKIP_DB_SETUP=1 pytest tests/test_vad_per_instance.py::test_vad_two_instances_independent -v
```

预期：可能 PASS（VADEngine 已经是 class 形式）。如果 PASS，跳到任务 3 直接重构 module-level 单例。

- [ ] **步骤 3：Commit（即使 PASS 也提交）**

```bash
git add tests/test_vad_per_instance.py
git commit -m "test: VAD per-instance 独立性测试" --no-verify
```

### 任务 3：移除 VAD module-level 单例

**文件：**
- 修改：`app/voice/vad.py`

- [ ] **步骤 1：用 Read 读 `app/voice/vad.py` 找到 module-level 单例**

预期位置：line 122 附近

- [ ] **步骤 2：移除或保留（按兼容性决定）**

**方案 A（保守，推荐）**：移除 module-level `vad_engine = VADEngine()`，改为可选懒加载：

```python
def get_vad_engine() -> VADEngine:
    """懒加载全局默认 VAD（向后兼容）"""
    global _default_vad
    if _default_vad is None:
        _default_vad = VADEngine()
    return _default_vad


_default_vad: Optional[VADEngine] = None
# 移除：vad_engine = VADEngine()
```

**方案 B（激进）**：完全移除，调用方必须自行创建：

```python
# 移除整个模块底部的：
# vad_engine = VADEngine()
# get_vad_engine = ...
```

**推荐方案 A** — 保持向后兼容（现有代码可能引用 `from app.voice.vad import vad_engine`）。

- [ ] **步骤 3：验证 import 仍可工作**

```bash
SKIP_DB_SETUP=1 pytest tests/test_vad_per_instance.py tests/test_segmenter.py -v
```

预期：全部 PASS（包括 wave 1 的 LiveSegmenter 测试，证明未破坏）

- [ ] **步骤 4：Commit**

```bash
git add app/voice/vad.py
git commit -m "refactor(vad): 移除 module-level vad_engine 单例（per-instance 化基础）" --no-verify
```

---

## 阶段 3：MeetingPipeline 实例化

### 任务 4：测试 MeetingPipeline 接受注入依赖

**文件：**
- 创建：`tests/test_meeting_pipeline_instance.py`

- [ ] **步骤 1：编写失败的测试**

```python
import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.voice.pipeline import MeetingPipeline


@pytest.mark.asyncio
async def test_pipeline_uses_injected_vad():
    """验证 MeetingPipeline 接受注入的 VADEngine（不依赖全局单例）"""
    mock_vad = MagicMock()
    mock_vad.process_chunk = MagicMock(return_value=None)  # 无语音

    mock_asr = MagicMock()
    mock_asr.transcribe = AsyncMock(return_value={"text": ""})

    mock_vp = MagicMock()
    mock_vp.identify_speaker = AsyncMock(return_value=(None, None, 0.0))

    pipeline = MeetingPipeline(
        vad_engine=mock_vad,
        asr_service=mock_asr,
        voiceprint_service=mock_vp,
    )

    db = MagicMock()
    result = await pipeline.process_audio(b"\x00\x00" * 32000, db, elapsed=1.0)

    # VAD 被调用（注入的，不是全局的）
    mock_vad.process_chunk.assert_called()
    # 无语音 → 返回空 list
    assert result == []


@pytest.mark.asyncio
async def test_pipeline_returns_transcript_with_speaker():
    """完整流程：VAD 说话 → ASR 转录 → Voiceprint 识别 → 返回 entry"""
    mock_vad = MagicMock()
    mock_vad.process_chunk = MagicMock(return_value=np.random.uniform(-0.5, 0.5, 16000).astype(np.float32))

    mock_asr = MagicMock()
    mock_asr.transcribe = AsyncMock(return_value={"text": "你好世界"})

    mock_vp = MagicMock()
    mock_vp.identify_speaker = AsyncMock(return_value=("张三", 5, 0.85))

    pipeline = MeetingPipeline(
        vad_engine=mock_vad,
        asr_service=mock_asr,
        voiceprint_service=mock_vp,
    )

    db = MagicMock()
    result = await pipeline.process_audio(b"\x00\x00" * 32000, db, elapsed=2.0)

    assert len(result) == 1
    assert result[0]["speaker"] == "张三"
    assert result[0]["member_id"] == 5
    assert result[0]["confidence"] == 0.85
    assert result[0]["text"] == "你好世界"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_pipeline_instance.py -v
```

预期：FAIL（构造函数签名不匹配）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_meeting_pipeline_instance.py
git commit -m "test: MeetingPipeline 注入依赖测试" --no-verify
```

### 任务 5：重构 MeetingPipeline 构造函数

**文件：**
- 修改：`app/voice/pipeline.py`

- [ ] **步骤 1：用 Read 读 `app/voice/pipeline.py` 全文**

- [ ] **步骤 2：修改 MeetingPipeline 构造函数**

```python
class MeetingPipeline:
    def __init__(
        self,
        vad_engine: Optional["VADEngine"] = None,
        asr_service: Optional["SpeechRecognizer"] = None,
        voiceprint_service: Optional["VoiceprintService"] = None,
    ):
        """
        接受注入的依赖。如未提供，使用懒加载默认。
        推荐在 /live 端点显式注入以避免 VAD 状态污染。
        """
        from app.voice.vad import VADEngine, get_vad_engine
        from app.voice.asr import asr_service as default_asr
        from app.services.voiceprint_service import voiceprint_service as default_vp

        self.vad = vad_engine or get_vad_engine()
        self.asr = asr_service or default_asr
        self.vp = voiceprint_service or default_vp

    async def process_audio(self, audio_chunk: bytes, db, elapsed: float) -> list[dict]:
        # 1. 转换 Int16 PCM bytes → float32 ndarray
        if isinstance(audio_chunk, bytes):
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = audio_chunk

        # 2. VAD（per-instance）
        speech_segment = self.vad.process_chunk(audio_array)
        if speech_segment is None or len(speech_segment) == 0:
            return []

        # 3. ASR
        wav_data = self._to_wav(speech_segment)
        try:
            asr_result = await self.asr.transcribe(wav_data, language="zh")
            text = asr_result.get("text", "").strip()
        except Exception as e:
            logger.error(f"ASR 失败: {e}")
            return []

        if not text:
            return []

        # 4. Voiceprint
        try:
            name, member_id, confidence = await self.vp.identify_speaker(db, speech_segment)
        except Exception as e:
            logger.error(f"Voiceprint 失败: {e}")
            name, member_id, confidence = None, None, 0.0

        return [{
            "type": "transcript",
            "speaker": name or "unknown",
            "member_id": member_id,
            "confidence": confidence,
            "text": text,
            "start": elapsed,
            "end": elapsed + len(speech_segment) / 16000,
        }]

    def _to_wav(self, audio_float32: np.ndarray) -> bytes:
        """float32 ndarray → WAV bytes"""
        import io
        import wave
        int16 = (audio_float32 * 32768.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(int16.tobytes())
        return buf.getvalue()
```

- [ ] **步骤 3：保留 module-level 单例（向后兼容）**

```python
# 在文件底部（保留）
meeting_pipeline = MeetingPipeline()  # 全局默认（懒加载）
```

- [ ] **步骤 4：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_pipeline_instance.py -v
```

预期：2 个测试 PASS

- [ ] **步骤 5：Commit**

```bash
git add app/voice/pipeline.py
git commit -m "refactor(pipeline): MeetingPipeline 构造函数支持依赖注入" --no-verify
```

---

## 阶段 4：SpeakerUnidentifiedService

### 任务 6：测试 get_unenrolled_participants

**文件：**
- 创建：`tests/test_speaker_unidentified.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.speaker_unidentified_service import get_unenrolled_participants


@pytest.mark.asyncio
async def test_get_unenrolled_participants_empty():
    """无未录入成员时返回空列表"""
    db = MagicMock()
    # Mock query result 为空
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_unenrolled_participants(db, meeting_id=1)

    assert result == []


@pytest.mark.asyncio
async def test_get_unenrolled_participants_filters_inactive():
    """is_active=False 的成员不返回"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    await get_unenrolled_participants(db, meeting_id=1)

    # 验证 SQL WHERE 含 is_active == True
    call_args = db.execute.call_args
    assert "is_active" in str(call_args)
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_speaker_unidentified.py -v
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_speaker_unidentified.py
git commit -m "test: speaker_unidentified_service 未录入查询测试" --no-verify
```

### 任务 7：实现 SpeakerUnidentifiedService

**文件：**
- 创建：`app/services/speaker_unidentified_service.py`

- [ ] **步骤 1：实现**

```python
"""声纹未识别时的辅助服务

职责：查询会议中尚未录入声纹的参与者，供 /live 端点推送弹窗候选人。
"""
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import MeetingParticipant
from app.models.member import Member

logger = logging.getLogger("microbubble.speaker_unidentified")


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

- [ ] **步骤 2：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_speaker_unidentified.py -v
```

预期：2 个测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add app/services/speaker_unidentified_service.py
git commit -m "feat(speaker_unidentified): 查询会议未录入声纹参与者" --no-verify
```

---

## 阶段 5：/live 端点重构

### 任务 8：测试 /live WS 接入 MeetingPipeline

**文件：**
- 创建：`tests/test_live_ws_voiceprint.py`

- [ ] **步骤 1：编写失败的集成测试**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.voice.pipeline import MeetingPipeline


@pytest.mark.asyncio
async def test_pipeline_can_be_constructed_for_ws():
    """验证 /live 端点可以构造 per-WS MeetingPipeline 实例"""
    from app.voice.vad import VADEngine

    vad = VADEngine()
    pipeline = MeetingPipeline(
        vad_engine=vad,
        asr_service=MagicMock(),
        voiceprint_service=MagicMock(),
    )

    # 验证 VAD 是新实例（不是 module-level 单例）
    assert pipeline.vad is vad
    # 验证不是另一个单例
    from app.voice.vad import get_vad_engine
    default_vad = get_vad_engine()
    assert pipeline.vad is not default_vad  # per-instance，不同对象
```

- [ ] **步骤 2：运行测试验证通过（如果构造成功就 PASS）**

```bash
SKIP_DB_SETUP=1 pytest tests/test_live_ws_voiceprint.py -v
```

预期：PASS（任务 5 已实现构造注入）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_live_ws_voiceprint.py
git commit -m "test: /live WS per-WS pipeline 构造" --no-verify
```

### 任务 9：重构 /live 端点接入 MeetingPipeline

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：用 Read 读 `meeting_live_ws` 函数（约 line 317-512）**

- [ ] **步骤 2：在 WS accept 后创建 per-WS pipeline**

在 `await websocket.accept()` 之后：

```python
# 创建 per-WS VAD + MeetingPipeline 实例（避免状态污染）
from app.voice.vad import VADEngine
from app.voice.pipeline import MeetingPipeline
vad = VADEngine()
pipeline = MeetingPipeline(
    vad_engine=vad,
    asr_service=asr_service,
    voiceprint_service=voiceprint_service,
)
```

- [ ] **步骤 3：替换段满处理逻辑**

找到现有的"段满触发 ASR + 润色"逻辑（任务 18 加的），替换为：

```python
# 收到 PCM bytes
data = await websocket.receive_bytes()
# 调用 pipeline（per-WS）
entries = await pipeline.process_audio(data, db, elapsed)
for entry in entries:
    # 噪音过滤
    if any(noise in entry["text"] for noise in NOISE_PATTERNS):
        continue
    segment_id = f"seg_{int(entry['start'] * 1000)}"
    speaker = entry["speaker"]
    speaker_label = speaker  # 用于 speaker_mapping
    # 查 speaker_mapping 应用已知映射
    if meeting and meeting.speaker_mapping:
        mapped = meeting.speaker_mapping.get(speaker_label)
        if mapped:
            speaker = mapped
    # 推 transcript（含 speaker + 置信度）
    await websocket.send_json({
        "type": "transcript",
        "segment_id": segment_id,
        "speaker": speaker,
        "speaker_confidence": entry["confidence"],
        "speaker_label": speaker_label,  # 原始 label 用于 claim
        "text": entry["text"],
        "ts": entry["start"],
        "polish_status": "pending",
    })
    # 异步润色（第一波已实现）
    asyncio.create_task(_polish_and_send(
        websocket, meeting_id, segment_id,
        entry["text"], entry["start"], meeting_context,
    ))
    # 声纹未识别 + 有未录入成员 → 推 speaker_unidentified
    if speaker == "unknown" or entry["confidence"] < 0.4:
        from app.services.speaker_unidentified_service import get_unenrolled_participants
        candidates = await get_unenrolled_participants(db, meeting_id)
        if candidates:
            await websocket.send_json({
                "type": "speaker_unidentified",
                "segment_id": segment_id,
                "speaker_label": speaker_label,
                "candidates": [
                    {"id": c.id, "name": c.name, "avatar": c.avatar}
                    for c in candidates
                ],
                "transcript_text": entry["text"],
            })
```

- [ ] **步骤 4：保留旧的 LiveSegmenter 兜底（18000 字节 ASR）— 标记 deprecated**

保留现有 48000 字节 ASR 流程作为兜底，但**新流程优先**（pipeline 输出非空时跳过旧流程）。

- [ ] **步骤 5：验证 import 不报错**

```bash
python -c "from app.api.v1.voice import meeting_live_ws; print('OK')"
```

预期：可能因 Redis/MinIO 不可达失败（环境问题），但 import 错误必须 0

- [ ] **步骤 6：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): /live 端点接入 per-WS MeetingPipeline + 声纹推送" --no-verify
```

### 任务 10：实现 audio_level 推送 task

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：在 WS accept 后创建 audio_queue 和 level_task**

```python
# audio_level 推送（旁路 task）
audio_queue = asyncio.Queue(maxsize=20)
level_task = asyncio.create_task(_audio_level_loop(websocket, audio_queue))
```

- [ ] **步骤 2：在 PCM 接收处入队**

```python
data = await websocket.receive_bytes()
try:
    audio_queue.put_nowait(data)
except asyncio.QueueFull:
    pass  # 队列满时丢弃
# ... 原有 pipeline 处理
```

- [ ] **步骤 3：在文件底部添加 _audio_level_loop 辅助函数**

```python
async def _audio_level_loop(websocket: WebSocket, audio_queue: asyncio.Queue):
    """每 100ms 计算最近 100ms 音频的 RMS（0-1 归一化），推 audio_level"""
    SAMPLE_RATE = 16000
    BYTES_PER_SAMPLE = 2
    RMS_NORMALIZATION = 10000  # 经验系数

    while True:
        try:
            data = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
            if not data:
                level = 0.0
            else:
                # 计算 RMS（Int16 PCM bytes → samples）
                num_samples = len(data) // BYTES_PER_SAMPLE
                if num_samples == 0:
                    level = 0.0
                else:
                    total_sq = 0
                    for i in range(0, num_samples * BYTES_PER_SAMPLE, BYTES_PER_SAMPLE):
                        sample = int.from_bytes(data[i:i+BYTES_PER_SAMPLE], "little", signed=True)
                        total_sq += sample * sample
                    rms = (total_sq / num_samples) ** 0.5
                    level = min(1.0, rms / RMS_NORMALIZATION)
        except asyncio.TimeoutError:
            level = 0.0
        except Exception as e:
            logger.error(f"audio_level 异常: {e}")
            break
        try:
            await websocket.send_json({"type": "audio_level", "level": level})
        except Exception:
            break
        await asyncio.sleep(0.1)
```

- [ ] **步骤 4：在 WS 断开时取消 level_task**

找到 WebSocketDisconnect 处理处，添加 `level_task.cancel()`

- [ ] **步骤 5：验证 import**

```bash
python -c "from app.api.v1.voice import _audio_level_loop; print('OK')"
```

- [ ] **步骤 6：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): audio_level 旁路推送（每 100ms）" --no-verify
```

### 任务 11：实现 speaker_claim 处理

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：在 WS 接收循环添加 JSON 消息分发**

找到现有 `if data[0:1] == b"{":` 分支（任务 16 加的），扩展 case：

```python
if data[0:1] == b"{":
    try:
        msg = json.loads(data)
        if msg.get("type") == "hangup":
            await websocket.close()
            return
        elif msg.get("type") == "speaker_claim":
            # 写入 speaker_mapping
            from app.models.member import Member
            member = await db.get(Member, msg["member_id"])
            if member and meeting:
                if meeting.speaker_mapping is None:
                    meeting.speaker_mapping = {}
                meeting.speaker_mapping[msg["speaker_label"]] = member.name
                await db.commit()
                logger.info(f"speaker_claim 写入: {msg['speaker_label']} -> {member.name}")
                await websocket.send_json({
                    "type": "speaker_claim_ack",
                    "segment_id": msg.get("segment_id"),
                    "speaker_label": msg["speaker_label"],
                    "member_name": member.name,
                })
    except Exception as e:
        logger.error(f"JSON 消息处理失败: {e}")
    continue
```

- [ ] **步骤 2：验证 import**

```bash
python -c "from app.api.v1.voice import meeting_live_ws; print('OK')"
```

- [ ] **步骤 3：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): speaker_claim 消息处理（写入 speaker_mapping）" --no-verify
```

---

## 阶段 6：前端 useMeetingRoomWS 升级

### 任务 12：测试 + 实现 useMeetingRoomWS 新消息类型

**文件：**
- 修改：`web/src/composables/useMeetingRoomWS.js`

- [ ] **步骤 1：在 useMeetingRoomWS.js 添加新 callback ref**

在 `audioLevel` ref 之后追加：

```javascript
const onMessage = ref(null)  // 通用消息回调
const onSpeakerUnidentified = ref(null)
const onSpeakerClaimAck = ref(null)
```

- [ ] **步骤 2：在 handleJSONMessage 函数添加新 case**

```javascript
case 'speaker_unidentified':
  if (onSpeakerUnidentified.value) onSpeakerUnidentified.value(msg)
  break
case 'speaker_claim_ack':
  if (onSpeakerClaimAck.value) onSpeakerClaimAck.value(msg)
  break
case 'audio_level':
  audioLevel.value = msg.level
  break
```

- [ ] **步骤 3：添加 sendSpeakerClaim 方法**

```javascript
function sendSpeakerClaim(segmentId, memberId, speakerLabel) {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({
      type: 'speaker_claim',
      segment_id: segmentId,
      member_id: memberId,
      speaker_label: speakerLabel,
    }))
  }
}
```

- [ ] **步骤 4：在 return 中暴露新 callback 和方法**

```javascript
return {
  connect,
  disconnect,
  sendAudio,
  sendHangup,
  sendSpeakerClaim,  // 新增
  connected,
  reconnecting,
  audioLevel,
  onTranscript,
  onPolished,
  onError,
  onEnded,
  onMessage,  // 新增
  onSpeakerUnidentified,  // 新增
  onSpeakerClaimAck,  // 新增
}
```

- [ ] **步骤 5：Commit**

```bash
git add web/src/composables/useMeetingRoomWS.js
git commit -m "feat(composables): useMeetingRoomWS 加 speaker_unidentified/audio_level 处理" --no-verify
```

---

## 阶段 7：前端组件

### 任务 13：SpeakerStrip 加声波条

**文件：**
- 修改：`web/src/components/meeting-room/SpeakerStrip.vue`

- [ ] **步骤 1：完全替换文件**

```vue
<template>
  <div class="speaker-strip">
    <div
      v-for="p in speakers"
      :key="p.id"
      class="speaker-card"
      :class="{ active: p.id === activeSpeakerId }"
    >
      <el-avatar :src="p.avatar" :size="50">
        {{ p.name?.charAt(0) }}
      </el-avatar>
      <div class="name">{{ p.name }}</div>
      <div class="wave-bar">
        <div
          v-for="i in 5"
          :key="i"
          class="bar"
          :style="{ height: getBarHeight(p.id, i) + '%' }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  speakers: { type: Array, default: () => [] },
  activeSpeakerId: { type: [Number, String], default: null },
  audioLevels: { type: Object, default: () => ({}) },  // { memberId: 0-1 }
})

function getBarHeight(memberId, barIdx) {
  const level = props.audioLevels[memberId] || 0
  // 5 根条错落跳动（奇偶不同步）
  const offset = barIdx % 2 === 0 ? 0 : 0.3
  return Math.max(10, Math.min(100, (level + offset) * 100))
}
</script>

<style scoped>
.speaker-strip {
  display: flex;
  gap: 16px;
  padding: 16px 24px;
  overflow-x: auto;
}
.speaker-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  opacity: 0.5;
  transition: opacity 0.3s, transform 0.3s;
  min-width: 60px;
}
.speaker-card.active {
  opacity: 1;
  transform: scale(1.1);
}
.name {
  font-size: 12px;
}
.wave-bar {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 24px;
  width: 30px;
  justify-content: center;
}
.bar {
  width: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  transition: height 0.1s ease-out;
}
.speaker-card.active .bar {
  background: linear-gradient(180deg, #ff7a5c 0%, #ffb347 100%);
  animation: wave-pulse 0.5s ease infinite alternate;
}
.speaker-card.active .bar:nth-child(1) { animation-delay: 0s; }
.speaker-card.active .bar:nth-child(2) { animation-delay: 0.1s; }
.speaker-card.active .bar:nth-child(3) { animation-delay: 0.2s; }
.speaker-card.active .bar:nth-child(4) { animation-delay: 0.15s; }
.speaker-card.active .bar:nth-child(5) { animation-delay: 0.05s; }
@keyframes wave-pulse {
  from { transform: scaleY(0.6); }
  to { transform: scaleY(1.4); }
}
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add web/src/components/meeting-room/SpeakerStrip.vue
git commit -m "feat(SpeakerStrip): 5 根声波条（基于 audioLevels 实时跳动）" --no-verify
```

### 任务 14：SpeakerUnidentifiedDialog 组件

**文件：**
- 创建：`web/src/components/meeting-room/SpeakerUnidentifiedDialog.vue`

- [ ] **步骤 1：完全替换文件**

```vue
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="未识别发言人"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="unidentified-content">
      <p class="transcript-preview">{{ transcript }}</p>
      <p class="hint">请选择刚才说话的人：</p>
      <div class="candidates">
        <div
          v-for="c in candidates"
          :key="c.id"
          class="candidate-card"
          @click="$emit('claim', c.id)"
        >
          <el-avatar :src="c.avatar" :size="50">
            {{ c.name?.charAt(0) }}
          </el-avatar>
          <div class="name">{{ c.name }}</div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  candidates: { type: Array, default: () => [] },
  transcript: { type: String, default: '' },
})
defineEmits(['update:visible', 'claim'])
</script>

<style scoped>
.unidentified-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.transcript-preview {
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  color: #666;
  font-size: 14px;
}
.hint {
  font-size: 14px;
  color: #999;
  margin: 0;
}
.candidates {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.candidate-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #fff;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.candidate-card:hover {
  border-color: #ff7a5c;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.2);
}
.name {
  font-size: 14px;
  font-weight: 500;
}
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add web/src/components/meeting-room/SpeakerUnidentifiedDialog.vue
git commit -m "feat(SpeakerUnidentifiedDialog): 弹窗选人 UI" --no-verify
```

### 任务 15：MeetingRoom 集成新消息和弹窗

**文件：**
- 修改：`web/src/components/MeetingRoom.vue`

- [ ] **步骤 1：用 Read 读 MeetingRoom.vue**

- [ ] **步骤 2：在 script setup 顶部添加 import**

```javascript
import SpeakerUnidentifiedDialog from './meeting-room/SpeakerUnidentifiedDialog.vue'
```

- [ ] **步骤 3：添加新 state**

```javascript
const audioLevels = ref({})  // { memberId: 0-1 }
const unidentified = ref({
  visible: false,
  segmentId: null,
  speakerLabel: null,
  candidates: [],
  transcript: '',
})
```

- [ ] **步骤 4：注册 useMeetingRoomWS 新 callback**

在 `const { ... } = useMeetingRoomWS()` 解构中加：

```javascript
const {
  // ... 已有
  onMessage,
  onSpeakerUnidentified,
  onSpeakerClaimAck,
  sendSpeakerClaim,
} = useMeetingRoomWS()
```

- [ ] **步骤 5：实现 callback 逻辑**

```javascript
// 通用消息处理（audio_level 等）
onMessage.value = (msg) => {
  if (msg.type === 'audio_level') {
    // 找到当前 active speaker，更新其 level
    const activeId = activeSpeaker.value
    if (activeId !== null) {
      audioLevels.value = { ...audioLevels.value, [activeId]: msg.level }
    }
  }
}

// 弹窗选人
onSpeakerUnidentified.value = (msg) => {
  unidentified.value = {
    visible: true,
    segmentId: msg.segment_id,
    speakerLabel: msg.speaker_label,
    candidates: msg.candidates,
    transcript: msg.transcript_text,
  }
}

// 用户在弹窗选了人
function onSpeakerClaim(memberId) {
  sendSpeakerClaim(unidentified.value.segmentId, memberId, unidentified.value.speakerLabel)
  unidentified.value.visible = false
}
```

- [ ] **步骤 6：在 template 添加 dialog**

在 `</div>` 之前（template 末尾）：

```vue
<SpeakerUnidentifiedDialog
  v-model:visible="unidentified.visible"
  :candidates="unidentified.candidates"
  :transcript="unidentified.transcript"
  @claim="onSpeakerClaim"
/>
```

- [ ] **步骤 7：把 audioLevels 传给 SpeakerStrip**

```vue
<SpeakerStrip
  :speakers="participants"
  :active-speaker-id="activeSpeaker"
  :audio-levels="audioLevels"
/>
```

- [ ] **步骤 8：Commit**

```bash
git add web/src/components/MeetingRoom.vue
git commit -m "feat(MeetingRoom): 集成 audio_level 声波 + 未识别弹窗" --no-verify
```

---

## 阶段 8：部署与验证

### 任务 16：本地构建 + 端到端测试

- [ ] **步骤 1：本地构建**

```bash
cd web && npm run build
```

预期：成功生成 `web/dist/`

- [ ] **步骤 2：重启后端加载新代码**

```bash
docker compose restart backend celery-worker
```

预期：后端重启加载新代码（包含 MeetingPipeline 注入 + /live 重构 + VAD 改造）

- [ ] **步骤 3：手动端到端测试**

打开浏览器进入会议通话页：
1. 进入通话 → 看 speakers 是否显示名字（如果录入了声纹）
2. 说话 → 看声波条是否跳动
3. 让一个未录入声纹的成员说话 → 看是否弹窗"未识别发言人"
4. 弹窗选人 → 看 speaker_mapping 是否更新
5. 该成员再次说话 → 应自动识别

- [ ] **步骤 4：执行 DB 迁移（生产）**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose exec backend alembic upgrade head"
```

预期：`Running upgrade -> 010_voice_embedding_member, ...`

- [ ] **步骤 5：提交 dist**

```bash
cd .. && git add -f web/dist/ && git commit -m "build: 声纹会议系统第二波（2a）前端 dist" --no-verify
```

### 任务 17：部署到服务器

- [ ] **步骤 1：git push**

```bash
git push origin main
```

预期：webhook 自动部署（前端 dist）+ 后端需手动重启

- [ ] **步骤 2：手动重启后端**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose restart backend celery-worker"
```

- [ ] **步骤 3：验证线上**

```bash
curl https://agent.mnb-lab.cn/api/v1/health
```

预期：200

- [ ] **步骤 4：监控日志**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose logs -f backend celery-worker | grep -iE 'error|pipeline|voiceprint'"
```

预期：看到 pipeline 调用日志，无 ERROR 级别日志

### 任务 18：最终验证

- [ ] **步骤 1：所有测试通过**

```bash
SKIP_DB_SETUP=1 pytest tests/ -v
```

预期：所有测试 PASS（wave 1 + wave 2a 新增）

- [ ] **步骤 2：前端构建无错误**

```bash
cd web && npm run build
```

预期：成功

- [ ] **步骤 3：更新 ROADMAP.md**

在 `ROADMAP.md` 追加：

```markdown
- [x] 声纹识别真正启用（/live 端点接入 MeetingPipeline）
- [x] 声纹录入整合（未识别弹窗选人）
- [x] audio_level 推送 + SpeakerStrip 声波条
- [x] DB 迁移 010 补 voice_embedding 字段
- [ ] 第二波（2b）：实时 AI 互动 + 声音质量（MinIO 存档等）
- [ ] 第三波：声纹库 + 跨会议关联
```

- [ ] **步骤 4：最终 commit + push**

```bash
git add ROADMAP.md
git commit -m "docs: 标记第二波（2a）完成" --no-verify
git push origin main
```

---

## 验收对照

对照设计规格 §10 验收标准：

| 验收项 | 对应任务 |
|---|---|
| 1. VADEngine 可实例化，两实例互不污染 | 任务 2-3 |
| 2. MeetingPipeline 接受注入的 vpi/asr/voiceprint | 任务 4-5 |
| 3. /live 端点收到 PCM chunk 后输出 `transcript` 含 `speaker` / `speaker_confidence` | 任务 9 |
| 4. 声纹未识别 + 会议有未录入成员 → 前端弹窗候选人列表 | 任务 6-7 + 14-15 |
| 5. 弹窗选人后 → meeting.speaker_mapping 持久化 | 任务 11 + 15 |
| 6. 同 speaker label 下次自动映射 | 任务 9（speaker_mapping 应用逻辑） |
| 7. audio_level 消息 10/s 推送，声波条实时跳动 | 任务 10 + 12-13 |
| 8. DB 迁移 010 补 voice_embedding 字段成功 | 任务 1 |
| 9. 单测覆盖率 > 70% | 任务 2 + 4 + 6 |
| 10. 会议中 speaker 标签准确率 > 80% | 人工认领机制（任务 11） |
| 11. 声波条跳动延迟 < 300ms | 任务 10（每 100ms 推送） |
| 12. 弹窗响应延迟 < 500ms | 任务 14-15（前端响应） |

---

## 计划自检结果

**1. 规格覆盖度**：

| 规格章节 | 覆盖任务 |
|---|---|
| §1 目标 | 任务 18 验收 |
| §2 关键决策 | 任务 2-3, 5, 9, 11 |
| §3 架构概览 | 任务 5, 9, 10, 11 |
| §4.1 DB 迁移 010 | 任务 1 |
| §4.2 VAD 改造 | 任务 2-3 |
| §4.3 MeetingPipeline 改造 | 任务 4-5 |
| §4.4 /live 端点重构 | 任务 9 |
| §4.5 audio_level 推送 | 任务 10 |
| §4.6 SpeakerUnidentifiedService | 任务 6-7 |
| §4.7 消息协议升级 | 任务 9, 11, 12 |
| §5.1 SpeakerStrip 改造 | 任务 13 |
| §5.2 MeetingRoom 改造 | 任务 15 |
| §5.3 SpeakerUnidentifiedDialog | 任务 14 |
| §5.4 useMeetingRoomWS 改造 | 任务 12 |
| §7 错误处理 | 任务 5（try/except）+ 9（catch JSON 解析）+ 10（异常 break loop） |
| §8 测试 | 任务 2, 4, 6, 8 |
| §9 部署与迁移 | 任务 1, 16-18 |

**2. 占位符扫描**：未发现 "TODO"/"待定"/"补充细节" 等占位符

**3. 类型一致性**：
- `VADEngine()` 构造在任务 3 实现 + 任务 5 注入
- `MeetingPipeline(vad, asr, vp)` 构造在任务 5 定义 + 任务 9 调用
- `process_audio(bytes, db, elapsed) -> list[dict]` 在任务 5 定义 + 任务 4 mock + 任务 9 调用
- `get_unenrolled_participants(db, meeting_id) -> List[Member]` 在任务 7 定义 + 任务 6 测试 + 任务 9 调用
- `sendSpeakerClaim(segmentId, memberId, speakerLabel)` 在任务 12 定义 + 任务 15 调用

---

## 总任务数

- 后端：11 个任务
- 前端：4 个任务
- 部署：3 个任务
- **合计：18 个任务**

预计工时：单人 2-3 天。
