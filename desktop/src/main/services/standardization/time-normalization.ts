// Time Normalization — Phase 10.6
// measurement 时间单位标准化: ms / s / min / h → 统一 ms. 反向: ms → 任意单位.

export type TimeUnit = 'ms' | 's' | 'min' | 'h' | 'd'

const TO_MS: Record<TimeUnit, number> = {
  ms: 1,
  s: 1000,
  min: 60_000,
  h: 3_600_000,
  d: 86_400_000
}

export function toMilliseconds(value: number, unit: TimeUnit): number {
  const factor = TO_MS[unit]
  if (!Number.isFinite(value) || !Number.isFinite(factor)) throw new Error(`Invalid time conversion: value=${value} unit=${unit}`)
  return Math.round(value * factor)
}

export function fromMilliseconds(ms: number, target: TimeUnit): number {
  const factor = TO_MS[target]
  if (factor === 0) throw new Error(`Invalid target unit: ${target}`)
  return ms / factor
}

export function convertTime(value: number, from: TimeUnit, to: TimeUnit): number {
  return fromMilliseconds(toMilliseconds(value, from), to)
}

export interface TimeFormatHint {
  unit: TimeUnit
  /** 输入是 Unix epoch (秒) 还是 Unix ms */
  epoch: 'seconds' | 'milliseconds' | 'none'
}

export function autoNormalizeTimestamp(raw: number | string, hint: TimeFormatHint = { unit: 'ms', epoch: 'milliseconds' }): number {
  if (typeof raw === 'string') {
    const parsed = Date.parse(raw)
    if (!Number.isNaN(parsed)) return parsed
    const num = Number(raw)
    if (Number.isFinite(num)) return autoNormalizeTimestamp(num, hint)
    throw new Error(`Invalid time string: ${raw}`)
  }
  if (hint.epoch === 'seconds') return raw * 1000
  if (hint.epoch === 'milliseconds') return raw
  // none → assume already in target unit
  return toMilliseconds(raw, hint.unit)
}

export const SUPPORTED_TIME_UNITS: ReadonlyArray<TimeUnit> = ['ms', 's', 'min', 'h', 'd']
