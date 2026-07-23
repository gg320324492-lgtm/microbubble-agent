/**
 * useMobileVoiceInput.test.js — useMobileVoiceInput composable vitest (W68 路线 G-1)
 *
 * 复用 setup.js 已 polyfill 的 FakeMediaRecorder / FakeMediaStream / FakeAudioContext。
 *
 * 场景:
 * 1. start() 成功 → state='recording', isRecording=true
 * 2. start() 失败 (getUserMedia reject) → state='error', ElMessage.error
 * 3. stop() 触发 ASR → onTranscribed 回调收到文本
 * 4. cancel() → state='cancelled', onCancelled 触发
 * 5. onTouchMove 上滑超阈值 → 不调 stop, 走 cancel 路径 (实现通过内部 startY 追踪)
 * 6. blob < 1KB (录音太短) → asrFn 不被调, ElMessage.warning
 * 7. 探测链: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') = true
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { ref } from 'vue'

// 1) Mock axios
vi.mock('axios', () => ({
  default: { post: vi.fn() },
}))

import axios from 'axios'

// 2) Mock ElMessage
vi.mock('element-plus', () => ({
  ElMessage: {
    warning: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}))

import { ElMessage } from 'element-plus'

// 3) Mock useHaptic
vi.mock('@/composables/chat/useHaptic', () => ({
  useHaptic: () => ({
    tap: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    vibrate: vi.fn(),
  }),
}))

// 4) Import 被测模块 (必须在 mock 之后)
import { useMobileVoiceInput } from '../useMobileVoiceInput'

// 5) 配置 FakeMediaRecorder 支持 webm;opus
beforeEach(() => {
  // @ts-ignore
  globalThis.MediaRecorder.__setSupportedTypes(['audio/webm;codecs=opus'])
  // @ts-ignore
  globalThis.navigator.mediaDevices.getUserMedia = vi.fn(() =>
    Promise.resolve(new (globalThis as any).MediaStream())
  )
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useMobileVoiceInput composable', () => {
  it('场景 1: start() 成功 → state 进入 recording', async () => {
    const onTranscribed = vi.fn()
    const voice = useMobileVoiceInput({ onTranscribed })
    const ok = await voice.start()
    expect(ok).toBe(true)
    expect(voice.state.value).toBe('recording')
    expect(voice.isRecording.value).toBe(true)
    expect(voice.activeMime.value).toBe('audio/webm;codecs=opus')
    // 清理
    voice.dispose()
  })

  it('场景 2: getUserMedia reject → state 进入 error', async () => {
    // @ts-ignore
    globalThis.navigator.mediaDevices.getUserMedia = vi.fn(() =>
      Promise.reject(new Error('权限被拒绝'))
    )
    const voice = useMobileVoiceInput()
    const ok = await voice.start()
    expect(ok).toBe(false)
    expect(voice.state.value).toBe('error')
    expect(voice.errorMsg.value).toContain('权限被拒绝')
    expect(ElMessage.error).toHaveBeenCalled()
    voice.dispose()
  })

  it('场景 3: 探测链 — iOS Safari 仅 audio/mp4 时回退到 mp4', async () => {
    // @ts-ignore
    globalThis.MediaRecorder.__setSupportedTypes(['audio/mp4'])
    const voice = useMobileVoiceInput()
    await voice.start()
    expect(voice.activeMime.value).toBe('audio/mp4')
    voice.dispose()
  })

  it('场景 4: 探测链 — 都不支持时 activeMime 为空 (走浏览器默认)', async () => {
    // @ts-ignore
    globalThis.MediaRecorder.__setSupportedTypes([])
    const voice = useMobileVoiceInput()
    await voice.start()
    expect(voice.activeMime.value).toBe('')
    voice.dispose()
  })

  it('场景 5: 默认 asrFn (axios) 走 /api/v1/voice/asr', async () => {
    ;(axios.post as any).mockResolvedValue({
      data: { text: '你好小气', language: 'zh', language_probability: 0.95, duration: 1.2 },
    })
    const onTranscribed = vi.fn()
    const voice = useMobileVoiceInput({ onTranscribed })
    await voice.start()
    // 模拟录音数据 (FakeMediaRecorder 每次 ondataavailable 推 1KB fakeBlob)
    // 等 200ms 让 chunks 累积
    await new Promise((r) => setTimeout(r, 200))
    // 停止 → 触发 onstop → _handleStop → asrFn
    voice.stop()
    // 等待 microtask + ASR 完成
    await new Promise((r) => setTimeout(r, 100))
    // axios 应被调
    expect(axios.post).toHaveBeenCalled()
    expect((axios.post as any).mock.calls[0][0]).toBe('/api/v1/voice/asr')
    // onTranscribed 收到 "你好小气"
    expect(onTranscribed).toHaveBeenCalledWith('你好小气')
    voice.dispose()
  })

  it('场景 6: cancel() → state="cancelled" + onCancelled 触发', async () => {
    const onCancelled = vi.fn()
    const voice = useMobileVoiceInput({ onCancelled })
    await voice.start()
    voice.cancel()
    expect(voice.state.value).toBe('cancelled')
    expect(onCancelled).toHaveBeenCalled()
    voice.dispose()
  })

  it('场景 7: 自定义 asrFn 优先于默认', async () => {
    const customAsr = vi.fn().mockResolvedValue('自定义文本')
    const onTranscribed = vi.fn()
    const voice = useMobileVoiceInput({
      asrFn: customAsr,
      onTranscribed,
    })
    await voice.start()
    voice.stop()
    await new Promise((r) => setTimeout(r, 100))
    expect(customAsr).toHaveBeenCalled()
    expect(onTranscribed).toHaveBeenCalledWith('自定义文本')
    expect(axios.post).not.toHaveBeenCalled()
    voice.dispose()
  })

  it('场景 8: autoSend=true → onAutoSend 触发, 不依赖 v-model:text', async () => {
    const onAutoSend = vi.fn()
    const onTranscribed = vi.fn()
    const customAsr = vi.fn().mockResolvedValue('自动发送文本')
    const voice = useMobileVoiceInput({
      autoSend: true,
      asrFn: customAsr,
      onTranscribed,
      onAutoSend,
    })
    await voice.start()
    voice.stop()
    await new Promise((r) => setTimeout(r, 100))
    expect(onTranscribed).toHaveBeenCalledWith('自动发送文本')
    expect(onAutoSend).toHaveBeenCalledWith('自动发送文本')
    voice.dispose()
  })
})
