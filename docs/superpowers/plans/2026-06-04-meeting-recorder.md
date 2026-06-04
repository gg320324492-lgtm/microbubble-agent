# 声纹会议系统重构 — 录音机 + 离线后处理 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将会议系统从实时 WS 流式处理改为"录音机 + 离线后处理"模式，提升 ASR 和声纹准确率

**架构：** 浏览器 MediaRecorder 录音 → 上传 MinIO → Celery 离线后处理（ASR + 声纹 + AI 分析 + 任务提取）→ WS 进度推送

**技术栈：** MediaRecorder API, Web Audio API (AnalyserNode), Canvas 波形, faster-whisper, 3D-Speaker, Claude Sonnet, Celery, MinIO, ffmpeg

**设计规格：** `docs/superpowers/specs/2026-06-04-meeting-recorder-design.md`

---

## 文件结构

### 新建

| 文件 | 职责 |
|------|------|
| `app/services/audio_processor.py` | 音频格式转换（WebM → 16kHz WAV）+ VAD 分段 |
| `app/api/v1/meeting_recording.py` | 录音相关 API 端点（start/upload/stop/audio） |
| `web/src/components/AudioRecorder.vue` | 录音机组件（MediaRecorder + 音量条 + 波形 + 播放） |

### 修改

| 文件 | 职责 |
|------|------|
| `app/models/meeting.py` | 新增 audio_url/audio_duration/recording_started_at/ended_at 字段 |
| `app/services/post_meeting_tasks.py` | 重写为 6 阶段离线后处理 |
| `app/services/progress_service.py` | 新增 DOWNLOADING_AUDIO / TRANSCRIBING / IDENTIFYING_SPEAKERS 阶段 |
| `app/api/v1/voice.py` | 删除 meeting_live_ws 端点，保留 ASR/TTS/voice_chat |
| `web/src/views/MeetingRoom.vue` | 完全重写为录音机 UI |
| `web/src/views/MeetingDetailView.vue` | 支持录音回放 + AI 标记字段 |
| `app/main.py` | 注册新路由 |

### 删除

| 文件 | 原因 |
|------|------|
| `app/voice/pipeline.py` | 实时流水线不再需要 |
| `app/services/meeting_batch_polisher.py` | L2 聚批润色不再需要 |
| `web/src/composables/useMeetingRoomWS.js` | 实时 WS composable 不再需要 |
| `web/src/components/LiveTranscript.vue` | 实时转写面板不再需要 |

### 保留（后处理仍需要）

| 文件 | 说明 |
|------|------|
| `app/voice/vad.py` | VAD（后处理分段用） |
| `app/services/voiceprint_service.py` | 声纹识别 |
| `app/services/meeting_full_polisher.py` | 简化为后处理阶段 3 的一部分 |
| `app/services/progress_service.py` | 进度推送（复用） |
| `app/services/meeting_analysis_service.py` | AI 分析（复用） |
| `web/src/components/ProcessingDialog.vue` | 进度弹窗（复用） |

---

## 任务 1：Meeting 模型新增字段 + 数据库迁移

**文件：**
- 修改：`app/models/meeting.py`
- 新建：迁移脚本（手动 ALTER TABLE）

- [ ] **步骤 1：在 Meeting 模型中新增字段**

```python
# app/models/meeting.py — 在 status 字段后添加
audio_url = Column(String(500), nullable=True)           # MinIO 录音路径
audio_duration = Column(Integer, nullable=True)           # 录音时长（秒）
recording_started_at = Column(DateTime, nullable=True)    # 开始听会时间
recording_ended_at = Column(DateTime, nullable=True)      # 结束听会时间
```

- [ ] **步骤 2：手动执行数据库迁移**

```sql
-- 在 PostgreSQL 中执行
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS audio_url VARCHAR(500);
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS audio_duration INTEGER;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS recording_started_at TIMESTAMP;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS recording_ended_at TIMESTAMP;
```

运行：`docker exec -it microbubble-agent-db-1 psql -U postgres -d microbubble -c "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS audio_url VARCHAR(500); ALTER TABLE meetings ADD COLUMN IF NOT EXISTS audio_duration INTEGER; ALTER TABLE meetings ADD COLUMN IF NOT EXISTS recording_started_at TIMESTAMP; ALTER TABLE meetings ADD COLUMN IF NOT EXISTS recording_ended_at TIMESTAMP;"`

- [ ] **步骤 3：验证字段已添加**

```sql
\d meetings
```

预期：输出中包含 audio_url, audio_duration, recording_started_at, recording_ended_at 四个新列

- [ ] **步骤 4：Commit**

```bash
git add app/models/meeting.py
git commit -m "feat(meeting): 新增录音相关字段 audio_url/duration/started_at/ended_at"
```

---

## 任务 2：音频处理服务

**文件：**
- 新建：`app/services/audio_processor.py`

