/**
 * 统一「开始听会」建会时序。
 *
 * 2026-11-23 深层 bug 修复：
 *   旧链路是 AudioRecorder 先开 MediaRecorder（波形开始动），再 emit recording-start，
 *   父组件才异步 POST /meetings/start-recording。若建会失败（例如 token 过期 401），
 *   录音仍在跑，但父组件 meetingId 仍是 null；停止时就会弹「会议未创建」。
 *   更糟的是旧 useRecordingState 在 API 失败时回退 sessionStorage，会把很久以前的
 *   recording_meeting_id（如 278）显示成右下角「正在听会」，形成假续录。
 *
 * 新时序：prepareRecording() 先确保服务端会议存在并设置本地 meetingId，
 *   只有成功后 AudioRecorder 才真正 start()。任何失败都立即回滚本地状态并抛出，
 *   AudioRecorder 的 catch 会停止录音/停心跳/通知父组件清理。
 *
 * 所有调用方（桌面全屏页、移动全屏页、旧 MeetingRoom）必须共用本 helper，
 * 不允许再各自在 recording-start 事件里异步建会。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRecordingState } from './useRecordingState'

export function useMeetingRecordingStart(meetingIdRef) {
  const { startRecording, stopRecording, recordingMeetingId } = useRecordingState()

  function titleFor(id) {
    return `正在听会（ID ${id}）`
  }

  async function prepareRecording() {
    // 恢复态必须来自本标签页真实建会，不能拿 sessionStorage/后端旧 recording 会议顶替。
    const existingId = Number(meetingIdRef.value)
    const storeId = Number(recordingMeetingId.value)
    if (existingId > 0 && storeId === existingId) {
      const id = existingId
      startRecording(id, titleFor(id))
      ElMessage.success('继续听会')
      return { meetingId: id, resumed: true }
    }

    let createdId = null
    try {
      const res = await axios.post('/api/v1/meetings/start-recording')
      createdId = Number(res.data?.id)
      if (!Number.isFinite(createdId) || createdId <= 0) {
        throw new Error('服务端未返回有效会议 ID')
      }
      meetingIdRef.value = createdId
      startRecording(createdId, res.data?.title || titleFor(createdId))
      ElMessage.success('开始听会')
      return { meetingId: createdId, resumed: false }
    } catch (err) {
      // 建会成功但后续麦克风/MediaRecorder 启动失败时，只清这里刚建的 ID；
      // 35 秒超时失败也绝不回退到 sessionStorage 旧会议。
      meetingIdRef.value = null
      stopRecording()
      ElMessage.error('创建会议失败: ' + (err.response?.data?.detail || err.message))
      throw err
    }
  }

  function onRecordingStartFailed() {
    // MediaRecorder 启动失败 / 建会后录音失败：父组件的本地 ID 必须一起清空，
    // 否则下一次点击会复用一个已经 cancel 的会议。
    meetingIdRef.value = null
    stopRecording()
  }

  return { prepareRecording, onRecordingStartFailed }
}
