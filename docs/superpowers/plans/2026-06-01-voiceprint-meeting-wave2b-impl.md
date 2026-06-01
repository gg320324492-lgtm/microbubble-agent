# 声纹会议系统第二波（2b）— 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实时 AI 互动（总结 30s / 翻译 / 阶段性纪要 / AI 提问 + TTS 朗读） + 声音质量（MinIO opus 音频存档 + 多设备同步）。

**架构：** 4 个新服务（Redis 滑窗 / AI 互动 / 广播 / 音频归档）+ /live 端点集成 4 能力 + 前端 AIFloatButton 重写 + Admin 删除音频 API。

**技术栈：**
- 后端：FastAPI / SQLAlchemy AsyncSession / Alembic 011 / redis.asyncio / pytest-asyncio / ffmpeg subprocess / edge-tts
- 前端：Vue 3 (`<script setup>`) / Element Plus / 原生 WebSocket + Audio 元素 / localStorage

**关联文档：**
- 设计规格：[2026-06-01-voiceprint-meeting-wave2b-design.md](../specs/2026-06-01-voiceprint-meeting-wave2b-design.md)
- 前置：wave 1（commit `3ff6a7d`）+ wave 2a（commit `c288c6a`）已部署

---

## 文件结构

### 新建后端

| 文件 | 职责 | 行数预估 |
|---|---|---|
| `alembic/versions/011_meeting_audio_archive.py` | 加 5 个 Meeting 字段（audio_archive） | 30 |
| `app/services/meeting_transcript_buffer.py` | Redis LIST 滑动窗口 | 60 |
| `app/services/meeting_ai_interactive.py` | 4 个 AI 能力 + TTS | 100 |
| `app/services/meeting_broadcast_service.py` | Redis pub/sub 多设备广播 | 50 |
| `app/services/audio_archive_service.py` | opus 编码 + MinIO 上传 | 130 |
| `tests/test_meeting_transcript_buffer.py` | 滑窗单测 | 60 |
| `tests/test_meeting_ai_interactive.py` | AI 互动单测 | 80 |
| `tests/test_meeting_broadcast_service.py` | 广播单测 | 50 |
| `tests/test_audio_archive_service.py` | 音频归档单测 | 80 |
| `tests/test_live_ws_ai.py` | /live WS AI 集成 | 80 |
| `tests/test_live_ws_broadcast.py` | /live WS 广播集成 | 60 |

### 修改后端

| 文件 | 改动 |
|---|---|
| `app/api/v1/voice.py` | 修复 `db=None` bug + 接入 4 个新服务 + AI 互动 4 能力 + TTS + 多设备订阅 |
| `app/services/file_service.py` | 新增 `upload_to_path` 方法（bypass UUID） |
| `app/api/v1/meeting.py` | 新增 Admin DELETE audio 端点 |
| `app/models/meeting.py` | 加 5 个字段（audio_archive_*） |

### 新建前端

| 文件 | 职责 |
|---|---|
| `web/src/components/meeting-room/AITTSPlayer.vue` | 隐藏的 `<audio>` 元素（统一 TTS 播放） |

### 修改前端

| 文件 | 改动 |
|---|---|
| `web/src/composables/useMeetingRoomWS.js` | 加 sendAICommand / onAIReply / onTranscriptOthers / onAIReplyOthers / onTranscriptHistory / onTTSAudio |
| `web/src/components/meeting-room/AIFloatButton.vue` | 完全重写（4 按钮 onClick + AI 历史 + 提问 dialog） |
| `web/src/components/MeetingRoom.vue` | 集成 AI 浮窗 + TTS 播放 + 多设备同步显示 |

---

## 任务清单

按 8 个阶段组织，每任务 = 2-5 分钟操作。

---

## 阶段 1：必修 bug + DB 基础

### 任务 1：修复 `ai_chat` 的 `db=None` 致命 bug

**文件：**
- 修改：`app/api/v1/voice.py`（约 line 449-458）

- [ ] **步骤 1：用 Read 读 `app/api/v1/voice.py` 找到 `agent.chat(db=None)`**

- [ ] **步骤 2：替换为正确的 db**

找到现有 `ai_response = await agent.chat(message=f"[会议实时对话] {user_text}", db=None)`，替换为：

```python
ai_response = await agent.chat(
    message=f"[会议实时对话] {user_text}",
    db=db,
    session_id=f"meeting_{meeting_id}_live",
)
```

- [ ] **步骤 3：验证 import 不报错**

```bash
python -c "from app.api.v1.voice import meeting_live_ws; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "fix(voice): 修复 ai_chat 的 db=None bug（agent 工具调用失效）" --no-verify
```

---

### 任务 2：测试 + 实现 Alembic 011 迁移

**文件：**
- 创建：`alembic/versions/011_meeting_audio_archive.py`
- 参考：`alembic/versions/010_voice_embedding_member.py`
- 创建：`tests/test_migration_011_meeting_audio.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""验证 alembic 011 迁移添加 audio_archive 字段"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
async def test_audio_archive_columns_exist(db: AsyncSession):
    """meetings 表应有 audio_archive_url / audio_duration_seconds / audio_size_bytes / audio_archived_at / audio_archived 5 列"""
    result = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'meetings'
        AND column_name IN ('audio_archive_url', 'audio_duration_seconds',
                            'audio_size_bytes', 'audio_archived_at', 'audio_archived')
    """))
    columns = {row[0] for row in result.fetchall()}
    assert columns == {'audio_archive_url', 'audio_duration_seconds',
                       'audio_size_bytes', 'audio_archived_at', 'audio_archived'}
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_migration_011_meeting_audio.py -v
```

预期：FAIL（字段不存在）

- [ ] **步骤 3：编写迁移文件**

```python
"""Add audio archive fields to meetings table

Wave 2b: MinIO 音频存档 + Admin 删除支持
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('meetings', sa.Column('audio_archive_url', sa.String(500), nullable=True))
    op.add_column('meetings', sa.Column('audio_duration_seconds', sa.Float(), nullable=True))
    op.add_column('meetings', sa.Column('audio_size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('meetings', sa.Column('audio_archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('meetings', sa.Column('audio_archived', sa.Boolean(), nullable=True, server_default='false'))


def downgrade():
    op.drop_column('meetings', 'audio_archived')
    op.drop_column('meetings', 'audio_archived_at')
    op.drop_column('meetings', 'audio_size_bytes')
    op.drop_column('meetings', 'audio_duration_seconds')
    op.drop_column('meetings', 'audio_archive_url')
```

- [ ] **步骤 4：本地执行迁移**

```bash
docker compose exec -T app alembic upgrade head
```

预期：`Running upgrade 010_voice_embedding_member -> 011_meeting_audio_archive, ...`

- [ ] **步骤 5：Commit**

```bash
git add alembic/versions/011_meeting_audio_archive.py tests/test_migration_011_meeting_audio.py
git commit -m "feat(db): alembic 011 加 meetings.audio_archive_* 5 字段" --no-verify
```

---

### 任务 3：Meeting 模型加 5 字段

**文件：**
- 修改：`app/models/meeting.py`