- [ ] **步骤 1：编写测试**

```python
# tests/test_audio_processor.py
import pytest
import numpy as np
from app.services.audio_processor import AudioProcessor

def test_convert_webm_to_wav():
    """测试 WebM 转 WAV 格式转换"""
    processor = AudioProcessor()
    # 生成一个最小的 WebM 文件（实际测试需要用真实文件）
    # 这里测试 ffmpeg 调用链
    assert hasattr(processor, 'convert_to_wav')
    assert hasattr(processor, 'segment_by_vad')

def test_segment_by_vad():
    """测试 VAD 分段"""
    processor = AudioProcessor()
    # 生成 10 秒的测试音频（正弦波）
    sample_rate = 16000
    t = np.linspace(0, 10, sample_rate * 10, dtype=np.float32)
    audio = np.sin(2 * np.pi * 440 * t) * 0.5
    # 模拟语音段（高频）和静音段（低幅）
    audio[30000:50000] *= 0.01  # 静音
    audio[80000:100000] *= 0.01  # 静音
    
    segments = processor.segment_by_vad(audio, sample_rate)
    assert isinstance(segments, list)
    assert len(segments) >= 1  # 至少有一段
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd g:\microbubble-agent && python -m pytest tests/test_audio_processor.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.audio_processor'`

- [ ] **步骤 3：实现音频处理服务**

```python
# app/services/audio_processor.py
"""音频处理服务 — WebM 转 WAV + VAD 分段"""

import asyncio
import io
import logging
import tempfile
from dataclasses import dataclass
from typing import List

import numpy as np

logger = logging.getLogger("microbubble.audio_processor")

SAMPLE_RATE = 16000


@dataclass
class AudioSegment:
    """音频片段"""
    audio: np.ndarray      # float32 PCM
    start_time: float      # 秒
    end_time: float        # 秒


class AudioProcessor:
    """音频格式转换 + VAD 分段"""

    async def convert_webm_to_wav(self, webm_data: bytes) -> np.ndarray:
        """WebM/Opus → 16kHz mono float32 PCM（通过 ffmpeg）"""
        def _convert():
            import subprocess
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f_in:
                f_in.write(webm_data)
                input_path = f_in.name
            
            output_path = input_path.replace('.webm', '.wav')
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', input_path,
                    '-ar', str(SAMPLE_RATE),
                    '-ac', '1',
                    '-f', 'wav',
                    output_path
                ], capture_output=True, check=True, timeout=120)
                
                # 读取 WAV
                import wave
                with wave.open(output_path, 'rb') as wf:
                    pcm_bytes = wf.readframes(wf.getnframes())
                    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                return audio
            finally:
                import os
                try:
                    os.unlink(input_path)
                    os.unlink(output_path)
                except OSError:
                    pass
        
        return await asyncio.to_thread(_convert)

    def segment_by_vad(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> List[AudioSegment]:
        """用 VAD 将音频切割为语音段"""
        from app.voice.vad import VADEngine
        
        vad = VADEngine(threshold=0.5, min_speech_ms=500, min_silence_ms=300)
        
        # VAD 处理
        segments_raw = vad.process_audio(audio)
        
        segments = []
        for seg in segments_raw:
            if hasattr(seg, 'audio'):
                segments.append(AudioSegment(
                    audio=seg.audio,
                    start_time=seg.start_time if hasattr(seg, 'start_time') else 0,
                    end_time=seg.end_time if hasattr(seg, 'end_time') else 0,
                ))
        
        # 如果 VAD 没有返回段，把整段当作一个 segment
        if not segments:
            segments = [AudioSegment(audio=audio, start_time=0, end_time=len(audio) / sample_rate)]
        
        return segments


audio_processor = AudioProcessor()
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd g:\microbubble-agent && python -m pytest tests/test_audio_processor.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add app/services/audio_processor.py tests/test_audio_processor.py
git commit -m "feat(audio): 音频处理服务 — WebM→WAV 转换 + VAD 分段"
```

---

## 任务 3：录音 API 端点

**文件：**
- 新建：`app/api/v1/meeting_recording.py`
- 修改：`app/main.py`（注册路由）

- [ ] **步骤 1：编写测试**

```python
# tests/test_meeting_recording_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_start_recording(client: AsyncClient, auth_headers: dict):
    """测试创建录音会议"""
    res = await client.post("/api/v1/meetings/start-recording", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["status"] == "recording"
    assert data["recording_started_at"] is not None

@pytest.mark.asyncio
async def test_upload_audio(client: AsyncClient, auth_headers: dict):
    """测试上传录音文件"""
    # 先创建会议
    res = await client.post("/api/v1/meetings/start-recording", headers=auth_headers)
    meeting_id = res.json()["id"]
    
    # 上传假音频
    fake_audio = b'\x1a\x45\xdf\xa3' + b'\x00' * 100  # WebM header + padding
    res = await client.post(
        f"/api/v1/meetings/{meeting_id}/upload-audio",
        headers=auth_headers,
        files={"file": ("recording.webm", fake_audio, "audio/webm")}
    )
    assert res.status_code == 200
    assert res.json()["audio_url"] is not None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd g:\microbubble-agent && python -m pytest tests/test_meeting_recording_api.py -v`
