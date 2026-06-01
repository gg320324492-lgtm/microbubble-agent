/**
 * 会议进度订阅 WS
 * 端点: /api/v1/ws/meeting/{id}/progress?token=...
 * 消息类型: progress_snapshot | progress_update | progress_done | ping
 */
import { ref, onUnmounted } from 'vue'

export function useMeetingProgress() {
  const ws = ref(null)
  const connected = ref(false)
  const progress = ref(null)  // { stage, detail, percent, status }
  const done = ref(false)
  const error = ref(null)

  function connect(meetingId, token) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/v1/ws/meeting/${meetingId}/progress?token=${token}`

    ws.value = new WebSocket(url)

    ws.value.onopen = () => {
      connected.value = true
      error.value = null
    }

    ws.value.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'progress_snapshot' || msg.type === 'progress_update') {
          progress.value = msg.data
          if (msg.data.status === 'done') {
            done.value = true
            setTimeout(() => disconnect(), 5000)  // 5s 后自动断开
          }
        } else if (msg.type === 'ping') {
          // 心跳
        }
      } catch (e) {
        console.error('进度消息解析失败:', e)
      }
    }

    ws.value.onerror = (e) => {
      console.error('进度 WS 错误:', e)
      error.value = '连接失败'
    }

    ws.value.onclose = (e) => {
      connected.value = false
      if (e.code === 4001) {
        error.value = '登录已过期'
      }
    }
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
    connected,
    progress,
    done,
    error,
  }
}