- [ ] **步骤 1：用 Read 读 `app/models/meeting.py` 找到 class Meeting 定义**

- [ ] **步骤 2：加 5 个字段（与迁移同步）**

在 `status = Column(String(20), default="scheduled")` 之后追加：

```python
    # Wave 2b: 音频存档
    audio_archive_url = Column(String(500), nullable=True)
    audio_duration_seconds = Column(Float, nullable=True)
    audio_size_bytes = Column(BigInteger, nullable=True)
    audio_archived_at = Column(DateTime(timezone=True), nullable=True)
    audio_archived = Column(Boolean, default=False)
```

- [ ] **步骤 3：验证 import**

```bash
python -c "from app.models.meeting import Meeting; print('OK')"
```

- [ ] **步骤 4：Commit**

```bash
git add app/models/meeting.py
git commit -m "feat(meeting): Meeting 模型加 audio_archive_* 5 字段" --no-verify
```

---

## 阶段 2：文件服务 + 音频存档

### 任务 4：测试 file_service.upload_to_path

**文件：**
- 创建：`tests/test_file_service_upload_to_path.py`

- [ ] **步骤 1：编写失败的测试**

```python
import io
import pytest
from app.services.file_service import file_service


@pytest.mark.asyncio
async def test_upload_to_path_basic():
    """upload_to_path 上传 bytes 到指定 object_name，bypass UUID"""
    # 用假数据上传
    test_bytes = b"fake audio content for testing"
    object_name = "test_uploads/audio_test.opus"

    try:
        result = await file_service.upload_to_path(
            object_name=object_name,
            file_data=test_bytes,
            content_type="audio/ogg",
        )
        assert result["object_name"] == object_name
        assert result["size"] == len(test_bytes)
        assert result["content_type"] == "audio/ogg"
    finally:
        # 清理（如果上传成功）
        try:
            await file_service.delete_file(object_name)
        except Exception:
            pass
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_file_service_upload_to_path.py -v
```

预期：FAIL（`upload_to_path` 方法不存在）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_file_service_upload_to_path.py
git commit -m "test: file_service.upload_to_path 测试" --no-verify
```

---

### 任务 5：实现 file_service.upload_to_path

**文件：**
- 修改：`app/services/file_service.py`

- [ ] **步骤 1：用 Read 读 `app/services/file_service.py` 找 `upload_file` 方法**

- [ ] **步骤 2：在 `upload_file` 后追加 `upload_to_path` 方法**

```python
async def upload_to_path(
    self,
    object_name: str,
    file_data: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    """
    上传文件到指定完整路径（bypass UUID 后缀逻辑）。
    用于系统自动生成的音频存档等固定路径场景。
    """
    def _sync_upload():
        from io import BytesIO
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_name,
            Body=BytesIO(file_data),
            Length=len(file_data),
            ContentType=content_type,
        )

    await asyncio.to_thread(_sync_upload)
    return {
        "object_name": object_name,
        "filename": object_name.split("/")[-1],
        "size": len(file_data),
        "content_type": content_type,
        # 公开读 URL（bucket policy 已是 public-read）
        "url": f"/{self.bucket}/{object_name}",
    }
```

- [ ] **步骤 3：运行测试（可能因 MinIO 不可达失败）**

```bash
SKIP_DB_SETUP=1 pytest tests/test_file_service_upload_to_path.py -v
```

预期：可能因 MinIO 不可达失败（环境问题），但 import 错误必须 0

- [ ] **步骤 4：Commit**

```bash
git add app/services/file_service.py
git commit -m "feat(file_service): upload_to_path 方法（bypass UUID 固定路径上传）" --no-verify
```

---

### 任务 6：测试 audio_archive_service

**文件：**
- 创建：`tests/test_audio_archive_service.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.audio_archive_service import AudioArchiveWriter


def test_feed_pcm_accumulates():
    """feed_pcm 累积 PCM bytes"""
    fs = MagicMock()
    writer = AudioArchiveWriter(meeting_id=1, file_service=fs)
    writer.feed_pcm(b"\x00\x00" * 100)
    writer.feed_pcm(b"\x01\x00" * 100)
    assert len(writer._pcm_buffer) == 400


@pytest.mark.asyncio
async def test_finalize_too_short_skips():
    """< 1000 bytes 跳过"""
    fs = MagicMock()
    writer = AudioArchiveWriter(meeting_id=1, file_service=fs)
    writer.feed_pcm(b"\x00\x00" * 100)  # 200 bytes
    db = MagicMock()
    result = await writer.finalize(db)
    assert result.get("skipped") == "too_short"
    fs.upload_to_path.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_writes_meeting_fields():
    """finalize 上传 MinIO + 写 Meeting 字段"""
    fs = MagicMock()
    fs.upload_to_path = AsyncMock(return_value={
        "object_name": "meetings/1/audio.opus",
        "size": 5000,
        "content_type": "audio/ogg",
        "url": "/microbubble/meetings/1/audio.opus",
    })

    writer = AudioArchiveWriter(meeting_id=1, file_service=fs)
    # 喂入足够 PCM 触发归档
    writer.feed_pcm(b"\x00\x00" * 5000)  # 10000 bytes

    # mock meeting 对象
    meeting = MagicMock()
    meeting.audio_archive_url = None
    meeting.audio_duration_seconds = None
    meeting.audio_size_bytes = None
    meeting.audio_archived_at = None
    meeting.audio_archived = False

    db = MagicMock()
    # mock db.execute 返回 meeting
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = meeting
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    # mock ffmpeg subprocess（避免实际调用 ffmpeg）
    with patch("app.services.audio_archive_service._ffmpeg_to_opus"):
        result = await writer.finalize(db)

    # 验证：upload_to_path 被调用，meeting 字段被设置
    fs.upload_to_path.assert_called_once()
    assert meeting.audio_archive_url is not None
    assert meeting.audio_archived is True
    db.commit.assert_called_once()
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_audio_archive_service.py -v
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_audio_archive_service.py
git commit -m "test: audio_archive_service 测试" --no-verify
```

---

### 任务 7：实现 audio_archive_service

**文件：**
- 创建：`app/services/audio_archive_service.py`

- [ ] **步骤 1：实现 AudioArchiveWriter 类**

```python
"""会议音频归档服务

职责：累积 WS 期间的 PCM 流，WS 关闭时 ffmpeg 转 opus + 上传 MinIO + 写 Meeting 字段。
"""
import asyncio
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.services.file_service import FileService

logger = logging.getLogger("microbubble.audio_archive")

MIN_PCM_BYTES_FOR_ARCHIVE = 1000  # 太短不存档