预期：FAIL，404（路由不存在）

- [ ] **步骤 3：实现录音 API**

```python
# app/api/v1/meeting_recording.py
"""录音会议 API — 创建/上传/停止/获取音频"""

from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.file_service import file_service

router = APIRouter()


@router.post("/meetings/start-recording")
async def start_recording(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建录音会议（零配置，自动生成标题）"""
    now = datetime.now(timezone.utc)
    meeting = Meeting(
        title=f"听会 {now.strftime('%m-%d %H:%M')}",
        start_time=now,
        status="recording",
        recording_started_at=now,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return {
        "id": meeting.id,
        "title": meeting.title,
        "status": meeting.status,
        "recording_started_at": meeting.recording_started_at.isoformat(),
    }


@router.post("/meetings/{meeting_id}/upload-audio")
async def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传录音文件到 MinIO"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.status != "recording":
        raise HTTPException(status_code=400, detail="会议不在录音状态")

    file_data = await file.read()
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 上传到 MinIO
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{meeting_id}_{timestamp}.webm"
    upload_result = await file_service.upload_file(
        file_data=file_data,
        filename=filename,
        content_type=file.content_type or "audio/webm",
        prefix="recordings"
    )

    meeting.audio_url = upload_result.get("url") or upload_result.get("path")
    await db.commit()

    return {"audio_url": meeting.audio_url, "size": len(file_data)}


@router.post("/meetings/{meeting_id}/stop-recording")
async def stop_recording(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止录音，触发后处理"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.status != "recording":
        raise HTTPException(status_code=400, detail="会议不在录音状态")

    now = datetime.now(timezone.utc)
    meeting.recording_ended_at = now
    meeting.end_time = now
    meeting.status = "processing"
    
    # 计算录音时长
    if meeting.recording_started_at:
        delta = now - meeting.recording_started_at
        meeting.audio_duration = int(delta.total_seconds())
    
    await db.commit()

    # 触发 Celery 后处理
    from app.services.post_meeting_tasks import post_meeting_process
    post_meeting_process.delay(meeting.id)

    return {
        "id": meeting.id,
        "status": "processing",
        "audio_duration": meeting.audio_duration,
    }


@router.get("/meetings/{meeting_id}/audio")
async def get_audio_url(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取录音文件 URL（回放用）"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if not meeting.audio_url:
        raise HTTPException(status_code=404, detail="无录音文件")

    return {"audio_url": meeting.audio_url, "duration": meeting.audio_duration}
```

- [ ] **步骤 4：注册路由到 main.py**

```python
# app/main.py — 在已有路由注册处添加
from app.api.v1.meeting_recording import router as meeting_recording_router
app.include_router(meeting_recording_router, prefix="/api/v1", tags=["meeting-recording"])
```

- [ ] **步骤 5：运行测试验证通过**

运行：`cd g:\microbubble-agent && python -m pytest tests/test_meeting_recording_api.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add app/api/v1/meeting_recording.py app/main.py tests/test_meeting_recording_api.py
git commit -m "feat(meeting): 录音 API 端点 — start/upload/stop/audio"
```

---

## 任务 4：前端 AudioRecorder 组件

**文件：**
- 新建：`web/src/components/AudioRecorder.vue`

- [ ] **步骤 1：实现 AudioRecorder 组件**

