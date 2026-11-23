/**
 * 恢复录音会话的硬判据。
 *
 * 2026-11-23 深层 bug：
 *   只看会议 status='recording' 会把「服务端残留的旧 recording 会议」当成正在录音，
 *   刷新后右下角显示旧 ID（现场是 278），但当前标签页根本没有 MediaRecorder。
 *   真实判据必须同时满足：
 *     ① 会议详情状态仍是 recording/error；
 *     ② Redis 录音心跳仍存活（前端每 60s 上报，300s TTL）。
 *   任一查不到/失败都拒绝恢复，避免把旧会议复活成假录音。
 */
import axios from 'axios'

const RESUMABLE_STATUSES = ['recording', 'error']

export async function validateRecordingSession(meetingId) {
  const id = Number(meetingId)
  if (!Number.isFinite(id) || id <= 0) {
    return { allowed: false, status: null, reason: 'invalid_meeting_id' }
  }

  try {
    const [detailRes, heartbeatRes] = await Promise.all([
      axios.get(`/api/v1/meetings/${id}`),
      axios.get(`/api/v1/meetings/${id}/recording-heartbeat`),
    ])
    const status = detailRes.data?.status ?? null
    const heartbeatAlive = heartbeatRes.data?.alive === true

    if (!RESUMABLE_STATUSES.includes(status)) {
      return { allowed: false, status, reason: 'meeting_not_recordable' }
    }
    if (!heartbeatAlive) {
      return { allowed: false, status, reason: 'recording_heartbeat_dead' }
    }
    return { allowed: true, status, reason: 'ok' }
  } catch (err) {
    return { allowed: false, status: null, reason: 'validation_failed', error: err }
  }
}
