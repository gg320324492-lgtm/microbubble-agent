# 声纹会议系统升级 — 第二波（2b）设计规格

**日期**：2026-06-01
**作者**：Claude (brainstorming 阶段产物)
**范围**：第二波 2b — 实时 AI 互动 + 声音质量 + 多设备同步（10+ 子功能）
**状态**：待用户审阅
**关联**：
- 第一波已上线（commit `3ff6a7d`）
- 第二波（2a）已上线（commit `c288c6a`）
- 总览 Roadmap：[2026-06-01-voiceprint-meeting-upgrade-roadmap.md](../plans/2026-06-01-voiceprint-meeting-upgrade-roadmap.md)

---

## 1. 目标与背景

### 1.1 2a 成果（已上线）

- ✅ 声纹识别真正启用（per-WS MeetingPipeline）
- ✅ 声纹录入整合（未识别弹窗选人）
- ✅ audio_level 推送 + SpeakerStrip 声波条
- ✅ DB 迁移 010 补 voice_embedding 字段

### 1.2 2b 痛点

1. **AI 互动空白** — AIFloatButton 3 个按钮无 onClick（"总结 30 秒" / "中英翻译" / "AI 提问"）
2. **`db=None` 致命 bug** — `voice.py:453` `agent.chat(db=None)` → 所有工具调用失效（wave 1 任务 18 留下）
3. **滑动窗口缺失** — `/live` 端 `transcript_entries` 是 WS 局部变量，无法"重述刚才 30 秒"
4. **音频无存档** — `Meeting.audio_archive_url` 字段缺失（无迁移）
5. **多设备不同步** — speaker_claim 后其他 WS 看不到（DB 缓存）
6. **TTS 未对接** — `tts_service` 已就绪但 `/live` 端不用
7. **翻译未实现** — 完全无翻译能力
8. **无 Admin 音频管理** — 录音无法删除

### 1.3 2b 目标

让用户**开会中**能：
1. 总结最近 30 秒（基于滑动窗口）
2. 中英互译
3. 现在总结阶段性纪要
4. AI 主动提问
5. AI 浮窗历史记录持久化
6. 听完 TTS 朗读 AI 回复
7. 看到多设备同步的转录/AI 回复
8. 录音完整存档到 MinIO

**会后**：
- 管理员可删除录音但保留纪要

### 1.4 非目标（YAGNI，留到 3）

- 声纹画像可视化
- 跨会议关联
- 横屏移动端会议模式
- 离线缓冲
- 时间轴跳转

---

## 2. 关键决策（已通过 brainstorming 确认）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 范围 | **2b 全部**（10+ 子功能） | 用户要求"深入高质量全面完善" |
| 音频存档格式 | **opus 压缩** | 1 小时 16kHz mono ≈ 5-10MB（10 倍压缩） |
| 多设备同步范围 | **转录 + AI 互动** | 3 个 Redis channel，带宽适中 |
| 30s 滑窗 | **Redis LIST + ts 过滤** | 与 progress_service 复用模式 |

---

