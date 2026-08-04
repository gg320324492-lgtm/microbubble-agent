/**
 * W100 +60 WS 重连退避 successfulConnects 守卫测试
 *
 * 真根因 (W100 +50b 修复遗留):
 *   wsClient.js onopen 中条件 `this.lastPongAt && (now - this.lastPongAt) > 30000`
 *   因 lastPongAt=0 是 falsy, 短路成 false → attempts 永远不重置.
 *   W100 +50b 设计意图: 仅"稳定连接" (lastPongAt > 30s 前) 才 reset,
 *   短期 connect-then-close (auth race) 不 reset, 让指数退避真正生效.
 *
 * W100 +60 修复:
 *   1) 用 `successfulConnects >= 2` 守卫替代 lastPongAt 时间窗口判断
 *      (避免 lastPongAt=0 falsy 短路 bug)
 *   2) 增加 `lastConnectAt` 字段 (connect 时就更新, 不等 pong)
 *   3) lastPongAt 也立即在 onopen 时更新 (不再依赖 server pong)
 *
 * 3 case 覆盖：
 * ① 连续 auth-race (每次 onopen 立即 close) → 1st 不 reset, 2nd+ reset 失败循环
 * ② 稳定连接守恒: 成功 2 次 connect 后, attempts=0 (新 disconnect 周期重新开始)
 * ③ lastConnectAt + lastPongAt 在 onopen 立即更新, 不等 server pong
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const buildModule = async () => {
  vi.resetModules()
  const mod = await import('../../utils/wsClient')
  return mod
}

describe('wsClient — W100 +60 successfulConnects 守卫 + lastPongAt falsy 短路修复', () => {
  let mockWsInstances = []
  let originalLocalStorage
  let originalWebSocket

  beforeEach(() => {
    vi.useFakeTimers()
    mockWsInstances = []
    originalWebSocket = globalThis.WebSocket
    globalThis.WebSocket = class MockWebSocket {
      constructor(url) {
        this.url = url
        this.readyState = 0
        this.onopen = null
        this.onclose = null
        this.onerror = null
        this.onmessage = null
        mockWsInstances.push(this)
      }
      close() {
        this.readyState = 3
      }
      send() {}
    }
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

  it('① 1st connect-onopen 立即 close (auth race) → 不重置 attempts (successfulConnects<2)', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    localStorage.setItem('access_token', 'test-token')
    client.connect('test-token')
    expect(mockWsInstances).toHaveLength(1)
    mockWsInstances[0].onopen() // successfulConnects=1
    expect(client.successfulConnects).toBe(1)
    // 立即 close (auth race 模拟) → attempts 不应被重置
    mockWsInstances[0].onclose()
    expect(client.reconnectAttempts).toBe(1) // 累加自 _scheduleReconnect, 非 reset
    // reconnect
    vi.advanceTimersByTime(1100)
    expect(mockWsInstances).toHaveLength(2)
    mockWsInstances[1].onopen() // successfulConnects=2 → 此时才 reset
    expect(client.successfulConnects).toBe(2)
    // 修复后: successfulConnects>=2 触发 reset, attempts=0
    expect(client.reconnectAttempts).toBe(0)
  })

  it('② 2nd+ 稳定 onopen → reset attempts = 0 (新 disconnect 周期重新开始)', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    localStorage.setItem('access_token', 'test-token')
    client.connect('test-token')
    mockWsInstances[0].onopen() // successfulConnects=1
    mockWsInstances[0].onclose() // attempts=1
    expect(client.reconnectAttempts).toBe(1)
    // reconnect
    vi.advanceTimersByTime(1100)
    mockWsInstances[1].onopen() // successfulConnects=2 → reset attempts
    expect(client.reconnectAttempts).toBe(0)
    // 立即又 close (新一轮断开) → attempts=1 (从 0 重新累加)
    mockWsInstances[1].onclose()
    expect(client.reconnectAttempts).toBe(1)
    // 验证: 不再"永远 attempt=1" 死循环 (修复前: 永远 1; 修复后: 1, 2, 3 累加)
    vi.advanceTimersByTime(2100)
    expect(mockWsInstances).toHaveLength(3)
    mockWsInstances[2].onopen() // successfulConnects=3, 仍 reset
    mockWsInstances[2].onclose()
    expect(client.reconnectAttempts).toBe(1) // reset 后从 1 重新累加
  })

  it('③ lastConnectAt + lastPongAt 在 onopen 立即更新 (不等 server pong)', async () => {
    const { getWsClient } = await buildModule()
    const client = getWsClient()
    localStorage.setItem('access_token', 'test-token')
    expect(client.lastConnectAt).toBe(0)
    expect(client.lastPongAt).toBe(0)
    client.connect('test-token')
    mockWsInstances[0].onopen()
    // 关键: onopen 后立即更新, 不依赖 server ping/pong
    expect(client.lastConnectAt).toBeGreaterThan(0)
    expect(client.lastPongAt).toBeGreaterThan(0)
    // 同一时刻 (同步)
    expect(client.lastPongAt).toBe(client.lastConnectAt)
  })
})