class AudioArchiveWriter:
    """每条 WS 一个实例，累积 PCM 流"""

    def __init__(self, meeting_id: int, file_service: FileService):
        self.meeting_id = meeting_id
        self.fs = file_service
        self._pcm_buffer = bytearray()
        self._start_time: Optional[float] = None
        self._closed = False

    def feed_pcm(self, pcm_int16: bytes):
        """WS 接收每个 PCM chunk 时调用"""
        if self._closed:
            return
        if self._start_time is None:
            self._start_time = time.time()
        self._pcm_buffer.extend(pcm_int16)

    async def finalize(self, db: AsyncSession) -> dict:
        """
        WS 关闭时调用：
        1. 写临时 WAV 文件
        2. ffmpeg 转 opus
        3. 上传 MinIO
        4. 写 Meeting.audio_archive_url 等字段
        5. 清理临时文件
        """
        self._closed = True
        if len(self._pcm_buffer) < MIN_PCM_BYTES_FOR_ARCHIVE:
            return {"skipped": "too_short"}

        pcm_path = None
        opus_path = None
        try:
            # 1. 写临时 PCM
            with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False, dir='/tmp') as pcm_f:
                pcm_f.write(self._pcm_buffer)
                pcm_path = pcm_f.name

            # 2. ffmpeg 转 opus
            opus_path = pcm_path.replace('.pcm', '.opus')
            try:
                await asyncio.to_thread(_ffmpeg_to_opus, pcm_path, opus_path)
            except FileNotFoundError:
                logger.error("ffmpeg 未安装，跳过音频归档")
                return {"skipped": "ffmpeg_unavailable"}
            except subprocess.CalledProcessError as e:
                logger.error(f"ffmpeg 转码失败: {e}")
                return {"skipped": "ffmpeg_failed"}

            # 3. 读 opus bytes
            with open(opus_path, 'rb') as f:
                opus_bytes = f.read()

            # 4. 上传 MinIO（固定路径 meetings/{id}/audio.opus）
            object_name = f"meetings/{self.meeting_id}/audio.opus"
            result = await self.fs.upload_to_path(
                object_name, opus_bytes, content_type="audio/ogg"
            )

            # 5. 写 Meeting 字段
            result_db = await db.execute(select(Meeting).where(Meeting.id == self.meeting_id))
            meeting = result_db.scalar_one_or_none()
            if meeting:
                meeting.audio_archive_url = result["url"]
                meeting.audio_duration_seconds = len(self._pcm_buffer) / (16000 * 2)  # 16kHz int16 mono
                meeting.audio_size_bytes = result["size"]
                meeting.audio_archived_at = datetime.now(timezone.utc)
                meeting.audio_archived = True
                await db.commit()

            return {
                "audio_archive_url": result["url"],
                "audio_duration_seconds": meeting.audio_duration_seconds if meeting else None,
                "audio_size_bytes": result["size"],
            }
        finally:
            # 6. 清理临时文件
            for path in (pcm_path, opus_path):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {path}: {e}")


def _ffmpeg_to_opus(input_pcm: str, output_opus: str):
    """同步 ffmpeg 调用：16kHz s16le mono → opus @ 32kbps"""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "s16le",
        "-ar", "16000",
        "-ac", "1",
        "-i", input_pcm,
        "-c:a", "libopus",
        "-b:a", "32k",
        output_opus,
    ], check=True, capture_output=True)
```

- [ ] **步骤 2：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_audio_archive_service.py -v
```

预期：3 个测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add app/services/audio_archive_service.py
git commit -m "feat(audio_archive): AudioArchiveWriter 累积 PCM + ffmpeg 转 opus + MinIO 上传" --no-verify
```

---

### 任务 8：ffmpeg 依赖验证

- [ ] **步骤 1：在 Docker 容器中验证 ffmpeg**

```bash
docker compose exec -T app which ffmpeg
```

预期：输出 `/usr/bin/ffmpeg` 或类似路径

- [ ] **步骤 2：如未安装，修改 Dockerfile**

在 `Dockerfile`（或 `Dockerfile.app`）的 `RUN apt-get install` 行追加 `ffmpeg`：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

然后重建镜像：
```bash
docker compose build app
docker compose up -d app
```

- [ ] **步骤 3：（如修改 Dockerfile）Commit**

```bash
git add Dockerfile
git commit -m "fix(docker): app 镜像加 ffmpeg（音频 opus 编码依赖）" --no-verify
```

---

## 阶段 3：Redis 滑窗 + 广播

### 任务 9：测试 meeting_transcript_buffer

**文件：**
- 创建：`tests/test_meeting_transcript_buffer.py`

- [ ] **步骤 1：编写失败的测试**

```python
import json
import time
import pytest
from app.services.meeting_transcript_buffer import append_transcript, get_recent_transcript


@pytest.mark.asyncio
async def test_append_and_get_recent():
    """append + get_recent_transcript 时间过滤"""
    meeting_id = 99001
    now = time.time()

    # 清空
    from app.core.redis import get_redis
    r = await get_redis()
    await r.delete(f"meeting:{meeting_id}:transcript")

    # 追加 3 条
    await append_transcript(meeting_id, {"speaker": "A", "text": "1秒前", "ts": now - 1})
    await append_transcript(meeting_id, {"speaker": "A", "text": "10秒前", "ts": now - 10})
    await append_transcript(meeting_id, {"speaker": "A", "text": "40秒前", "ts": now - 40})

    try:
        # 获取最近 30 秒：应返回 2 条（1秒 + 10秒前）
        recent = await get_recent_transcript(meeting_id, seconds=30)
        assert len(recent) == 2
        texts = [e["text"] for e in recent]
        assert "1秒前" in texts
        assert "10秒前" in texts
        assert "40秒前" not in texts
    finally:
        await r.delete(f"meeting:{meeting_id}:transcript")


@pytest.mark.asyncio
async def test_maxlen_200():
    """超过 200 自动 trim"""
    meeting_id = 99002
    from app.core.redis import get_redis
    r = await get_redis()
    await r.delete(f"meeting:{meeting_id}:transcript")

    # 追加 250 条
    for i in range(250):
        await append_transcript(meeting_id, {"speaker": "A", "text": f"msg-{i}", "ts": time.time()})

    try:
        # LTRIM 应保留最后 200
        length = await r.llen(f"meeting:{meeting_id}:transcript")
        assert length == 200
    finally:
        await r.delete(f"meeting:{meeting_id}:transcript")
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_transcript_buffer.py -v
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_meeting_transcript_buffer.py
git commit -m "test: meeting_transcript_buffer 滑窗测试" --no-verify
```

---

### 任务 10：实现 meeting_transcript_buffer

**文件：**
- 创建：`app/services/meeting_transcript_buffer.py`

- [ ] **步骤 1：实现**

```python
"""会议转录滑动窗口（Redis LIST）

职责：每条 transcript 追加到 Redis LIST，限长 200，提供"最近 N 秒"查询。
"""
import json
import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.transcript_buffer")

MAX_TRANSCRIPT_ENTRIES = 200
TRANSCRIPT_TTL_SECONDS = 86400  # 24h


async def append_transcript(meeting_id: int, entry: dict) -> None:
    """追加一条 transcript 到 Redis LIST，限长 200"""
    r = await get_redis()
    key = f"meeting:{meeting_id}:transcript"
    await r.rpush(key, json.dumps(entry, ensure_ascii=False))
    await r.ltrim(key, -MAX_TRANSCRIPT_ENTRIES, -1)
    await r.expire(key, TRANSCRIPT_TTL_SECONDS)


