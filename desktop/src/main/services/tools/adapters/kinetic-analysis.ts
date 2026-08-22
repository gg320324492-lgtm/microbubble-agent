// Kinetic Analysis Adapter (Phase 7-T6: Scientific Tool Adapters).
//
// Phase 7-T6 strict: pure function, no IO, no state, no external calls.

import type { ToolAdapter } from '@shared/tools/tool-adapter-schema'

type KineticModel = 'pseudo-first-order' | 'pseudo-second-order'

interface KineticAnalysisInput {
  time: number[]
  concentration: number[]
  model?: KineticModel
}

interface KineticCurvePoint {
  t: number
  c: number
  cModel: number
}

interface KineticAnalysisOutput {
  model: KineticModel
  parameters: { c0: number }
  k: number
  rSquared: number
  curve: KineticCurvePoint[]
}

function validateInput(input: unknown): { ok: true; value: KineticAnalysisInput } | { ok: false; error: string } {
  if (!input || typeof input !== 'object') return { ok: false, error: 'args must be an object' }
  const a = input as Record<string, unknown>
  if (!Array.isArray(a.time)) return { ok: false, error: 'time must be an array' }
  if (!Array.isArray(a.concentration)) return { ok: false, error: 'concentration must be an array' }
  if (a.time.length === 0) return { ok: false, error: 'time array is empty' }
  if (a.time.length !== a.concentration.length) {
    return { ok: false, error: 'time and concentration length mismatch' }
  }
  for (const t of a.time) {
    if (typeof t !== 'number' || !Number.isFinite(t)) return { ok: false, error: 'time contains non-number' }
  }
  for (const c of a.concentration) {
    if (typeof c !== 'number' || !Number.isFinite(c)) return { ok: false, error: 'concentration contains non-number' }
  }
  const model = a.model ?? 'pseudo-first-order'
  if (model !== 'pseudo-first-order' && model !== 'pseudo-second-order') {
    return { ok: false, error: `unknown model '${String(model)}'` }
  }
  return { ok: true, value: { time: a.time as number[], concentration: a.concentration as number[], model } }
}

function linearRegression(xs: number[], ys: number[]): { slope: number; intercept: number; r2: number } {
  const n = xs.length
  let sx = 0; let sy = 0; let sxy = 0; let sxx = 0; let syy = 0
  for (let i = 0; i < n; i++) {
    sx += xs[i]!
    sy += ys[i]!
    sxy += xs[i]! * ys[i]!
    sxx += xs[i]! * xs[i]!
    syy += ys[i]! * ys[i]!
  }
  const denom = n * sxx - sx * sx
  if (denom === 0) return { slope: 0, intercept: 0, r2: 0 }
  const slope = (n * sxy - sx * sy) / denom
  const intercept = (sy - slope * sx) / n
  const meanY = sy / n
  let ssTot = 0; let ssRes = 0
  for (let i = 0; i < n; i++) {
    const yPred = slope * xs[i]! + intercept
    ssTot += (ys[i]! - meanY) ** 2
    ssRes += (ys[i]! - yPred) ** 2
  }
  const r2 = ssTot === 0 ? 0 : 1 - ssRes / ssTot
  return { slope, intercept, r2 }
}

function fit(input: KineticAnalysisInput): KineticAnalysisOutput {
  const c0 = input.concentration[0]!
  const model = input.model!
  if (model === 'pseudo-first-order') {
    // ln(c0 / c) = k * t
    const xs: number[] = []
    const ys: number[] = []
    for (let i = 0; i < input.time.length; i++) {
      const c = input.concentration[i]!
      const t = input.time[i]!
      if (c <= 0) continue
      xs.push(t)
      ys.push(Math.log(c0 / c))
    }
    if (xs.length < 2) {
      return {
        model, parameters: { c0 }, k: 0, rSquared: 0,
        curve: input.time.map((t, i) => ({ t, c: input.concentration[i]!, cModel: c0 }))
      }
    }
    const reg = linearRegression(xs, ys)
    const k = reg.slope
    const curve: KineticCurvePoint[] = input.time.map((t, i) => ({
      t,
      c: input.concentration[i]!,
      cModel: c0 * Math.exp(-k * t)
    }))
    return { model, parameters: { c0 }, k, rSquared: reg.r2, curve }
  }
  // pseudo-second-order: 1/c - 1/c0 = k * t
  const xs: number[] = []
  const ys: number[] = []
  for (let i = 0; i < input.time.length; i++) {
    const c = input.concentration[i]!
    const t = input.time[i]!
    if (c <= 0) continue
    xs.push(t)
    ys.push(1 / c - 1 / c0)
  }
  if (xs.length < 2) {
    return {
      model, parameters: { c0 }, k: 0, rSquared: 0,
      curve: input.time.map((t, i) => ({ t, c: input.concentration[i]!, cModel: c0 }))
    }
  }
  const reg = linearRegression(xs, ys)
  const k = reg.slope
  const curve: KineticCurvePoint[] = input.time.map((t, i) => {
    const cObs = input.concentration[i]!
    const cModel = c0 === 0 || 1 / c0 + k * t === 0 ? c0 : 1 / (1 / c0 + k * t)
    return { t, c: cObs, cModel }
  })
  return { model, parameters: { c0 }, k, rSquared: reg.r2, curve }
}

export const KINETIC_ANALYSIS_ADAPTER: ToolAdapter = {
  toolId: 'tool:kinetic-analysis',
  version: '1.0.0',
  execute: async (args) => {
    const v = validateInput(args)
    if (!v.ok) return { success: false, error: { code: 'INVALID_ARGS', message: v.error } }
    try {
      const result = fit(v.value)
      return { success: true, data: result as unknown as Record<string, unknown> }
    } catch (e) {
      return {
        success: false,
        error: {
          code: 'EXECUTION_ERROR',
          message: e instanceof Error ? e.message : String(e)
        }
      }
    }
  }
}
