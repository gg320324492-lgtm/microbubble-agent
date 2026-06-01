# 声纹会议系统升级 — 第一波设计规格

**日期**：2026-06-01
**作者**：Claude (brainstorming + writing-plans)
**范围**：第一波（核心）— 转录 AI 润色 / 智能分段 / 关键句高亮 / 处理进度条
**状态**：待用户审阅
**关联**：[声纹会议系统升级方案](#)（用户原始方案）
**后续波次**：第二波（实时 AI 互动 + 声纹录入整合 + 声音质量），第三波（声纹画像中心 + 跨会议关联）

---

## 1. 目标与背景

### 1.1 用户痛点（来自原始方案）

1. 转录显示差：固定字号、不自动滚动、临时输出眼花
2. 分析延迟：挂断后用户看到空白，不知道系统在处理
3. Whisper 幻觉输出"字幕志愿者"等噪音（已部分解决）
4. 声纹不可靠（属第二波修复）

### 1.2 第一波目标

让用户**开会中**看到高质量分段转录（AI 润色口语为书面语，关键决策/待办自动高亮），**挂断后**清楚知道系统在做什么、做到哪一步。

### 1.3 非目标（YAGNI）

- 声纹识别实时启用（第二波）
- 音频存档到 MinIO（第二波）
- AI 主动对话/翻译/提问（第二波）
- 声纹画像可视化（第三波）
- 跨会议关联（第三波）

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                       MeetingRoom.vue (重写)                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ useMeetingWS()   │  │ useTranscript()  │  │ AI 润色层     │ │
│  │  /live WS        │  │  分段/滚动/字号  │  │  渐进覆盖     │ │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬───────┘ │
└───────────┼─────────────────────┼──────────────────────┼────────┘
            │                     │                      │
   ┌────────▼────────┐    ┌───────▼────────┐    ┌────────▼────────┐
   │ /ws/meeting/:id │    │ /ws/meeting/:id│    │ /ws/meeting/:id │
   │      /live      │    │   /progress    │    │     /live       │
   │  实时:ASR+润色  │    │  挂断:进度     │    │  AI 主动推送    │
   └────────┬────────┘    └───────┬────────┘    └────────┬────────┘
            │                     │                      │
   ┌────────▼─────────────────────▼──────────────────────▼────────┐
   │  app/voice/pipeline.py  │  app/services/progress_service.py │
   │  - ASR (Whisper)       │  - Redis HSET progress:{id}        │
   │  - VAD (silero-vad)    │  - Redis PUBLISH progress:{id}     │
   │  - 累积分段 → 触发润色  │  - Celery task post_meeting_hook   │
   └────────┬────────────────────────────────────────────────────┘
            │
   ┌────────▼──────────────────────────────────────────────────┐
   │  app/services/meeting_ai_polish.py (新)                    │
   │  - Claude Sonnet 一次调用：                                │
   │    输入 {segments[], context{meeting_title, participants}} │
   │    输出 {polished, decisions[], todos[], risks[]}          │
   │  - 缓存：Redis SETNX polish:{segment_hash} (24h TTL)       │
   │  - 节流：asyncio.Lock 防同一 segment 重复请求              │
   └────────────────────────────────────────────────────────────┘
```

**关键模块边界**：
- `meeting_ai_polish.py` — 纯 LLM 调用 + 缓存，与 WS/Celery 解耦
- `progress_service.py` — 单一职责"写 Redis + 推 pub/sub"，与具体阶段任务解耦
- `pipeline.py` — 扩展 `process_audio()` 增加"段满触发润色"钩子

---

## 3. 后端设计

### 3.1 新建 `app/services/meeting_ai_polish.py`

**职责**：把若干 ASR 原始转录段润色为书面语，结构化输出决策/待办/风险点。

**公开 API**：

```python
async def polish_segments(
    segments: list[dict],         # [{"speaker": str, "text": str, "ts": float}]
    meeting_context: dict,         # {"title": str, "participants": list[str], "topic": str|None}
    db: AsyncSession,
) -> dict:
    """
    输入：N 条 ASR 原始转录段
    输出：{
        "polished": [
            {"speaker": str, "text": str, "ts": float}
        ],
        "key_points": [{"text": str, "ts": float, "kind": "decision|todo|risk"}],
        "boundary_after_index": int | None,  # 智能分段：第几条之后是话题切换
        "summary": str | None,                # 整段一句话总结（可选）
    }
    """
```

**Prompt 设计要点**（写入 `app/services/prompts/meeting_polish.py`，与其他 prompt 集中管理）：
- 系统提示：研究组会议秘书角色
- 输入模板：`会议主题\n参会人\n原始转录（带时间戳）`
- 输出要求：**严格 JSON**，含 `polished[]`、`key_points[]`、`boundary_after_index`
- 反幻觉：标注"如未识别出决策/待办，对应字段返回空数组"
- 上下文感知：传入最近 1-2 段已润色文本作为衔接

**缓存策略**：
- Key: `polish:{meeting_id}:{segment_hash}`，其中 `segment_hash = sha1(json.dumps(segments, sort_keys=True))[:16]`
- TTL: 24 小时
- 缓存命中时直接返回（不调 LLM）
- 用 `redis.asyncio` 异步客户端（项目已有）

**并发控制**：
- 同一 meeting_id 同一时间只允许 1 个 polish 任务（Redis `SETNX polish:lock:{meeting_id}` 60s TTL）
- 失败时 DEL lock，调用方捕获后重试或跳过

**调用方式**：
- 通过 `app/voice/pipeline.py` 在 VAD 段满（静音 > 1.5s 或累积 > 8s）时触发
- 完成后通过 `meeting_live_ws` 的 `transcript_polished` 消息推给前端
- 失败 fallback：保留原文，前端"润色失败"提示，不阻塞后续段

**新增 prompt 文件** `app/services/prompts/__init__.py` + `meeting_polish.py`：
- 与 `meeting_analysis_service.py` 的 prompts 集中管理
- 现有 `SPEAKER_DETECTION_PROMPT` / `ANALYSIS_PROMPT` 在后续 PR 迁移过来（不在本波范围）

### 3.2 新建 `app/services/progress_service.py`

**职责**：会议挂断后处理进度的写入与推送。

**公开 API**：

```python
class ProgressStage(str, Enum):
    EXTRACTING_TRANSCRIPT = "extracting_transcript"  # 0
    IDENTIFYING_SPEAKERS = "identifying_speakers"    # 1
    GENERATING_TITLE = "generating_title"            # 2
    GENERATING_MINUTES = "generating_minutes"        # 3
    CREATING_TASKS = "creating_tasks"                # 4
    LINKING_HISTORY = "linking_history"              # 5 (第三波启用)
    DONE = "done"                                    # 6

async def init_progress(meeting_id: int, total_stages: int) -> None:
    """初始化进度：HSET progress:{id} {stage: 0, total: N, started_at: ts, status: running}"""

async def update_progress(
    meeting_id: int,
    stage: ProgressStage,
    detail: str | None = None,
    percent: float | None = None,
) -> None:
    """
    更新进度：HSET + PUBLISH
    1. 计算 stage_index / percent
    2. HSET progress:{id} stage=X detail=Y percent=Z updated_at=ts
    3. PUBLISH progress:{id} json.dumps({stage, detail, percent, updated_at})
    4. 如果是 DONE，设置 TTL 1 小时（前端断开后仍可查历史）
    """

async def get_progress(meeting_id: int) -> dict | None:
    """REST 端点用，HGETALL progress:{id}"""

async def cleanup_progress(meeting_id: int) -> None:
    """1 小时后 Celery 清理（或立即调用）"""
```

**Redis Key 规范**：
- `progress:{meeting_id}` — HASH，字段 `stage` / `detail` / `percent` / `status` / `started_at` / `updated_at`
- TTL: 1 小时（DONE 后）

**与现有 reminder_scheduler 复用**：
- 复用 `app/services/reminder_scheduler.py` 的 `RedisSessionStore` 模式（已存在异步 Redis 客户端）
- 复用 `app.core.config.settings.REDIS_URL`

### 3.3 新建 `app/api/v1/meeting_progress.py`

**职责**：进度查询 + 进度 WebSocket 端点。

```python
@router.websocket("/ws/meeting/{meeting_id}/progress")
async def meeting_progress_ws(
    websocket: WebSocket,
    meeting_id: int,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    1. 校验 JWT (复用 voice.py 的 token 解析模式)
    2. 发送当前快照 (HGETALL progress:{id})
    3. SUBSCRIBE progress:{id} redis channel
    4. 循环接收 pub/sub 消息并 forward 给前端
    5. 前端 disconnect 时 UNSUBSCRIBE + 关闭
    """
```

**消息类型**（JSON）：
- `{"type": "progress_snapshot", "data": {stage, detail, percent, status, updated_at}}`（连接时首推）
- `{"type": "progress_update", "data": {stage, detail, percent, status, updated_at}}`（订阅推送）
- `{"type": "progress_done", "data": {meeting_url, summary, task_count}}`（完成）

**认证**：
- 复用 `voice.py` 的 `decode_access_token` 模式（已实现 JWT 验证）
- 失败立即 close 4401

**并发**：每个 meeting_id 允许多个 WS 客户端订阅（同一会议多设备同步），pub/sub fanout 自动处理

**REST 端点** `GET /api/v1/meetings/{id}/progress`：
- 给非 WS 场景使用（如用户刷新页面后）
- 返回当前 HGETALL 结果
- 找不到进度时返回 `null`

### 3.4 修改 `app/api/v1/voice.py` — `/live` 端点

**改动 1：触发 AI 润色**
- 累积段满（静音 > 1.5s 或累积 > 8s）时调用 `meeting_ai_polish.polish_segments()`
- 完成后通过 WS 发送 `transcript_polished` 消息：
  ```json
  {
    "type": "transcript_polished",
    "segment_id": "...",
    "polished": [{"speaker": "张三", "text": "...", "ts": 12.3}],
    "key_points": [{"text": "...", "ts": 12.3, "kind": "decision"}],
    "boundary_after_index": 2
  }
  ```

**改动 2：原文标记**
- 原始 ASR 段在发送时带 `polish_status: "pending"` 字段
- 前端看到 pending 显示"润色中…"
- 润色完成后用 `transcript_polished` 消息按 `segment_id` 匹配并替换

**改动 3：错误处理**
- LLM 调用失败：发送 `transcript_polished_error: {segment_id, error: "..."}`，前端降级显示原文 + 灰色"润色失败"角标

**不动**：
- WebSocket 协议二进制帧（Int16 PCM）保持原样
- 噪音黑名单 `NOISE_PATTERNS` 保持
- Whisper 反幻觉参数保持

### 3.5 修改 `app/voice/pipeline.py` — 段满钩子

**改动**：在 `MeetingPipeline.process_audio()` 的 ASR 完成后，触发润色任务。

```python
# 现有代码（line 100 附近）：transcribed = await self.asr.transcribe(...)
# 新增：判断是否需要润色
if transcribed and transcribed.get("text"):
    # 累积到一个内部 buffer
    self._pending_segments.append({
        "speaker": identified_speaker or "发言人",
        "text": transcribed["text"],
        "ts": elapsed,
    })
    # 触发条件：静音 > 1.5s 或累积 > 8s
    if self._silence_duration > 1.5 or self._accumulated_time > 8:
        asyncio.create_task(self._trigger_polish(...))
        self._pending_segments.clear()
        self._silence_duration = 0
        self._accumulated_time = 0
```

**注意**：因 VAD 单例状态污染问题（探索报告 §二.5），`/live` 端点**暂不直接用 MeetingPipeline**。本波保留原 `/live` 端点的"直接 ASR 累积"模式，**新增一个轻量类 `LiveSegmenter`** 在 `app/voice/segmenter.py`：

```python
class LiveSegmenter:
    """轻量段满检测：不依赖 VAD 单例，仅基于静音字节阈值"""
    def __init__(self, silence_threshold_ms: int = 1500, max_segment_ms: int = 8000):
        self._silence_bytes = 0
        self._silence_threshold = silence_threshold_ms * 16 * 2  # 16kHz * 2 bytes
        self._max_bytes = max_segment_ms * 16 * 2
        self._segment_buffer = bytearray()
        self._should_segment = False

    def feed(self, pcm_int16: bytes) -> bool:
        """返回 True 表示应该触发段满处理"""
        # 检测静音（连续低能量字节数）
        is_silent = self._is_silent(pcm_int16)
        self._segment_buffer.extend(pcm_int16)
        if is_silent:
            self._silence_bytes += len(pcm_int16)
        else:
            self._silence_bytes = 0
        if self._silence_bytes >= self._silence_threshold or len(self._segment_buffer) >= self._max_bytes:
            return True
        return False

    def drain(self) -> bytes:
        """取出并清空缓冲区"""
        data = bytes(self._segment_buffer)
        self._segment_buffer.clear()
        self._silence_bytes = 0
        return data
```

**理由**：避免 VAD 全局单例状态污染；纯字节级静音检测足够触发润色；VAD 在声纹识别时（第二波）才需要。

### 3.6 新建 Celery 任务 `app/services/post_meeting_tasks.py`

**职责**：挂断后按阶段执行处理 + 写进度。

```python
@celery_app.task(bind=True, max_retries=2)
def post_meeting_process(self, meeting_id: int):
    """
    阶段：
    0. extracting_transcript: 转录已在 /live 中保存，确认完整性
    1. identifying_speakers: 重跑声纹识别（如有完整音频）或确认现有 speaker_mapping
    2. generating_title: meeting_analysis.generate_title（已有）
    3. generating_minutes: meeting_analysis.analyze_transcript（已有）
    4. creating_tasks: meeting_service._auto_create_task_from_meeting（已有）
    5. linking_history: 第三波启用，本波占位
    6. done

    每步：
    - progress_service.update_progress(meeting_id, stage, detail)
    - 失败：重试 1 次，仍失败标记 stage=failed 但继续下一阶段
    """
```

**触发时机**：用户在前端点击"挂断"按钮时，前端调 `POST /meetings/{id}/end-call` → 后端 dispatch Celery 任务

### 3.7 新建 API 端点 `POST /meetings/{id}/end-call`

**位置**：`app/api/v1/meeting.py`

```python
@router.post("/{meeting_id}/end-call")
async def end_meeting_call(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """
    1. 校验 meeting 存在 + 用户在参与者中
    2. status = "completed", end_time = now()
    3. dispatch post_meeting_process.delay(meeting_id)
    4. 返回 {progress_ws_url: "ws://.../ws/meeting/{id}/progress?token=..."}
    """
```

**注意**：与现有 `POST /meetings/{id}/analyze` 不冲突（end-call 是显式结束通话 + 启动进度跟踪；analyze 是手动重跑分析）

---

## 4. 前端设计

### 4.1 重写 `web/src/components/MeetingRoom.vue`

**目标**：从 227 行临时版本升级为完整主屏。

**新增 props/emits**：
- props: `meetingId`, `meetingTitle`, `participants[]`
- emits: `call-ended` (挂断时通知父组件显示进度弹窗)

**核心结构**（template 概览）：
```vue
<template>
  <div class="meeting-room">
    <TopBar :title :duration :connection-status />
    <SpeakerStrip :speakers :active-speaker-id />  <!-- 头像 + 实时声波 -->
    <AgendaPanel :items="agenda" />  <!-- 会议小目标 -->
    <TranscriptPanel :entries :font-size @user-scroll />
    <AIFloatButton @summarize @translate @ask />
    <ControlBar @mute @hangup />
  </div>
</template>
```

**关键交互**（§4.2-§4.6）

### 4.2 TranscriptPanel — 转录面板

**字号自适应**：
- entries < 5：大字号 22px，行距 1.8
- entries 5-10：中字号 18px，行距 1.6
- entries > 10：小字号 15px，行距 1.4
- 切换有过渡动画（200ms）

**智能滚动**：
- 用户在底部 200px 范围内 → 自动跟随新条目
- 用户向上滚动 → 停止自动滚动，"↓ N 条新消息"悬浮按钮出现
- 点击按钮平滑滚回底部

**AI 润色层**（核心）：
- 每条 entry 状态机：`pending`（ASR 原文 + "润色中…"灰色）→ `polishing` → `polished`（替换文本）→ `error`（原文 + "润色失败"角标）
- `key_points` 渲染：在 polished entry 下用 ✨ 黄色徽章显示 `重要决策` / ⏰ 蓝色徽章显示 `待办` / ⚠️ 红色徽章显示 `风险`
- 边界切换：相邻 entry speaker 不同时，渲染一条细分隔线（避免每 2s 机械分隔）

**关键句高亮规则**（来自后端结构化 JSON）：
- `kind: "decision"` → ✨ 黄色徽章 + 文本加粗
- `kind: "todo"` → ⏰ 蓝色徽章
- `kind: "risk"` → ⚠️ 红色徽章
- 点击徽章展开详情（来源时间戳、上下文）

### 4.3 SpeakerStrip — 发言者条

**布局**：顶部横排卡片，每个参与者一张
**状态**：
- `idle`：灰色头像
- `speaking`：彩色头像 + 实时声波条（基于 `audioLevel` 0-1 范围）
- `just_stopped`：头像放大 1.1x 持续 1.5s（发言者切换反馈）
- `unregistered`：橙色问号头像 + "录入声纹"按钮

**数据流**：
- 接收 `entries[].speaker` 推断当前说话人
- 接收 WebSocket `audio_level` 消息（0-1 浮点）驱动声波条

### 4.4 AIFloatButton — AI 助手浮窗

**位置**：右下角，固定悬浮
**状态**：
- 收起：圆形小气泡 + "小气" 文字
- 展开：弹出 200x300 抽屉，显示最近 5 次 AI 互动
- 加载中：旋转 spinner + 灰底

**快捷指令**（点击触发 WS 消息）：
- "📝 总结最近 30 秒" → `ai_command: {action: "summarize_recent", seconds: 30}`
- "🌐 中英翻译" → `ai_command: {action: "translate"}`
- "🤔 AI 提问" → `ai_command: {action: "ai_question"}`（属第二波，本波 UI 占位）

**响应接收**：
- 后端通过 `ai_reply` 消息推送
- 抽屉内追加气泡 + TTS 可选播放（属第二波，本波不播）

### 4.5 ControlBar — 底部控制

**按钮**（从左到右）：
- 静音切换（图标变化）
- 摄像头（占位，本波不开视频）
- 共享屏幕（占位）
- AI 助手（与 AIFloatButton 联动）
- 挂断（红色，主操作）

**挂断交互**：
- 点击 → 二次确认弹窗（避免误触）
- 确认 → emit `call-ended` + 关闭 WS
- 父组件收到事件后弹出 `ProcessingDialog`

### 4.6 新建 `web/src/components/ProcessingDialog.vue`

**职责**：挂断后显示处理进度。

**结构**：
```vue
<el-dialog :visible fullscreen :show-close="false">
  <div class="processing-container">
    <h2>AI 正在整理会议纪要...</h2>
    <ProgressTimeline :stages :current :detail />
    <p class="hint">预计 30-60 秒，您可以先看看其他内容</p>
  </div>
</el-dialog>
```

**ProgressTimeline 阶段**（与后端 `ProgressStage` 枚举对齐）：
- ✓ 提取转录（已完成）
- ⟳ 识别发言人（进行中，带 spinner）
- ○ 生成标题
- ○ 生成纪要
- ○ 创建任务
- 完成态：显示"📄 纪要已生成" + "查看详情" 按钮

**WebSocket 订阅**：
- 挂断时 `useMeetingProgress(meetingId)` 建立连接
- 收到 `progress_update` 更新 UI
- 收到 `progress_done` 显示"查看详情"按钮 + 3s 后自动跳转
- 异常：连接断开 5s 后显示"重连"按钮

**视觉规范**：
- 居中显示 + 暖橙主题（与项目一致）
- 完成步骤绿色对勾
- 进行中步骤橙色 spinner + 脉动
- 未开始步骤灰色空心圆

### 4.7 抽取 `web/src/composables/`

**新增**：
- `useMeetingRoomWS.js` — 封装 /live WS 状态机（连接/重连/断线/二进制帧/JSON 帧分发）
- `useMeetingProgress.js` — 封装 /progress WS（同上但更简单）
- `useTranscript.js` — 状态机（pending → polished → error）+ 滚动逻辑
- `useAutoScroll.js` — 通用自动滚动 composable

**理由**：当前 `MeetingRoom.vue` script setup 把所有逻辑堆一起（探索报告 §六.7 标红），拆分后各 composable 独立可测。

### 4.8 修改 `web/src/views/MeetingView.vue` 和 `MeetingDetailView.vue`

**MeetingView.vue**：
- 拆出 `<MeetingCreateDialog>` / `<LiveTranscriptDialog>` / `<MeetingRoomDialog>`（现有 713 行拆分）
- 通话挂断后弹出 `ProcessingDialog`
- 不在 `MeetingView` 列表里直接渲染 `LiveTranscript`（避免与 MeetingRoom 重复路径）

**MeetingDetailView.vue**：
- 现有嵌入 `MeetingRoom`（height 400px）保持
- 通话挂断后切换为 `ProcessingDialog`
- 完成后刷新会议详情展示纪要

---

## 5. 数据流（端到端）

### 5.1 实时通话数据流

```
浏览器 AudioWorklet (16kHz Float32)
    │ 降采样为 Int16
    ▼
MeetingRoom.sendAudio(Int16Array)
    │ 累积到 LiveSegmenter.feed()
    │ 当返回 True → 触发段满
    ▼
WS 发送: {"type": "audio_segment", "pcm": base64, "ts": ...}
    │ 后端 /live 端点接收
    ▼
ASR.transcribe(pcm)
    │ Whisper 返回 {text, segments}
    ▼
noise_filter(transcript)        # 现有 NOISE_PATTERNS 黑名单
    │
    ▼
meeting_ai_polish.polish_segments()  # 异步触发
    │ 检查缓存 SETNX polish:{hash}
    │ 命中 → 直接返回
    │ 未命中 → Claude API 调用
    │ 缓存结果 24h
    ▼
WS 推回前端两条消息：
    1. transcript (原文，polish_status: pending)  # 立即推
    2. transcript_polished (润色 + 关键点)         # 异步推 (1-3s 后)
    │
    ▼
MeetingRoom.useTranscript.update(segment_id, polished_data)
    │ 状态机：pending → polished
    │ 替换显示文本 + 渲染 key_points 徽章
```

### 5.2 挂断后进度数据流

```
用户点击"挂断" → 二次确认 → emit call-ended
    │
    ▼
MeetingView 收到 → 显示 ProcessingDialog
    │
    ├─→ POST /api/v1/meetings/{id}/end-call
    │   │ 后端 dispatch Celery post_meeting_process
    │   └─→ 返 {progress_ws_url}
    │
    ├─→ WS 连接 /ws/meeting/{id}/progress?token=...
    │   │ 首推 progress_snapshot
    │   └─→ 订阅 progress:{id} redis channel
    │
    ▼
Celery post_meeting_process 启动
    │ 0. extracting_transcript → update_progress(0, ...)
    │ 1. identifying_speakers → update_progress(1, ...)
    │ 2. generating_title → update_progress(2, ...)
    │ 3. generating_minutes → update_progress(3, ...)
    │ 4. creating_tasks → update_progress(4, ...)
    │ 5. linking_history → 跳过（第三波）
    │ 6. done → update_progress(6, done)
    │  Redis PUBLISH progress:{id} 各阶段
    │
    ▼
WS 转发给前端 → ProcessingDialog 更新 UI
    │
    ▼
收到 progress_done → 显示"查看详情" + 3s 后跳转 /meetings/{id}
```

---

## 6. 错误处理

### 6.1 后端错误

| 场景 | 处理 | 用户感知 |
|---|---|---|
| ASR 失败 | catch Exception，记日志，发送 `transcript_error: {segment_id}` | 该条 entry 标红"识别失败" |
| 润色 LLM 失败 | catch Exception，发送 `transcript_polished_error`，降级保留原文 | 灰色"润色失败"角标，可手动重试（占位按钮） |
| 润色 LLM 超时（>10s） | 跳过该段润色，不阻塞后续 | 润色状态保持 pending（视觉上：长时润色中…） |
| 缓存写入失败 | log warning，不影响主流程 | 无感知 |
| 进度 Celery 任务失败 | 重试 1 次，仍失败 stage=failed 但继续下一阶段 | UI 显示"⚠️ 此阶段失败"，但整体流程继续 |
| Celery 任务整体崩溃 | progress:{id} 保留 stage=failed，TTL 1h 后清理 | UI 长时间停留某一阶段，提供"手动重试"按钮 |
| WS 连接断开（前端） | 前端自动重连 3 次（间隔 1s/2s/4s） | "重连中..."提示 |
| WS 鉴权失败 | close 4401 | 显示"登录已过期，请刷新" |

### 6.2 前端错误

| 场景 | 处理 |
|---|---|
| AudioWorklet 不支持 | 检测能力，降级为 MediaRecorder 路径（复用 LiveTranscript 现有方案） |
| 浏览器后台标签页节流 | 提示"切回前台以保持连接" |
| 挂断前 WS 异常断开 | 弹窗提示"连接中断，是否结束会议？" |

---

## 7. 测试策略

### 7.1 后端单元测试（pytest + pytest-asyncio）

**`app/services/meeting_ai_polish.py`**：
- `test_polish_segments_basic` — 模拟 Claude API 返回，验证解析正确
- `test_polish_segments_cache_hit` — 二次调用不走 LLM
- `test_polish_segments_lock` — 同 meeting_id 并发只一个任务
- `test_polish_segments_llm_error` — LLM 抛异常时 fallback 原文

**`app/services/progress_service.py`**：
- `test_init_progress` — Redis HSET 字段正确
- `test_update_progress_pubsub` — HSET + PUBLISH 都被调用
- `test_get_progress_done` — TTL 过期后返 None
- `test_stage_progression` — 阶段枚举按预期顺序

**`app/voice/segmenter.py`**：
- `test_segmenter_silence_threshold` — 静音 1.5s 触发 True
- `test_segmenter_max_length` — 累积 8s 强制触发 True
- `test_segmenter_drain` — drain 后 buffer 清空

### 7.2 后端集成测试

- `test_live_ws_polish_flow` — WS 模拟发送 PCM → 收到 transcript + transcript_polished
- `test_live_ws_polish_error_fallback` — 模拟 LLM 失败 → 收到 transcript_polished_error
- `test_end_call_dispatch_celery` — POST /end-call → Celery 任务入队
- `test_progress_ws_subscribe` — 启动 Celery 任务 → progress WS 收到所有阶段

### 7.3 前端单元测试（Vitest）

- `useTranscript.test.js` — 状态机：pending → polished 正确更新
- `useAutoScroll.test.js` — 用户向上滚后停止自动滚动
- `TranscriptPanel.test.js` — 字号自适应阈值正确

### 7.4 端到端测试（Playwright，手动）

- 真实浏览器开两个标签页同会议，一方说话，另一方看到润色后转录
- 挂断后 ProcessingDialog 正确显示各阶段，完成后跳转详情
- 模拟网络断开，验证重连逻辑

---

## 8. 部署与迁移

### 8.1 数据库迁移

**Meeting 表新增字段**（ALTER TABLE）：
- 无（本波不新增字段；speaker_mapping / transcript JSON 字段已存在）

**新增 Redis Key 空间**：
- `polish:{meeting_id}:{segment_hash}` — 缓存润色结果，TTL 24h
- `polish:lock:{meeting_id}` — 防并发锁，TTL 60s
- `progress:{meeting_id}` — 进度 HASH，TTL 1h

### 8.2 后端部署

- `app/services/meeting_ai_polish.py` — 新文件
- `app/services/progress_service.py` — 新文件
- `app/services/post_meeting_tasks.py` — 新文件
- `app/api/v1/meeting_progress.py` — 新文件
- `app/api/v1/voice.py` — 修改 /live 端点
- `app/api/v1/meeting.py` — 新增 end-call 端点
- `app/voice/segmenter.py` — 新文件
- `app/main.py` — 注册新路由（`include_router(meeting_progress.router)`）

**不需要**：
- 数据库迁移（无新列）
- Celery worker 已有（复用）
- 模型重新加载（无新模型）

### 8.3 前端部署

- `web/src/components/MeetingRoom.vue` — 重写
- `web/src/components/ProcessingDialog.vue` — 新建
- `web/src/composables/useMeetingRoomWS.js` — 新建
- `web/src/composables/useMeetingProgress.js` — 新建
- `web/src/composables/useTranscript.js` — 新建
- `web/src/composables/useAutoScroll.js` — 新建
- `web/src/views/MeetingView.vue` — 拆分
- `web/src/views/MeetingDetailView.vue` — 嵌入 ProcessingDialog

**构建**：本地 `npm run build`，dist 提交

### 8.4 风险与回滚

| 风险 | 缓解 |
|---|---|
| 润色 LLM 调用增加延迟/成本 | 缓存 + 锁 + 可降级为跳过润色（开关） |
| Progress WS 占用连接 | 仅在挂断后开启，TTL 1h 自动清理 |
| MeetingRoom 重写引入 bug | 保留旧 LiveTranscript 路径作 fallback，先灰度 |

**回滚方案**：
- 后端：新文件用 `if not settings.ENABLE_AI_POLISH: return original` 包装
- 前端：MeetingRoom 保留 git tag `pre-wave1`，可一键回滚
- 进度功能回滚：直接 `include_router` 注释掉

---

## 9. 验收标准

第一波完成的定义：

1. ✅ 实时通话中，原文立即显示，1-3s 后被润色文本覆盖
2. ✅ 关键决策/待办/风险自动高亮（来自 LLM 结构化输出）
3. ✅ 转录面板字号随条目数量自适应
4. ✅ 用户向上滚动后停止自动滚动，"↓ N 条新消息"提示出现
5. ✅ 挂断后 ProcessingDialog 弹出，显示 5 个阶段
6. ✅ 每个阶段完成有视觉反馈（✓ 或 ⟳ 或 ○）
7. ✅ 处理完成后 3s 自动跳转到会议详情
8. ✅ 单元测试覆盖率 > 70%（新增模块）
9. ✅ 缓存命中时延迟 < 100ms
10. ✅ LLM 失败时前端降级显示，不影响后续段

---

## 10. 实施顺序（建议）

1. 后端 `meeting_ai_polish.py` + prompts（可独立测试）
2. 后端 `progress_service.py` + Redis 集成
3. 后端 `meeting_progress.py` WS 端点
4. 后端 `voice.py` /live 端点接入润色
5. 后端 `segmenter.py` + end-call API
6. 后端 Celery 任务 `post_meeting_tasks.py`
7. 前端 composables（useMeetingRoomWS / useTranscript / useAutoScroll）
8. 前端 MeetingRoom 重写
9. 前端 ProcessingDialog + useMeetingProgress
10. 前端 MeetingView 拆分
11. 端到端联调 + 灰度

---

## 11. 开放问题

1. **润色 LLM 模型选择**：Sonnet vs Haiku？Sonnet 质量高但慢（~2s），Haiku 快（~0.5s）但偶尔降级。**建议：Sonnet，缓存保底**。
2. **关键点是否需要用户确认**：LLM 识别出的"决策"是否要二次确认后才入库？**本波不做，确认环节留到挂断后纪要编辑**。
3. **进度条是否要给非参与者看**：其他人能订阅别人会议的进度吗？**本波限制：仅 meeting 参与者**。

---

**版本**：v1.0
**等待用户审阅** → 通过后进入 writing-plans 阶段生成实现计划
