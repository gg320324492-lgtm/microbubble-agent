// Mock MQTT / OPC-UA / Serial Drivers — Phase 8-M1-F
// 3 个 mock 驱动共用同一 baseline: 接受 connect, 周期性 sin 扰动, 写命令直接 set value.

import type { CommandAck, DeviceConfig, TelemetrySample } from './device-types'
import type { DeviceDriver, Unsubscribe } from './device-driver'

class BaseMockDriver implements DeviceDriver {
  readonly driverId: string
  private connected = false
  private values = new Map<string, number>()
  private pollers: ReturnType<typeof setInterval>[] = []
  private subs = new Set<(s: TelemetrySample) => void>()
  private readonly metrics: ReadonlyArray<{ register: string; unit: string; nominal: number }>

  constructor(driverId: string, metrics: ReadonlyArray<{ register: string; unit: string; nominal: number }>) {
    this.driverId = driverId
    this.metrics = metrics
  }

  async connect(config: DeviceConfig): Promise<void> {
    for (const m of this.metrics) this.values.set(m.register, m.nominal)
    this.connected = true
    const interval = config.pollIntervalMs ?? 1000
    const timer = setInterval(() => this.tick(config), interval)
    this.pollers.push(timer)
  }

  async disconnect(): Promise<void> {
    for (const t of this.pollers) clearInterval(t)
    this.pollers = []
    this.connected = false
    this.subs.clear()
  }

  isConnected(): boolean { return this.connected }

  async read(register: string): Promise<number | null> {
    return this.connected ? this.values.get(register) ?? null : null
  }

  async write(register: string, value: number, commandId: string): Promise<CommandAck> {
    if (!this.connected) return { commandId, status: 'rejected', message: 'driver not connected', timestamp: Date.now() }
    this.values.set(register, value)
    return { commandId, status: 'ok', appliedValue: value, message: `${this.driverId} 写成功`, timestamp: Date.now() }
  }

  subscribe(callback: (sample: TelemetrySample) => void): Unsubscribe {
    this.subs.add(callback)
    return () => this.subs.delete(callback)
  }

  private tick(config: DeviceConfig): void {
    const m = this.metrics[Math.floor(Math.random() * this.metrics.length)]
    if (!m) return
    const noise = (Math.random() - 0.5) * m.nominal * 0.1
    const newValue = m.nominal + noise
    this.values.set(m.register, newValue)
    for (const cb of this.subs) {
      cb({
        deviceId: config.deviceId,
        deviceType: config.deviceType,
        metric: m.register,
        value: Number(newValue.toFixed(3)),
        unit: m.unit,
        timestamp: Date.now(),
        quality: 'good'
      })
    }
  }
}

export class MqttMockDriver extends BaseMockDriver {
  constructor() {
    super('mqtt-mock', [
      { register: 'pH', unit: '', nominal: 7.0 },
      { register: 'ORP', unit: 'mV', nominal: 320 },
      { register: 'temperature', unit: '°C', nominal: 25 }
    ])
  }
}

export class OpcUaMockDriver extends BaseMockDriver {
  constructor() {
    super('opcua-mock', [
      { register: 'flow', unit: 'm³/h', nominal: 1.2 },
      { register: 'pressure', unit: 'kPa', nominal: 101 }
    ])
  }
}

export class SerialMockDriver extends BaseMockDriver {
  constructor() {
    super('serial-mock', [
      { register: 'power', unit: 'kW', nominal: 0.85 }
    ])
  }
}