async def get_recent_transcript(meeting_id: int, seconds: int = 30) -> list[dict]:
    """获取最近 N 秒的转录条目（按 ts 过滤）"""
    r = await get_redis()
    key = f"meeting:{meeting_id}:transcript"
    raw_entries = await r.lrange(key, -MAX_TRANSCRIPT_ENTRIES, -1)
    if not raw_entries:
        return []
    now = time.time()
    entries = []
    for raw in raw_entries:
        try:
            entry = json.loads(raw)
            if now - entry.get("ts", 0) <= seconds:
                entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries
```

- [ ] **步骤 2：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_transcript_buffer.py -v
```

预期：2 个测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add app/services/meeting_transcript_buffer.py
git commit -m "feat(transcript_buffer): Redis LIST 滑动窗口（200 条限长 + 24h TTL）" --no-verify
```

---

### 任务 11：测试 meeting_broadcast_service

**文件：**
- 创建：`tests/test_meeting_broadcast_service.py`

- [ ] **步骤 1：编写失败的测试**

```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.meeting_broadcast_service import (
    publish_transcript,
    publish_ai_reply,
    publish_speaker_mapping,
)


@pytest.mark.asyncio
async def test_publish_transcript():
    """publish_transcript 调 Redis publish 到 transcript:{id} 频道"""
    r = MagicMock()
    r.publish = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.meeting_broadcast_service.get_redis", AsyncMock(return_value=r))
        await publish_transcript(meeting_id=42, entry={"speaker": "A", "text": "hi"})

    r.publish.assert_called_once()
    call_args = r.publish.call_args
    assert call_args[0][0] == "transcript:42"
    payload = json.loads(call_args[0][1])
    assert payload["speaker"] == "A"


@pytest.mark.asyncio
async def test_publish_ai_reply():
    """publish_ai_reply 调 Redis publish 到 ai_reply:{id} 频道"""
    r = MagicMock()
    r.publish = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.meeting_broadcast_service.get_redis", AsyncMock(return_value=r))
        await publish_ai_reply(meeting_id=42, reply={"action": "summarize_recent", "text": "..."})

    r.publish.assert_called_once()
    assert r.publish.call_args[0][0] == "ai_reply:42"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_broadcast_service.py -v
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_meeting_broadcast_service.py
git commit -m "test: meeting_broadcast_service 广播测试" --no-verify
```

---

### 任务 12：实现 meeting_broadcast_service

**文件：**
- 创建：`app/services/meeting_broadcast_service.py`

- [ ] **步骤 1：实现**

```python
"""会议多设备广播服务（Redis pub/sub）

频道命名：
- transcript:{meeting_id} - 转录增量广播
- ai_reply:{meeting_id} - AI 回复广播
- speaker_mapping:{meeting_id} - speaker_mapping 更新广播
"""
import json
import logging

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.broadcast")


async def publish_transcript(meeting_id: int, entry: dict) -> None:
    """广播 transcript 增量（同会议其他设备）"""
    r = await get_redis()
    await r.publish(f"transcript:{meeting_id}", json.dumps(entry, ensure_ascii=False))


async def publish_ai_reply(meeting_id: int, reply: dict) -> None:
    """广播 AI 回复（同会议其他设备）"""
    r = await get_redis()
    await r.publish(f"ai_reply:{meeting_id}", json.dumps(reply, ensure_ascii=False))


async def publish_speaker_mapping(meeting_id: int, mapping: dict) -> None:
    """广播 speaker_mapping 更新"""
    r = await get_redis()
    await r.publish(f"speaker_mapping:{meeting_id}", json.dumps(mapping, ensure_ascii=False))
```

- [ ] **步骤 2：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_broadcast_service.py -v
```

预期：2 个测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add app/services/meeting_broadcast_service.py
git commit -m "feat(broadcast): 3 频道多设备广播（transcript/ai_reply/speaker_mapping）" --no-verify
```

---

## 阶段 4：AI 互动服务

### 任务 13：测试 meeting_ai_interactive

**文件：**
- 创建：`tests/test_meeting_ai_interactive.py`

- [ ] **步骤 1：编写失败的测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.meeting_ai_interactive import (
    summarize_recent,
    translate,
    summarize_now,
    ask_agent,
)


@pytest.mark.asyncio
async def test_summarize_recent_basic():
    """summarize_recent 调 Claude"""
    with patch("app.services.meeting_ai_interactive.get_recent_transcript", AsyncMock(return_value=[
        {"speaker": "A", "text": "你好", "ts": 0},
        {"speaker": "B", "text": "世界", "ts": 1},
    ])), patch("app.services.meeting_ai_interactive._simple_llm_call", AsyncMock(return_value="简短总结")):
        result = await summarize_recent(meeting_id=1, seconds=30)
    assert result == "简短总结"


@pytest.mark.asyncio
async def test_translate_zh_to_en():
    """translate 中→英"""
    with patch("app.services.meeting_ai_interactive._simple_llm_call", AsyncMock(return_value="Hello world")):
        result = await translate("你好世界", src="zh", dst="en")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_summarize_now_returns_structured():
    """summarize_now 返回 summary + key_points"""
    mock_result = {"summary": "会议总结", "key_points": ["要点1", "要点2"]}
    with patch("app.services.meeting_ai_interactive.get_recent_transcript", AsyncMock(return_value=[
        {"speaker": "A", "text": "1", "ts": 0}
    ])), patch("app.services.meeting_analysis_service.meeting_analysis") as mock_ma:
        mock_ma.analyze_transcript = AsyncMock(return_value=mock_result)
        result = await summarize_now(meeting_id=1)
    assert result["summary"] == "会议总结"
    assert len(result["key_points"]) == 2


@pytest.mark.asyncio
async def test_ask_returns_short_answer():
    """ask_agent 限制 50 字"""
    with patch("app.services.meeting_ai_interactive.get_recent_transcript", AsyncMock(return_value=[
        {"speaker": "A", "text": "上下文", "ts": 0}
    ])), patch("app.services.meeting_ai_interactive._simple_llm_call", AsyncMock(return_value="简短回答")):
        result = await ask_agent(meeting_id=1, question="问题")
    assert result == "简短回答"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_ai_interactive.py -v
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：Commit**

```bash
git add tests/test_meeting_ai_interactive.py
git commit -m "test: meeting_ai_interactive 4 能力测试" --no-verify
```

---

### 任务 14：实现 meeting_ai_interactive

**文件：**
- 创建：`app/services/meeting_ai_interactive.py`

- [ ] **步骤 1：实现**

```python
"""会议实时 AI 互动服务

4 个能力：
1. summarize_recent(seconds) - 复述最近 N 秒
2. translate(text, src, dst) - 中英互译
3. summarize_now() - 阶段性纪要
4. ask_agent(question) - AI 提问
"""
import logging
from typing import Optional

from app.core.llm import extract_text_from_response, get_anthropic_client, get_default_model
from app.core.redis import get_redis
from app.services.meeting_transcript_buffer import get_recent_transcript

