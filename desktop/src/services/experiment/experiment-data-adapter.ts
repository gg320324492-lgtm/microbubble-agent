// Experiment Data Adapter — 连接 ExperimentRecord 与 ScientificDataset。
//
// 提供 recordToDataset / validateDataset / mergeRecords 三函数，
// 仅复用 Phase 8-H2 ScientificDataset 契约，不修改其类型。

import type { ExperimentRecord } from '../../shared/experiment/experiment-schema'
import type { ScientificDataset, VariableDefinition, DataType } from '../../shared/science/scientific-data-schema'

export function recordToDataset(record: ExperimentRecord, datasetName: string): ScientificDataset {
  const variables: VariableDefinition[] = record.parameters.map((p) => ({
    name: p.name,
    type: ((): DataType => {
      if (p.type === 'numeric') return 'number'
      if (p.type === 'boolean') return 'boolean'
      if (p.type === 'categorical') return 'string'
      return 'string'
    })(),
    unit: p.unit
  }))

  const row: Record<string, unknown> = { _timestamp: record.timestamp, _operator: record.operator, _observations: record.observations, _notes: record.notes }
  for (const p of record.parameters) {
    row[p.name] = p.value
  }

  return {
    datasetId: `ds-${record.id}`,
    name: datasetName,
    variables,
    rows: [row],
    metadata: {
      experimentId: record.experimentId,
      recordId: record.id,
      operator: record.operator,
      timestamp: record.timestamp
    }
  }
}

export function validateDataset(ds: unknown): ds is ScientificDataset {
  if (typeof ds !== 'object' || ds === null || Array.isArray(ds)) return false
  const d = ds as Record<string, unknown>
  if (typeof d.datasetId !== 'string' || d.datasetId.length === 0) return false
  if (typeof d.name !== 'string' || d.name.length === 0) return false
  if (!Array.isArray(d.variables)) return false
  if (!Array.isArray(d.rows)) return false
  if (typeof d.metadata !== 'object' || d.metadata === null) return false
  return true
}

export function mergeRecords(records: ExperimentRecord[], datasetName: string): ScientificDataset {
  if (records.length === 0) {
    return { datasetId: `ds-empty-${Date.now()}`, name: datasetName, variables: [], rows: [], metadata: { merged: 0 } }
  }
  const seen = new Set<string>()
  const variables: VariableDefinition[] = []
  for (const r of records) {
    for (const p of r.parameters) {
      if (seen.has(p.name)) continue
      seen.add(p.name)
      variables.push({
        name: p.name,
        type: ((): DataType => {
          if (p.type === 'numeric') return 'number'
          if (p.type === 'boolean') return 'boolean'
          return 'string'
        })(),
        unit: p.unit
      })
    }
  }

  const rows: Record<string, unknown>[] = records.map((r) => {
    const row: Record<string, unknown> = { _recordId: r.id, _timestamp: r.timestamp, _operator: r.operator, _observations: r.observations }
    for (const p of r.parameters) row[p.name] = p.value
    return row
  })

  return {
    datasetId: `ds-merged-${records[0].experimentId}-${records.length}`,
    name: datasetName,
    variables,
    rows,
    metadata: {
      experimentId: records[0].experimentId,
      merged: records.length,
      operators: Array.from(new Set(records.map((r) => r.operator))).sort()
    }
  }
}