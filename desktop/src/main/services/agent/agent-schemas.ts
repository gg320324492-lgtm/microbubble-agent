// Agent Scientific Tool Schemas — Phase 8-M1-E
// 6 scientific tools: list_experiments, get_measurements, get_samples, run_kinetic,
// run_statistics, write_manuscript_section. 全部在主进程执行, 通过 IPC 桥接渲染端.

import type { KineticModelKind, StatisticsResult } from '../analysis/types'

export interface ListExperimentsInput {
  projectId?: string
  status?: string
  limit?: number
}

export interface ExperimentSummary {
  id: string
  projectId: string
  name: string
  status: string | null
  createdAt: number
  measurementCount: number
}

export interface GetMeasurementsInput {
  experimentId: string
  metric: string
  startTime?: number
  endTime?: number
  limit?: number
}

export interface MeasurementRow {
  id: number
  experimentId: string
  timestamp: number
  metric: string
  value: number
  unit: string | null
  quality: string | null
  sampleId: string | null
}

export interface GetSamplesInput {
  experimentId: string
  batch?: string
  limit?: number
}

export interface SampleRow {
  id: string
  experimentId: string
  batch: string | null
  replicate: number | null
  conditionLabel: string | null
  sampledAt: number
  operator: string | null
  measurementCount: number
}

export interface RunKineticInput {
  experimentId: string
  model: KineticModelKind
  metric: string
}

export interface RunKineticResult {
  analysisId: string
  model: KineticModelKind
  parameters: Record<string, number>
  rSquared: number
  adjustedRSquared: number
  residualError: number
  curve: Array<{ x: number; y: number }>
  interpretation: string
}

export interface RunStatisticsInput {
  experimentId: string
  metric: string
}

export interface RunStatisticsResult {
  summary: StatisticsResult
  n: number
}

export interface CitationRef {
  analysisId?: string
  figureId?: string
  measurementId?: number
  sampleId?: string
  description?: string
}

export interface WriteManuscriptSectionInput {
  projectId: string
  section: string
  content: string
  citations?: CitationRef[]
}

export interface WriteManuscriptSectionResult {
  manuscriptId: string
  projectId: string
  section: string
  updatedAt: number
  citationsCount: number
}

export interface ScientificToolMetadata {
  name: string
  description: string
  parametersJson: string
}

export const SCIENTIFIC_TOOL_NAMES = [
  'list_experiments',
  'get_measurements',
  'get_samples',
  'run_kinetic',
  'run_statistics',
  'write_manuscript_section'
] as const

export type ScientificToolName = typeof SCIENTIFIC_TOOL_NAMES[number]

export interface ScientificToolRegistry {
  list(): ScientificToolMetadata[]
  invoke(name: string, params: Record<string, unknown>): Promise<unknown>
}