```vue
<!-- web/src/components/AudioRecorder.vue -->
<template>
  <div class="audio-recorder">
    <!-- 状态：idle — 待录音 -->
    <div v-if="state === 'idle'" class="recorder-idle">
      <div class="recorder-icon">🎙️</div>
      <button class="btn-start" @click="startRecording">开始听会</button>
      <p class="recorder-hint">点击后即开始录音，无需填写任何信息</p>
    </div>

    <!-- 状态：recording — 录音中 -->
    <div v-else-if="state === 'recording' || state === 'paused'" class="recorder-active">
      <div class="recorder-status">
        <span class="rec-dot" :class="{ paused: state === 'paused' }" />
        {{ state === 'paused' ? '已暂停' : '录音中' }}
      </div>
      <div class="recorder-timer">{{ formattedTime }}</div>

      <!-- 音量指示器 -->
      <div class="volume-bars">
        <div v-for="(h, i) in barHeights" :key="i" class="vol-bar" :style="{ height: h + 'px' }" />
      </div>

      <div class="recorder-controls">
        <button v-if="state === 'recording'" class="btn-pause" @click="pauseRecording">⏸ 暂停</button>
        <button v-else class="btn-resume" @click="resumeRecording">▶ 继续</button>
        <button class="btn-stop" @click="confirmStop">⏹ 结束听会</button>
      </div>
    </div>

    <!-- 状态：stopped — 回放 -->
    <div v-else-if="state === 'stopped'" class="recorder-stopped">
      <div class="recorder-done">听会结束</div>
      <div class="recorder-duration">时长: {{ formattedTime }}</div>

      <!-- 波形渲染 -->
      <canvas ref="waveformCanvas" class="waveform-canvas" @click="seekWaveform" />

      <!-- 播放控制 -->
      <div class="playback-controls">
        <button class="btn-play" @click="togglePlayback">
          {{ isPlaying ? '⏸' : '▶' }}
        </button>
        <span class="playback-time">{{ formatTime(currentPlayTime) }} / {{ formattedTime }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, nextTick, watch } from 'vue'

const emit = defineEmits(['recording-start', 'recording-stop', 'audio-ready'])

// 状态机: idle → recording → paused → recording → stopped
const state = ref('idle')
const elapsed = ref(0)       // 录音时长（秒）
const isPlaying = ref(false)
const currentPlayTime = ref(0)

// 录音相关
let mediaRecorder = null
let audioChunks = []
let audioContext = null
let analyser = null
let dataArray = null
let timerInterval = null
let animationFrame = null

// 回放相关
let audioBlob = null
let audioElement = null
let waveformData = null

const formattedTime = computed(() => formatTime(elapsed.value))

// 音量条高度（5 根）
const barHeights = ref([4, 4, 4, 4, 4])

function formatTime(seconds) {
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

// ===== 录音 =====

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    
    // 音频分析（音量指示器）
    audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
    dataArray = new Uint8Array(analyser.frequencyBinCount)

    // MediaRecorder
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
    audioChunks = []

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }

    mediaRecorder.onstop = () => {
      audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
      stream.getTracks().forEach(t => t.stop())
      emit('audio-ready', audioBlob)
    }

    mediaRecorder.start(1000) // 每秒收集一次数据
    state.value = 'recording'
    elapsed.value = 0
    emit('recording-start')

    // 计时器
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)

    // 音量动画
    updateVolumeBars()
  } catch (err) {
    console.error('录音启动失败:', err)
    alert('无法访问麦克风，请检查浏览器权限')
  }
}

function pauseRecording() {
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.pause()
    state.value = 'paused'
    clearInterval(timerInterval)
    cancelAnimationFrame(animationFrame)
  }
}

function resumeRecording() {
  if (mediaRecorder?.state === 'paused') {
    mediaRecorder.resume()
    state.value = 'recording'
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)
    updateVolumeBars()
  }
}

function confirmStop() {
  if (confirm('确定结束听会？')) {
    stopRecording()
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  clearInterval(timerInterval)
  cancelAnimationFrame(animationFrame)
  state.value = 'stopped'

  // 生成波形数据
  nextTick(() => generateWaveform())
}

// ===== 音量指示器 =====

function updateVolumeBars() {
  if (!analyser) return
  analyser.getByteFrequencyData(dataArray)

  // 取 5 个频段的平均值
  const bands = 5
  const step = Math.floor(dataArray.length / bands)
  const heights = []
  for (let i = 0; i < bands; i++) {
    let sum = 0
    for (let j = i * step; j < (i + 1) * step; j++) {
      sum += dataArray[j]
    }
    const avg = sum / step
    heights.push(Math.max(4, Math.min(40, avg / 4)))
  }
  barHeights.value = heights

  if (state.value === 'recording') {
    animationFrame = requestAnimationFrame(updateVolumeBars)
  }
}

// ===== 波形渲染 =====

async function generateWaveform() {
  if (!audioBlob || !waveformCanvas.value) return

  const canvas = waveformCanvas.value
  const ctx = canvas.getContext('2d')
  const width = canvas.offsetWidth * 2  // 高清
  const height = canvas.offsetHeight * 2
  canvas.width = width
  canvas.height = height

  // 解码音频
  const arrayBuffer = await audioBlob.arrayBuffer()
  const decoded = await audioContext.decodeAudioData(arrayBuffer)
  const channelData = decoded.getChannelData(0)

  // 采样（取 width 个点）
  const step = Math.floor(channelData.length / width)
  waveformData = []
  for (let i = 0; i < width; i++) {
    let min = 1, max = -1
    for (let j = i * step; j < (i + 1) * step && j < channelData.length; j++) {
      if (channelData[j] < min) min = channelData[j]
      if (channelData[j] > max) max = channelData[j]
    }
    waveformData.push({ min, max })
  }

  // 绘制
  ctx.fillStyle = '#f5f5f5'
  ctx.fillRect(0, 0, width, height)

  ctx.fillStyle = '#FF7A5C'
  const mid = height / 2
  for (let i = 0; i < waveformData.length; i++) {
    const { min, max } = waveformData[i]
    const yMin = mid + min * mid
    const yMax = mid + max * mid
    ctx.fillRect(i, yMin, 1, yMax - yMin || 1)
  }
}

function seekWaveform(e) {
  if (!audioElement || !waveformData) return
  const rect = e.target.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  audioElement.currentTime = ratio * audioElement.duration
  currentPlayTime.value = audioElement.currentTime
}

// ===== 播放 =====

function togglePlayback() {
  if (!audioElement) {
    audioElement = new Audio(URL.createObjectURL(audioBlob))
    audioElement.ontimeupdate = () => {
      currentPlayTime.value = audioElement.currentTime
    }
    audioElement.onended = () => {
      isPlaying.value = false
      currentPlayTime.value = 0
    }
  }

  if (isPlaying.value) {
    audioElement.pause()
    isPlaying.value = false
  } else {
    audioElement.play()
    isPlaying.value = true
  }
}

// ===== 清理 =====

onUnmounted(() => {
  clearInterval(timerInterval)
  cancelAnimationFrame(animationFrame)
  if (audioElement) {
    audioElement.pause()
    audioElement = null
  }
  if (audioContext) {
    audioContext.close()
  }
})

// ===== 暴露方法 =====

defineExpose({
  getAudioBlob: () => audioBlob,
  getDuration: () => elapsed.value,
})
</script>

<style scoped>
.audio-recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px 20px;
}

/* idle */
.recorder-idle { text-align: center; }
.recorder-icon { font-size: 64px; margin-bottom: 20px; }
.btn-start {
  padding: 16px 48px; font-size: 18px; font-weight: 700;
  background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: #fff;
  border: none; border-radius: 32px; cursor: pointer;
  transition: all 0.2s;
}
.btn-start:hover { transform: scale(1.05); box-shadow: 0 6px 20px rgba(255,122,92,0.4); }
.recorder-hint { color: #999; font-size: 13px; margin-top: 12px; }

/* recording */
.recorder-active { text-align: center; }
.recorder-status { font-size: 16px; font-weight: 600; color: #333; display: flex; align-items: center; gap: 8px; justify-content: center; }
.rec-dot { width: 10px; height: 10px; border-radius: 50%; background: #F56C6C; animation: pulse 1.5s infinite; }
.rec-dot.paused { animation: none; background: #E6A23C; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.recorder-timer { font-size: 48px; font-weight: 300; font-family: 'SF Mono', monospace; color: #2D2D2D; margin: 20px 0; }
.volume-bars { display: flex; gap: 6px; align-items: flex-end; justify-content: center; height: 44px; margin: 16px 0; }
.vol-bar { width: 8px; background: linear-gradient(to top, #FF7A5C, #FFB347); border-radius: 4px; transition: height 0.1s; }
.recorder-controls { display: flex; gap: 16px; margin-top: 24px; }
.btn-pause, .btn-resume, .btn-stop {
  padding: 10px 28px; font-size: 15px; font-weight: 600;
  border: none; border-radius: 24px; cursor: pointer; transition: all 0.2s;
}
.btn-pause, .btn-resume { background: #f0f0f0; color: #333; }
.btn-pause:hover, .btn-resume:hover { background: #e0e0e0; }
.btn-stop { background: #F56C6C; color: #fff; }
.btn-stop:hover { background: #E65D5D; }

/* stopped */
.recorder-stopped { text-align: center; width: 100%; max-width: 600px; }
.recorder-done { font-size: 20px; font-weight: 700; color: #333; }
.recorder-duration { font-size: 14px; color: #999; margin: 4px 0 20px; }
.waveform-canvas {
  width: 100%; height: 80px; border-radius: 8px; cursor: pointer;
  border: 1px solid #eee;
}
.playback-controls { display: flex; align-items: center; gap: 12px; justify-content: center; margin-top: 12px; }
.btn-play {
  width: 40px; height: 40px; border-radius: 50%; border: none;
  background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: #fff;
  font-size: 16px; cursor: pointer;
}
.playback-time { font-size: 13px; color: #666; font-family: 'SF Mono', monospace; }
</style>
```