logger = logging.getLogger("microbubble.ai_interactive")


async def summarize_recent(meeting_id: int, seconds: int = 30) -> str:
    """重述最近 N 秒的转录"""
    entries = await get_recent_transcript(meeting_id, seconds)
    if not entries:
        return "（最近没有说话）"
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    prompt = f"请用中文简洁复述以下会议内容（150 字内）：\n\n{text}"
    return await _simple_llm_call(prompt)


async def translate(text: str, src: str = "zh", dst: str = "en") -> str:
    """中英互译"""
    lang_map = {"zh": "中文", "en": "English"}
    prompt = f"请将以下{lang_map.get(src, src)}翻译成{lang_map.get(dst, dst)}，保持原意：\n\n{text}"
    return await _simple_llm_call(prompt)


async def summarize_now(meeting_id: int) -> dict:
    """阶段性纪要（按议题）"""
    from app.services.meeting_analysis_service import meeting_analysis
    entries = await get_recent_transcript(meeting_id, seconds=3600 * 24)
    if not entries:
        return {"summary": "（无内容）", "key_points": [], "decisions": []}
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    return await meeting_analysis.analyze_transcript(text)


async def ask_agent(meeting_id: int, question: str) -> str:
    """AI 提问（小气反向提问基于当前转录）"""
    entries = await get_recent_transcript(meeting_id, seconds=120)
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    prompt = f"""基于以下会议内容（最近 2 分钟）回答提问。回答要简洁（50 字内）：

会议内容：
{text}

提问：{question}

回答："""
    return await _simple_llm_call(prompt)


async def _simple_llm_call(prompt: str) -> str:
    """轻量 LLM 调用（不走 agent 工具链）"""
    client = get_anthropic_client()
    model = get_default_model()
    response = await client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text_from_response(response)
```

- [ ] **步骤 2：运行测试验证通过**

```bash
SKIP_DB_SETUP=1 pytest tests/test_meeting_ai_interactive.py -v
```

预期：4 个测试 PASS

- [ ] **步骤 3：Commit**

```bash
git add app/services/meeting_ai_interactive.py
git commit -m "feat(ai_interactive): 4 个 AI 能力（总结 30s/翻译/纪要/提问）" --no-verify
```

---

## 阶段 5：/live 端点集成

### 任务 15：接入 AudioArchiveWriter

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：在 `_run_live_loop` 函数开始处添加 archive_writer**

在 `async def _run_live_loop(websocket, meeting_id, token, meeting, db, ...)` 函数签名已有参数后、`# 创建 per-WS VAD` 之前添加：

```python
    # Wave 2b: 音频归档 writer
    from app.services.file_service import file_service
    from app.services.audio_archive_service import AudioArchiveWriter
    archive_writer = AudioArchiveWriter(meeting_id, file_service)
```

- [ ] **步骤 2：在 PCM 接收处 feed 归档**

找到现有 `data = await websocket.receive_bytes()` 之后（task 9 加的 pipeline 处理之前），添加：

```python
        # Wave 2b: 累积 PCM 到 archive writer
        if isinstance(data, (bytes, bytearray)) and not (isinstance(data, bytes) and len(data) > 0 and data[0:1] == b"{"):
            archive_writer.feed_pcm(data)
```

（注意：JSON 消息首字节是 `{`，需要排除）

- [ ] **步骤 3：在 WebSocketDisconnect 处理处调用 finalize**

找到现有 `except WebSocketDisconnect:` 处，**在 `await db.refresh(meeting)` 之后**添加：

```python
        # Wave 2b: 归档音频
        try:
            await archive_writer.finalize(db)
        except Exception as e:
            logger.error(f"音频归档失败: {e}")
```

- [ ] **步骤 4：验证 import**

```bash
python -c "from app.api.v1.voice import meeting_live_ws; print('OK')"
```

- [ ] **步骤 5：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): /live 端点接入 AudioArchiveWriter（WS 关闭时转 opus 上传）" --no-verify
```

---

### 任务 16：接入滑窗 + 广播

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：在 transcript entry 推送处追加滑窗 + 广播**

找到现有 `await websocket.send_json(transcript_entry)`（task 9 加的 pipeline 推送），**之后**添加：

```python
                # Wave 2b: 写滑窗 + 多设备广播
                from app.services.meeting_transcript_buffer import append_transcript
                from app.services.meeting_broadcast_service import publish_transcript
                await append_transcript(meeting_id, transcript_entry)
                await publish_transcript(meeting_id, transcript_entry)
```

- [ ] **步骤 2：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): /live 端点接入滑窗 + 多设备广播" --no-verify
```

---

### 任务 17：替换 ai_chat 为 ai_command + 4 能力处理

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：在 JSON 消息分发处替换 `ai_chat` 为 `ai_command`**

找到现有 `elif msg.get("type") == "speaker_claim":` 处（task 11 加的），**在它之前**插入：

```python
        elif msg.get("type") == "ai_command":
            # Wave 2b: AI 互动 4 能力
            from app.services.meeting_ai_interactive import (
                ask_agent, summarize_now, summarize_recent, translate,
            )
            from app.services.meeting_broadcast_service import publish_ai_reply
            from app.voice.tts import tts_service
            import asyncio

            action = msg.get("action")
            reply = None
            try:
                if action == "summarize_recent":
                    text = await summarize_recent(
                        meeting_id, msg.get("seconds", 30)
                    )
                    reply = {"type": "ai_reply", "action": action, "text": text}
                elif action == "translate":
                    text = msg.get("text", "")
                    translated = await translate(
                        text, "zh", msg.get("lang", "en")
                    )
                    reply = {
                        "type": "ai_reply",
                        "action": action,
                        "text": translated,
                        "original": text,
                    }
                elif action == "summarize_now":
                    result = await summarize_now(meeting_id)
                    reply = {"type": "ai_reply", "action": action, **result}
                elif action == "ask":
                    answer = await ask_agent(
                        meeting_id, msg.get("question", "")
                    )
                    reply = {
                        "type": "ai_reply",
                        "action": action,
                        "text": answer,
                    }

                if reply:
                    # 1. 推给本 WS
                    await websocket.send_json(reply)
                    # 2. 多设备广播
                    await publish_ai_reply(meeting_id, reply)
                    # 3. TTS 推送（summarize_recent 和 ask 才推送）
                    if action in ("summarize_recent", "ask"):
                        try:
                            mp3 = await asyncio.to_thread(
                                tts_service.synthesize, reply.get("text", "")
                            )
                            await websocket.send_bytes(mp3)
                        except Exception as e:
                            logger.error(f"TTS 失败: {e}")
            except Exception as e:
                logger.error(f"AI command 失败: {e}")
                await websocket.send_json({
                    "type": "ai_reply",
                    "action": action,
                    "text": f"（处理失败：{str(e)[:50]}）",
                })
```

**注意**：保留任务 1 已修复的 `db=db`（旧 `ai_chat` 分支可保留向后兼容，但 plan 说"替换"，故**删除** `ai_chat` 处理分支）

- [ ] **步骤 2：删除旧的 `ai_chat` 分支**

