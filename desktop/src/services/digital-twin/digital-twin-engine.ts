// Digital Twin Engine — 本地确定性预测引擎。
//
// 提供 3 种预测: linear / polynomial / kinetic
// 全部纯函数,无 ML 依赖,完全确定性。

import type { TwinPrediction, TwinParameter } from '../../shared/digital-twin/digital-twin-schema'

export interface LinearSpec {
  kind: 'linear'
  coefficients: number[]
  intercept: number
}

export interface PolynomialSpec {
  kind: 'polynomial'
  coefficients: number[]
  degree: number
}

export interface KineticSpec {
  kind: 'kinetic'
  rateConstant: number
  order: number
  initialConcentration: number
}

export type PredictionSpec = LinearSpec | PolynomialSpec | KineticSpec

export interface PredictionResult {
  output: Record<string, number>
  confidence: number
  raw: number[]
}

/**
 * Linear prediction: y = intercept + sum(coeff[i] * x[i])
 */
export function linearPredict(spec: LinearSpec, input: Record<string, number>): PredictionResult {
  const xs = spec.coefficients.map(() => 0)
  let i = 0
  for (const [, v] of Object.entries(input)) {
    if (i < xs.length) {
      xs[i] = typeof v === 'number' && Number.isFinite(v) ? v : 0
      i++
    }
  }
  let y = spec.intercept
  for (let j = 0; j < spec.coefficients.length; j++) y += spec.coefficients[j] * xs[j]
  return {
    output: { y },
    confidence: 0.85,
    raw: [y]
  }
}

/**
 * Polynomial prediction: y = sum(coeff[i] * x^i) for i in 0..degree
 */
export function polynomialPredict(spec: PolynomialSpec, x: number): PredictionResult {
  const xv = typeof x === 'number' && Number.isFinite(x) ? x : 0
  let y = 0
  for (let i = 0; i <= spec.degree && i < spec.coefficients.length; i++) {
    y += spec.coefficients[i] * Math.pow(xv, i)
  }
  return {
    output: { y },
    confidence: 0.8,
    raw: [y]
  }
}

/**
 * Kinetic prediction: pseudo-first-order reaction C(t) = C0 * exp(-k * t)
 */
export function kineticPredict(spec: KineticSpec, t: number): PredictionResult {
  const tSafe = typeof t === 'number' && Number.isFinite(t) ? Math.max(0, t) : 0
  const ct = spec.initialConcentration * Math.exp(-spec.rateConstant * spec.order * tSafe)
  return {
    output: { concentration: ct },
    confidence: 0.9,
    raw: [ct]
  }
}

export function predict(spec: PredictionSpec, input: Record<string, number>): PredictionResult {
  if (spec.kind === 'linear') return linearPredict(spec, input)
  if (spec.kind === 'polynomial') {
    const firstVal = Object.values(input)[0] ?? 0
    return polynomialPredict(spec, firstVal)
  }
  const firstVal = Object.values(input)[0] ?? 0
  return kineticPredict(spec, firstVal)
}

export function predictAndRecord(spec: PredictionSpec, modelId: string, input: Record<string, number>): TwinPrediction {
  const r = predict(spec, input)
  return {
    modelId,
    input: { ...input },
    output: { ...r.output },
    confidence: r.confidence,
    timestamp: Date.now()
  }
}

export function paramsToLinear(parameters: TwinParameter[]): LinearSpec {
  return {
    kind: 'linear',
    coefficients: parameters.map((p) => p.value),
    intercept: 0
  }
}

export const __testHelpers = { linearPredict, polynomialPredict, kineticPredict }