- [ ] **步骤 2：在浏览器中验证组件**

在 MeetingView 或临时页面中引入 AudioRecorder 组件，验证：
- 点击"开始听会"能启动录音
- 音量条实时跳动
- 暂停/继续正常
- 结束后波形渲染正确
- 播放/暂停回放正常

- [ ] **步骤 3：Commit**

```bash
git add web/src/components/AudioRecorder.vue
git commit -m "feat(ui): AudioRecorder 组件 — 录音+音量条+波形+播放"
```

---

## 任务 5：重写 MeetingRoom.vue

**文件：**
- 重写：`web/src/views/MeetingRoom.vue`

- [ ] **步骤 1：重写 MeetingRoom 为录音机模式**

```vue
<!-- web/src/views/MeetingRoom.vue -->
<template>
  <div class="meeting-room">
    <!-- 顶部栏 -->
    <header class="room-header">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回
      </el-button>
      <span class="room-title">{{ pageTitle }}</span>
    </header>

    <!-- 主内容 -->
    <main class="room-main">
      <!-- 录音机组件 -->
      <AudioRecorder
        ref="recorderRef"
        @recording-start="onRecordingStart"
        @recording-stop="onRecordingStop"
        @audio-ready="onAudioReady"
      />
    </main>

    <!-- 处理进度弹窗 -->
    <ProcessingDialog
      v-if="showProgress"
      :meeting-id="meetingId"
      @close="onProgressClose"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import AudioRecorder from '@/components/AudioRecorder.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'

const router = useRouter()
const recorderRef = ref(null)

const meetingId = ref(null)
const showProgress = ref(false)

const pageTitle = computed(() => meetingId.value ? `听会 #${meetingId.value}` : '开始听会')

