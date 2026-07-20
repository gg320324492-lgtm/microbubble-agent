/**
 * jsdom MediaRecorder / MediaStream / AudioContext polyfill
 * 2026-07-16: 用于 useGlobalRecorder.js 单测 (#207 完整流程修复)
 *
 * 浏览器原生 API 在 jsdom 环境下不存在, 但 useGlobalRecorder.start() 启动时会调
 * navigator.mediaDevices.getUserMedia / new MediaRecorder / new AudioContext。
 * 注入 polyfill 后, 测试可通过 vi.spyOn / __setSupportedTypes 模拟各种浏览器行为。
 */

export class FakeMediaRecorder extends EventTarget {
  constructor(stream, options = {}) {
    super()
    this.stream = stream
    this.mimeType = options.mimeType || ''
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
    this.onerror = null
    this.__interval = null
    this.__chunks = []
  }
  static isTypeSupported(type) {
    return FakeMediaRecorder.__supportedTypes?.includes(type) ?? false
  }
  static __setSupportedTypes(types) {
    FakeMediaRecorder.__supportedTypes = types
  }
  start(timeslice = 1000) {
    this.state = 'recording'
    this.__interval = setInterval(() => {
      if (this.state !== 'recording') return
      const fakeBlob = new Blob([new Uint8Array(1024)], { type: this.mimeType })
      this.__chunks.push(fakeBlob)
      this.ondataavailable?.({ data: fakeBlob, size: fakeBlob.size })
    }, timeslice)
  }
  stop() {
    this.state = 'inactive'
    clearInterval(this.__interval)
    this.onstop?.()
  }
  pause() {
    this.state = 'paused'
  }
  resume() {
    this.state = 'recording'
  }
}

export class FakeMediaStream {
  constructor() {
    this.__tracks = [{ stop: () => {} }]
  }
  getTracks() {
    return this.__tracks
  }
  getAudioTracks() {
    return this.__tracks
  }
}

export class FakeAudioContext {
  constructor() {
    this.state = 'running'
    this.destination = {}
  }
  createMediaStreamSource() {
    return { connect: () => {} }
  }
  createAnalyser() {
    return {
      fftSize: 256,
      frequencyBinCount: 128,
      getByteFrequencyData: (arr) => { arr.fill(50) },
      connect: () => {},
    }
  }
  close() {
    this.state = 'closed'
  }
}