## 3. 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│              浏览器 MeetingRoom + AIFloatButton              │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────┐ ┌─────────┐│
│  │ AIFloatBtn │ │AI 历史浮窗  │ │ TTS 播放器  │ │ 滑窗 30s││
│  │ 4 按钮      │ │(localStorage)│ │(Blob audio)│ │ 提示    ││
│  └─────┬──────┘ └──────┬──────┘ └──────┬───────┘ └────┬────┘│
│        │ sendAIChat   │ onAIReply     │ tts bytes  │       │
│        │ sendTranslate│ onTranscript  │            │       │
│        │ sendSummarize│ onAIFromOther │            │       │
│        │ sendAsk      │               │            │       │
└────────┼─────────────┼──────────────┼────────────┼───────┘
         │             │              │            │
   ┌─────▼─────────────▼──────────────▼────────────▼──────┐
   │  /ws/meeting/{id}/live                            │
   │  新协议（增加）:                                  │
   │    收: {type: "ai_chat",                          │
   │         action: "summarize_recent|translate|       │
   │                   summarize_now|ask",              │
   │         text?, seconds?, lang?}                    │
   │    推: {type: "ai_reply", text, action, tts_url?}  │
   │    二进制帧: TTS MP3 bytes                       │
   │    推: {type: "transcript_others", entry}         │  广播
   │    推: {type: "ai_reply_others", reply}           │  广播
   └─────┬──────────────────────────────────────────────┘
         │
   ┌──────▼──────────────────────────────────────────────┐
   │  滑动窗口缓冲（Redis LIST）                       │
   │  Key: meeting:{id}:transcript (LIST, maxlen=200)│
   │  Value: JSON {speaker, text, ts, speaker_label}  │
   └─────┬──────────────────────────────────────────────┘
         │
   ┌──────▼──────────────────────────────────────────────┐
   │  /ws/meeting/{id}/live 后端处理                    │
   │  ┌──────────┐ ┌─────────────┐ ┌──────────────┐  │
   │  │Meeting   │ │ AI 互动     │ │ 音频归档     │  │
   │  │Pipeline  │ │ Service     │ │ Service      │  │
   │  │(wave 2a) │ │ (4 能力+TTS)│ │ (opus+MinIO) │  │
   │  └────┬─────┘ └──────┬──────┘ └──────┬───────┘  │
   │       │              │              │            │
   │  ┌────▼──────────────▼──────────────▼───────┐    │
   │  │ MeetingBroadcastService (Redis pub/sub) │    │
   │  │ 频道: transcript:{id} / ai_reply:{id}  │    │
   │  └──────────────────────────────────────────┘    │
   └────────────────────────────────────────────────────┘
         │
   ┌──────▼──────────────────────────────────────────────┐
   │  /ws/meeting/{id}/live 后端处理（同会议多设备订阅）│
   │  订阅 transcript:{id} + ai_reply:{id}              │
   │  WS 初始 LRANGE 拉最近 60s 历史                    │
   └────────────────────────────────────────────────────┘
```

---

## 4. 后端设计

### 4.1 必修：修复 `ai_chat` 的 `db=None` bug

**文件**：`app/api/v1/voice.py:449-458`

**改动**（5 行）：
```python
# 原代码（db=None 致命 bug）
ai_response = await agent.chat(
    message=f"[会议实时对话] {user_text}", db=None)

# 修复：用当前 WS 已有的 db session
ai_response = await agent.chat(
    message=f"[会议实时对话] {user_text}", db=db,
    session_id=f"meeting_{meeting_id}_live")
```

### 4.2 DB 迁移 011 — Meeting 音频存档字段

**文件**：`alembic/versions/011_meeting_audio_archive.py`

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

**Meeting 模型更新**（`app/models/meeting.py`）：加 5 个字段（与迁移同步）

### 4.3 FileService 扩展 — `upload_to_path`

**文件**：`app/services/file_service.py`

**新方法**：
```python
async def upload_to_path(
    self,
    object_name: str,        # 完整路径如 "meetings/123/audio.opus"
    file_data: bytes,
    content_type: str = "audio/ogg",
) -> dict:
    """
    上传文件到指定完整路径（bypass UUID 后缀逻辑）。
    用于系统自动生成的音频存档。
    """
    def _sync_upload():
        # 直接 put_object 到指定 key
        from io import BytesIO
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_name,
            Body=BytesIO(file_data),
            Length=len(file_data),
            ContentType=content_type,
        )
        return object_name

    obj = await asyncio.to_thread(_sync_upload)
    return {
        "object_name": obj,
        "size": len(file_data),
        "content_type": content_type,
        # 公开读 URL（bucket policy 已是 public-read）
        "url": f"/{self.bucket}/{object_name}",
    }
```

### 4.4 audio_archive_service — opus 编码 + 上传

**文件**：`app/services/audio_archive_service.py`（新）

**职责**：
- 累积 WS 期间的 PCM 流（per-WS 临时文件）
- WS 关闭时调 ffmpeg 转 opus
- 上传到 MinIO 固定路径
- 写 Meeting.audio_archive_* 字段

**核心 API**：
```python
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
        if len(self._pcm_buffer) < 1000:  # 太短不存档
            return {"skipped": "too_short"}

        # 1. 写临时 PCM
        with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False, dir='/tmp') as pcm_f:
            pcm_f.write(self._pcm_buffer)
            pcm_path = pcm_f.name

        # 2. ffmpeg 转 opus
        opus_path = pcm_path.replace('.pcm', '.opus')
        await asyncio.to_thread(
            _ffmpeg_to_opus, pcm_path, opus_path
        )

        # 3. 读 opus bytes
        with open(opus_path, 'rb') as f:
            opus_bytes = f.read()

        # 4. 上传 MinIO
        object_name = f"meetings/{self.meeting_id}/audio.opus"
        result = await self.fs.upload_to_path(
            object_name, opus_bytes, content_type="audio/ogg"
        )

        # 5. 写 Meeting 字段
        from app.models.meeting import Meeting
        from sqlalchemy import select
        result_db = await db.execute(select(Meeting).where(Meeting.id == self.meeting_id))
        meeting = result_db.scalar_one_or_none()
        if meeting:
            meeting.audio_archive_url = result["url"]
            meeting.audio_duration_seconds = len(self._pcm_buffer) / (16000 * 2)  # 16kHz int16 mono
            meeting.audio_size_bytes = result["size"]
            meeting.audio_archived_at = datetime.now(timezone.utc)
            meeting.audio_archived = True
            await db.commit()

        # 6. 清理临时文件
        os.unlink(pcm_path)
        os.unlink(opus_path)

        return {
            "audio_archive_url": result["url"],
            "audio_duration_seconds": meeting.audio_duration_seconds,
            "audio_size_bytes": meeting.audio_size_bytes,
        }


