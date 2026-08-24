// Device Stream Manager — 设备数据流管理器。

import type { SensorReading } from '../../shared/device/device-schema'
import type { DeviceAdapter } from '../../shared/device/device-adapter-schema'

export type StreamEventType = 'reading' | 'buffer-flush' | 'error' | 'subscribed' | 'unsubscribed'
export const STREAM_EVENT_TYPES: readonly StreamEventType[] = Object.freeze([
  'reading', 'buffer-flush', 'error', 'subscribed', 'unsubscribed'
])

export interface StreamEvent {
  type: StreamEventType
  deviceId: string
  payload: Record<string, unknown>
  timestamp: number
}

export type StreamListener = (event: StreamEvent) => void

export interface StreamSubscription {
  deviceId: string
  metric: string
  listener: StreamListener
}

export class DeviceStreamManager {
  private listeners: Map<string, Set<StreamListener>> = new Map()
  private allListeners: Set<StreamListener> = new Set()
  private buffers: Map<string, SensorReading[]> = new Map()
  private bufferSize: number
  private adapters: Map<string, DeviceAdapter> = new Map()

  constructor(bufferSize = 100) {
    this.bufferSize = bufferSize
  }

  registerAdapter(adapter: DeviceAdapter): void {
    this.adapters.set(adapter.id, adapter)
  }

  unregisterAdapter(deviceId: string): void {
    this.adapters.delete(deviceId)
    this.buffers.delete(deviceId)
  }

  subscribe(deviceId: string, metric: string, listener: StreamListener): () => void {
    const key = `${deviceId}:${metric}`
    let set = this.listeners.get(key)
    if (!set) {
      set = new Set()
      this.listeners.set(key, set)
    }
    set.add(listener)
    this.emit({ type: 'subscribed', deviceId, payload: { metric }, timestamp: Date.now() })
    return () => {
      set!.delete(listener)
      this.emit({ type: 'unsubscribed', deviceId, payload: { metric }, timestamp: Date.now() })
    }
  }

  unsubscribeAll(deviceId: string): number {
    let removed = 0
    for (const [key, set] of this.listeners) {
      if (key.startsWith(`${deviceId}:`)) {
        removed += set.size
        set.clear()
      }
    }
    return removed
  }

  async collectReading(deviceId: string, metric: string): Promise<SensorReading | null> {
    const adapter = this.adapters.get(deviceId)
    if (!adapter) {
      this.emit({ type: 'error', deviceId, payload: { metric, reason: 'adapter not found' }, timestamp: Date.now() })
      return null
    }
    try {
      const reading = await adapter.read(metric)
      if (reading) {
        this.bufferData(reading)
        this.emit({ type: 'reading', deviceId, payload: { metric, reading }, timestamp: Date.now() })
      }
      return reading
    } catch (err) {
      this.emit({ type: 'error', deviceId, payload: { metric, reason: String(err) }, timestamp: Date.now() })
      return null
    }
  }

  bufferData(reading: SensorReading): void {
    let buf = this.buffers.get(reading.deviceId)
    if (!buf) {
      buf = []
      this.buffers.set(reading.deviceId, buf)
    }
    buf.push(reading)
    if (buf.length > this.bufferSize) {
      buf.splice(0, buf.length - this.bufferSize)
    }
  }

  flush(deviceId: string): SensorReading[] {
    const buf = this.buffers.get(deviceId) ?? []
    this.buffers.set(deviceId, [])
    this.emit({ type: 'buffer-flush', deviceId, payload: { count: buf.length }, timestamp: Date.now() })
    return [...buf]
  }

  getBuffer(deviceId: string): SensorReading[] {
    return [...(this.buffers.get(deviceId) ?? [])]
  }

  getBufferSize(deviceId: string): number {
    return (this.buffers.get(deviceId) ?? []).length
  }

  emit(event: StreamEvent): void {
    const set = this.listeners.get(`${event.deviceId}:${String(event.payload.metric ?? '')}`)
    if (set) {
      for (const fn of [...set]) {
        try { fn(event) } catch { /* listener errors must not break emission */ }
      }
    }
    for (const fn of [...this.allListeners]) {
      try { fn(event) } catch { /* listener errors must not break emission */ }
    }
  }

  subscribeAll(listener: StreamListener): () => void {
    this.allListeners.add(listener)
    return () => { this.allListeners.delete(listener) }
  }

  getAdapters(): DeviceAdapter[] { return Array.from(this.adapters.values()) }
  adapterCount(): number { return this.adapters.size }
  listenerCount(): number {
    let n = 0
    for (const s of this.listeners.values()) n += s.size
    return n
  }
  clear(): void { this.listeners.clear(); this.allListeners.clear(); this.buffers.clear(); this.adapters.clear() }
}