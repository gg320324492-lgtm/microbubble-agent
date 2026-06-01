/**
 * 会议实时通话 WS 状态机
 * 端点: /api/v1/ws/meeting/{id}/live?token=...
 * 消息类型:
 *   - transcript: 原文（polish_status: pending）
 *   - transcript_polished: 润色结果
 *   - transcript_polished_error: 润色失败
 *   - meeting_ended: 会议结束
 */
import { ref, onUnmounted } from 'vue'

export function useMeetingRoomWS() {
  const ws = ref(null)
  const connected = ref(false)
  const reconnecting = ref(false)
  const audioLevel = ref(0)  // 0-1
  const onTranscript = ref(null)  // (entry) => void
  const onPolished = ref(null)    // (data) => void
  const onError = ref(null)       // (data) => void
  const onEnded = ref(null)       // () => void
  const onMessage = ref(null)     // 通用消息回调
  const onSpeakerUnidentified = ref(null)
  const onSpeakerClaimAck = ref(null)
  const onAIReply = ref(null)
  const onTranscriptOthers = ref(null)
  const onAIReplyOthers = ref(null)
  const onTranscriptHistory = ref(null)
  const onTTSAudio = ref(null)  // 二进制 TTS MP3

  let reconnectAttempts = 0
  let maxReconnectAttempts = 10
  const maxReconnectDelay = 30000  // 30s 退避上限
  let everConnected = false  // 区分「首次连接失败」与「运行中断开」
  let reconnectTimer = null  // 跟踪重连定时器（防止 disconnect 后又触发）
  let pendingAudioQueue = []  // 重连前累积的音频
  // Wave 3b: pending 数量变化通知（用于 NetworkStatusBar 显示）
  const pendingCount = ref(0)
  let pendingCountNotify = null
  function setPendingCountCallback(fn) {
    pendingCountNotify = fn
  }

  function connect(meetingId, token) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/v1/ws/meeting/${meetingId}/live?token=${token}`

    ws.value = new WebSocket(url)
    ws.value.binaryType = 'arraybuffer'

    ws.value.onopen = () => {
      connected.value = true
      reconnecting.value = false
      everConnected = true
      // 注意：不要在这里把 reconnectAttempts = 0 — 让退避曲线继续走，
      // 避免「重连成功 → 服务端又抖断 → 退避从头算起」的循环闪烁。
      // 一旦用户主动挂断（disconnect → resetReconnect）才清零。
      // 重连后 flush 累积音频
      while (pendingAudioQueue.length > 0) {
        const chunk = pendingAudioQueue.shift()
        sendAudio(chunk)
      }
      // Wave 3b: flush 后清零 pending count
      pendingCount.value = 0
      pendingCountNotify?.(0)
    }

    ws.value.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        if (onTTSAudio.value) onTTSAudio.value(event.data)
        return
      }
      if (typeof event.data === 'string') {
        try {
          const msg = JSON.parse(event.data)
          handleJSONMessage(msg)
        } catch (e) {
          console.error('WS 消息解析失败:', e)
        }
      }
    }

    ws.value.onerror = (e) => {
      console.error('WS 错误:', e)
    }

    ws.value.onclose = (e) => {
      connected.value = false
      if (e.code === 4001) {
        // 鉴权失败，不重连
        if (onError.value) onError.value({ message: '登录已过期' })
        return
      }
      // 主动 disconnect 不重连
      if (!ws.value) {
        return
      }
      // 自动重连
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnecting.value = true
        reconnectAttempts++
        // 指数退避（首次 1s，封顶 30s）
        const delay = Math.min(Math.pow(2, reconnectAttempts) * 500, maxReconnectDelay)
        console.log(`[WS] 断开 (code=${e.code}), ${delay}ms 后第 ${reconnectAttempts} 次重连`)
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null
          connect(meetingId, token)
        }, delay)
      } else {
        reconnecting.value = false
        if (onError.value) onError.value({ message: '连接已断开，请刷新页面重试' })
      }
    }
  }

  function handleJSONMessage(msg) {
    switch (msg.type) {
      case 'transcript':
        if (onTranscript.value) onTranscript.value(msg)
        break
      case 'transcript_polished':
        if (onPolished.value) onPolished.value(msg)
        break
      case 'transcript_polished_error':
      case 'transcript_error':
        if (onError.value) onError.value(msg)
        break
      case 'meeting_ended':
        if (onEnded.value) onEnded.value()
        break
      case 'speaker_unidentified':
        if (onSpeakerUnidentified.value) onSpeakerUnidentified.value(msg)
        break
      case 'speaker_claim_ack':
        if (onSpeakerClaimAck.value) onSpeakerClaimAck.value(msg)
        break
      case 'audio_level':
        audioLevel.value = msg.level
        break
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
    }
    // 通用消息回调（兜底，避免新增 type 时静默丢失）
    if (onMessage.value) onMessage.value(msg)
  }

  function sendAudio(int16ArrayBuffer) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(int16ArrayBuffer)
    } else {
      // 重连前累积
      pendingAudioQueue.push(int16ArrayBuffer)
      if (pendingAudioQueue.length > 100) {
        pendingAudioQueue.shift()  // 防止内存爆炸
      }
      // Wave 3b: 通知外部 pending count 变化
      pendingCount.value = pendingAudioQueue.length
      pendingCountNotify?.(pendingAudioQueue.length)
    }
  }

  function sendHangup() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'hangup' }))
    }
    disconnect()
  }

  function sendSpeakerClaim(segmentId, memberId, speakerLabel) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({
        type: 'speaker_claim',
        segment_id: segmentId,
        member_id: memberId,
        speaker_label: speakerLabel,
      }))
    }
  }

  function sendAICommand(action, params = {}) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'ai_command', action, ...params }))
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
    reconnecting.value = false
    // 主动挂断后才清零，下次 connect() 重新从 0 开始
    reconnectAttempts = 0
    everConnected = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connect,
    disconnect,
    sendAudio,
    sendHangup,
    sendSpeakerClaim,
    sendAICommand,
    setPendingCountCallback,  // Wave 3b
    pendingCount,              // Wave 3b: reactive 队列长度
    connected,
    reconnecting,
    audioLevel,
    onTranscript,
    onPolished,
    onError,
    onEnded,
    onMessage,
    onSpeakerUnidentified,
    onSpeakerClaimAck,
    onAIReply,
    onTranscriptOthers,
    onAIReplyOthers,
    onTranscriptHistory,
    onTTSAudio,
  }
}
