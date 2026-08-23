// Model Fitting Engine (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: deterministic fitting of kinetic and regression models to
// scientific data. Computes R² and residual error. No LLM.

import type {
  ScientificDataset,
  ModelFitResult
} from '../../../shared/science/scientific-data-schema'

// ============ Helpers ============

function getXY(dataset: ScientificDataset, xName: string, yName: string): Array<{ x: number; y: number }> {
  const pairs: Array<{ x: number; y: number }> = []
  for (const row of dataset.rows) {
    const x = row[xName]
    const y = row[yName]
    if (typeof x === 'number' && typeof y === 'number' && Number.isFinite(x) && Number.isFinite(y)) {
      pairs.push({ x, y })
    }
  }
  return pairs.sort((a, b) => a.x - b.x)
}

function rSquared(yActual: number[], yPredicted: number[]): number {
  const meanY = yActual.reduce((s, v) => s + v, 0) / yActual.length
  let ssRes = 0, ssTot = 0
  for (let i = 0; i < yActual.length; i++) {
    ssRes += (yActual[i] - yPredicted[i]) ** 2
    ssTot += (yActual[i] - meanY) ** 2
  }
  return ssTot === 0 ? 1 : Math.max(0, 1 - ssRes / ssTot)
}

function residualError(yActual: number[], yPredicted: number[]): number {
  if (yActual.length === 0) return 0
  const sse = yActual.reduce((s, v, i) => s + (v - yPredicted[i]) ** 2, 0)
  return Math.sqrt(sse / yActual.length)
}

// ============ Kinetic models ============

function fitZeroOrder(pairs: Array<{ x: number; y: number }>): ModelFitResult | null {
  if (pairs.length < 2) return null
  // y = k*t + C (linear fit with x as time)
  const n = pairs.length
  const sumX = pairs.reduce((s, p) => s + p.x, 0)
  const sumY = pairs.reduce((s, p) => s + p.y, 0)
  const sumXY = pairs.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = pairs.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return null
  const k = (n * sumXY - sumX * sumY) / denom
  const C = (sumY - k * sumX) / n
  const yPred = pairs.map(p => k * p.x + C)
  const yAct = pairs.map(p => p.y)
  return {
    model: 'zero-order',
    parameters: { k, C },
    rSquared: rSquared(yAct, yPred),
    residualError: residualError(yAct, yPred)
  }
}

function fitFirstOrder(pairs: Array<{ x: number; y: number }>): ModelFitResult | null {
  if (pairs.length < 2) return null
  // ln(y) = -k*t + ln(y0) — transform to linear
  const transformed = pairs.filter(p => p.y > 0).map(p => ({ x: p.x, y: Math.log(p.y) }))
  if (transformed.length < 2) return null
  const n = transformed.length
  const sumX = transformed.reduce((s, p) => s + p.x, 0)
  const sumY = transformed.reduce((s, p) => s + p.y, 0)
  const sumXY = transformed.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = transformed.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return null
  const slope = (n * sumXY - sumX * sumY) / denom
  const intercept = (sumY - slope * sumX) / n
  const k = -slope
  const y0 = Math.exp(intercept)
  const yPred = pairs.filter(p => p.y > 0).map(p => y0 * Math.exp(-k * p.x))
  const yAct = pairs.filter(p => p.y > 0).map(p => p.y)
  return {
    model: 'first-order',
    parameters: { k, y0 },
    rSquared: rSquared(yAct, yPred),
    residualError: residualError(yAct, yPred)
  }
}

function fitSecondOrder(pairs: Array<{ x: number; y: number }>): ModelFitResult | null {
  if (pairs.length < 3) return null
  // 1/y = kt + 1/y0 — transform to linear
  const transformed = pairs.filter(p => p.y !== 0).map(p => ({ x: p.x, y: 1 / p.y }))
  if (transformed.length < 3) return null
  const n = transformed.length
  const sumX = transformed.reduce((s, p) => s + p.x, 0)
  const sumY = transformed.reduce((s, p) => s + p.y, 0)
  const sumXY = transformed.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = transformed.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return null
  const k = (n * sumXY - sumX * sumY) / denom
  const invY0 = (sumY - k * sumX) / n
  const y0 = invY0 === 0 ? 1 : 1 / invY0
  const yPred = pairs.filter(p => p.y !== 0).map(p => 1 / (k * p.x + invY0))
  const yAct = pairs.filter(p => p.y !== 0).map(p => p.y)
  return {
    model: 'second-order',
    parameters: { k, y0 },
    rSquared: rSquared(yAct, yPred),
    residualError: residualError(yAct, yPred)
  }
}

