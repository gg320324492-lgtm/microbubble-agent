// Device Twin Adapter — 连接 Device Data → Twin Prediction。

import type { SensorReading } from '../../shared/device/device-schema'
import type { TwinPrediction } from '../../shared/digital-twin/digital-twin-schema'
import type { DigitalTwinModel } from '../../shared/digital-twin/digital-twin-schema'
import { extractFeatures, normalize } from '../digital-twin/feature-engineer'
import { predict, predictAndRecord, paramsToLinear } from '../digital-twin/digital-twin-engine'

export interface DeviceToTwinInput {
  deviceId: string
  readings: SensorReading[]
  twinModel: DigitalTwinModel
}

export function readingsToFeatures(readings: SensorReading[]): { name: string; values: number[] }[] {
  const groups = new Map<string, SensorReading[]>()
  for (const r of readings) {
    let arr = groups.get(r.metric)
    if (!arr) {
      arr = []
      groups.set(r.metric, arr)
    }
    arr.push(r)
  }
  const out: { name: string; values: number[] }[] = []
  for (const [metric, arr] of groups) {
    const rowLike = arr.map((r) => ({ [metric]: r.value }))
    const f = extractFeatures(rowLike, metric)
    out.push({ name: f.name, values: f.values })
  }
  return out
}

export function predictFromReadings(input: DeviceToTwinInput): TwinPrediction[] {
  const features = readingsToFeatures(input.readings)
  const normalized = features.map((f) => {
    const n = normalize({ name: f.name, values: f.values, kind: 'time-series' })
    return { name: n.name, latestValue: n.values[n.values.length - 1] ?? 0 }
  })
  const inputMap: Record<string, number> = {}
  for (const f of normalized) inputMap[f.name] = f.latestValue
  const spec = paramsToLinear(input.twinModel.parameters)
  return [predictAndRecord(spec, input.twinModel.id, inputMap)]
}

export function predictLatestReading(reading: SensorReading, twinModel: DigitalTwinModel): TwinPrediction {
  const spec = paramsToLinear(twinModel.parameters)
  return predictAndRecord(spec, twinModel.id, { [reading.metric]: reading.value })
}

export function streamPredict(input: DeviceToTwinInput, onPrediction: (p: TwinPrediction) => void): TwinPrediction[] {
  const predictions: TwinPrediction[] = []
  for (const reading of input.readings) {
    const p = predictLatestReading(reading, input.twinModel)
    predictions.push(p)
    onPrediction(p)
  }
  return predictions
}

export const __testHelpers = { readingsToFeatures }