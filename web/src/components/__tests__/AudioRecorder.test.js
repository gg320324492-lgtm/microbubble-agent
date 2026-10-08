/**
 * AudioRecorder.test.js - 2026-07-16 (#207 完整流程修复)
 *
 * 覆盖:
 * - handleStart 失败 → 调 cancel-recording + 清 meetingIdRef + ElMessage (Step 4)
 * - handleStart 失败 + meetingId=null → 不调 cancel-recording
 * - cancel-recording 网络错 → 不阻塞 catch 块, ElMessage 仍显示
 * - 错误类型精细化: NotAllowedError / NotFoundError / NotReadableError / NotSupportedError / SecurityError (Step 9)
 *
 * 实现策略: 不依赖 DOM 查找 .btn-start (jsdom 不渲染 Element Plus 复杂组件),
 * 直接调 wrapper.vm.handleStart() 验证 catch 路径。
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import axios from 'axios'

// === vi.mock 会 hoist 到文件顶部, mock 引用的 fn 必须用 vi.hoisted 包起来 ===
const { mockStart, mockUnsubscribe, mockStopRecording, mockElMessageError, mockElMessageSuccess, mockElMessageWarning, mockElMessageCall, mockEnsureHeartbeat, mockStopModuleHeartbeat, mockBeat, postSpy } = vi.hoisted(() => ({
  mockStart: vi.fn(),
  mockUnsubscribe: vi.fn(),
  mockStopRecording: vi.fn(),
  mockElMessageError: vi.fn(),
  mockElMessageSuccess: vi.fn(),
  mockElMessageWarning: vi.fn(),
  // 2026-10-08 P1-1: ElMessage(options) 也被 AudioRecorder 调用 (iOS 5s 提示)
  mockElMessageCall: vi.fn(),
  // 2026-10-08 P0-1: useRecordingHeartbeat 模块级单例的 mock,
  // 让 AudioRecorder 测试不必真正启动心跳
  mockEnsureHeartbeat: vi.fn(),
  mockStopModuleHeartbeat: vi.fn(),
  mockBeat: vi.fn(),
  postSpy: vi.fn().mockResolvedValue({ data: { cancelled: true } }),
}))

vi.mock('@/composables/useGlobalRecorder', () => ({
  useGlobalRecorder: () => ({
    state: { value: 'idle' },
    elapsed: { value: 0 },
    barHeights: { value: [4, 4, 4, 4, 4] },
    isPaused: { value: false },
    start: mockStart,
    pause: vi.fn(),
    resumePaused: vi.fn(),
    stop: vi.fn().mockResolvedValue(null),
    reset: vi.fn(),
    isActive: () => false,
    getAudioBlob: () => null,
    onChunk: () => mockUnsubscribe,
  }),
}))

vi.mock('@/composables/useRecordingState', () => ({
  useRecordingState: () => ({
    stopRecording: mockStopRecording,
  }),
}))

vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    online: { value: true },
  }),
}))

vi.mock('@/composables/useChunkedRecorder', () => ({
  useChunkedRecorder: () => ({
    uploadedCount: { value: 0 },
    pendingCount: { value: 0 },
    lastChunkIndex: { value: -1 },
    totalChunks: { value: 0 },
    status: { value: 'idle' },
    stop: vi.fn().mockResolvedValue(undefined),
  }),
}))

// 2026-10-08 P0-1: mock 模块级心跳单例, 测试不真发 HTTP
vi.mock('@/composables/useRecordingHeartbeat', () => ({
  ensureHeartbeat: mockEnsureHeartbeat,
  stopHeartbeat: mockStopModuleHeartbeat,
  beat: mockBeat,
}))

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(mockElMessageCall, {
    error: mockElMessageError,
    success: mockElMessageSuccess,
    warning: mockElMessageWarning,
  }),
  ElMessageBox: { confirm: vi.fn() },
}))

vi.mock('axios', () => ({
  default: {
    post: postSpy,
  },
}))

import AudioRecorder from '@/components/AudioRecorder.vue'

const mountAudio = (props = {}) => {
  return mount(AudioRecorder, {
    props: { meetingId: 207, meetingTitle: '正在听会（ID 207）', ...props },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  postSpy.mockResolvedValue({ data: { cancelled: true } })
  mockStopRecording.mockClear()
  mockElMessageError.mockClear()
  mockElMessageWarning.mockClear()
  mockElMessageCall.mockClear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('AudioRecorder.handleStart catch 完整 rollback (Step 4, #207 修复)', () => {
  it('start() reject → 调 cancel-recording + meetingIdRef=null + clearRecordingIndicator', async () => {
    const permErr = Object.assign(new Error('Permission denied'), { name: 'NotAllowedError' })
    mockStart.mockRejectedValueOnce(permErr)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(postSpy).toHaveBeenCalledWith('/api/v1/meetings/207/cancel-recording')
    expect(mockStopRecording).toHaveBeenCalled()
  })

  it('start() reject + meetingId=null → 不调 cancel-recording', async () => {
    const someErr = new Error('boom')
    mockStart.mockRejectedValueOnce(someErr)
    const wrapper = mountAudio({ meetingId: null })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(postSpy).not.toHaveBeenCalled()
  })

  it('cancel-recording 网络错 → 不阻塞 catch, ElMessage 仍显示', async () => {
    const someErr = new Error('microphone timeout')
    mockStart.mockRejectedValueOnce(someErr)
    postSpy.mockRejectedValueOnce(new Error('network fail'))
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(postSpy).toHaveBeenCalledWith('/api/v1/meetings/207/cancel-recording')
    expect(mockStopRecording).toHaveBeenCalled()
  })
})

describe('AudioRecorder.handleStart 错误类型精细化 (Step 9)', () => {
  it('NotAllowedError → 用户提示 "麦克风权限被拒绝"', async () => {
    const err = Object.assign(new Error('x'), { name: 'NotAllowedError' })
    mockStart.mockRejectedValueOnce(err)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(mockElMessageError).toHaveBeenCalledWith(expect.stringMatching(/麦克风权限被拒绝/))
  })

  it('NotFoundError → 用户提示 "未检测到麦克风设备"', async () => {
    const err = Object.assign(new Error('x'), { name: 'NotFoundError' })
    mockStart.mockRejectedValueOnce(err)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(mockElMessageError).toHaveBeenCalledWith(expect.stringMatching(/未检测到麦克风/))
  })

  it('NotReadableError → 用户提示 "麦克风被其他程序占用"', async () => {
    const err = Object.assign(new Error('x'), { name: 'NotReadableError' })
    mockStart.mockRejectedValueOnce(err)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(mockElMessageError).toHaveBeenCalledWith(expect.stringMatching(/占用/))
  })

  it('NotSupportedError → 用户提示 "请使用 Chrome/Edge/Safari"', async () => {
    const err = Object.assign(new Error('x'), { name: 'NotSupportedError' })
    mockStart.mockRejectedValueOnce(err)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(mockElMessageError).toHaveBeenCalledWith(expect.stringMatching(/Chrome \/ Edge \/ Safari/))
  })

  it('SecurityError → 用户提示 "请使用 HTTPS 或 localhost"', async () => {
    const err = Object.assign(new Error('x'), { name: 'SecurityError' })
    mockStart.mockRejectedValueOnce(err)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(mockElMessageError).toHaveBeenCalledWith(expect.stringMatching(/HTTPS/))
  })

  it('其他错误 (getUserMedia timeout) → 显示原 error message', async () => {
    const err = new Error('getUserMedia 5000ms timeout')
    mockStart.mockRejectedValueOnce(err)
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    expect(mockElMessageError).toHaveBeenCalledWith(expect.stringMatching(/getUserMedia 5000ms timeout/))
  })
})

// 2026-10-08 P1-1: iOS Safari 5s 无分片提示
// AudioRecorder 内 isIOSSafari 是局部函数, 通过 mount + 修改 navigator.userAgent 间接验证
describe('AudioRecorder P1-1: iOS Safari 5s 无分片提示', () => {
  const origUA = navigator.userAgent

  afterEach(() => {
    Object.defineProperty(navigator, 'userAgent', { value: origUA, configurable: true })
    vi.useRealTimers()
  })

  it('iOS Safari UA → handleStart 启动 5s 后 totalChunks=0 弹 ElMessage warning', async () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.6 Mobile/15E148 Safari/604.1',
      configurable: true,
    })
    mockStart.mockResolvedValueOnce(undefined)
    // totalChunks=0 默认 → mock 里 useChunkedRecorder 已经返 { value: 0 }

    vi.useFakeTimers()
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    // 推进 5s 触发 iOS 5s 提示
    vi.advanceTimersByTime(5000)
    await flushPromises()
    expect(mockElMessageCall).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringMatching(/iOS Safari/),
        type: 'warning',
      }),
    )
  })

  it('Chrome on iOS UA → 不弹 iOS 提示', async () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.0.0 Safari/604.1',
      configurable: true,
    })
    mockStart.mockResolvedValueOnce(undefined)

    vi.useFakeTimers()
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    vi.advanceTimersByTime(5000)
    await flushPromises()
    // iOS Chrome 不命中, ElMessage(options) 不被调
    expect(mockElMessageCall).not.toHaveBeenCalled()
  })

  it('桌面 Chrome UA → 不弹 iOS 提示', async () => {
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
      configurable: true,
    })
    mockStart.mockResolvedValueOnce(undefined)

    vi.useFakeTimers()
    const wrapper = mountAudio({ meetingId: 207 })
    await wrapper.vm.handleStart()
    await flushPromises()
    vi.advanceTimersByTime(5000)
    await flushPromises()
    expect(mockElMessageCall).not.toHaveBeenCalled()
  })
})