def _ffmpeg_to_opus(input_pcm: str, output_opus: str):
    """同步 ffmpeg 调用：16kHz s16le mono → opus"""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "s16le",
        "-ar", "16000",
        "-ac", "1",
        "-i", input_pcm,
        "-c:a", "libopus",
        "-b:a", "32k",  # 32kbps 适合人声
        output_opus,
    ], check=True, capture_output=True)
```

### 4.5 meeting_transcript_buffer — Redis 滑动窗口

**文件**：`app/services/meeting_transcript_buffer.py`（新）

**职责**：每条 transcript 追加到 Redis LIST，提供"最近 N 秒"查询。

**核心 API**：
```python
import json
import time
from app.core.redis import get_redis


async def append_transcript(meeting_id: int, entry: dict) -> None:
    """追加一条 transcript 到 Redis LIST，限长 200"""
    r = await get_redis()
    key = f"meeting:{meeting_id}:transcript"
    # entry 含 speaker, text, ts, speaker_label
    await r.rpush(key, json.dumps(entry, ensure_ascii=False))
    await r.ltrim(key, -200, -1)  # 保留最后 200 条
    await r.expire(key, 86400)  # 24h TTL


async def get_recent_transcript(meeting_id: int, seconds: int = 30) -> list[dict]:
    """获取最近 N 秒的转录条目（按 ts 过滤）"""
    r = await get_redis()
    key = f"meeting:{meeting_id}:transcript"
    raw_entries = await r.lrange(key, -200, -1)
    if not raw_entries:
        return []
    # 解析 + ts 过滤
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


async def get_full_transcript_for_summary(meeting_id: int) -> list[dict]:
    """获取完整转录（用于阶段性纪要）"""
    return await get_recent_transcript(meeting_id, seconds=3600 * 24)  # 24h
```

### 4.6 meeting_ai_interactive — 4 个 AI 能力

**文件**：`app/services/meeting_ai_interactive.py`（新）

**核心 API**：
```python
from typing import Optional
from app.services.meeting_transcript_buffer import get_recent_transcript
from app.core.llm import get_anthropic_client, get_default_model
from app.core.redis import get_redis
import json


async def summarize_recent(
    meeting_id: int, seconds: int = 30, db = None
) -> str:
    """重述最近 N 秒的转录"""
    entries = await get_recent_transcript(meeting_id, seconds)
    if not entries:
        return "（最近没有说话）"
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    prompt = f"请用中文简洁复述以下会议内容（150 字内）：\n\n{text}"
    return await _simple_llm_call(prompt, db)


async def translate(text: str, src: str = "zh", dst: str = "en", db = None) -> str:
    """中英互译"""
    lang_map = {"zh": "中文", "en": "English"}
    prompt = f"请将以下{lang_map.get(src, src)}翻译成{lang_map.get(dst, dst)}，保持原意：\n\n{text}"
    return await _simple_llm_call(prompt, db)


async def summarize_now(meeting_id: int, db = None) -> dict:
    """阶段性纪要（按议题）"""
    from app.services.meeting_analysis_service import meeting_analysis
    entries = await get_recent_transcript(meeting_id, seconds=3600 * 24)
    if not entries:
        return {"summary": "（无内容）", "key_points": []}
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    # 复用 meeting_analysis.analyze_transcript
    return await meeting_analysis.analyze_transcript(text)