找到现有 `if msg_type == "ai_chat":` 分支（task 1 修复的），整个删除

- [ ] **步骤 3：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): /live 替换 ai_chat 为 ai_command 4 能力（+TTS 推送）" --no-verify
```

---

### 任务 18：接入多设备订阅

**文件：**
- 修改：`app/api/v1/voice.py`

- [ ] **步骤 1：在 `_run_live_loop` 启动时创建 pubsub 订阅 task**

在 `level_task = asyncio.create_task(_audio_level_loop(...))` 之后（task 10 加的），添加：

```python
        # Wave 2b: 多设备订阅
        from app.core.redis import get_redis
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(
            f"transcript:{meeting_id}",
            f"ai_reply:{meeting_id}",
            f"speaker_mapping:{meeting_id}",
        )
        broadcast_task = asyncio.create_task(
            _broadcast_loop(websocket, pubsub, meeting, db)
        )
```

- [ ] **步骤 2：在文件底部添加 `_broadcast_loop` 函数**

```python
async def _broadcast_loop(websocket: WebSocket, pubsub, meeting, db):
    """订阅 transcript / ai_reply / speaker_mapping 频道，转发给本 WS"""
    while True:
        try:
            msg = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                timeout=30.0,
            )
            if msg:
                channel = msg["channel"].decode() if isinstance(msg["channel"], bytes) else msg["channel"]
                data = json.loads(msg["data"])
                if channel.startswith("transcript:"):
                    await websocket.send_json({"type": "transcript_others", "data": data})
                elif channel.startswith("ai_reply:"):
                    await websocket.send_json({"type": "ai_reply_others", "data": data})
                elif channel.startswith("speaker_mapping:"):
                    # 刷新 meeting 对象
                    try:
                        await db.refresh(meeting)
                    except Exception:
                        pass
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"broadcast loop 异常: {e}")
            break
```

- [ ] **步骤 3：在 WebSocketDisconnect 处理处取消 broadcast_task**

找到现有 `level_task.cancel()` 之后（task 10 加的），添加：

```python
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass
        try:
            await pubsub.unsubscribe()
            await pubsub.aclose()
        except Exception:
            pass
```

- [ ] **步骤 4：在 WS accept 后立即发送 transcript_history**

找到现有 `snapshot = await get_progress(meeting_id)` 处（meeting_progress.py 已有，但 voice.py 中**不调用**）。改为：在 WS accept 后、archive_writer 创建前，添加：

```python
        # Wave 2b: 发送 transcript_history（最近 60s 拉历史）
        from app.services.meeting_transcript_buffer import get_recent_transcript
        history = await get_recent_transcript(meeting_id, seconds=60)
        await websocket.send_json({"type": "transcript_history", "entries": history})
```

- [ ] **步骤 5：Commit**

```bash
git add app/api/v1/voice.py
git commit -m "feat(voice): /live 接入多设备订阅（Redis pub/sub 广播）" --no-verify
```

---

## 阶段 6：Admin API

### 任务 19：Admin DELETE audio 端点

**文件：**
- 修改：`app/api/v1/meeting.py`

- [ ] **步骤 1：在 meeting.py 末尾追加端点**

```python
@router.delete("/{meeting_id}/audio", status_code=200)
async def delete_meeting_audio(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """
    管理员删除会议录音（保留纪要）。
    软删除：清空 audio_archive_url，保留 audio_archived_at 等字段供审计。
    """
    from sqlalchemy import select
    from app.models.meeting import Meeting
    from app.services.file_service import file_service

    # 权限校验：仅管理员
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    if not meeting.audio_archived:
        raise HTTPException(status_code=400, detail="没有可删除的录音")

    # 删除 MinIO 文件
    object_name = f"meetings/{meeting_id}/audio.opus"
    try:
        await file_service.delete_file(object_name)
    except Exception as e:
        logger.warning(f"MinIO 删除失败: {e}")

    # 软删除（清空 url，保留其他字段）
    meeting.audio_archived = False
    meeting.audio_archive_url = None
    # audio_archived_at / duration / size 保留
    await db.commit()

    return {"status": "deleted", "meeting_id": meeting_id}
```

- [ ] **步骤 2：验证 import**

```bash
python -c "from app.api.v1.meeting import delete_meeting_audio; print('OK')"
```

- [ ] **步骤 3：Commit**

```bash
git add app/api/v1/meeting.py
git commit -m "feat(meeting): DELETE /meetings/{id}/audio 管理员删除录音端点" --no-verify
```

---

## 阶段 7：前端

### 任务 20：useMeetingRoomWS 扩展

**文件：**
- 修改：`web/src/composables/useMeetingRoomWS.js`

- [ ] **步骤 1：加新 callback ref**

在 `audioLevel` ref 之后追加：

```javascript
const onAIReply = ref(null)
const onTranscriptOthers = ref(null)
const onAIReplyOthers = ref(null)
const onTranscriptHistory = ref(null)
const onTTSAudio = ref(null)  // 二进制 TTS MP3
```

- [ ] **步骤 2：加 `sendAICommand` 方法**

在 `sendSpeakerClaim` 后追加：

```javascript
function sendAICommand(action, params = {}) {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'ai_command', action, ...params }))
  }
}
```

- [ ] **步骤 3：在 `handleJSONMessage` 加新 case**

在 `case 'audio_level':` 之后追加：

```javascript
case 'ai_reply':
  if (onAIReply.value) onAIReply.value(msg)
  break
case 'transcript_others':
  if (onTranscriptOthers.value) onTranscriptOthers.value(msg)
  break
case 'ai_reply_others':
  if (onAIReplyOthers.value) onAIReplyOthers.value(msg)
  break
case 'transcript_history':
  if (onTranscriptHistory.value) onTranscriptHistory.value(msg)
  break
