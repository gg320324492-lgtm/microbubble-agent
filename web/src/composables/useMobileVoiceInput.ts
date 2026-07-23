/**
 * useMobileVoiceInput.ts — 移动端语音输入（录音 + ASR 转写 + 插入 textarea）
 *
 * W68 路线 G-1: Mobile 语音输入
 *
 * 设计：
 * - 复用 asrRecognize (useChatStream 暴露) → 走 /api/v1/voice/asr 端点
 * - MediaRecorder API 探测链 webm;opus → webm → ogg;opus → mp4 (iOS Safari)
 *   (与 useGlobalRecorder.js #207 修复保持一致, 2026-07-16 教训)
 * - 录音状态 idle | recording | processing | error
 * - iOS Safari PWA 后台 audio 兼容: 录音 active 时保持 AudioContext alive
 * - 触觉反馈: tap() on start, success() on done, warning() on cancel
 * - 视觉反馈: barHeights (5 根柱) 模拟录音波浪, ref 暴露给组件
 * - 上滑超阈值取消: 监听 touchmove dy < -threshold → cancel()
 * - getUserMedia 5s timeout 兜底 (复用 #207 修复)
 *
 * 与 MobileChatView 既有 onVoiceStart / onVoiceEnd 区别：
 * - 老路径: 拿 blob 直接 asrRecognize + 立即 sendMessage
 * - 新路径 (G-1): 拿 blob → asr → **仅插入 inputText** (不发), 让用户编辑后手动发送
 *   理由: 误触发防护 (避免长按误发), 用户可继续编辑修正识别错误
 *   兜底: 组件 prop autoSend=true 可切换为自动发送 (v3.1 默认)
 *
 * 输入: component 通过 useMobileVoiceInput() 拿 controls, 监听 state / 调用 start() / stop() / cancel()
 * 输出: 录音 blob / ASR 文本 / 插入 textarea 文本
 *
 * 关键铁律（CLAUDE.md 2026-06-04 升级 + 2026-07-16 #207）:
 * 1. getUserMedia 5s timeout 兜底 (HarmonyOS / X5 不 reject 永久卡死)
 * 2. MediaRecorder MIME 探测链 (iOS Safari / HarmonyOS / 老 WebView)
 * 3. ASR 失败 best-effort: 不阻塞 UI, ElMessage 提示
 * 4. blob < 1KB 客户端拦截 (避免 400 提示用户体验差)
 * 5. 上滑取消: dy < -50px (类似微信), 触觉 warning()
 * 6. mobile long-press 必带 navigator.vibrate(10) (CLAUDE.md 2026-06-27)
 * 7. ts + Vue ref 强类型, props 全部 Pydantic 风格签名
 */

import { ref, computed, readonly } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useHaptic } from '@/composables/chat/useHaptic'

// MIME 探测链（与 useGlobalRecorder.js #207 修复同步, 2026-07-16）
const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4', // iOS Safari 必须
]

// 1KB 客户端拦截 (与 asrRecognize 一致, CLAUDE.md 2026-06-18 教训)
const MIN_AUDIO_SIZE = 1024

// getUserMedia 5s timeout 兜底 (#207 直接根因, 2026-07-16)
const GET_USER_MEDIA_TIMEOUT_MS = 5000

// 上滑取消阈值（类似微信）
const SLIDE_CANCEL_THRESHOLD = 50

// 单次录音最大时长 (60s, 防滥用)
const MAX_RECORDING_MS = 60_000

export type VoiceInputState = 'idle' | 'recording' | 'processing' | 'error' | 'cancelled'

export interface UseMobileVoiceInputOptions {
  /** ASR 后是否自动发送消息 (默认 false, 让用户编辑后手动发) */
  autoSend?: boolean
  /** 取消上滑阈值 (px, 默认 50) */
  slideCancelThreshold?: number
  /** 录音最大时长 (ms, 默认 60s) */
  maxDurationMs?: number
  /** 外部提供的 ASR 识别函数 (默认用 axios 直调 /api/v1/voice/asr) */
  asrFn?: (blob: Blob) => Promise<string | null>
  /** 转写结果插入的回调 (inputText.value = text) */
  onTranscribed?: (text: string) => void
  /** 自动发送回调 (autoSend=true 时触发) */
  onAutoSend?: (text: string) => void
  /** 录音取消回调 (用户上滑取消) */
  onCancelled?: () => void
  /** 录音错误回调 (权限拒绝/ASR 失败) */
  onError?: (err: Error) => void
}