// ============ Regression ============

function fitLinear(pairs: Array<{ x: number; y: number }>): ModelFitResult | null {
  if (pairs.length < 2) return null
  const n = pairs.length
  const sumX = pairs.reduce((s, p) => s + p.x, 0)
  const sumY = pairs.reduce((s, p) => s + p.y, 0)
  const sumXY = pairs.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2 = pairs.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sumX2 - sumX * sumX
  if (denom === 0) return null
  const slope = (n * sumXY - sumX * sumY) / denom
  const intercept = (sumY - slope * sumX) / n
  const yPred = pairs.map(p => slope * p.x + intercept)
  const yAct = pairs.map(p => p.y)
  return {
    model: 'linear',
    parameters: { slope, intercept },
    rSquared: rSquared(yAct, yPred),
    residualError: residualError(yAct, yPred)
  }
}

function fitPolynomial(pairs: Array<{ x: number; y: number }>): ModelFitResult | null {
  if (pairs.length < 3) return null
  // Quadratic: y = a*x^2 + b*x + c using least squares
  const n = pairs.length
  const sumX = pairs.reduce((s, p) => s + p.x, 0)
  const sumX2 = pairs.reduce((s, p) => s + p.x ** 2, 0)
  const sumX3 = pairs.reduce((s, p) => s + p.x ** 3, 0)
  const sumX4 = pairs.reduce((s, p) => s + p.x ** 4, 0)
  const sumY = pairs.reduce((s, p) => s + p.y, 0)
  const sumXY = pairs.reduce((s, p) => s + p.x * p.y, 0)
  const sumX2Y = pairs.reduce((s, p) => s + p.x ** 2 * p.y, 0)

  // Solve 3x3 system: [n sumX sumX2; sumX sumX2 sumX3; sumX2 sumX3 sumX4] * [c; b; a] = [sumY; sumXY; sumX2Y]
  // Using Cramer's rule
  const det = n * (sumX2 * sumX4 - sumX3 * sumX3) - sumX * (sumX * sumX4 - sumX3 * sumX2) + sumX2 * (sumX * sumX3 - sumX2 * sumX2)
  if (Math.abs(det) < 1e-10) return null

  // Use Cramer's rule to solve 3x3 system
  const c = (sumY * (sumX2 * sumX4 - sumX3 * sumX3) - sumX * (sumXY * sumX4 - sumX3 * sumX2Y) + sumX2 * (sumXY * sumX3 - sumX2 * sumX2Y)) / det
  const b = (n * (sumXY * sumX4 - sumX3 * sumX2Y) - sumY * (sumX * sumX4 - sumX3 * sumX2) + sumX2 * (sumX * sumX2Y - sumXY * sumX2)) / det
  const a2 = (n * (sumX2 * sumX2Y - sumXY * sumX3) - sumX * (sumX * sumX2Y - sumXY * sumX2) + sumY * (sumX * sumX3 - sumX2 * sumX2)) / det

  const yPred = pairs.map(p => a2 * p.x ** 2 + b * p.x + c)
  const yAct = pairs.map(p => p.y)
  return {
    model: 'polynomial',
    parameters: { a: a2, b, c },
    rSquared: rSquared(yAct, yPred),
    residualError: residualError(yAct, yPred)
  }
}

// ============ Public API ============

/**
 * Phase 8-H2: fit multiple models to dataset and return results ranked by R².
 * Deterministic — least squares fitting, no LLM.
 */
export function fitModels(
  dataset: ScientificDataset,
  xVariable: string,
  yVariable: string
): ModelFitResult[] {
  const pairs = getXY(dataset, xVariable, yVariable)
  if (pairs.length < 2) return []

  const results: ModelFitResult[] = []
  const candidates = [fitZeroOrder, fitFirstOrder, fitSecondOrder, fitLinear, fitPolynomial]

  for (const fitFn of candidates) {
    const result = fitFn(pairs)
    if (result) results.push(result)
  }

  // Sort by R² descending
  results.sort((a, b) => b.rSquared - a.rSquared)
  return results
}