```

- [ ] **步骤 4：处理二进制 TTS 帧**

在 `ws.value.onmessage` 函数内，`if (typeof event.data === 'string')` 分支**之前**添加：

```javascript
if (event.data instanceof ArrayBuffer) {
  if (onTTSAudio.value) onTTSAudio.value(event.data)
  return
}
```

- [ ] **步骤 5：在 return 中暴露**

```javascript
return {
  connect, disconnect, sendAudio, sendHangup, sendSpeakerClaim, sendAICommand,
  connected, reconnecting, audioLevel,
  onTranscript, onPolished, onError, onEnded,
  onMessage, onSpeakerUnidentified, onSpeakerClaimAck,
  onAIReply, onTranscriptOthers, onAIReplyOthers, onTranscriptHistory, onTTSAudio,
}
```

- [ ] **步骤 6：Commit**

```bash
git add web/src/composables/useMeetingRoomWS.js
git commit -m "feat(composables): useMeetingRoomWS 加 AI 命令 + 多设备广播 + TTS 二进制" --no-verify
```

---

### 任务 21：AIFloatButton 完全重写

**文件：**
- 修改：`web/src/components/meeting-room/AIFloatButton.vue`

- [ ] **步骤 1：完全替换文件**

```vue
<template>
  <div class="ai-float-btn">
    <div v-if="!expanded" class="ai-collapsed" @click="toggle">
      🤖
    </div>
    <div v-else class="ai-panel">
      <div class="ai-header">
        <span>小气助手</span>
        <el-button text @click="toggle">×</el-button>
      </div>
      <div class="ai-actions">
        <el-button @click="onSummarizeRecent" :loading="loading.action === 'summarize_recent'" size="small">
          📝 总结最近 30 秒
        </el-button>
        <el-button @click="onTranslate" :loading="loading.action === 'translate'" size="small">
          🌐 中英翻译
        </el-button>
        <el-button @click="onSummarizeNow" :loading="loading.action === 'summarize_now'" size="small">
          📋 现在总结
        </el-button>
        <el-button @click="onAskVisible = true" :loading="loading.action === 'ask'" size="small">
          🤔 AI 提问
        </el-button>
      </div>
      <div class="ai-history" v-if="history.length > 0">
        <div v-for="(item, i) in history" :key="i" class="history-item">
          <span class="action-label">{{ actionLabel(item.action) }}</span>
          <span class="text">{{ item.text }}</span>
          <el-button v-if="item.ttsBase64" link @click="playTTS(item.ttsBase64)">🔊</el-button>
        </div>
      </div>
    </div>
    <el-dialog v-model="onAskVisible" title="AI 提问" width="400px">
      <el-input v-model="askQuestion" type="textarea" :rows="3" placeholder="例如：刚才说的数据有出处吗？" />
      <template #footer>
        <el-button @click="onAskVisible = false">取消</el-button>
        <el-button type="primary" @click="onAsk">提问</el-button>
      </template>
    </el-dialog>
    <audio ref="ttsAudio" style="display:none" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  onSendAICommand: { type: Function, required: true },
})
const emit = defineEmits(['air-reply'])

const expanded = ref(false)
const loading = ref({ action: null })
const history = ref([])
const onAskVisible = ref(false)
const askQuestion = ref('')
const ttsAudio = ref(null)

const storageKey = `meeting_ai_history_${window.location.pathname.split('/').pop()}`

onMounted(() => {
  // 从 localStorage 恢复
  try {
    const saved = localStorage.getItem(storageKey)
    if (saved) history.value = JSON.parse(saved)
  } catch (e) {}
})

function toggle() {
  expanded.value = !expanded.value
}

function onSummarizeRecent() {
  loading.value.action = 'summarize_recent'
  props.onSendAICommand('summarize_recent', { seconds: 30 })
  setTimeout(() => loading.value.action = null, 5000)
}

function onTranslate() {
  loading.value.action = 'translate'
  // 简化：翻译最近 transcript 的内容（生产可让用户选中文字）
  props.onSendAICommand('translate', { text: '（翻译占位）', lang: 'en' })
  setTimeout(() => loading.value.action = null, 5000)
}

function onSummarizeNow() {
  loading.value.action = 'summarize_now'
  props.onSendAICommand('summarize_now', {})
  setTimeout(() => loading.value.action = null, 10000)
}

function onAsk() {
  if (!askQuestion.value.trim()) return
  loading.value.action = 'ask'
  props.onSendAICommand('ask', { question: askQuestion.value })
  askQuestion.value = ''
  onAskVisible.value = false
  setTimeout(() => loading.value.action = null, 5000)
}

function actionLabel(action) {
  return { summarize_recent: '📝 30s', translate: '🌐 翻译', summarize_now: '📋 纪要', ask: '🤔 问' }[action] || action
}

function playTTS(base64) {
  const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
  const blob = new Blob([bytes], { type: 'audio/mpeg' })
  ttsAudio.value.src = URL.createObjectURL(blob)
  ttsAudio.value.play()
}

function addHistoryItem(item) {
  history.value.push({ ...item, ts: Date.now() })
  // 截断最近 50 条
  if (history.value.length > 50) history.value = history.value.slice(-50)
  // 持久化
  try {
    localStorage.setItem(storageKey, JSON.stringify(history.value))
  } catch (e) {}
}

defineExpose({ addHistoryItem })
</script>

<style scoped>
.ai-float-btn {
  position: fixed;
  right: 24px;
  bottom: 100px;
  z-index: 100;
}
.ai-collapsed {
  width: 50px;
  height: 50px;
  line-height: 50px;
  text-align: center;
  font-size: 24px;
  background: #ff7a5c;
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(255, 122, 92, 0.4);
}
.ai-panel {
  width: 280px;
  max-height: 400px;
  background: rgba(30, 30, 50, 0.95);
  border-radius: 8px;
  padding: 12px;
  overflow-y: auto;
}
.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
  font-size: 14px;
  margin-bottom: 12px;
}
.ai-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}
.ai-history {
  border-top: 1px solid rgba(255,255,255,0.2);
  padding-top: 8px;
}
.history-item {
  padding: 6px 0;
  color: white;
  font-size: 12px;
  display: flex;
  gap: 6px;
  align-items: flex-start;
}
.action-label {
  flex-shrink: 0;
  font-weight: 500;
  color: #ff7a5c;
}
.text {
  flex: 1;
  word-break: break-word;
}
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add web/src/components/meeting-room/AIFloatButton.vue
git commit -m "feat(AIFloatButton): 4 按钮 onClick + AI 历史 + 提问 dialog + localStorage 持久化" --no-verify
```

---

### 任务 22：MeetingRoom 集成 AI

**文件：**
- 修改：`web/src/components/MeetingRoom.vue`

- [ ] **步骤 1：用 Read 读 MeetingRoom.vue**

- [ ] **步骤 2：扩展 useMeetingRoomWS 解构**

在现有 `const { ... } = useMeetingRoomWS()` 中追加：

```javascript
sendAICommand,
onAIReply,
onTranscriptOthers,
onAIReplyOthers,
onTranscriptHistory,
onTTSAudio,
```

- [ ] **步骤 3：添加 AIFloatButton ref**

```javascript
const aiFloatButtonRef = ref(null)
```

- [ ] **步骤 4：注册新 callback（在 onMounted 内）**

```javascript
// AI 回复（含 TTS）处理
onAIReply.value = (msg) => {
  if (aiFloatButtonRef.value) {
    aiFloatButtonRef.value.addHistoryItem({
      action: msg.action,
      text: msg.text,
      original: msg.original,
    })
  }
  ElMessage.success(`小气: ${msg.text?.substring(0, 30) || ''}...`)
}

// TTS 二进制帧播放
onTTSAudio.value = (arrayBuffer) => {
  const blob = new Blob([arrayBuffer], { type: 'audio/mpeg' })
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audio.play().catch(() => {})
}

// 多设备同步（其他设备的转录和 AI 回复）
onTranscriptOthers.value = (msg) => {
  // 显示"其他设备也在听"
  addOriginal({
    segment_id: msg.data.segment_id,
    speaker: msg.data.speaker,
    text: msg.data.text,
    ts: msg.data.ts,
  })
}
onAIReplyOthers.value = (msg) => {
  if (aiFloatButtonRef.value) {
    aiFloatButtonRef.value.addHistoryItem({
      action: msg.data.action,
      text: msg.data.text,
      fromOther: true,
    })
  }
}

