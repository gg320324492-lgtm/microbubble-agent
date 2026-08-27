// Kinetic Unit Conversion — Phase 10.6
// 一级动力学参数在不同时间单位之间的换算: k (min⁻¹ ↔ s⁻¹ ↔ h⁻¹) + half-life.

import type { TimeUnit } from './time-normalization'
import { convertTime } from './time-normalization'

export interface KineticParams {
  k: number
  halfLife: number
  rSquared: number
  unit: TimeUnit
  model: 'first-order' | 'zero-order' | 'pseudo-second-order'
}

const TO_PER_MIN: Record<TimeUnit, number> = {
  ms: 60_000,
  s: 60,
  min: 1,
  h: 1 / 60,
  d: 1 / 1440
}

export function convertK(k: number, from: TimeUnit, to: TimeUnit): number {
  const kPerMin = k * TO_PER_MIN[from]
  return kPerMin / TO_PER_MIN[to]
}

export function convertHalfLife(tHalf: number, from: TimeUnit, to: TimeUnit): number {
  return convertTime(tHalf, from, to)
}

/** Convert a full kinetic result set between time units. */
export function convertKineticParams(params: KineticParams, target: TimeUnit): KineticParams {
  if (params.unit === target) return params
  return {
    k: convertK(params.k, params.unit, target),
    halfLife: convertHalfLife(params.halfLife, params.unit, target),
    rSquared: params.rSquared,
    unit: target,
    model: params.model
  }
}

export interface ConcentrationUnit {
  symbol: 'mg/L' | 'μg/L' | 'g/L' | 'mol/L' | 'mmol/L' | 'μmol/L' | 'ppm' | 'ppb'
  factor: number
}

export const CONCENTRATION_UNITS: Record<string, ConcentrationUnit> = {
  'mg/L': { symbol: 'mg/L', factor: 1 },
  'μg/L': { symbol: 'μg/L', factor: 0.001 },
  'g/L': { symbol: 'g/L', factor: 1000 }
}

export function convertConcentration(value: number, from: string, to: string, molarMass?: number): number {
  if (from === to) return value
  if (from === 'mol/L' || from === 'mmol/L' || from === 'μmol/L' || to === 'mol/L' || to === 'mmol/L' || to === 'μmol/L') {
    if (!molarMass) throw new Error('需要 molarMass 进行 mol 单位换算')
    const toMolar = (v: number, unit: string): number => {
      if (unit === 'mol/L') return v
      if (unit === 'mmol/L') return v * 0.001
      if (unit === 'μmol/L') return v * 1e-6
      return v / molarMass
    }
    const fromMolar = (v: number, unit: string): number => {
      if (unit === 'mol/L') return v
      if (unit === 'mmol/L') return v * 1000
      if (unit === 'μmol/L') return v * 1e6
      return v * molarMass
    }
    const molar = toMolar(value, from)
    return fromMolar(molar, to)
  }
  const f = CONCENTRATION_UNITS[from]
  const t = CONCENTRATION_UNITS[to]
  if (!f || !t) throw new Error(`未知浓度单位: ${from} 或 ${to}`)
  return (value * f.factor) / t.factor
}
