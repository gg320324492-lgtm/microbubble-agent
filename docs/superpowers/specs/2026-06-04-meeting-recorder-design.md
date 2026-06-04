# 声纹会议系统重构：录音机 + 离线后处理

> 日期：2026-06-04
> 状态：设计通过，待实现
> 替代：现有实时 WS 流式处理（VAD → 声纹 → ASR 实时流水线）

## 背景

现有声纹会议系统采用实时流式处理（WebSocket + VAD + 声纹 + ASR），存在以下问题：
- faster-whisper 实时分段转写幻觉严重（短音频上下文不足）
- WebSocket 连接不稳定（频繁断连重连）
- 声纹匹配基于 0.5s 碎片，准确率低
- 三级润色流水线（L1/L2/L3）复杂度高，维护困难

## 目标

将会议系统从"实时流式"改为"录音机 + 离线后处理"：
1. **零配置开录** — 点击「开始听会」即录，无需填写任何信息
2. **录音中有反馈** — 音量指示器实时跳动，录音时长计时
3. **录音后可回放** — 波形渲染 + 播放控制
4. **AI 自动补信息** — 后处理自动填充标题、参会人、摘要、要点、决议
5. **人工微调** — AI 不确定的字段留空，人工补充

## 数据流

```
浏览器 MeetingRoom
  │
  ├─ 点击「开始听会」→ MediaRecorder 录音
  │   ├─ AnalyserNode → 音量指示器（竖条跳动）
  │   └─ 暂停/继续/停止
  │
  ├─ 停止录音 → WebM 音频
  │   ├─ decodeAudioData → Canvas 波形渲染
  │   └─ 上传到 MinIO
  │
  └─ 触发后处理 → ProcessingDialog 显示进度
       │
       ▼
Celery Worker (post_meeting_process)
  │
  ├─ 阶段 0: 音频预处理（WebM → 16kHz WAV → VAD 分段）
  ├─ 阶段 1: ASR 转写（faster-whisper，整段处理）
  ├─ 阶段 2: 声纹识别（完整语段匹配 → 发言人标注）
  ├─ 阶段 3: AI 分析（标题 + 摘要 + 要点 + 决议 + 润色）
  ├─ 阶段 4: 自动创建任务
  └─ 阶段 5: 存储结果 + WS 通知
```

## 前端设计

### 听会前（极简）

MeetingRoom 页面只有一个大按钮：

```
┌──────────────────────────────────────────┐
│                                          │
│          🎙️                              │
│                                          │
│       [ 开始听会 ]                        │
│                                          │
│   点击后即开始录音，无需填写任何信息         │
│                                          │
└──────────────────────────────────────────┘
```

### 听会中

```
┌──────────────────────────────────────────┐
│                                          │
│           🔴 录音中                       │
│           00:12:34                       │
│                                          │
│    ▎▎ ▎▎▎ ▎▎ ▎▎▎▎ ▎▎ ▎▎▎ ▎▎            │  ← 音量指示器
│                                          │
│     [⏸ 暂停]    [⏹ 结束听会]             │
│                                          │
└──────────────────────────────────────────┘
```

- **计时器** — `HH:MM:SS` 格式
- **音量指示器** — 5-8 根竖条，根据 `AnalyserNode.getByteFrequencyData()` 实时跳动
- **暂停/继续** — `MediaRecorder.pause()` / `.resume()`
- **结束听会** — 二次确认弹窗

### 听会结束后（回放 + 处理中）

```
┌──────────────────────────────────────────┐
│  听会结束                                 │
│  时长: 00:12:34                          │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  ~~~~∿∿∿~~~~∿∿∿∿~~~~∿∿~~~~∿∿∿∿~~  │  │  ← 波形渲染
│  │  ▲                                   │  │
│  └────────────────────────────────────┘  │
│  [▶ 播放]  00:03:12 / 00:12:34          │
│                                          │
│  [🔄 开始处理]                            │  ← 自动触发
│                                          │
└──────────────────────────────────────────┘
```

- **波形** — `AudioContext.decodeAudioData()` 解码 → Canvas 绘制振幅
- **播放控制** — 播放/暂停 + 进度条（可拖拽）
- **自动触发** — 录音停止后 2 秒自动开始后处理（用户也可手动点击）

### 处理完成后（会议详情页）

AI 自动填充的字段显示「AI」标签，可编辑：

```
┌──────────────────────────────────────────┐
│  📝 微纳米气泡 zeta 电位讨论  [AI] [编辑]  │
│                                          │
│  参会人: 张三、李四、王五  [AI] [编辑]      │
│  时间: 2026-06-04 14:00 ~ 14:12          │
│  地点: _______________  ← 人工填写        │
│                                          │
│  📋 摘要                                  │
│  本次会议讨论了 zeta 电位的测量方法...      │
│                                          │
│  🔑 要点                                  │
│  • zeta 电位与气泡稳定性正相关             │
│  • pH 值 6-8 时测量最准确                 │
│                                          │
│  ✅ 决议                                  │
│  • 下周补充 pH 对照实验                    │
│  • 张三负责整理文献综述                    │
│                                          │
│  🎵 录音回放  [▶ 播放]                    │
│                                          │
│  📝 转写                                  │
│  张三: 我们今天讨论一下 zeta 电位...       │
│  李四: 好的，我先说一下实验数据...          │
│                                          │
└──────────────────────────────────────────┘
```

