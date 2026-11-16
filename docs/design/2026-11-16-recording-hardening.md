# 会议录音/听会链路深度加固（2026-11-16）

## Context

会议录音链路在 2026-06 至 2026-11 间反复出现同类事故：255 长会议因心跳组件级失效被孤儿清理误杀；258 前端显示可重试但后端 400；265 先删后传导致 5041 个实时分片丢失；273 状态词汇长度溢出把 warning 变 error；278 仅剩 4 秒静音分片却被 reprocess 当成有效录音。共同根因不是单点 bug，而是状态机分散、心跳与上传收尾脱钩、分片生命周期没有硬约束、前后端恢复判定不一致、测试停留在 mock 或源码字符串层面。

本次目标是把恢复能力收敛成单一状态机，把心跳/分片/合并/补传都变成可断言的不变量，并让桌面与移动端使用同一套恢复体验。

## 已落地改动

### 1. 后端统一恢复状态机

新增 `app/services/meeting_recovery.py`，提供纯函数 `evaluate_recovery(meeting)`：

- `recording`：返回 `resume`，允许上传/合并。
- `processing/completed`：返回 `none`，禁止任何恢复写操作。
- `error + audio_url + media_duration_seconds >= 30`：返回 `reprocess`。
- `error + audio_url + 0 < media_duration < 30`：返回 `reupload`，禁止 reprocess，避免 278 类静音产物重跑。
- `error + 无 audio_url + last_chunk_index>=0`：返回 `reupload/merge_first`，禁止直接 reprocess。
- `error + 无 audio_url + 无分片`：返回 `reupload`。

`/upload-status` 返回 `recovery` 字段与 `media_duration_seconds`；`upload-audio`、`merge-chunks`、`reprocess`、`chunks/reset`、`stop-recording` 全部使用或对齐这套语义。`reprocess` 现在要求 `audio_url` 非空，并对 0–30 秒短音频 fail loud。

### 2. 心跳会话化与上传收尾宽限

`app/services/recording_heartbeat.py`：

- Redis value 从纯时间戳升级为 `timestamp|session_id|phase`，兼容旧纯时间戳解析。
- 新增 `read_recording_heartbeat()`、`is_upload_finalizing()`。
- `phase` 支持 `recording/finalizing/uploading`。
- Redis 读异常仍保守返回存活，避免误杀。

`app/services/orphan_meeting_cleanup.py`：

- 返回值新增 `grace_extended`。
- 心跳消失但处于 `finalizing/uploading` 且 TTL 新鲜时，宽限跳过清理。
- 清理会议时补写 `recording_ended_at`，修复 reprocess/merge 对墙钟时长的错误假设。
- 日志明确区分 `skipped_alive`、`grace_extended`、`cleaned`、`preserved_chunks`。

### 3. 分片与合并完整性

`app/services/chunked_upload_service.py` 新增 `validate_chunk_indices()`：

- 分片必须从 0 连续、无重复、无缺失、无零字节对象。
- `merge_chunks`、`merge_chunks_raw`、`merge_staged_raw` 在拼接前校验，失败 fail loud。
- 保留 `assert_merged_integrity` 与 `should_preserve_chunks` 语义。
- 会议 253/265 类的“merge rc=0 但产物只剩首片”现在会在合并前被拦截。

### 4. 前端恢复中心

- `useGlobalRecorder` 生成模块级 `sessionId`，心跳携带 session/phase。
- `AudioRecorder` 停止时切到 `finalizing`，不在 finalize 开始前停表；父组件在 finalize 成功/失败后调用 `stopHeartbeatForMeeting()`。
- `useMeetingAudioUpload` 增加分片重试、收敛循环修正、finalize 失败兜底停表。
- `idbStore` 增加 `[meeting_id, chunk_index]` 复合唯一索引，防止重复片。
- `useChunkedRecorder` 成功后正确递减 pendingCount，启动时扫描 pending 并 drain。
- `meetingFailure` 与后端状态机对齐；桌面和移动端都提供“补传录音到本会议”入口。
- `UploadStatusBadge` 悬空的 manual-retry 按钮已移除，避免假动作。

## 验证

后端集成测试：

```bash
MSYS_NO_PATHCONV=1 docker exec -w /app -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \
  python -m pytest tests/test_meeting_recording_error_recovery.py \
  tests/test_meeting_recovery_state.py \
  tests/test_recording_heartbeat_session.py \
  tests/test_orphan_meeting_cleanup_audio_chunks.py \
  tests/test_chunked_staging.py \
  tests/test_merge_integrity.py -q
```

结果：**86 passed**。

前端相关测试：

```bash
cd web
npx vitest run src/utils/__tests__/meetingFailure.test.js \
  src/composables/__tests__/useRecordingHeartbeat.test.js \
  src/composables/__tests__/meetingRecoverySession.test.js --reporter=dot
```

结果：**36 passed**。

## 验收不变量

1. `status=recording` 且正在 finalize 的会议不得被孤儿清理误杀。
2. `error + audio_url 为空 + last_chunk_index>=0` 不得直接 reprocess。
3. `media_duration_seconds` 在 0–30 秒之间的产物不得用于重跑。
4. 分片合并前必须连续、无重复、无缺失、无零字节对象。
5. 桌面/移动端失败态动作必须与后端恢复状态机一致。
6. 心跳 session/phase 可从前端一路传到 Redis，并被 cleanup 读取。
7. finalize 成功/失败后停表，不在上传开始前停表。
8. 生产发布后必须比对首页资源指纹与本地 `web/dist/index.html`。

## 会议 278

会议 278 已用用户提供音频完成恢复：446 段转录、553 字摘要、8 条要点、9 项决议；质量状态 `fail`，原因是最长 240 秒无转录间隔且 7/12 个空窗含疑似语音。该会议仍只有 4473 秒录音，不等于用户口述的整场约 2 小时 40 分钟，后续应按“部分录音”看待，直至补齐前半段音频。