async def ask_agent(meeting_id: int, question: str, db) -> str:
    """AI 提问（小气反向提问基于当前转录）"""
    entries = await get_recent_transcript(meeting_id, seconds=120)
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    prompt = f"""基于以下会议内容（最近 2 分钟）回答提问。回答要简洁（50 字内）：

会议内容：
{text}

提问：{question}

回答："""
    return await _simple_llm_call(prompt, db)


async def _simple_llm_call(prompt: str, db = None) -> str:
    """轻量 LLM 调用（不走 agent 工具链）"""
    from app.core.llm import get_anthropic_client, get_default_model
    client = get_anthropic_client()
    model = get_default_model()
    response = await client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    from app.core.llm import extract_text_from_response
    return extract_text_from_response(response)
```

### 4.7 meeting_broadcast_service — 多设备同步

**文件**：`app/services/meeting_broadcast_service.py`（新）

**核心 API**：
```python
import json
from app.core.redis import get_redis


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

### 4.8 /live 端点 — 全面集成

**文件**：`app/api/v1/voice.py`（大量修改）

**集成点**：

1. **WS accept 后初始化**：
```python
# Wave 2b 新增
archive_writer = AudioArchiveWriter(meeting_id, file_service)
# （meeting, db 已有）
```

2. **接收 PCM chunk 时**：
```python
data = await websocket.receive_bytes()
# 1. Wave 2a 已有：入队 audio_level_queue
# 2. Wave 2a 已有：pipeline.process_audio
# 3. Wave 2b 新增：archive_writer.feed_pcm(data)
```

3. **transcript entry 推送时**：
```python
# Wave 2a 已有：本地 ws.send_json(transcript_entry)
# Wave 2b 新增：
await append_transcript(meeting_id, transcript_entry)  # Redis LIST
await publish_transcript(meeting_id, transcript_entry)  # 多设备广播
```

4. **AI 互动消息处理**（替换现有 `ai_chat`）：
```python
if msg_type == "ai_command":
    action = msg.get("action")
    if action == "summarize_recent":
        text = await summarize_recent(meeting_id, msg.get("seconds", 30), db=db)
        reply = {"type": "ai_reply", "action": action, "text": text}
        await ws.send_json(reply)
        # 广播 + TTS
        await publish_ai_reply(meeting_id, reply)
        await _tts_send(ws, text)
    elif action == "translate":
        text = msg.get("text", "")
        translated = await translate(text, "zh", msg.get("lang", "en"), db=db)
        reply = {"type": "ai_reply", "action": action, "text": translated, "original": text}
        await ws.send_json(reply)
    elif action == "summarize_now":
        result = await summarize_now(meeting_id, db=db)
        reply = {"type": "ai_reply", "action": action, **result}
        await ws.send_json(reply)
    elif action == "ask":
        answer = await ask_agent(meeting_id, msg.get("question", ""), db=db)
        reply = {"type": "ai_reply", "action": action, "text": answer}
        await ws.send_json(reply)
```

5. **二进制 TTS 帧推送**：
```python
async def _tts_send(ws: WebSocket, text: str):
    from app.voice.tts import tts_service
    try:
        mp3_bytes = await asyncio.to_thread(tts_service.synthesize, text)
        await ws.send_bytes(mp3_bytes)  # 二进制帧，前端 <audio> 播放
    except Exception as e:
        logger.error(f"TTS 失败: {e}")
```

6. **WS 关闭时触发归档 finalize**：
```python
# 在 WebSocketDisconnect 处理处追加
await archive_writer.finalize(db)
```

7. **多设备订阅**（每条 WS 都订阅）：
```python
# 在 _run_live_loop 启动时
r = await get_redis()
pubsub = r.pubsub()
await pubsub.subscribe(f"transcript:{meeting_id}", f"ai_reply:{meeting_id}", f"speaker_mapping:{meeting_id}")

# 循环中（已有 level_task 旁路）加 transcript_broadcast_task：
async def _transcript_broadcast_loop(ws, pubsub):
    while True:
        try:
            msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), timeout=30.0)
            if msg:
                data = json.loads(msg["data"])
                if msg["channel"].decode().startswith("transcript:"):
                    await ws.send_json({"type": "transcript_others", "data": data})
                elif msg["channel"].decode().startswith("ai_reply:"):
                    await ws.send_json({"type": "ai_reply_others", "data": data})
                elif msg["channel"].decode().startswith("speaker_mapping:"):
                    # 刷新 meeting 对象
                    await db.refresh(meeting)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"broadcast loop 异常: {e}")
            break
```

