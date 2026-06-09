/**
 * 全局录音状态管理
 * 解决：开始听会后导航到其他页面，录音界面消失且无法返回的问题
 *
 * 使用模块级单例（而非 Pinia store），因为状态极其轻量（一个 ID），
 * 且不需要 devtools/persist 等 store 特性。
 */
import { ref } from 'vue'
import axios from 'axios'

/** 当前正在录音的会议 ID，null 表示无录音 */
const recordingMeetingId = ref(null)

/** 会议标题（用于指示器显示） */
const recordingMeetingTitle = ref('')

/** 是否已初始化检查 */
const initialized = ref(false)

/**
 * 启动录音状态（MeetingRoom 开始录音后调用）
 */
function startRecording(meetingId, title = '') {
  recordingMeetingId.value = meetingId
  recordingMeetingTitle.value = title || `听会 #${meetingId}`
  // 持久化到 sessionStorage，刷新页面也能恢复
  sessionStorage.setItem('recording_meeting_id', String(meetingId))
  sessionStorage.setItem('recording_meeting_title', recordingMeetingTitle.value)
}

/**
 * 停止录音状态（挂断/结束录音后调用）
 */
function stopRecording() {
  recordingMeetingId.value = null
  recordingMeetingTitle.value = ''
  sessionStorage.removeItem('recording_meeting_id')
  sessionStorage.removeItem('recording_meeting_title')
}

/**
 * 检查后端是否有正在录音的会议（页面加载时调用一次）
 */
async function checkActiveRecording() {
  if (initialized.value) return
  initialized.value = true

  // 优先从 sessionStorage 恢复（同标签页内导航）
  const cached = sessionStorage.getItem('recording_meeting_id')
  if (cached) {
    recordingMeetingId.value = Number(cached)
    recordingMeetingTitle.value = sessionStorage.getItem('recording_meeting_title') || `听会 #${cached}`
    return
  }

  // 兜底：查后端是否有 recording 状态的会议
  try {
    const res = await axios.get('/api/v1/meetings', {
      params: { status: 'recording', page_size: 1 }
    })
    const items = res.data.items || res.data
    if (items && items.length > 0) {
      const m = items[0]
      startRecording(m.id, m.title)
    }
  } catch {
    // 静默失败，不影响正常功能
  }
}

export function useRecordingState() {
  return {
    recordingMeetingId,
    recordingMeetingTitle,
    startRecording,
    stopRecording,
    checkActiveRecording,
  }
}
