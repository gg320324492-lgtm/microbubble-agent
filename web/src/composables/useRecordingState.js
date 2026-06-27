/**
 * 全局录音状态管理
 * 解决：开始听会后导航到其他页面，录音界面消失且无法返回的问题
 *
 * 使用模块级单例（而非 Pinia store），因为状态极其轻量（一个 ID），
 * 且不需要 devtools/persist 等 store 特性。
 *
 * 2026-06-27 加 force 参数（跳过 initialized 短路），便于关键路由 mount 时
 * 强制同步后端状态；加 dev console.warn 便于复现"显示开始听会"类 bug。
 */
import { ref } from 'vue'
import axios from 'axios'

const DEBUG = import.meta.env.DEV
const log = (...args) => {
  if (DEBUG) console.warn('[useRecordingState]', ...args)
}

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
  recordingMeetingTitle.value = title || `正在听会（ID ${meetingId}）`
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
 * sessionStorage 数据必须与后端验证，避免残留脏数据
 *
 * @param {Object} [opts]
 * @param {boolean} [opts.force=false] - 跳过 initialized 短路，强制重新查后端
 *   用于关键路由 mount（如 /meetings/room）保证状态最新
 *   2026-06-27 加：修复桌面端"正在听会"指示器点击跳 /meetings/room 显示"开始听会"bug。
 *   根因：MainLayout.onMounted 首次调时若 API 失败 + sessionStorage 空，
 *   initialized 已为 true 但 recordingMeetingId 仍 null，
 *   MeetingRoomView.onMounted 再调会直接短路 return。
 */
async function checkActiveRecording({ force = false } = {}) {
  if (initialized.value && !force) {
    log('short-circuit: already initialized, current id =', recordingMeetingId.value)
    return
  }
  if (force) log('force=true, bypassing initialized short-circuit')
  initialized.value = true

  try {
    // 始终查后端确认是否有 recording 状态的会议
    const res = await axios.get('/api/v1/meetings', {
      params: { status: 'recording', page_size: 1 }
    })
    const items = res.data.items || res.data
    if (items && items.length > 0) {
      const m = items[0]
      log('backend has active recording, syncing id =', m.id, 'title =', m.title)
      startRecording(m.id, m.title)
    } else {
      // 后端没有录音中的会议，清除 sessionStorage 残留
      log('backend has NO active recording, clearing local state')
      stopRecording()
    }
  } catch (err) {
    log('API failed, falling back to sessionStorage:', err.message)
    // API 失败时降级读 sessionStorage，但标记未验证
    const cached = sessionStorage.getItem('recording_meeting_id')
    if (cached) {
      recordingMeetingId.value = Number(cached)
      recordingMeetingTitle.value = sessionStorage.getItem('recording_meeting_title') || `正在听会（ID ${cached}）`
    } else {
      log('no sessionStorage cache either — recordingMeetingId stays null')
    }
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