## 后端设计

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/meetings/start-recording` | POST | 创建会议（status=recording），返回 meeting_id |
| `/meetings/{id}/upload-audio` | POST | 上传录音文件到 MinIO |
| `/meetings/{id}/stop-recording` | POST | 更新状态，触发后处理 |
| `/meetings/{id}/audio` | GET | 获取录音文件 URL（回放用） |
| `/ws/meeting/{id}/progress` | WS | 后处理进度推送（复用现有） |

### 后处理流水线（Celery）

```python
@celery_app.task
def post_meeting_process(meeting_id: int):
    """6 阶段离线后处理"""
    # 阶段 0: 音频预处理
    #   MinIO 下载 WebM → ffmpeg 转 16kHz WAV → VAD 分段（5-30s/段）
    
    # 阶段 1: ASR 转写
    #   faster-whisper 整段转写，condition_on_previous_text=True
    #   输出: [{text, start, end, speaker_label}, ...]
    
    # 阶段 2: 声纹识别
    #   3D-Speaker 提取每段嵌入 → pgvector 匹配 members
    #   完整语段匹配（5-30s），准确率远高于实时碎片（0.5s）
    #   输出: speaker_mapping + 每段标注发言人
    
    # 阶段 3: AI 分析
    #   Claude Sonnet 分析完整转写 → 标题 + 摘要 + 要点 + 决议 + 润色
    
    # 阶段 4: 自动创建任务
    #   从决议/要点提取待办，指派给声纹匹配的成员
    
    # 阶段 5: 存储 + 通知
    #   写入 Meeting 表，WS 推送完成通知
```

### 音频处理

- **录音格式**：WebM/Opus（浏览器 MediaRecorder 默认，体积小）
- **转换**：ffmpeg 转 16kHz mono PCM（ASR/声纹标准格式）
- **存储**：MinIO `microbubble` bucket，路径 `recordings/{meeting_id}_{timestamp}.webm`

### Meeting 模型变更

**新增字段**：
```python
audio_url = Column(String(500))           # MinIO 录音路径
audio_duration = Column(Integer)           # 录音时长（秒）
recording_started_at = Column(DateTime)    # 开始听会时间
recording_ended_at = Column(DateTime)      # 结束听会时间
```

**status 状态机**：
```
recording → processing → completed
                     ↘ error（处理失败）
```

## 代码变更范围

### 删除（实时系统相关）

| 文件 | 说明 |
|------|------|
| `app/api/v1/voice.py` 的 `meeting_live_ws` | 实时 WS 端点 |
| `app/voice/pipeline.py` | 实时 VAD→声纹→ASR 流水线 |
| `app/services/meeting_batch_polisher.py` | L2 聚批润色 |
| `web/src/components/LiveSpeakerPanel.vue` | 实时发言人面板 |
| `web/src/components/ConfidenceChart.vue` | 声纹置信度图表 |
| `web/src/components/TimelineScrubber.vue` | 时间轴滑块 |
| `web/src/composables/useMeetingRoomWS.js` | 实时 WS composable |

### 保留（后处理仍需要）

| 文件 | 说明 |
|------|------|
| `app/voice/vad.py` | VAD（后处理分段用） |
| `app/services/voiceprint_service.py` | 声纹识别（后处理匹配用） |
| `app/services/meeting_full_polisher.py` | 简化为后处理阶段 3 |
| `app/services/post_meeting_tasks.py` | 重写为 6 阶段 |
| `app/services/progress_service.py` | 进度推送（复用） |
| `app/services/meeting_analysis_service.py` | AI 分析（复用） |

### 新增

| 文件 | 说明 |
|------|------|
| `web/src/components/AudioRecorder.vue` | 录音机组件（MediaRecorder + 音量条 + 波形） |
| `app/api/v1/meeting_recording.py` | 录音相关 API 端点 |
| `app/services/audio_processor.py` | 音频格式转换（WebM → WAV） |

### 重写

| 文件 | 说明 |
|------|------|
| `web/src/views/MeetingRoom.vue` | 完全重写为录音机 UI |
| `app/services/post_meeting_tasks.py` | 从 5 阶段改为 6 阶段离线处理 |

## 优势 vs 现有系统

| 维度 | 现有（实时） | 新方案（录音机） |
|------|-------------|-----------------|
| ASR 质量 | 分段 0.5-3s，幻觉严重 | 完整音频，上下文充分 |
| 声纹准确率 | 0.5s 碎片，区分度低 | 5-30s 完整语段，准确率高 |
| WS 稳定性 | 频繁断连重连 | 无需 WS（录音期间） |
| 架构复杂度 | VAD+声纹+ASR+三级润色+WS | 录音+上传+离线处理 |
| 用户体验 | 实时字幕（但不准） | 录后可回放+AI 分析（准） |
| 维护成本 | 高（多组件联动） | 低（各阶段独立） |
