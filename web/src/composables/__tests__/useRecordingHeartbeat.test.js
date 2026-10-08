/**
 * useRecordingHeartbeat.test.js — 2026-10-08 P0-1 / P0-2 / P0-3 单测
 *
 * 事故链:
 *   - 会议 255 (2026-10-08) 录音 38min 全程 0 心跳 → orphan 误杀
 *   - 根因 A: 心跳绑 AudioRecorder 组件, 恢复路径不启动心跳
 *
 * 覆盖:
 *   1. 模块级心跳在组件卸载后仍发 (P0-1 保证: useGlobalRecorder 同寿命, 不绑组件)
 *   2. visibilitychange → visible 立即 beat (P0-2: 切回前台补一次)
 *   3. 恢复路径 startGlobalRecorder() 后心跳启动 (P0-1 保证: MeetingRoomView.onMounted 显式调)
 *   4. pagehide 时 fetch(keepalive) POST /recording-presence (P0-3: 通知后端页面离开)
 *
 * 注意: useRecordingHeartbeat 是模块级单例 + 注册 document/window listener。
 * 每个测试前必须调 _resetForTests() 避免状态污染。
 * listener 重复挂载由 listenersRegistered 守卫 + unregisterListeners() 双重保证。
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// mock sendRecordingHeartbeat 避免真实 HTTP
vi.mock('@/composables/useMeetingAudioUpload', () => ({
  sendRecordingHeartbeat: vi.fn(() => Promise.resolve(true)),
}))

import {
  ensureHeartbeat,
  stopHeartbeat,
  beat,
  isHeartbeatActive,
  getCurrentMeetingId,
  getLastBeatAt,
  _resetForTests,
} from '@/composables/useRecordingHeartbeat'

describe('useRecordingHeartbeat 模块级单例 (P0-1)', () => {
  let sendRecordingHeartbeat

  beforeEach(async () => {
    _resetForTests()
    const mod = await import('@/composables/useMeetingAudioUpload')
    sendRecordingHeartbeat = mod.sendRecordingHeartbeat
    sendRecordingHeartbeat.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    _resetForTests()
  })

  it('ensureHeartbeat(id) 启动 60s interval + 立即 beat 一次', () => {
    ensureHeartbeat(255)
    expect(isHeartbeatActive()).toBe(true)
    expect(getCurrentMeetingId()).toBe(255)
    expect(getLastBeatAt()).toBeGreaterThan(0)
    // 立即 beat 一次
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(1)
    expect(sendRecordingHeartbeat).toHaveBeenCalledWith(255)
  })

  it('重复 ensureHeartbeat 同 id 幂等 (setInterval 不重建, 但 beat 仍发一次)', () => {
    const setIntervalSpy = vi.spyOn(globalThis, 'setInterval')
    ensureHeartbeat(255)
    const callsAfterFirst = setIntervalSpy.mock.calls.length
    sendRecordingHeartbeat.mockClear()
    ensureHeartbeat(255)
    // ensureHeartbeat 语义是 "确保心跳在" —— 即使 meetingId 未变, 仍立即 beat 一次
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(1)
    // 但 setInterval 不重建 (没新增调用)
    expect(setIntervalSpy.mock.calls.length).toBe(callsAfterFirst)
    setIntervalSpy.mockRestore()
  })

  it('60s interval 持续 beat', () => {
    ensureHeartbeat(255)
    sendRecordingHeartbeat.mockClear()
    vi.advanceTimersByTime(60000)
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(60000)
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(2)
  })

  it('stopHeartbeat 清 timer + currentMeetingId + lastBeatAt', () => {
    ensureHeartbeat(255)
    stopHeartbeat()
    expect(isHeartbeatActive()).toBe(false)
    expect(getCurrentMeetingId()).toBe(null)
    expect(getLastBeatAt()).toBe(0)
    sendRecordingHeartbeat.mockClear()
    vi.advanceTimersByTime(60000)
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(0)
  })

  it('ensureHeartbeat(null) 不启动 (无会议 ID)', () => {
    ensureHeartbeat(null)
    expect(isHeartbeatActive()).toBe(false)
    expect(sendRecordingHeartbeat).not.toHaveBeenCalled()
  })
})

describe('useRecordingHeartbeat 模块级心跳在组件卸载后仍发 (P0-1 验收点 1)', () => {
  let sendRecordingHeartbeat

  beforeEach(async () => {
    _resetForTests()
    const mod = await import('@/composables/useMeetingAudioUpload')
    sendRecordingHeartbeat = mod.sendRecordingHeartbeat
    sendRecordingHeartbeat.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    _resetForTests()
  })

  it('ensureHeartbeat 后即使 stopHeartbeat 没调, 60s/120s/180s 仍 beat (模拟组件卸载但心跳不挂)', () => {
    ensureHeartbeat(255)
    sendRecordingHeartbeat.mockClear()

    // 模拟「组件卸载」: 调用方什么都不做, 心跳继续
    // 推进 180s 模拟三段间隔
    vi.advanceTimersByTime(60000)
    vi.advanceTimersByTime(60000)
    vi.advanceTimersByTime(60000)

    // 3 个 60s 周期 = 3 次 beat
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(3)
    expect(sendRecordingHeartbeat).toHaveBeenLastCalledWith(255)
  })

  it('beat() 无 currentMeetingId 不抛错 (录音未启动场景)', () => {
    // 未调 ensureHeartbeat, 直接 beat → no-op
    expect(() => beat()).not.toThrow()
    expect(sendRecordingHeartbeat).not.toHaveBeenCalled()
  })
})

describe('useRecordingHeartbeat visibilitychange 切回前台立即 beat (P0-2 验收点 2)', () => {
  let sendRecordingHeartbeat

  beforeEach(async () => {
    _resetForTests()
    const mod = await import('@/composables/useMeetingAudioUpload')
    sendRecordingHeartbeat = mod.sendRecordingHeartbeat
    sendRecordingHeartbeat.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    _resetForTests()
  })

  it('document.visibilitychange → visible 立即 beat (60s 周期未到)', () => {
    ensureHeartbeat(255)
    sendRecordingHeartbeat.mockClear()

    // 模拟 jsdom visibilityState 默认 'visible', 改为 'hidden' 再改回
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'hidden',
    })
    document.dispatchEvent(new Event('visibilitychange'))

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'visible',
    })
    document.dispatchEvent(new Event('visibilitychange'))

    // 切回前台立即 beat 一次 (不等 60s)
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(1)
    expect(sendRecordingHeartbeat).toHaveBeenCalledWith(255)
  })

  it('切到 hidden 时写 localStorage presence (P0-3 弱信号)', () => {
    ensureHeartbeat(255)
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'hidden',
    })
    document.dispatchEvent(new Event('visibilitychange'))

    expect(setItemSpy).toHaveBeenCalledWith(
      'recording:presence',
      expect.stringContaining('"meetingId":255')
    )
    setItemSpy.mockRestore()
  })
})

describe('useRecordingHeartbeat pageshow persisted / focus 立即 beat (P0-2)', () => {
  let sendRecordingHeartbeat

  beforeEach(async () => {
    _resetForTests()
    const mod = await import('@/composables/useMeetingAudioUpload')
    sendRecordingHeartbeat = mod.sendRecordingHeartbeat
    sendRecordingHeartbeat.mockClear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    _resetForTests()
  })

  it('window pageshow (e.persisted=true) 立即 beat', () => {
    ensureHeartbeat(255)
    sendRecordingHeartbeat.mockClear()
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }))
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(1)
  })

  it('window pageshow (e.persisted=false) 不 beat (普通导航, 不是 bfcache)', () => {
    ensureHeartbeat(255)
    sendRecordingHeartbeat.mockClear()
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: false }))
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(0)
  })

  it('window focus 立即 beat', () => {
    ensureHeartbeat(255)
    sendRecordingHeartbeat.mockClear()
    window.dispatchEvent(new Event('focus'))
    expect(sendRecordingHeartbeat).toHaveBeenCalledTimes(1)
  })
})

describe('useRecordingHeartbeat pagehide fetch keepalive (P0-3)', () => {
  let sendRecordingHeartbeat
  let fetchSpy

  beforeEach(async () => {
    _resetForTests()
    localStorage.setItem('access_token', 'test-jwt-token')
    const mod = await import('@/composables/useMeetingAudioUpload')
    sendRecordingHeartbeat = mod.sendRecordingHeartbeat
    sendRecordingHeartbeat.mockClear()
    // fetch mock (2026-10-08 主指挥复验修正: sendBeacon 无法带 Authorization header,
    // 改用 fetch + keepalive:true)
    fetchSpy = vi.fn(() => Promise.resolve({ ok: true, status: 200 }))
    vi.stubGlobal('fetch', fetchSpy)
  })

  afterEach(() => {
    _resetForTests()
    localStorage.removeItem('access_token')
    vi.unstubAllGlobals()
  })

  it('pagehide 时 fetch POST /recording-presence 带 Authorization + keepalive', () => {
    ensureHeartbeat(255)
    window.dispatchEvent(new Event('pagehide'))

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const [url, opts] = fetchSpy.mock.calls[0]
    expect(url).toBe('/api/v1/meetings/255/recording-presence')
    expect(opts.method).toBe('POST')
    // keepalive 是关键 —— 页面卸载后仍完成请求 (sendBeacon 的等价能力)
    expect(opts.keepalive).toBe(true)
    // Authorization header 是 sendBeacon 做不到的
    expect(opts.headers.Authorization).toBe('Bearer test-jwt-token')
    expect(JSON.parse(opts.body)).toMatchObject({ presence: 'pagehide' })
  })

  it('无 currentMeetingId 时 fetch 不发 (录音未启动)', () => {
    // 没 ensureHeartbeat, pagehide 应该 no-op
    window.dispatchEvent(new Event('pagehide'))
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('无 access_token 时跳过上报 (避免注定 401 的请求)', () => {
    localStorage.removeItem('access_token')
    ensureHeartbeat(255)
    window.dispatchEvent(new Event('pagehide'))
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('fetch reject 静默失败 (pagehide 是弱信号, 不该抛错影响页面卸载)', () => {
    fetchSpy.mockImplementation(() => Promise.reject(new Error('network down')))
    ensureHeartbeat(255)
    // 不应抛错 —— handler 内部 catch 了
    expect(() => window.dispatchEvent(new Event('pagehide'))).not.toThrow()
  })
})

describe('useRecordingHeartbeat 恢复路径 startGlobalRecorder 后心跳启动 (P0-1 验收点 3)', () => {
  // 这个 case 是端到端的真实路径 — MeetingRoomView.onMounted:
  //   await startGlobalRecorder()
  //   ensureHeartbeat(id)
  // 这里用纯单元测试模拟「meetingId 到位」后 ensureHeartbeat 触发

  let sendRecordingHeartbeat

  beforeEach(async () => {
    _resetForTests()
    const mod = await import('@/composables/useMeetingAudioUpload')
    sendRecordingHeartbeat = mod.sendRecordingHeartbeat
    sendRecordingHeartbeat.mockClear()
  })

  afterEach(() => {
    _resetForTests()
  })

  it('meetingId 从 query 进入页面 → ensureHeartbeat(255) → 心跳立即启动', () => {
    // 模拟 MeetingRoomView.onMounted: 拿到 meetingId 后调 ensureHeartbeat
    // (前端真实代码 web/src/views/MeetingRoomView.vue:277 已加 ensureHeartbeat(id))
    ensureHeartbeat(255)

    // 验证: 心跳已启, currentMeetingId 正确
    expect(isHeartbeatActive()).toBe(true)
    expect(getCurrentMeetingId()).toBe(255)
    expect(sendRecordingHeartbeat).toHaveBeenCalledWith(255)
  })

  it('录音真正结束 stopHeartbeat 后心跳停 (组件卸载但 stopHeartbeat 没调 → 心跳仍跑)', () => {
    ensureHeartbeat(255)
    // 模拟 doStop 路径
    stopHeartbeat()
    expect(isHeartbeatActive()).toBe(false)

    // 验证: 即使 "组件卸载" (什么都不做), 心跳也不会自动重启
    // 避免幽灵录音状态
    const sendMock = sendRecordingHeartbeat
    sendMock.mockClear()
    // 等 60s (用 fake timer)
    vi.useFakeTimers()
    vi.advanceTimersByTime(60000)
    expect(sendMock).not.toHaveBeenCalled()
    vi.useRealTimers()
  })
})