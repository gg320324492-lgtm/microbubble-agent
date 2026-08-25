// Mock Modbus Driver — Phase 8-M1-F
// 模拟 Modbus TCP 设备: 接 register 名称映射到内部 16-bit 寄存器,
// 写命令按 (register, value) 缓存并 ACK.

import type { CommandAck, DeviceConfig, TelemetrySample } from './device-types'
import type { DeviceDriver, Unsubscribe } from './device-driver'

const REGISTERS: ReadonlyArray<{ register: string; unit: string; nominal: number }> = [
  { register: 'O3_concentration', unit: 'mg/L', nominal: 4.5 },
  { register: 'DO', unit: 'mg/L', nominal: 7.2 },
  { register: 'ORP', unit: 'mV', nominal: 320 },
  { register: 'pH', unit: '', nominal: 7.0 },
  { register: 'temperature', unit: '°C', nominal: 25 },
  { register: 'pressure', unit: 'kPa', nominal: 101 },
  { register: 'flow', unit: 'm³/h', nominal: 1.2 },
  { register: 'power', unit: 'kW', nominal: 0.85 }
]

export class ModbusMockDriver implements DeviceDriver {
  readonly driverId = 'modbus-mock'
  private connected = false
  private values = new Map<string, number>()
  private pollers: ReturnType<typeof setInterval>[] = []
  private subs = new Set<(s: TelemetrySample) => void>()

  async connect(config: DeviceConfig): Promise<void> {
    for (const r of REGISTERS) this.values.set(r.register, r.nominal)
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
    if (!this.connected) return null
    return this.values.get(register) ?? null
  }

  async write(register: string, value: number, commandId: string): Promise<CommandAck> {
    if (!this.connected) {
      return { commandId, status: 'rejected', message: 'driver not connected', timestamp: Date.now() }
    }
    this.values.set(register, value)
    return { commandId, status: 'ok', appliedValue: value, message: 'modbus 写寄存器成功', timestamp: Date.now() }
  }

  subscribe(callback: (sample: TelemetrySample) => void): Unsubscribe {
    this.subs.add(callback)
    return () => this.subs.delete(callback)
  }

  private tick(config: DeviceConfig): void {
    const r = REGISTERS[Math.floor(Math.random() * REGISTERS.length)]
    if (!r) return
    const noise = (Math.random() - 0.5) * r.nominal * 0.1
    const newValue = r.nominal + noise
    this.values.set(r.register, newValue)
    const sample: TelemetrySample = {
      deviceId: config.deviceId,
      deviceType: config.deviceType,
      metric: r.register,
      value: Number(newValue.toFixed(3)),
      unit: r.unit,
      timestamp: Date.now(),
      quality: 'good'
    }
    for (const cb of this.subs) cb(sample)
  }
}