8. **WS 初始连接拉历史**：
```python
# 在 accept 后，发送 snapshot
recent = await get_recent_transcript(meeting_id, seconds=60)
await ws.send_json({"type": "transcript_history", "entries": recent})
```

### 4.9 Admin 删除音频 API

**文件**：`app/api/v1/meeting.py`（追加）

```python
@router.delete("/{meeting_id}/audio", status_code=200)
async def delete_meeting_audio(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """
    管理员删除会议录音（保留纪要）
    """
    from app.models.meeting import Meeting
    from sqlalchemy import select
    from app.services.file_service import file_service
    from app.core.security import require_admin  # 如有

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

    # 软删除（标记 archived=False，保留字段供历史查询）
    meeting.audio_archived = False
    meeting.audio_archive_url = None
    # audio_archived_at / duration / size 保留（用于审计）
    await db.commit()

    return {"status": "deleted", "meeting_id": meeting_id}
```

### 4.10 ffmpeg 依赖验证

**前置条件**：Docker 镜像需含 ffmpeg。验证：
```bash
docker compose exec app which ffmpeg  # 应输出 /usr/bin/ffmpeg
```

如未安装，需修改 `Dockerfile.voice-pipeline` 或 `Dockerfile.app` 加 `apt-get install -y ffmpeg`。

---

## 5. 前端设计

### 5.1 useMeetingRoomWS 扩展

**文件**：`web/src/composables/useMeetingRoomWS.js`

**新增**：
```javascript
// 新 callback
const onAIReply = ref(null)  // AI 回复（含 action/text）
const onTranscriptOthers = ref(null)  // 其他设备的转录
const onAIReplyOthers = ref(null)  // 其他设备的 AI 回复
const onTranscriptHistory = ref(null)  // WS 初始历史
const onTTSAudio = ref(null)  // 二进制 TTS 帧（Blob）

// 新方法
function sendAICommand(action, params = {}) {
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ type: 'ai_command', action, ...params }))
  }
}

// handleJSONMessage 新增 case
case 'ai_reply': if (onAIReply.value) onAIReply.value(msg); break
case 'transcript_others': if (onTranscriptOthers.value) onTranscriptOthers.value(msg); break
case 'ai_reply_others': if (onAIReplyOthers.value) onAIReplyOthers.value(msg); break
case 'transcript_history': if (onTranscriptHistory.value) onTranscriptHistory.value(msg); break

// onmessage 二进制分支
if (typeof event.data !== 'string') {
  // 二进制帧 = TTS MP3
  if (onTTSAudio.value) onTTSAudio.value(event.data)
  return
}

// return 新增
return {
  ..., sendAICommand,
  onAIReply, onTranscriptOthers, onAIReplyOthers,
  onTranscriptHistory, onTTSAudio,
}
```

### 5.2 AIFloatButton 完善

**文件**：`web/src/components/meeting-room/AIFloatButton.vue`（完全重写）

**新结构**：
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
      <!-- 4 个快捷按钮 -->
      <div class="ai-actions">
        <el-button @click="onSummarizeRecent" :loading="loading.action === 'summarize_recent'">
          📝 总结最近 30 秒
        </el-button>
        <el-button @click="onTranslate" :loading="loading.action === 'translate'">
          🌐 中英翻译
        </el-button>
        <el-button @click="onSummarizeNow" :loading="loading.action === 'summarize_now'">
          📋 现在总结
        </el-button>
        <el-button @click="onAskVisible = true" :loading="loading.action === 'ask'">
          🤔 AI 提问
        </el-button>
      </div>
      <!-- 历史记录 -->
      <div class="ai-history">
        <div v-for="(item, i) in history" :key="i" class="history-item">
          <span class="action-label">{{ actionLabel(item.action) }}</span>
          <span class="text">{{ item.text }}</span>
          <el-button v-if="item.ttsUrl" link @click="playTTS(item)">🔊</el-button>
        </div>
      </div>
    </div>
    <!-- 提问对话框 -->
    <el-dialog v-model="onAskVisible" title="AI 提问" width="400px">
      <el-input v-model="askQuestion" type="textarea" :rows="3" placeholder="例如：刚才说的数据有出处吗？" />
      <template #footer>
        <el-button @click="onAskVisible = false">取消</el-button>
        <el-button type="primary" @click="onAsk">提问</el-button>
      </template>
    </el-dialog>
    <!-- TTS 播放器（隐藏） -->
    <audio ref="ttsAudio" style="display:none" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  onSendAICommand: { type: Function, required: true },
  onAIReply: { type: Function, default: null },
})
const emit = defineEmits(['air-reply'])

