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
          // 2026-06-02 修复：防御性检查 msg.data
          // 后端 get_progress() 返回 None 时曾发过 {"type":"progress_snapshot","data":null}，
          // 访问 msg.data.status 抛 TypeError。已修后端不发空快照；前端这里也加防御
          if (msg.data && typeof msg.data === 'object') {
            progress.value = msg.data
            if (msg.data.status === 'done') {
              done.value = true
              setTimeout(() => disconnect(), 5000)  // 5s 后自动断开
            }
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