export interface MobileVoiceInputControls {
  /** 录音状态 */
  state: Readonly<import('vue').Ref<VoiceInputState>>
  /** 录音已用时长 (ms) */
  elapsedMs: Readonly<import('vue').Ref<number>>
  /** 录音音量柱 (5 根, 0-100), 用于波浪动画 */
  barHeights: Readonly<import('vue').Ref<number[]>>
  /** 是否正在录音 */
  isRecording: Readonly<import('vue').Ref<boolean>>
  /** 是否正在转写 (上传中) */
  isProcessing: Readonly<import('vue').Ref<boolean>>
  /** 错误信息 (null = 无错) */
  errorMsg: Readonly<import('vue'). Ref<string | null>>
  /** 当前 MIME (探测结果) */
  activeMime: Readonly<import('vue').Ref<string>>
  /** 开始录音 (touchstart) */
  start: () => Promise<boolean>
  /** 停止录音并转写 (touchend, 松开发送) */
  stop: () => Promise<void>
  /** 取消录音 (上滑超阈值, 不转写) */
  cancel: () => void
  /** touchmove 处理器, 组件内 @touchmove.passive="onTouchMove" */
  onTouchMove: (e: TouchEvent) => void
  /** 清理资源 (unmount 时调) */
  dispose: () => void
}

/**
 * getUserMedia 5s timeout 兜底
 * @param timeoutMs
 */
function getUserMediaWithTimeout(timeoutMs: number): Promise<MediaStream> {
  const getUserMediaPromise = navigator.mediaDevices.getUserMedia({ audio: true })
  const timeoutPromise = new Promise<MediaStream>((_, __reject) =>
    setTimeout(
      () =>
        __reject(
          new Error(
            `getUserMedia ${timeoutMs}ms timeout (浏览器可能不支持, 如 HarmonyOS ArkWeb / 企业微信 X5)`
          )
        ),
      timeoutMs
    )
  )
  return Promise.race([getUserMediaPromise, timeoutPromise])
}

/**
 * 探测浏览器支持的 MediaRecorder MIME
 * @returns 支持的 MIME 字符串, 空字符串表示走浏览器默认
 */
function getSupportedMimeType(): string {
  if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) {
    return ''
  }
  for (const m of MIME_CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(m)) return m
    } catch {
      continue
    }
  }
  return ''
}

/**
 * 默认 ASR 识别函数 (走 /api/v1/voice/asr)
 * 与 useChatStream.asrRecognize 行为一致, 客户端先 < 1KB 拦截
 */
async function defaultAsrFn(blob: Blob): Promise<string | null> {
  if (!blob || blob.size === 0) {
    ElMessage.warning('录音为空，请重试')
    return null
  }
  if (blob.size < MIN_AUDIO_SIZE) {
    ElMessage.warning('录音太短（不到 1 秒），请长按说话')
    return null
  }
  try {
    const fd = new FormData()
    fd.append('audio', blob, 'voice.webm')
    const r = await axios.post('/api/v1/voice/asr', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { language: 'zh' },
    })
    const text = r.data?.text?.trim()
    if (text) return text
    ElMessage.warning('未能识别语音，请重试')
    return null
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'ASR 识别失败')
    return null
  }
}

