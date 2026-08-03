/**
 * W100 +50d WS 指数退避测试 — 验证 connect-then-close 不重置 attempts
 *
 * 真根因: wsClient.js onopen 立即 reset reconnectAttempts=0,
 *   server 401/403/auth race → connect-立刻-close → 永远 attempt=1 / 1000ms 死循环。
 * 修复: 仅 lastPongAt>30s 才重置 (稳定连接守恒)。
 *
 * 纯算法测试: 直接 new WsClient(url), mock localStorage + WebSocket,
 *   触发 onopen → onclose → _scheduleReconnect, 验证 attempts 累加。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// 隔离模块副作用, 每个 test fresh import
const buildModule = async () => {
  vi.resetModules()
  const mod = await import('../../utils/wsClient')
  return mod
}

describe('wsClient — W100 +50d 指数退避 bug 修复', () => {
  let mockWsInstances = []
  let originalLocalStorage
  let originalWebSocket

  beforeEach(() => {
    vi.useFakeTimers()
    mockWsInstances = []
    // mock WebSocket
    originalWebSocket = globalThis.WebSocket
    globalThis.WebSocket = class MockWebSocket {
      constructor(url) {
        this.url = url
        this.readyState = 0 // CONNECTING
        this.onopen = null
        this.onclose = null
        this.onerror = null
        this.onmessage = null
        mockWsInstances.push(this)
      }
      close() {
        this.readyState = 3 // CLOSED
        // 不自动触发 onclose, 由测试手动触发
      }
      send() {}
    }
    // mock localStorage
    originalLocalStorage = globalThis.localStorage
    const store = {}
    globalThis.localStorage = {
      getItem: (k) => store[k] || null,
      setItem: (k, v) => { store[k] = String(v) },
      removeItem: (k) => { delete store[k] },
    }
  })

  afterEach(() => {
    vi.useRealTimers()
    globalThis.WebSocket = originalWebSocket
    globalThis.localStorage = originalLocalStorage
  })

  it('case 1: 首次 connect 触发 1 次 _scheduleReconnect (attempts=1, delay=1000ms)', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    client.connect('test-token')
    expect(mockWsInstances).toHaveLength(1)
    // 模拟 server 端 close
    mockWsInstances[0].onclose()
    expect(client.reconnectAttempts).toBe(1)
    expect(client.reconnectTimer).not.toBeNull()
  })

  it('case 2: 连续 connect-then-close, attempts 必须累加 (1 → 2 → 3)', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    // case 2 也需要 token 让 _scheduleReconnect 真正 reconnect
    localStorage.setItem('access_token', 'test-token')
    // 第 1 次: connect → close
    client.connect('test-token')
    mockWsInstances[0].onclose()
    expect(client.reconnectAttempts).toBe(1)
    // 等 1000ms, _scheduleReconnect 触发, 再次 connect
    vi.advanceTimersByTime(1100)
    expect(mockWsInstances).toHaveLength(2)
    // 第 2 次 close (修复前: onopen 立即 reset → 永远 1; 修复后: 累加到 2)
    mockWsInstances[1].onclose()
    expect(client.reconnectAttempts).toBe(2)
    // 等 2000ms
    vi.advanceTimersByTime(2100)
    expect(mockWsInstances).toHaveLength(3)
    mockWsInstances[2].onclose()
    expect(client.reconnectAttempts).toBe(3)
  })

  it('case 3: onopen 在短期连接下不重置 attempts (lastPongAt 距离 < 30s)', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    // case 3 也需要 token 让 _scheduleReconnect 真正 reconnect
    localStorage.setItem('access_token', 'test-token')
    client.connect('test-token')
    mockWsInstances[0].onclose() // attempts=1
    expect(client.reconnectAttempts).toBe(1)
    vi.advanceTimersByTime(1100)
    // 第 2 次 connect
    expect(mockWsInstances).toHaveLength(2)
    // 模拟 onopen (修复前: 立即 reset → attempts=0; 修复后: lastPongAt 刚 set, < 30s, 不重置)
    mockWsInstances[1].onopen()
    expect(client.connected).toBe(true)
    // 立即 close
    mockWsInstances[1].onclose()
    expect(client.reconnectAttempts).toBe(2) // 必须保持累加
  })

  it('case 4: 稳定连接 (lastPongAt > 30s) 后 onopen 才重置 attempts', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    // case 4 必须先存 access_token (connect 内从 localStorage 读)
    localStorage.setItem('access_token', 'test-token-1')
    client.connect('test-token-1')
    mockWsInstances[0].onclose() // attempts=1
    vi.advanceTimersByTime(1100)
    // 第 2 次 connect → onopen (localStorage 仍存 token)
    expect(mockWsInstances).toHaveLength(2)
    mockWsInstances[1].onopen()
    expect(client.connected).toBe(true)
    // 模拟时间快进 > 30s, 让 lastPongAt 距离上次 onopen > 30s
    vi.advanceTimersByTime(35000)
    // 重新 connect (token 刷新等场景)
    client.disconnect()
    localStorage.setItem('access_token', 'test-token-2')
    client.connect('test-token-2')
    // 此时 onopen, lastPongAt 距离上次 > 30s, 应当重置 attempts
    expect(mockWsInstances).toHaveLength(3)
    mockWsInstances[2].onopen()
    expect(client.connected).toBe(true)
    // 新一轮 close 应从 1 开始
    mockWsInstances[2].onclose()
    expect(client.reconnectAttempts).toBe(1)
  })

  it('case 5: disconnect 阻止后续重连', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    client.connect('test-token')
    mockWsInstances[0].onclose()
    expect(client.reconnectAttempts).toBe(1)
    // 用户主动 disconnect
    client.disconnect()
    expect(client.shouldReconnect).toBe(false)
    vi.advanceTimersByTime(5000)
    // 不应再 connect
    expect(mockWsInstances).toHaveLength(1)
  })
})
