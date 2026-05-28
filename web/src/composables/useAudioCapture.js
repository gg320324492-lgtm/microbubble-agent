/**
 * AudioWorklet 音频采集 — 低延迟、持续流式输出
 *
 * 使用 AudioWorklet 替代 ScriptProcessor，在独立线程中重采样到 16kHz。
 */

// AudioWorklet 处理器代码（作为 Blob URL 注入）
const workletCode = `
class ResampleProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.targetRate = 16000
    this._buffer = []
  }

  process(inputs, outputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true

    const channel = input[0]
    const inputRate = sampleRate
    const ratio = inputRate / this.targetRate

    // 简单线性重采样（降采样到 16kHz）
    const outputLength = Math.floor(channel.length / ratio)
    const output = new Float32Array(outputLength)
    for (let i = 0; i < outputLength; i++) {
      const srcIdx = i * ratio
      const srcIdxFloor = Math.floor(srcIdx)
      const frac = srcIdx - srcIdxFloor
      const a = channel[srcIdxFloor] || 0
      const b = channel[Math.min(srcIdxFloor + 1, channel.length - 1)] || 0
      output[i] = a + (b - a) * frac
    }

    this.port.postMessage({ type: 'audio', data: output.buffer }, [output.buffer])
    return true
  }
}
registerProcessor('resample-processor', ResampleProcessor)
`

let workletBlobUrl = null

export function useAudioCapture() {
  let audioContext = null
  let mediaStream = null
  let workletNode = null
  let onAudioData = null

  function getWorkletUrl() {
    if (!workletBlobUrl) {
      const blob = new Blob([workletCode], { type: 'application/javascript' })
      workletBlobUrl = URL.createObjectURL(blob)
    }
    return workletBlobUrl
  }

  async function start(onData) {
    onAudioData = onData

    // 获取麦克风
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: { ideal: 16000 },
        channelCount: { ideal: 1 },
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: false,
      },
    })

    // 创建 AudioContext
    audioContext = new AudioContext({ sampleRate: 16000 })
    const source = audioContext.createMediaStreamSource(mediaStream)

    // 加载 AudioWorklet
    await audioContext.audioWorklet.addModule(getWorkletUrl())
    workletNode = new AudioWorkletNode(audioContext, 'resample-processor')

    workletNode.port.onmessage = (event) => {
      if (event.data.type === 'audio' && onAudioData) {
        onAudioData(new Float32Array(event.data.data))
      }
    }

    source.connect(workletNode)
    // 不连接到 destination（不播放自己的声音避免回音）
  }

  function stop() {
    if (workletNode) {
      workletNode.port.onmessage = null
      workletNode.disconnect()
      workletNode = null
    }
    if (audioContext) {
      audioContext.close()
      audioContext = null
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop())
      mediaStream = null
    }
    onAudioData = null
  }

  function isActive() {
    return audioContext != null && audioContext.state === 'running'
  }

  return { start, stop, isActive }
}