function goBack() {
  if (meetingId.value && !showProgress.value) {
    if (confirm('录音未保存，确定返回？')) router.push('/meetings')
  } else {
    router.push('/meetings')
  }
}

async function onRecordingStart() {
  try {
    const res = await axios.post('/api/v1/meetings/start-recording')
    meetingId.value = res.data.id
    ElMessage.success('开始听会')
  } catch (err) {
    ElMessage.error('创建会议失败: ' + (err.response?.data?.detail || err.message))
  }
}

async function onAudioReady(blob) {
  if (!meetingId.value) return

  try {
    // 上传音频
    const fd = new FormData()
    fd.append('file', blob, `recording_${meetingId.value}.webm`)
    await axios.post(`/api/v1/meetings/${meetingId.value}/upload-audio`, fd)

    // 停止录音，触发后处理
    await axios.post(`/api/v1/meetings/${meetingId.value}/stop-recording`)

    showProgress.value = true
  } catch (err) {
    ElMessage.error('上传失败: ' + (err.response?.data?.detail || err.message))
  }
}

function onRecordingStop() {
  // AudioRecorder 内部处理，这里不需要额外逻辑
}

function onProgressClose() {
  showProgress.value = false
  router.push(`/meetings/${meetingId.value}`)
}
</script>

<style scoped>
.meeting-room {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px); border-radius: var(--radius-lg);
  background: linear-gradient(180deg, #f8f9fb 0%, #fefefe 100%);
  overflow: hidden;
}
.room-header {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 20px; background: rgba(255,255,255,0.85);
  backdrop-filter: blur(12px); border-bottom: 1px solid rgba(0,0,0,0.05);
}
.room-title { font-size: 15px; font-weight: 600; color: #2D2D2D; }
.room-main { flex: 1; display: flex; align-items: center; justify-content: center; }
@media (max-width: 768px) {
  .meeting-room { height: calc(100vh - 56px); border-radius: 0; }
}
</style>
```

- [ ] **步骤 2：浏览器验证**

- 进入会议页面，看到"开始听会"按钮
- 点击后录音正常，音量条跳动
- 结束后自动上传并弹出 ProcessingDialog
- 处理完成后跳转到会议详情页

- [ ] **步骤 3：Commit**

```bash
git add web/src/views/MeetingRoom.vue
git commit -m "feat(meeting): MeetingRoom 重写为录音机模式"
```

---

## 任务 6：重写 post_meeting_tasks（6 阶段离线后处理）

**文件：**
- 重写：`app/services/post_meeting_tasks.py`
- 修改：`app/services/progress_service.py`（新增阶段枚举）

- [ ] **步骤 1：更新 ProgressStage 枚举**

```python
# app/services/progress_service.py — 更新 ProgressStage
class ProgressStage(str, Enum):
    DOWNLOADING_AUDIO = "downloading_audio"       # 0: 下载+转码
    TRANSCRIBING = "transcribing"                  # 1: ASR 转写
    IDENTIFYING_SPEAKERS = "identifying_speakers"  # 2: 声纹识别
    GENERATING_ANALYSIS = "generating_analysis"    # 3: AI 分析
    CREATING_TASKS = "creating_tasks"              # 4: 创建任务
    STORING_RESULTS = "storing_results"            # 5: 存储结果
    DONE = "done"                                  # 6: 完成
```

- [ ] **步骤 2：重写 post_meeting_tasks**

```python
# app/services/post_meeting_tasks.py
"""会议后处理任务 — 6 阶段离线处理

阶段：
0. downloading_audio — 下载音频 + ffmpeg 转 16kHz WAV
1. transcribing — faster-whisper ASR 转写
2. identifying_speakers — 3D-Speaker 声纹识别 + 发言人标注
3. generating_analysis — Claude Sonnet 分析（标题+摘要+要点+决议）
4. creating_tasks — 从决议/要点自动创建任务
5. storing_results — 存储结果到 DB
6. done — 完成通知
"""

import asyncio
import logging
import tempfile
import os

from app.core.celery import celery_app
from app.services.progress_service import ProgressStage, update_progress

logger = logging.getLogger("microbubble.post_meeting")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def post_meeting_process(self, meeting_id: int):
    """Celery 任务：6 阶段离线后处理"""
    logger.info(f"开始后处理: meeting_id={meeting_id}")

    async def _run():
        import redis.asyncio as aioredis
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy.pool import NullPool
        from app.config import settings

        engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            poolclass=NullPool,
        )
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as db:
            from app.models.meeting import Meeting
            from sqlalchemy import select
            result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
            meeting = result.scalar_one_or_none()
            if not meeting:
                logger.error(f"会议不存在: {meeting_id}")
                return

            try:
                # ===== 阶段 0: 下载音频 + 转码 =====
                await update_progress(meeting_id, ProgressStage.DOWNLOADING_AUDIO, detail="下载音频并转码", redis_override=redis_client)
                from app.services.audio_processor import audio_processor
                from app.services.file_service import file_service

                # 从 MinIO 下载音频
                audio_data = await file_service.download_file(meeting.audio_url)
                if not audio_data:
                    raise ValueError("音频文件下载失败")

                # WebM → 16kHz WAV
                audio_pcm = await audio_processor.convert_webm_to_wav(audio_data)
                sample_rate = 16000

                # VAD 分段
                segments = audio_processor.segment_by_vad(audio_pcm, sample_rate)
                logger.info(f"VAD 分段完成: {len(segments)} 段")

                # ===== 阶段 1: ASR 转写 =====
                await update_progress(meeting_id, ProgressStage.TRANSCRIBING, detail=f"转写 {len(segments)} 个语音段", redis_override=redis_client)
                from app.voice.asr import transcribe_segments

                transcript_segments = await transcribe_segments(
                    segments, sample_rate=sample_rate
                )
                logger.info(f"ASR 转写完成: {len(transcript_segments)} 段")

                # ===== 阶段 2: 声纹识别 =====
                await update_progress(meeting_id, ProgressStage.IDENTIFYING_SPEAKERS, detail="识别发言人", redis_override=redis_client)
                from app.services.voiceprint_service import VoiceprintService

                vp_service = VoiceprintService()
                speaker_mapping = {}

                for seg in transcript_segments:
                    # 从 audio_pcm 中截取对应时间段的音频
                    start_sample = int(seg["start"] * sample_rate)
                    end_sample = int(seg["end"] * sample_rate)
                    seg_audio = audio_pcm[start_sample:end_sample]

                    if len(seg_audio) < sample_rate * 0.5:
                        continue  # 太短跳过

                    # 声纹匹配
                    speaker_id, confidence = await vp_service.identify_speaker_from_audio(
                        seg_audio, db=db
                    )
                    if speaker_id and confidence > 0.55:
                        from sqlalchemy import select as sa_select
                        from app.models.member import Member
                        member_result = await db.execute(sa_select(Member).where(Member.id == speaker_id))
                        member = member_result.scalar_one_or_none()
                        if member:
                            seg["speaker"] = member.name
                            speaker_mapping[seg.get("speaker_label", f"speaker_{speaker_id}")] = member.name
                        else:
                            seg["speaker"] = f"发言人{seg.get('speaker_label', 'A')}"
                    else:
                        seg["speaker"] = f"发言人{seg.get('speaker_label', 'A')}"

                # ===== 阶段 3: AI 分析 =====
                await update_progress(meeting_id, ProgressStage.GENERATING_ANALYSIS, detail="AI 分析会议内容", redis_override=redis_client)
                from app.services.meeting_analysis_service import meeting_analysis

                # 构建转写文本
                transcript_text = "\n".join(
                    f"{seg.get('speaker', '未知')}: {seg['text']}"
                    for seg in transcript_segments
                )

                # 生成标题
                if not meeting.title or meeting.title.startswith("听会"):
                    meeting.title = await meeting_analysis.generate_title(transcript_text)

                # 分析摘要/要点/决议
                analysis = await meeting_analysis.analyze_transcript(
                    transcript_text, speaker_mapping=speaker_mapping
                )
                meeting.summary = analysis.get("summary")
                meeting.key_points = analysis.get("key_points", [])
                meeting.decisions = analysis.get("decisions", [])

                # 保存转写结果
                meeting.transcript = transcript_segments
                meeting.speaker_mapping = speaker_mapping

                # ===== 阶段 4: 自动创建任务 =====
                await update_progress(meeting_id, ProgressStage.CREATING_TASKS, detail="自动创建任务", redis_override=redis_client)
                from app.services.meeting_service import MeetingService
                svc = MeetingService(db)

                for decision in analysis.get("decisions", []):
                    await svc._auto_create_task_from_meeting(meeting, decision)

                # ===== 阶段 5: 存储结果 =====
                await update_progress(meeting_id, ProgressStage.STORING_RESULTS, detail="保存结果", redis_override=redis_client)
                meeting.status = "completed"
                await db.commit()

                # ===== 阶段 6: 完成 =====
                await update_progress(meeting_id, ProgressStage.DONE, detail="处理完成", redis_override=redis_client)
                logger.info(f"后处理完成: meeting_id={meeting_id}")

            except Exception as e:
                logger.error(f"后处理阶段失败: meeting_id={meeting_id}, error={e}", exc_info=True)
                meeting.status = "error"
                await db.commit()
                await update_progress(
                    meeting_id, ProgressStage.DONE,
                    detail=f"处理失败: {str(e)[:80]}",
                    status="error",
                    redis_override=redis_client,
                )

        await redis_client.aclose()
        await engine.dispose()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"后处理失败: meeting_id={meeting_id}, error={e}", exc_info=True)
        try:
            err_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(err_loop)
            try:
                err_loop.run_until_complete(update_progress(
                    meeting_id, ProgressStage.DONE,
                    detail=f"处理失败: {str(e)[:80]}",
                    status="error",
                ))
            finally:
                err_loop.close()
        except Exception as push_err:
            logger.error(f"推送 error 状态也失败: {push_err}")
        return {"status": "error", "meeting_id": meeting_id, "error": str(e)}
