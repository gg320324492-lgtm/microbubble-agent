import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'

import {
  useNetworkStatus,
  getNetworkStatus,
  markReachable,
  markUnreachable,
  _resetForTesting,
  _test_probe,
  _test_getFailStreak,
  _test_setFailStreak,
  _test_isProbing,
  _test_setWorkingEndpoint,
} from '../useNetworkStatus'

// 设置 navigator.onLine 工具
function setNavigatorOnline(value) {
  Object.defineProperty(navigator, 'onLine', { value, configurable: true, writable: true })
}

function fireOffline() {
  window.dispatchEvent(new Event('offline'))
}
function fireOnline() {
  window.dispatchEvent(new Event('online'))
}

// Stub 组件：仅触发 useNetworkStatus() 的 onMounted/onUnmounted 钩子
function makeStub() {
  return defineComponent({
    setup() {
      useNetworkStatus()
      return () => h('div')
    },
  })
}

describe('useNetworkStatus v2 — 心跳探测 (修复网络误报)', () => {
  let fetchSpy

  beforeEach(() => {
    vi.useFakeTimers()
    setNavigatorOnline(true)
    _resetForTesting()
    fetchSpy = vi.fn()
    global.fetch = fetchSpy
  })

  afterEach(() => {
    // 清理所有挂载的 stub
    _resetForTesting()
    vi.useRealTimers()
    vi.restoreAllMocks()
    delete global.fetch
  })

  // === Case 1: 初值采用 navigator.onLine ===
  it('1. navigator.onLine=false 时初值为 offline', () => {
    setNavigatorOnline(false)
    _resetForTesting()
    const { online, status } = getNetworkStatus()
    expect(online.value).toBe(false)
    expect(status.value).toBe('offline')
  })

  it('1b. navigator.onLine=true 时初值为 online', () => {
    setNavigatorOnline(true)
    _resetForTesting()
    const { online, status } = getNetworkStatus()
    expect(online.value).toBe(true)
    expect(status.value).toBe('online')
  })

  // === Case 2: 浏览器 offline 事件不立即翻状态 (修复 v1 误报) ===
  it('2. 浏览器 offline 事件不等探测不翻状态', async () => {
    fetchSpy.mockResolvedValue({ status: 200 })

    const wrapper = mount(makeStub())
    await nextTick()

    const before = wrapper.vm.$el ? true : true  // sanity
    const { online } = getNetworkStatus()
    expect(online.value).toBe(true)

    // v2 关键修复: offline 事件不立即翻状态
    fireOffline()
    expect(online.value).toBe(true)  // 仍为 true, 等探测

    // 探测成功 (mock fetch 200) → 仍 true
    await vi.advanceTimersByTimeAsync(10_100)  // 第一次探测 + 一次 setInterval
    expect(online.value).toBe(true)

    wrapper.unmount()
  })

  // === Case 3: 连续 FAIL_THRESHOLD 次失败才判 offline ===
  it('3. 连续 3 次探测失败才判 offline', async () => {
    fetchSpy.mockRejectedValue(new TypeError('NetworkError'))
    // 不 mount stub: 避免 startProbing 的初始 probe 与测试 _test_probe 冲突
    // 直接通过 _test_probe 触发探测, 验证 failStreak 累加 + offline 翻转
    _test_setFailStreak(0)
    _test_setWorkingEndpoint(null)

    const { online } = getNetworkStatus()
    expect(online.value).toBe(true)

    // 1 次失败
    await _test_probe()
    expect(_test_getFailStreak()).toBe(1)
    expect(online.value).toBe(true)

    // 2 次失败
    await _test_probe()
    expect(_test_getFailStreak()).toBe(2)
    expect(online.value).toBe(true)

    // 3 次失败 → 翻 offline
    await _test_probe()
    expect(_test_getFailStreak()).toBe(3)
    expect(online.value).toBe(false)
  })

  // === Case 4: 探测成功立即恢复 online ===
  it('4. 探测成功立即恢复 online=true', async () => {
    fetchSpy.mockResolvedValue({ status: 200 })

    const { online } = getNetworkStatus()
    // 连续 3 次失败才置为 offline，避免单次网络抖动误报
    markUnreachable()
    markUnreachable()
    markUnreachable()
    expect(online.value).toBe(false)
    expect(_test_getFailStreak()).toBe(3)

    // 探测成功
    await _test_probe()
    expect(online.value).toBe(true)
    expect(_test_getFailStreak()).toBe(0)
  })

  // === Case 5: markReachable 立即恢复 (不需要等探测) ===
  it('5. markReachable 立即恢复 online, 不等探测', () => {
    const { online } = getNetworkStatus()

    markUnreachable()
    markUnreachable()
    markUnreachable()
    expect(online.value).toBe(false)
    expect(_test_getFailStreak()).toBe(3)

    // markReachable 立即生效, 不需探测
    markReachable()
    expect(online.value).toBe(true)
    expect(_test_getFailStreak()).toBe(0)
  })

  // === Case 6: 探测并发去重 ===
  it('6. 探测并发去重 (同一时刻多次触发只发一次 fetch)', async () => {
    let resolveFetch
    fetchSpy.mockImplementation(() => new Promise((r) => { resolveFetch = r }))

    const wrapper = mount(makeStub())
    await nextTick()

    // 同时触发 3 次
    const p1 = _test_probe()
    const p2 = _test_probe()
    const p3 = _test_probe()
    expect(fetchSpy).toHaveBeenCalledTimes(1)  // 只发了一次

    // resolve 让 promise 全部 settle
    resolveFetch({ status: 200 })
    await Promise.all([p1, p2, p3])
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  // === Case 7: probe timeout 处理 ===
  it('7. probe timeout 5s 触发 AbortController 失败', async () => {
    // fetch 监听 abort 事件, abort 后 reject
    fetchSpy.mockImplementation((_url, init) => new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    _test_setFailStreak(0)
    _test_setWorkingEndpoint(null)

    const p = _test_probe()

    // 推进 20s 让 3 个端点都触发 timeout + abort (每个端点独立 5s timer)
    await vi.advanceTimersByTimeAsync(20_000)
    await p

    expect(_test_getFailStreak()).toBe(1)  // failStreak 仅累加 1 (一次 probe())
    const { online } = getNetworkStatus()
    expect(online.value).toBe(true)  // 还没到 3 次, 仍 online
  }, 30_000)  // 测试需要 ≥20s 推进 fake timer, 默认 5s timeout 不够

  // === Case 8: 卸载清理 timer (refCount 归零停心跳) ===
  it('8. 最后一个组件 unmount 后停心跳', async () => {
    const wrapper = mount(makeStub())
    await nextTick()
    expect(_test_isProbing()).toBe(true)

    wrapper.unmount()
    expect(_test_isProbing()).toBe(false)
  })

  // === Case 9: 多端点 fallback ===
  it('9. /health 失败时 fallback 到鉴权端点', async () => {
    fetchSpy.mockImplementation((url) => {
      if (url === '/health') return Promise.reject(new TypeError('NetworkError'))
      if (url === '/api/v1/auth/me') return Promise.resolve({ status: 401 })
      return Promise.reject(new TypeError('unknown'))
    })

    // 清空自学习缓存, 验证默认 fallback 顺序
    _test_setWorkingEndpoint(null)
    _test_setFailStreak(0)
    await _test_probe()

    expect(fetchSpy).toHaveBeenNthCalledWith(1, '/health', expect.objectContaining({ method: 'GET' }))
    expect(fetchSpy).toHaveBeenNthCalledWith(2, '/api/v1/auth/me', expect.objectContaining({ method: 'GET' }))

    const { online } = getNetworkStatus()
    expect(online.value).toBe(true)
  })

  // === Case 10: alive 判定宽松 (401/5xx 都算后端在响应) ===
  it('10. 401 响应也算 alive (后端在响应 = 网络通)', async () => {
    fetchSpy.mockResolvedValue({ status: 401 })  // /api/v1/auth/me 未登录
    _test_setWorkingEndpoint(null)
    _test_setFailStreak(0)

    const wrapper = mount(makeStub())
    await nextTick()

    await _test_probe()

    const { online } = getNetworkStatus()
    expect(online.value).toBe(true)  // 401 算 alive

    wrapper.unmount()
  })
})