const expanded = ref(false)
const loading = ref({ action: null })
const history = ref([])  // {action, text, original?, ttsBase64?, ts}
const onAskVisible = ref(false)
const askQuestion = ref('')
const ttsAudio = ref(null)

function toggle() {
  expanded.value = !expanded.value
}

function onSummarizeRecent() {
  loading.value.action = 'summarize_recent'
  props.onSendAICommand('summarize_recent', { seconds: 30 })
  setTimeout(() => loading.value.action = null, 3000)
}

function onTranslate() {
  // 找最近一条 transcript 翻译（如有选中文字更好；简化：翻译最近 30 秒的总结）
  loading.value.action = 'translate'
  props.onSendAICommand('translate', { text: '（占位：翻译最近 30 秒）', lang: 'en' })
  setTimeout(() => loading.value.action = null, 3000)
}

function onSummarizeNow() {
  loading.value.action = 'summarize_now'
  props.onSendAICommand('summarize_now', {})
  setTimeout(() => loading.value.action = null, 3000)
}

function onAsk() {
  if (!askQuestion.value.trim()) return
  loading.value.action = 'ask'
  props.onSendAICommand('ask', { question: askQuestion.value })
  askQuestion.value = ''
  onAskVisible.value = false
  setTimeout(() => loading.value.action = null, 3000)
}

function actionLabel(action) {
  return { summarize_recent: '📝 30s', translate: '🌐 翻译', summarize_now: '📋 纪要', ask: '🤔 问' }[action] || action
}

function playTTS(item) {
  if (!item.ttsBase64) return
  const blob = new Blob([Uint8Array.from(atob(item.ttsBase64), c => c.charCodeAt(0))], { type: 'audio/mpeg' })
  ttsAudio.value.src = URL.createObjectURL(blob)
  ttsAudio.value.play()
}

defineExpose({ addHistoryItem: (item) => history.value.push(item) })
</script>
```

### 5.3 MeetingRoom 集成

**文件**：`web/src/components/MeetingRoom.vue`

**新增**：
- import AIFloatButton
- 接收 onAIReply 回调 → 添加到 AIFloatButton 历史
- 接收 onTTSAudio → 播放

```javascript
// useMeetingRoomWS 解构新增
const { ..., sendAICommand, onAIReply, onTranscriptOthers, onAIReplyOthers, onTranscriptHistory, onTTSAudio } = useMeetingRoomWS()

// AI 回复处理
onAIReply.value = (msg) => {
  // 添加到 AIFloatButton 历史
  if (aiFloatButtonRef.value) {
    aiFloatButtonRef.value.addHistoryItem({
      action: msg.action,
      text: msg.text,
      original: msg.original,
      ttsBase64: msg.tts_base64,  // 后端可推 base64 二进制
      ts: Date.now(),
    })
  }
  ElMessage.success(`小气: ${msg.text.substring(0, 30)}...`)
}

// TTS 播放
onTTSAudio.value = (bytes) => {
  const blob = new Blob([bytes], { type: 'audio/mpeg' })
  const url = URL.createObjectURL(blob)
  new Audio(url).play()
}
```

### 5.4 AI 浮窗历史持久化

**localStorage key**：`meeting_ai_history_{meetingId}`
- 存储 `{action, text, original?, ts}` 数组
- WS 断开时持久化，下次进入会议时恢复

### 5.5 滑动窗口前端提示

**MeetingRoom** 在顶部状态栏加"最近 30 秒"小提示：
- 后端推 `transcript_history` 时，前端显示绿色脉冲"过去 60s 内 5 条转录"

---

## 6. 数据流

### 6.1 "总结最近 30 秒" 数据流

```
用户点 AIFloatButton "📝 总结最近 30 秒"
    │
    ▼
sendAICommand("summarize_recent", {seconds: 30})
    │
    ▼
WS {type: "ai_command", action: "summarize_recent", seconds: 30}
    │
    ▼
/live 后端：summarize_recent(meeting_id, 30, db=db)
    │
    ├─→ get_recent_transcript(meeting_id, 30)
    │      └─→ Redis LRANGE meeting:{id}:transcript
    │      └─→ ts 过滤（now - ts <= 30）
    │
    ├─→ _simple_llm_call(prompt, db)
    │      └─→ Claude API
    │
    ▼
