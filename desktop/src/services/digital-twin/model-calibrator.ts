// Model Calibrator — 模型校准工具。
//
// 提供 comparePrediction / calculateError / updateParameters 三函数。

import type { TwinParameter } from '../../shared/digital-twin/digital-twin-schema'
import type { PredictionSpec } from './digital-twin-engine'
import { predict } from './digital-twin-engine'

export interface ComparisonResult {
  predicted: number
  observed: number
  absoluteError: number
  relativeError: number
  withinTolerance: boolean
}

export interface CalibrationResult {
  totalAbsoluteError: number
  meanAbsoluteError: number
  maxAbsoluteError: number
  rmse: number
  rSquared: number
  samples: number
}

export interface CalibrationOptions {
  tolerance?: number
}

export function comparePrediction(predicted: number, observed: number, tolerance = 0.05): ComparisonResult {
  const absoluteError = Math.abs(predicted - observed)
  const denom = Math.abs(observed) === 0 ? 1 : Math.abs(observed)
  const relativeError = absoluteError / denom
  return {
    predicted,
    observed,
    absoluteError,
    relativeError,
    withinTolerance: absoluteError <= tolerance
  }
}

export function calculateError(predictions: ComparisonResult[]): CalibrationResult {
  if (predictions.length === 0) {
    return { totalAbsoluteError: 0, meanAbsoluteError: 0, maxAbsoluteError: 0, rmse: 0, rSquared: 0, samples: 0 }
  }
  let total = 0
  let max = 0
  let sumSq = 0
  const observedMean = predictions.reduce((s, p) => s + p.observed, 0) / predictions.length
  let ssTot = 0
  let ssRes = 0
  for (const p of predictions) {
    total += p.absoluteError
    if (p.absoluteError > max) max = p.absoluteError
    sumSq += p.absoluteError ** 2
    ssRes += (p.observed - p.predicted) ** 2
    ssTot += (p.observed - observedMean) ** 2
  }
  const rmse = Math.sqrt(sumSq / predictions.length)
  const rSquared = ssTot === 0 ? 1 : Math.max(0, 1 - ssRes / ssTot)
  return {
    totalAbsoluteError: total,
    meanAbsoluteError: total / predictions.length,
    maxAbsoluteError: max,
    rmse,
    rSquared,
    samples: predictions.length
  }
}

export function updateParameters(parameters: TwinParameter[], learningRate: number, gradient: number[]): TwinParameter[] {
  if (learningRate < 0 || learningRate > 1) {
    throw new Error(`learningRate must be in [0,1], got ${learningRate}`)
  }
  return parameters.map((p, i) => ({
    ...p,
    value: p.value - learningRate * (gradient[i] ?? 0)
  }))
}

export interface CalibrationDataset {
  inputs: Record<string, number>[]
  outputs: number[]
}

export function runCalibration(spec: PredictionSpec, dataset: CalibrationDataset, options: CalibrationOptions = {}): CalibrationResult {
  const tolerance = options.tolerance ?? 0.05
  const comparisons: ComparisonResult[] = []
  for (let i = 0; i < dataset.inputs.length; i++) {
    const input = dataset.inputs[i]
    const observed = dataset.outputs[i]
    const r = predict(spec, input)
    const y = r.raw[0] ?? 0
    comparisons.push(comparePrediction(y, observed, tolerance))
  }
  return calculateError(comparisons)
}