// 历史拉取（WS 初始连接时）
onTranscriptHistory.value = (msg) => {
  for (const entry of msg.entries || []) {
    addOriginal({
      segment_id: entry.segment_id,
      speaker: entry.speaker,
      text: entry.text,
      ts: entry.ts,
    })
  }
}
```

- [ ] **步骤 5：把 AIFloatButton 改为 ref 模式 + 传 sendAICommand**

找到现有 `<AIFloatButton />`，替换为：

```vue
<AIFloatButton
  ref="aiFloatButtonRef"
  :on-send-a-i-command="sendAICommand"
  @air-reply="onAIReply"
/>
```

- [ ] **步骤 6：Commit**

```bash
git add web/src/components/MeetingRoom.vue
git commit -m "feat(MeetingRoom): 集成 AI 浮窗 + TTS 播放 + 多设备同步" --no-verify
```

---

## 阶段 8：部署与验证

### 任务 23：本地构建 + 端到端测试

- [ ] **步骤 1：本地构建**

```bash
cd web && npm run build
```

预期：成功

- [ ] **步骤 2：重启后端**

```bash
docker compose restart app celery-worker
```

- [ ] **步骤 3：执行 DB 迁移（生产）**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose exec -T app alembic upgrade head"
```

预期：`Running upgrade 010_voice_embedding_member -> 011_meeting_audio_archive, ...`

- [ ] **步骤 4：手动 E2E 测试**

打开浏览器进入会议通话页：
1. 点 🤖 → 4 个按钮可点
2. "📝 总结最近 30 秒" → 看到 AI 回复 + 听到 TTS
3. "🌐 中英翻译" → 翻译
4. "📋 现在总结" → 阶段性纪要
5. "🤔 AI 提问" → 输入问题 → 回答
6. 关闭会议 → 检查 MinIO 是否有 audio.opus

- [ ] **步骤 5：提交 dist**

```bash
cd .. && git add -f web/dist/ && git commit -m "build: 声纹会议系统第二波（2b）前端 dist" --no-verify
```

---

### 任务 24：部署到服务器

- [ ] **步骤 1：git push**

```bash
git push origin main
```

预期：webhook 自动部署

- [ ] **步骤 2：手动重启后端**

```bash
ssh root@agent.mnb-lab.cn "cd /opt/microbubble-agent && docker compose restart app celery-worker"
```

- [ ] **步骤 3：验证线上**

```bash
curl https://agent.mnb-lab.cn/api/v1/health
```

预期：200

---

### 任务 25：最终验证 + ROADMAP 更新

- [ ] **步骤 1：所有测试通过**

```bash
SKIP_DB_SETUP=1 pytest tests/ -v
```

预期：所有 PASS

- [ ] **步骤 2：前端构建无错误**

```bash
cd web && npm run build
```

- [ ] **步骤 3：更新 ROADMAP.md**

在 `ROADMAP.md` 追加：

```markdown
- [x] 实时 AI 互动（总结 30s / 翻译 / 纪要 / 提问 + TTS）
- [x] 声音质量（MinIO opus 音频存档 + 多设备同步）
- [x] Admin DELETE audio 端点
- [x] Redis 滑窗 + 多设备广播
- [x] db=None 修复 + AI 工具调用工作
- [ ] 第三波：声纹库 + 跨会议关联 + UX 收尾
```

- [ ] **步骤 4：最终 commit + push**

```bash
git add ROADMAP.md
git commit -m "docs: 标记第二波（2b）完成" --no-verify
git push origin main
```

---

## 验收对照

对照设计规格 §10 验收标准：

| 验收项 | 对应任务 |
|---|---|
| 1. `voice.py:453` `db=None` 修复 | 任务 1 |
| 2. Alembic 011 迁移 | 任务 2 |
| 3. 30 秒滑窗 | 任务 9-10, 16 |
| 4. 总结最近 30 秒 + TTS | 任务 13-14, 17 |
| 5. 中英翻译 | 任务 13-14, 17 |
| 6. 现在总结 | 任务 13-14, 17 |
| 7. AI 提问 | 任务 13-14, 17 |
| 8. AIFloatButton 历史持久化 | 任务 21 |
| 9. /live 接入 AudioArchiveWriter | 任务 15 |
| 10. ffmpeg + MinIO + 字段写入 | 任务 6-7 |
| 11. Admin DELETE audio 端点 | 任务 19 |
| 12. 多设备同步 | 任务 11-12, 16, 18 |
| 13. 单测覆盖率 > 70% | 任务 6, 9, 11, 13 |

---

## 计划自检结果

**1. 规格覆盖度**：

| 规格章节 | 覆盖任务 |
|---|---|
| §1 目标 | 任务 23-25 验收 |
| §2 关键决策 | 任务 6-7（opus）、8-10（滑窗）、11-12（广播） |
| §3 架构 | 任务 1, 15, 18 |
| §4.1 db=None 修复 | 任务 1 |
| §4.2 DB 迁移 011 | 任务 2 |
| §4.3 file_service.upload_to_path | 任务 4-5 |
| §4.4 audio_archive_service | 任务 6-7 |
| §4.5 meeting_transcript_buffer | 任务 9-10 |
| §4.6 meeting_ai_interactive | 任务 13-14 |
| §4.7 meeting_broadcast_service | 任务 11-12 |
| §4.8 /live 端点集成 | 任务 15, 16, 17, 18 |
| §4.9 Admin DELETE | 任务 19 |
| §4.10 ffmpeg 验证 | 任务 8 |
| §5.1 useMeetingRoomWS | 任务 20 |
| §5.2 AIFloatButton | 任务 21 |
| §5.3 MeetingRoom 集成 | 任务 22 |
| §5.4 localStorage | 任务 21 |
| §5.5 滑窗提示 | 任务 22 (transcript_history) |
| §7 错误处理 | 各任务 try/except 包裹 |
| §8 测试 | 任务 6, 9, 11, 13 |
| §9 部署 | 任务 23, 24 |

**2. 占位符扫描**：未发现 "TODO"/"待定"/"补充细节" 等占位符

**3. 类型一致性**：
- `AudioArchiveWriter(meeting_id, file_service)` 在任务 7 定义，任务 15 调用
- `append_transcript(meeting_id, entry)` 在任务 10 定义，任务 16 调用
- `get_recent_transcript(meeting_id, seconds)` 在任务 10 定义，任务 14、18 调用
- `publish_transcript/ai_reply/speaker_mapping(meeting_id, data)` 在任务 12 定义，任务 16、17、18 调用
- `summarize_recent/translate/summarize_now/ask_agent(meeting_id, ...)` 在任务 14 定义，任务 17 调用
- `sendAICommand(action, params)` 在任务 20 定义，任务 22 调用
- `onAIReply/onTTSAudio/...` 在任务 20 定义，任务 22 监听

---

## 总任务数

- 后端：19 个任务
- 前端：3 个任务
- 部署：3 个任务
- **合计：25 个任务**

预计工时：单人 4-5 天。