ws.send_json({type: "ai_reply", action: "summarize_recent", text: "..."})
ws.send_bytes(MP3)  # TTS 二进制帧
publish_ai_reply(meeting_id, reply)  # 广播给同会议其他设备
    │
    ▼
AIFloatButton 收到 onAIReply → addHistoryItem
收到 onTTSAudio → 播放 MP3
```

### 6.2 多设备同步数据流

```
设备 A 说话 → VAD → ASR → 识别张三
    │
    ▼
/live A 处理:
    ├─→ ws.send_json(transcript_entry)  # 推给设备 A
    ├─→ append_transcript(meeting_id, entry)  # Redis LIST
    └─→ publish_transcript(meeting_id, entry)  # Redis pub/sub
              │
              ▼
设备 B /live 处理（已订阅 transcript:{id} 频道）:
    ├─→ 收到 pub/sub 消息
    └─→ ws.send_json({type: "transcript_others", data: entry})  # 推给设备 B
              │
              ▼
设备 B 浏览器：useMeetingRoomWS.onTranscriptOthers 触发 → addTranscript(entry)
```

### 6.3 音频存档数据流

```
WS 接收 PCM chunk（每个 ~33ms 音频）
    │
    ▼
AudioArchiveWriter.feed_pcm(chunk)
    │ bytearray 累积
    ▼
WS 关闭（WebSocketDisconnect）
    │
    ▼
AudioArchiveWriter.finalize(db)
    │
    ├─→ 写临时 .pcm 文件
    ├─→ ffmpeg 转 opus（subprocess）
    ├─→ file_service.upload_to_path("meetings/{id}/audio.opus", bytes)
    ├─→ Meeting.audio_archive_url = "..."
    ├─→ audio_duration_seconds / size / archived_at / archived = true
    └─→ db.commit()
