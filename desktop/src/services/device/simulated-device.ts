// Simulated Device — 本地确定性设备模拟器。

import type { ScientificDevice, SensorReading, DeviceParameter, DeviceType, DeviceStatus } from '../../shared/device/device-schema'
import type { DeviceAdapter, AdapterHealth } from '../../shared/device/device-adapter-schema'

/**
 * 基于 name 的确定性伪随机数生成器 (Mulberry32 简化版)。
 * 用于生成可重复的"传感器读数"。
 */
export function seededRandom(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6D2B79F5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function hashSeed(name: string): number {
  let h = 2166136261
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export interface SimulatorOptions {
  seed?: number
  protocol?: string
  drift?: number
  noise?: number
}

export class SimulatedDevice implements DeviceAdapter {
  readonly id: string
  readonly type: DeviceType
  private _name: string
  private _protocol: string
  private _status: DeviceStatus = 'offline'
  private _parameters: DeviceParameter[]
  private _seed: number
  private _drift: number
  private _noise: number
  private _lastSeen = 0
  private _createdAt = 0
  private _uptimeStart = 0
  private _reads = 0
  private _writes = 0
  private _errors = 0
  private _t: number = 0

  constructor(name: string, type: DeviceType, parameters: DeviceParameter[], options: SimulatorOptions = {}) {
    this.id = `dev-${name}-${Date.now()}`
    this._name = name
    this.type = type
    this._protocol = options.protocol ?? 'sim://local'
    this._parameters = parameters.map((p) => ({ ...p }))
    this._seed = options.seed ?? hashSeed(name)
    this._drift = options.drift ?? 0.01
    this._noise = options.noise ?? 0.05
    this._createdAt = Date.now()
  }

  status(): DeviceStatus { return this._status }

  async connect(): Promise<boolean> {
    this._status = 'connecting'
    await Promise.resolve()
    this._status = 'online'
    this._uptimeStart = Date.now()
    this._lastSeen = Date.now()
    return true
  }

  async disconnect(): Promise<boolean> {
    this._status = 'offline'
    this._lastSeen = Date.now()
    return true
  }

  async read(metric: string): Promise<SensorReading | null> {
    if (this._status !== 'online') {
      this._errors++
      return null
    }
    this._t++
    const rnd = seededRandom(this._seed + this._t * 31)
    const baseline = this._parameters.find((p) => p.name === metric)
    const baseValue = baseline && typeof baseline.value === 'number' ? baseline.value : 1
    const drift = this._drift * (rnd() - 0.5)
    const noise = this._noise * (rnd() - 0.5)
    const unit = baseline?.unit ?? ''
    this._reads++
    this._lastSeen = Date.now()
    return {
      deviceId: this.id,
      timestamp: this._lastSeen,
      metric,
      value: baseValue + drift + noise,
      unit
    }
  }

  async write(parameter: DeviceParameter): Promise<boolean> {
    const idx = this._parameters.findIndex((p) => p.name === parameter.name)
    if (idx === -1) {
      this._parameters.push({ ...parameter })
    } else {
      this._parameters[idx] = { ...parameter }
    }
    this._writes++
    this._lastSeen = Date.now()
    return true
  }

  describe(): ScientificDevice {
    return {
      id: this.id,
      name: this._name,
      type: this.type,
      protocol: this._protocol,
      status: this._status,
      parameters: this._parameters.map((p) => ({ ...p })),
      lastSeen: this._lastSeen,
      createdAt: this._createdAt
    }
  }

  health(): AdapterHealth {
    return {
      connected: this._status === 'online',
      uptime: this._status === 'online' ? Date.now() - this._uptimeStart : 0,
      reads: this._reads,
      writes: this._writes,
      errors: this._errors
    }
  }
}

export interface DeviceSimulatorFactoryOptions extends SimulatorOptions {
  flowRateLpm?: number
  ozoneDoseMgL?: number
  temperatureC?: number
}

export function createPumpSimulator(name: string, options: DeviceSimulatorFactoryOptions = {}): SimulatedDevice {
  return new SimulatedDevice(name, 'pump', [
    { name: 'flow_rate', value: options.flowRateLpm ?? 1.5, unit: 'L/min' },
    { name: 'pressure', value: 1.0, unit: 'bar' }
  ], options)
}

export function createOzoneSimulator(name: string, options: DeviceSimulatorFactoryOptions = {}): SimulatedDevice {
  return new SimulatedDevice(name, 'ozone-generator', [
    { name: 'ozone_dose', value: options.ozoneDoseMgL ?? 5, unit: 'mg/L' },
    { name: 'power', value: 80, unit: 'W' }
  ], options)
}

export function createSensorSimulator(name: string, options: DeviceSimulatorFactoryOptions = {}): SimulatedDevice {
  return new SimulatedDevice(name, 'sensor', [
    { name: 'temperature', value: options.temperatureC ?? 25, unit: 'C' },
    { name: 'ph', value: 7.0, unit: '' }
  ], options)
}