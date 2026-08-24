// Device Experiment Adapter — 连接 SensorReading → ExperimentRecord → ScientificDataset。

import type { SensorReading } from '../../shared/device/device-schema'
import type { ExperimentRecord, ExperimentParameter } from '../../shared/experiment/experiment-schema'
import type { ScientificDataset } from '../../shared/science/scientific-data-schema'

export function readingToRecord(reading: SensorReading, operator: string, experimentId: string): ExperimentRecord {
  const param: ExperimentParameter = {
    name: reading.metric,
    value: reading.value,
    unit: reading.unit,
    type: 'numeric'
  }
  return {
    id: `rec-${reading.deviceId}-${reading.timestamp}`,
    experimentId,
    timestamp: reading.timestamp,
    operator,
    parameters: [param],
    observations: `${reading.metric}=${reading.value.toFixed(4)} ${reading.unit}`,
    notes: `device=${reading.deviceId}`
  }
}

export function readingsToDataset(readings: SensorReading[], name: string): ScientificDataset {
  if (readings.length === 0) {
    return { datasetId: `ds-empty-${Date.now()}`, name, variables: [], rows: [], metadata: { count: 0 } }
  }
  const metricSet = new Set<string>()
  for (const r of readings) metricSet.add(r.metric)
  const metrics = Array.from(metricSet).sort()
  const variables = metrics.map((m) => {
    const sample = readings.find((r) => r.metric === m)!
    return { name: m, type: 'number' as const, unit: sample.unit }
  })
  const rows: Record<string, unknown>[] = readings.map((r) => {
    const row: Record<string, unknown> = { _timestamp: r.timestamp, _deviceId: r.deviceId }
    row[r.metric] = r.value
    return row
  })
  return {
    datasetId: `ds-readings-${readings[0].deviceId}-${readings.length}`,
    name,
    variables,
    rows,
    metadata: { deviceId: readings[0].deviceId, metrics, count: readings.length }
  }
}

export interface AggregateStats {
  count: number
  min: number
  max: number
  mean: number
  unit: string
}

export function aggregateReadings(readings: SensorReading[], metric: string): AggregateStats | null {
  const filtered = readings.filter((r) => r.metric === metric)
  if (filtered.length === 0) return null
  let min = filtered[0].value
  let max = filtered[0].value
  let sum = 0
  for (const r of filtered) {
    if (r.value < min) min = r.value
    if (r.value > max) max = r.value
    sum += r.value
  }
  return {
    count: filtered.length,
    min,
    max,
    mean: sum / filtered.length,
    unit: filtered[0].unit
  }
}