```

---

## 7. 错误处理

### 7.1 后端

| 场景 | 处理 | 用户感知 |
|---|---|---|
| ffmpeg 不可用 | catch + log + 跳过归档 | 会议无录音，纪要照常 |
| opus 编码失败 | catch + log + 跳过 | 同上 |
| MinIO 上传失败 | catch + log + 标记 audio_archived=False | 同上 |
| Redis 不可用 | catch + log + 滑窗查询返回空 | "最近没说话" |
| 滑窗无内容 | 提示"（无）" | 静默 |
| AI LLM 超时 | catch + return "(超时)" | 显示"(超时)" |
| TTS 失败 | catch + log + 静默 | 仍显示文本，不朗读 |
| 多设备订阅断线 | 静默重订阅 | 临时丢同步 |

### 7.2 前端

| 场景 | 处理 |
|---|---|
| TTS blob 构造失败 | console.error，不播放 |
| AI 回复未在 30s 内到 | loading.action = null（按钮恢复可点） |
| 历史记录 localStorage 满 | 截断保留最近 50 条 |
| WS 断线 | 第一波已处理 |

---

## 8. 测试策略

### 8.1 后端单测

**`tests/test_meeting_transcript_buffer.py`**（新）
- `test_append_and_get_recent`：append + get_recent_transcript 时间过滤
- `test_maxlen_200`：超过 200 自动 trim
- `test_expire_24h`：TTL 设置正确

**`tests/test_meeting_ai_interactive.py`**（新）
- `test_summarize_recent_basic`：mock Claude 返回文本
- `test_translate_zh_to_en`：中→英
- `test_summarize_now_returns_structured`：返回 summary + key_points
- `test_ask_returns_short_answer`：限制 50 字

**`tests/test_meeting_broadcast_service.py`**（新）
- `test_publish_transcript`：mock Redis publish
- `test_publish_ai_reply`：同上

**`tests/test_audio_archive_service.py`**（新）
- `test_feed_pcm_accumulates`：累积正确
- `test_finalize_too_short_skips`：< 1000 bytes 跳过
- `test_finalize_writes_meeting_fields`：mock 写入字段

### 8.2 集成测试

**`tests/test_live_ws_ai.py`**（新）
- `test_ai_command_summarize_recent`：WS 发 ai_command → 收到 ai_reply
- `test_ai_command_translate`：同上
- `test_ai_command_ask`：同上

**`tests/test_live_ws_broadcast.py`**（新）
- `test_2_devices_share_transcript`：两个 WS 互发广播

### 8.3 前端测试

项目无测试框架（wave 1 已确认）。E2E 手动验证。

---

## 9. 部署与迁移

### 9.1 DB 迁移

```bash
docker compose exec app alembic upgrade head
```

预期：`Running upgrade 010_voice_embedding_member -> 011_meeting_audio_archive, ...`

### 9.2 后端部署

新增/修改：
- 新建 `alembic/versions/011_meeting_audio_archive.py`
- 新建 `app/services/audio_archive_service.py`
- 新建 `app/services/meeting_transcript_buffer.py`
- 新建 `app/services/meeting_ai_interactive.py`
- 新建 `app/services/meeting_broadcast_service.py`
- 修改 `app/models/meeting.py`（+5 字段）
- 修改 `app/services/file_service.py`（+upload_to_path）
- 修改 `app/api/v1/voice.py`（/live 端点大量集成）
- 修改 `app/api/v1/meeting.py`（+admin DELETE 端点）
- 修改 `Dockerfile`（如 ffmpeg 缺失）

### 9.3 前端部署

- 修改 `web/src/composables/useMeetingRoomWS.js`（+新 callback）
- 修改 `web/src/components/meeting-room/AIFloatButton.vue`（完全重写）
- 修改 `web/src/components/MeetingRoom.vue`（集成 AI）

### 9.4 风险

| 风险 | 缓解 |
|---|---|
| ffmpeg 容器中缺失 | 部署前 `which ffmpeg` 验证；缺失则 apt-get |
| Redis LIST 内存增长 | LTRIM 限 200 条 + 24h TTL |
| 多设备 WS 增加 Redis pub/sub 流量 | 转录 10/min × 100 字节 = 16 KB/min，可忽略 |
| TTS 首次合成慢 | edge-tts 网络调用，< 2s |
| opus 文件大小预估 | 1h 16kHz mono @ 32kbps ≈ 14MB（5min = 1.2MB） |
| 浮窗 localStorage 满 | 截断保留最近 50 条 |

---

## 10. 验收标准

### 10.1 必达

1. ✅ `voice.py:453` `db=None` 修复，AI 工具调用工作
2. ✅ Alembic 011 迁移成功，5 字段就位
3. ✅ 30 秒滑窗：后端 Redis LIST 累积 + 时间过滤
4. ✅ "总结最近 30 秒"按钮 → 后端返回文本 + TTS MP3 推送给前端
5. ✅ "中英翻译"按钮 → 后端返回翻译文本
6. ✅ "现在总结"按钮 → 返回 summary + key_points
7. ✅ "AI 提问"按钮 → 输入问题 → 回答
8. ✅ AIFloatButton 历史记录 localStorage 持久化
9. ✅ /live 端点接入 AudioArchiveWriter，WS 关闭时自动 finalize
10. ✅ ffmpeg 转 opus + MinIO 上传 + 字段写入
11. ✅ Admin DELETE /meetings/{id}/audio 端点
12. ✅ 多设备：设备 A 的 transcript/AI 回复广播给设备 B
13. ✅ 单测覆盖率 > 70%（新增模块）

### 10.2 体验达

14. ✅ AI 回复延迟 < 5s（含 TTS）
15. ✅ 多设备同步延迟 < 500ms
16. ✅ 1 小时会议 opus 存档 < 15MB
17. ✅ TTS 播放延迟 < 1s

---

## 11. 实施顺序（建议 20-25 任务）

1. 修复 `db=None` bug
2. 测试 + 实现 Alembic 011 迁移
3. Meeting 模型 +5 字段
4. file_service.upload_to_path 扩展
5. audio_archive_service 实现
6. meeting_transcript_buffer 实现
7. meeting_ai_interactive 实现（4 能力）
8. meeting_broadcast_service 实现
9. /live 端点：AudioArchiveWriter 接入
10. /live 端点：滑窗 + 广播接入
11. /live 端点：AI 互动 4 能力接入
12. /live 端点：TTS 推送
13. /live 端点：多设备订阅
14. Admin DELETE audio 端点
15. 前端 useMeetingRoomWS 扩展
16. 前端 AIFloatButton 重写
17. 前端 MeetingRoom 集成
18. ffmpeg 依赖验证 + Dockerfile 修复（如需）
19. 本地构建 + 端到端测试
20. 部署到服务器
21. 最终验证 + ROADMAP 更新

---

**版本**：v1.0
**等待用户审阅** → 通过后进入 writing-plans 阶段生成实现计划