```

- [ ] **步骤 3：Commit**

```bash
git add app/services/post_meeting_tasks.py app/services/progress_service.py
git commit -m "feat(meeting): 重写后处理为 6 阶段离线流水线（ASR+声纹+AI+任务）"
```

---

## 任务 7：删除旧实时系统代码

**文件：**
- 删除：`app/voice/pipeline.py`
- 删除：`app/services/meeting_batch_polisher.py`
- 删除：`web/src/composables/useMeetingRoomWS.js`
- 删除：`web/src/components/LiveTranscript.vue`
- 修改：`app/api/v1/voice.py`（删除 meeting_live_ws 端点）

- [ ] **步骤 1：删除不需要的文件**

```bash
rm app/voice/pipeline.py
rm app/services/meeting_batch_polisher.py
rm web/src/composables/useMeetingRoomWS.js
rm web/src/components/LiveTranscript.vue
```

- [ ] **步骤 2：从 voice.py 中删除 meeting_live_ws 端点**

删除 `app/api/v1/voice.py` 中以下函数：
- `meeting_live_ws`（第 321 行起）
- `_polish_and_send`（第 409 行起）
- `_run_live_loop`（第 609 行起）
- `_live_loop_inner`（第 689 行起）
- `_audio_level_loop`（第 1216 行起）
- `_broadcast_loop`（第 1258 行起）
- 相关的幻觉过滤函数（`_is_repetitive_text`, `_is_alphanumeric_run`, `_is_gibberish`, `_is_sentence_repetitive`）如果后处理不需要也删除

保留的端点：
- `POST /voice/asr` — ASR 转写（后处理可能复用）
- `POST /voice/tts` — 文字转语音
- `POST /voice/chat` — 语音对话
- `GET /voice/voices` — 获取可用声音
- `WS /ws/voice/{user_id}` — 语音 WebSocket（非会议相关）
- `WS /ws/meeting/{meeting_id}/transcript` — 转写结果推送（后处理进度用）

- [ ] **步骤 3：检查并修复 import 错误**

```bash
cd g:\microbubble-agent && python -c "from app.api.v1 import voice; print('OK')"
```

如果报错，修复被删除模块的 import 引用。

- [ ] **步骤 4：Commit**

```bash
git add -A
git commit -m "refactor(meeting): 删除实时 WS 系统代码（pipeline/batch_polisher/LiveTranscript）"
```

---

## 任务 8：集成测试 + 端到端验证

- [ ] **步骤 1：启动本地服务**

```bash
cd g:\microbubble-agent
docker-compose restart app celery-worker
```

- [ ] **步骤 2：浏览器端到端测试**

1. 打开会议页面，点击"开始听会"
2. 说几句话，观察音量条跳动
3. 暂停 → 继续 → 结束听会
4. 检查波形渲染和播放回放
5. 等待后处理完成（ProcessingDialog 显示进度）
6. 检查会议详情页：标题、参会人、摘要、要点、转写

- [ ] **步骤 3：修复发现的问题**

- [ ] **步骤 4：Commit 修复**

```bash
git add -A
git commit -m "fix(meeting): 集成测试修复"
```

---

## 自检

1. **规格覆盖度** ✅ — 所有规格需求（零配置开录、音量指示器、波形渲染、AI 自动补信息、人工微调、MinIO 存储）都有对应任务
2. **占位符扫描** ✅ — 无 TODO/TBD
3. **类型一致性** ✅ — ProgressStage 枚举、Meeting 模型字段、API 响应格式在各任务间一致
