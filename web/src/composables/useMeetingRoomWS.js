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

  let reconnectAttempts = 0
  let maxReconnectAttempts = 3
  let pendingAudioQueue = []  // 重连前累积的音频

  function connect(meetingId, token) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/v1/ws/meeting/${meetingId}/live?token=${token}`

    ws.value = new WebSocket(url)
    ws.value.binaryType = 'arraybuffer'

    ws.value.onopen = () => {
      connected.value = true
      reconnecting.value = false
      reconnectAttempts = 0
      // 重连后 flush 累积音频
      while (pendingAudioQueue.length > 0) {
        const chunk = pendingAudioQueue.shift()
        sendAudio(chunk)
      }
    }

    ws.value.onmessage = (event) => {
      if (typeof event.data === 'string') {
        try {
          const msg = JSON.parse(event.data)
          handleJSONMessage(msg)
        } catch (e) {
          console.error('WS 消息解析失败:', e)
        }
      }
      // 二进制帧（暂时不处理）
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
      // 自动重连
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnecting.value = true
        reconnectAttempts++
        const delay = Math.pow(2, reconnectAttempts) * 500
        setTimeout(() => connect(meetingId, token), delay)
      } else {
        if (onError.value) onError.value({ message: '连接断开' })
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
      case 'audio_level':
        audioLevel.value = msg.level
        break
    }
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
    }
  }

  function sendHangup() {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'hangup' }))
    }
    disconnect()
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connect,
    disconnect,
    sendAudio,
    sendHangup,
    connected,
    reconnecting,
    audioLevel,
    onTranscript,
    onPolished,
    onError,
    onEnded,
  }
}
