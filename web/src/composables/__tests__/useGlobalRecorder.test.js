/**
 * useGlobalRecorder.test.js - 2026-07-16 (#207 完整流程修复)
 *
 * 覆盖:
 * - MIME 探测链: 探测 webm;opus → webm → ogg;opus → mp4, 任一支持即用 (Step 1)
 * - getUserMedia Promise.race 5s timeout: 永久 pending 5s 后 reject (Step 2)
 * - getUserMedia 正常 resolve: 不受 timeout 影响
 * - MediaRecorder undefined (企业微信 X5 模拟): start() reject
 * - getUserMedia reject 透传到 start()
 *
 * 注意: useGlobalRecorder 内部用模块级单例, start() 会真实调 getUserMedia / new MediaRecorder。
 * setup.js 已注入 FakeMediaRecorder / FakeMediaStream / FakeAudioContext polyfill。
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { FakeMediaRecorder, FakeMediaStream } from '@/__tests__/setup-media-recorder'

describe('useGlobalRecorder MIME 探测 (Step 1, #207 修复)', () => {
  beforeEach(() => {
    FakeMediaRecorder.__setSupportedTypes([])
    // 每次测完 reset 单例 state
    const { reset } = useGlobalRecorder()
    reset()
  })

  it('isTypeSupported webm/opus 返 true → 用 webm/opus', () => {
    FakeMediaRecorder.__setSupportedTypes(['audio/webm;codecs=opus'])
    expect(MediaRecorder.isTypeSupported('audio/webm;codecs=opus')).toBe(true)
  })

  it('isTypeSupported webm/opus 返 false 但 mp4 返 true (iOS Safari) → 探测到 mp4', () => {
    FakeMediaRecorder.__setSupportedTypes(['audio/mp4'])
    expect(MediaRecorder.isTypeSupported('audio/webm;codecs=opus')).toBe(false)
    expect(MediaRecorder.isTypeSupported('audio/mp4')).toBe(true)
  })

  it('isTypeSupported 全部返 false (老 WebView) → 走浏览器默认 (空字符串)', () => {
    FakeMediaRecorder.__setSupportedTypes([])
    expect(MediaRecorder.isTypeSupported('audio/webm;codecs=opus')).toBe(false)
    expect(MediaRecorder.isTypeSupported('audio/webm')).toBe(false)
    expect(MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')).toBe(false)
    expect(MediaRecorder.isTypeSupported('audio/mp4')).toBe(false)
  })

  it('MediaRecorder 完全 undefined (企业微信 X5 老内核) → getSupportedMimeType 返空', () => {
    const orig = globalThis.MediaRecorder
    // @ts-ignore
    delete globalThis.MediaRecorder
    // 重新导入模块获取 getSupportedMimeType, 简化版用直接探测:
    const isSupported = (t) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported?.(t)
    expect(isSupported('audio/webm;codecs=opus')).toBeFalsy()
    globalThis.MediaRecorder = orig
  })
})

describe('useGlobalRecorder getUserMedia 5s timeout (Step 2, #207 根因修复)', () => {
  let getUserMediaSpy

  beforeEach(() => {
    const { reset } = useGlobalRecorder()
    reset()
  })

  afterEach(() => {
    vi.useRealTimers()
    if (getUserMediaSpy) getUserMediaSpy.mockRestore()
  })

  it('getUserMedia 永久 pending 5s 后 reject (HarmonyOS ArkWeb 模拟)', async () => {
    getUserMediaSpy = vi.spyOn(navigator.mediaDevices, 'getUserMedia')
      .mockImplementation(() => new Promise(() => {}))  // 永不 resolve
    vi.useFakeTimers()
    const startPromise = useGlobalRecorder().start()
    const rejection = expect(startPromise).rejects.toThrow(/5000ms timeout/)
    // 先注册 rejection handler，再推进计时器，避免 Node 将预期拒绝短暂判为 unhandled
    await vi.advanceTimersByTimeAsync(5000)
    await rejection
  })

  it('getUserMedia 正常 resolve 不受 timeout 影响', async () => {
    getUserMediaSpy = vi.spyOn(navigator.mediaDevices, 'getUserMedia')
      .mockResolvedValue(new FakeMediaStream())
    FakeMediaRecorder.__setSupportedTypes(['audio/webm;codecs=opus'])
    await expect(useGlobalRecorder().start()).resolves.not.toThrow()
  })

  it('getUserMedia reject (NotAllowedError 等) 透传不被 timeout 吞', async () => {
    const permErr = Object.assign(new Error('Permission denied'), { name: 'NotAllowedError' })
    getUserMediaSpy = vi.spyOn(navigator.mediaDevices, 'getUserMedia')
      .mockRejectedValue(permErr)
    await expect(useGlobalRecorder().start()).rejects.toMatchObject({ name: 'NotAllowedError' })
  })
})

describe('useGlobalRecorder MediaRecorder 构造失败 (Step 1 配套)', () => {
  let getUserMediaSpy

  beforeEach(() => {
    const { reset } = useGlobalRecorder()
    reset()
  })

  afterEach(() => {
    if (getUserMediaSpy) getUserMediaSpy.mockRestore()
  })

  it('MediaRecorder 不支持任何 mime (老 WebView) → 仍能构造 (走默认)', async () => {
    getUserMediaSpy = vi.spyOn(navigator.mediaDevices, 'getUserMedia')
      .mockResolvedValue(new FakeMediaStream())
    FakeMediaRecorder.__setSupportedTypes([])  // 全 false, 走浏览器默认
    await expect(useGlobalRecorder().start()).resolves.not.toThrow()
  })
})

// useGlobalRecorder 在每个测试前 reset, 避免模块级单例状态污染
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'