export function useMobileVoiceInput(
  options: UseMobileVoiceInputOptions = {}
): MobileVoiceInputControls {
  const {
    autoSend = false,
    slideCancelThreshold = SLIDE_CANCEL_THRESHOLD,
    maxDurationMs = MAX_RECORDING_MS,
    asrFn = defaultAsrFn,
    onTranscribed,
    onAutoSend,
    onCancelled,
    onError,
  } = options

  const haptic = useHaptic()

  // ===== 响应式状态 =====
  const state = ref<VoiceInputState>('idle')
  const elapsedMs = ref(0)
  const barHeights = ref<number[]>([4, 4, 4, 4, 4])
  const errorMsg = ref<string | null>(null)
  const activeMime = ref<string>('')

  // ===== 内部状态（跨 start/stop 持久） =====
  let mediaStream: MediaStream | null = null
  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []
  let startEpoch: number = 0
  let elapsedTimer: number | null = null
  let maxDurationTimer: number | null = null
  let analyser: AnalyserNode | null = null
  let audioContext: AudioContext | null = null
  let dataArray: Uint8Array | null = null
  let animationFrame: number | null = null
  let startY = 0 // touchstart 时手指 Y 坐标

  // ===== 派生 =====
  const isRecording = computed(() => state.value === 'recording')
  const isProcessing = computed(() => state.value === 'processing')

  // ===== 计时器 =====
  function _startElapsedTimer() {
    if (elapsedTimer) return
    elapsedTimer = window.setInterval(() => {
      elapsedMs.value = Date.now() - startEpoch
    }, 100)
  }
  function _stopElapsedTimer() {
    if (elapsedTimer) {
      clearInterval(elapsedTimer)
      elapsedTimer = null
    }
  }

  // ===== 音量柱动画 (requestAnimationFrame + AnalyserNode) =====
  function _startBarAnimation() {
    if (!analyser || !dataArray) return
    const tick = () => {
      if (state.value !== 'recording') return
      analyser!.getByteFrequencyData(dataArray!)
      // 5 根柱: 取 5 段频率 bin 的均值
      const binsPerBar = Math.floor(dataArray!.length / 5)
      const heights: number[] = []
      for (let i = 0; i < 5; i++) {
        let sum = 0
        for (let j = 0; j < binsPerBar; j++) {
          sum += dataArray![i * binsPerBar + j]
        }
        const avg = sum / binsPerBar // 0-255
        // 映射到 4-40px 视觉范围
        heights.push(Math.max(4, Math.round((avg / 255) * 40)))
      }
      barHeights.value = heights
      animationFrame = requestAnimationFrame(tick)
    }
    animationFrame = requestAnimationFrame(tick)
  }
  function _stopBarAnimation() {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame)
      animationFrame = null
    }
    barHeights.value = [4, 4, 4, 4, 4]
  }

  // ===== 释放资源 =====
  function _releaseStream() {
    if (mediaStream) {
      try {
        mediaStream.getTracks().forEach((t) => t.stop())
      } catch {
        // ignore
      }
      mediaStream = null
    }
    if (audioContext && audioContext.state !== 'closed') {
      try {
        audioContext.close()
      } catch {
        // ignore
      }
    }
    audioContext = null
    analyser = null
    dataArray = null
  }

  function _resetState() {
    _stopElapsedTimer()
    _stopBarAnimation()
    if (maxDurationTimer) {
      clearTimeout(maxDurationTimer)
      maxDurationTimer = null
    }
    audioChunks = []
    elapsedMs.value = 0
    startEpoch = 0
  }

  // ===== 公开方法 =====
  async function start(): Promise<boolean> {
    if (state.value === 'recording' || state.value === 'processing') {
      return false // 已在录音/处理中, 拒绝重叠
    }
    state.value = 'recording'
    errorMsg.value = null
    audioChunks = []
    elapsedMs.value = 0
    startEpoch = Date.now()

    // 触觉反馈 (CLAUDE.md 2026-06-27 教训: mobile long-press 必带 vibrate)
    haptic.tap()

    try {
      mediaStream = await getUserMediaWithTimeout(GET_USER_MEDIA_TIMEOUT_MS)

      // AudioContext (iOS Safari PWA 后台 audio 兼容, 必须在 user gesture 内创建)
      try {
        audioContext = new (window.AudioContext ||
          (window as any).webkitAudioContext)()
        const source = audioContext.createMediaStreamSource(mediaStream)
        analyser = audioContext.createAnalyser()
        analyser.fftSize = 256
        source.connect(analyser)
        dataArray = new Uint8Array(analyser.frequencyBinCount)
      } catch {
        // AudioContext 创建失败不阻塞录音 (仅损失波浪动画)
        analyser = null
        dataArray = null
      }

      // MediaRecorder 探测链 (#207 修复, 2026-07-16)
      const supportedMime = getSupportedMimeType()
      activeMime.value = supportedMime
      mediaRecorder = supportedMime
        ? new MediaRecorder(mediaStream, { mimeType: supportedMime })
        : new MediaRecorder(mediaStream)

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data)
        }
      }
      mediaRecorder.onerror = (e: any) => {
        // MediaRecorder 运行时错误 (浏览器内部), best-effort 转 cancelled
        const msg = e?.error?.message || '录音失败'
        errorMsg.value = msg
        state.value = 'error'
        onError?.(new Error(msg))
        _releaseStream()
      }
      mediaRecorder.onstop = async () => {
        // _handleStop 内会处理 ASR
        await _handleStop(false)
      }

      mediaRecorder.start(100) // 100ms timeslice 边录边攒 chunk

      // 启动计时
      _startElapsedTimer()
      _startBarAnimation()

      // 最大时长兜底
      maxDurationTimer = window.setTimeout(() => {
        if (state.value === 'recording') {
          // 超时自动 stop (不取消, 正常转写)
          if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop()
          }
        }
      }, maxDurationMs)

      return true
    } catch (e: any) {
      // getUserMedia 失败 (权限拒绝 / 5s timeout / 设备占用)
      const msg = e?.message || '麦克风权限被拒绝或不可用'
      errorMsg.value = msg
      state.value = 'error'
      _releaseStream()
      _resetState()
      ElMessage.error(msg)
      onError?.(e instanceof Error ? e : new Error(msg))
      return false
    }
  }

  async function _handleStop(_cancelled: boolean): Promise<void> {
    if (state.value !== 'recording') return
    state.value = 'processing'
    _stopElapsedTimer()
    _stopBarAnimation()
    if (maxDurationTimer) {
      clearTimeout(maxDurationTimer)
      maxDurationTimer = null
    }

    const blob = new Blob(audioChunks, {
      type: activeMime.value || 'audio/webm',
    })
    _releaseStream()

    try {
      const text = await asrFn(blob)
      if (text) {
        state.value = 'idle'
        errorMsg.value = null
        onTranscribed?.(text)
        if (autoSend) {
          onAutoSend?.(text)
        }
        haptic.success()
      } else {
        // ASR 失败 / 空文本: 提示已在 asrFn 内 ElMessage 完成
        state.value = 'idle'
        haptic.warning()
      }
    } catch (e: any) {
      const msg = e?.message || 'ASR 识别异常'
      errorMsg.value = msg
      state.value = 'error'
      ElMessage.error(msg)
      onError?.(e instanceof Error ? e : new Error(msg))
    } finally {
      _resetState()
    }
  }

  function stop(): Promise<void> {
    if (state.value !== 'recording' || !mediaRecorder) {
      return Promise.resolve()
    }
    // MediaRecorder.stop() 触发 onstop → _handleStop
    if (mediaRecorder.state === 'recording') {
      mediaRecorder.stop()
    }
    return Promise.resolve()
  }

  function cancel(): void {
    if (state.value !== 'recording') return
    state.value = 'cancelled'
    _stopElapsedTimer()
    _stopBarAnimation()
    if (maxDurationTimer) {
      clearTimeout(maxDurationTimer)
      maxDurationTimer = null
    }
    // 注意: 这里**不**调 mediaRecorder.stop() (避免触发 onstop → ASR),
    // 直接 reset + release。MediaRecorder 不 stop 也能 GC (stream 释放后无引用)
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      // 强制 stop 丢弃数据: 用 pause() + 替换 chunks
      try {
        mediaRecorder.pause()
      } catch {
        // ignore
      }
    }
    audioChunks = []
    _releaseStream()
    _resetState()
    haptic.warning()
    onCancelled?.()
    // 延迟 1s 回到 idle, 让用户看到 "已取消" 状态
    setTimeout(() => {
      if (state.value === 'cancelled') {
        state.value = 'idle'
        errorMsg.value = null
      }
    }, 1000)
  }

  /**
   * touchmove 处理器 (组件内 @touchmove.passive="onTouchMove")
   * 上滑 dy < -threshold 触发取消 (类似微信)
   */
  function onTouchMove(e: TouchEvent): void {
    if (state.value !== 'recording') return
    const touch = e.touches[0]
    if (!touch) return
    // startY 在 touchstart 中设置 (但 touchstart 是组件 onTouchStart 调, 这里需读)
    // 我们用 ref 暂存: 实际在 start() 时记录 startY
    if (startY === 0) {
      startY = touch.clientY
      return
    }
    const dy = touch.clientY - startY
    if (dy < -slideCancelThreshold) {
      // 上滑超阈值 → 取消
      cancel()
    }
  }

  // 暴露 startY 给组件 (touchstart 时设置)
  // 注: 简单做法是组件 onTouchStart 直接 startY = e.touches[0].clientY
  // 这里我们提供一个 setStartY 帮助方法
  function _setStartY(y: number) {
    startY = y
  }
  // 挂载到 controls 上
  ;(onTouchMove as any)._setStartY = _setStartY

  function dispose(): void {
    cancel()
    _releaseStream()
    _resetState()
    errorMsg.value = null
    state.value = 'idle'
  }

  return {
    state: readonly(state) as any,
    elapsedMs: readonly(elapsedMs) as any,
    barHeights: readonly(barHeights) as any,
    isRecording,
    isProcessing,
    errorMsg: readonly(errorMsg) as any,
    activeMime: readonly(activeMime) as any,
    start,
    stop,
    cancel,
    onTouchMove,
    dispose,
  }
}

export default useMobileVoiceInput
