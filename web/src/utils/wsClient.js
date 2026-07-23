/**
 * wsClient.js — v2 PR6 WebSocket 单例客户端
 *
 * 设计:
 * - 单例 (整个 app 共 1 个 WS 连接)
 * - 自动重连 (指数退避 1s/2s/4s/8s, max 30s)
 * - EventEmitter 风格 (on / off / emit)
 * - JWT token 自动从 localStorage 读, 每 50 分钟过期前 reconnect 拿新 token
 * - 心跳响应: 收到 server ping 自动回 pong (服务端检测 60s 无响应会断)
 *
 * 事件:
 * - 'open' / 'close' / 'error'  (连接生命周期)
 * - 'mention' / 'activity' / 'hello'  (业务事件)
 * - 'pong' / 'ping'  (心跳)
 */
class WsClient {
  constructor(url) {
    this.url = url
    this.ws = null
    this.listeners = new Map()
    this.reconnectAttempts = 0
    this.reconnectTimer = null
    this.shouldReconnect = true
    this.connected = false
    this.lastPongAt = 0
  }

  connect(token, options = {}) {
    if (!token) {
      console.warn('[WS] connect() 无 token, 跳过')
      return
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return
    }
    this.shouldReconnect = true
    // W68 PR8d: 支持 priority filter (?priority=high|medium|low)
    let wsUrl = `${this.url}?token=${encodeURIComponent(token)}`
    if (options.priority) {
      wsUrl += `&priority=${encodeURIComponent(options.priority)}`
    }
    try {
      this.ws = new WebSocket(wsUrl)
    } catch (e) {
      console.error('[WS] new WebSocket failed:', e)
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.connected = true
      this.reconnectAttempts = 0
      this.lastPongAt = Date.now()
      this.emit('open')
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this._handleMessage(data)
      } catch (e) {
        // 忽略非 JSON
      }
    }

    this.ws.onerror = (e) => {
      this.emit('error', e)
    }

    this.ws.onclose = () => {
      this.connected = false
      this.emit('close')
      if (this.shouldReconnect) {
        this._scheduleReconnect()
      }
    }
  }

  _handleMessage(data) {
    if (data.type === 'ping') {
      // 服务端 ping, 自动回 pong (但 WebSocket 协议层有 pong 帧, 这里再回一次 JSON pong 也行)
      this.send({ type: 'pong', ts: Date.now() })
      this.lastPongAt = Date.now()
      this.emit('ping')
      return
    }
    if (data.type === 'pong') {
      this.lastPongAt = Date.now()
      this.emit('pong')
      return
    }
    // 业务事件转发
    if (data.type) {
      this.emit(data.type, data)
    }
  }

  send(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload))
      return true
    }
    return false
  }

  _scheduleReconnect() {
    if (!this.shouldReconnect) return
    if (this.reconnectTimer) return
    this.reconnectAttempts++
    const delay = Math.min(30000, 1000 * Math.pow(2, Math.min(this.reconnectAttempts - 1, 5)))
    console.log(`[WS] ${delay}ms 后重连 (attempt ${this.reconnectAttempts})`)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      const token = localStorage.getItem('access_token')
      if (token) {
        // W68 PR8d: 重连时保留 priority filter (从当前 ws URL 提取, fallback 无)
        let priority = null
        if (this.ws && this.ws.url) {
          try {
            const u = new URL(this.ws.url)
            priority = u.searchParams.get('priority')
          } catch (e) {}
        }
        this.connect(token, { priority })
      }
    }, delay)
  }

  disconnect() {
    this.shouldReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      try {
        this.ws.close()
      } catch (e) {}
      this.ws = null
    }
    this.connected = false
  }

  on(event, handler) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event).push(handler)
  }

  off(event, handler) {
    const arr = this.listeners.get(event)
    if (!arr) return
    const idx = arr.indexOf(handler)
    if (idx >= 0) arr.splice(idx, 1)
  }

  emit(event, payload) {
    const arr = this.listeners.get(event)
    if (!arr) return
    arr.slice().forEach((h) => {
      try {
        h(payload)
      } catch (e) {
        console.error('[WS] handler error:', e)
      }
    })
  }

  isConnected() {
    return this.connected
  }
}

// 默认 base URL (与 api/agent.js 同源)
function buildWsUrl() {
  if (typeof window === 'undefined') return ''
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/v1/ws/notifications`
}

// 单例
let _instance = null
export function getWsClient() {
  if (!_instance) {
    _instance = new WsClient(buildWsUrl())
  }
  return _instance
}

export default getWsClient