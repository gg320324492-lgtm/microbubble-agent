// Experiment Twin Adapter — 连接 ExperimentResult 与 DigitalTwinModel。
//
// 输入: Experiment + ExperimentResult
// 输出: DigitalTwinModel 校准后的 TwinPrediction

import type { Experiment, ExperimentResult } from '../../shared/experiment/experiment-schema'
import type { DigitalTwinModel, TwinParameter, TwinPrediction } from '../../shared/digital-twin/digital-twin-schema'
import { predictAndRecord, paramsToLinear } from './digital-twin-engine'
import { runCalibration, comparePrediction, type CalibrationResult } from './model-calibrator'

export interface TwinModelSpec {
  name: string
  domain: string
  inputs: string[]
  outputs: string[]
  parameters: TwinParameter[]
}

export function buildTwinModel(spec: TwinModelSpec, accuracy = 0.5): DigitalTwinModel {
  const now = Date.now()
  return {
    id: `twin-${spec.name}-${now}`,
    name: spec.name,
    domain: spec.domain,
    inputs: [...spec.inputs],
    outputs: [...spec.outputs],
    parameters: spec.parameters.map((p) => ({ ...p })),
    accuracy,
    status: 'draft',
    createdAt: now,
    updatedAt: now
  }
}

export interface ExperimentToModelInput {
  experiment: Experiment
  result: ExperimentResult
  twinModel: DigitalTwinModel
}

export interface CalibrationReport {
  calibration: CalibrationResult
  updatedAccuracy: number
  twinModel: DigitalTwinModel
  predictions: TwinPrediction[]
}

/**
 * 基于 ExperimentResult 校准 DigitalTwinModel:
 * - 提取 metrics 作为 observed 数据
 * - 用 model.parameters 跑 predict
 * - 计算误差, 更新 accuracy
 */
export function calibrateFromExperiment(input: ExperimentToModelInput): CalibrationReport {
  const { result, twinModel } = input
  const metricNames = Object.keys(result.metrics)
  const values = Object.values(result.metrics)
  const dataset = {
    inputs: values.map((_, i) => ({ [metricNames[i] ?? 'x']: 0 })),
    outputs: values
  }
  const spec = paramsToLinear(twinModel.parameters)
  const cal = runCalibration(spec, dataset)
  const updatedAccuracy = Math.max(0, Math.min(1, twinModel.accuracy + (cal.rSquared - 0.5) * 0.1))

  const predictions: TwinPrediction[] = values.map((v, i) =>
    predictAndRecord(spec, twinModel.id, { [metricNames[i] ?? 'x']: v })
  )

  return {
    calibration: cal,
    updatedAccuracy,
    twinModel: { ...twinModel, accuracy: updatedAccuracy, status: 'validated', updatedAt: Date.now() },
    predictions
  }
}

/**
 * 比较 ExperimentResult 与 TwinPrediction:
 * 返回 per-metric ComparisonResult 数组。
 */
export function compareExperimentResult(
  result: ExperimentResult,
  predictions: TwinPrediction[],
  tolerance = 0.05
): Array<ReturnType<typeof comparePrediction>> {
  const out: Array<ReturnType<typeof comparePrediction>> = []
  const metricNames = Object.keys(result.metrics)
  const metricValues = Object.values(result.metrics)
  for (let i = 0; i < metricNames.length; i++) {
    const pred = predictions[i]
    if (!pred) continue
    const predicted = pred.output[Object.keys(pred.output)[0]] ?? 0
    out.push(comparePrediction(predicted, metricValues[i], tolerance))
  }
  return out
}
