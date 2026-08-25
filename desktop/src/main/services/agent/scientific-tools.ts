// Scientific Tools Implementation — Phase 8-M1-E
// 6 个 scientific tools, 委托到 getDatabaseService() / analysisEngine / manuscriptRepo.
// 严禁业务逻辑: 全部为 thin wrapper, 验证 + 委托.

import type { DatabaseService } from '../database.service'
import type {
  ListExperimentsInput,
  GetMeasurementsInput,
  GetSamplesInput,
  RunKineticInput,
  RunKineticResult,
  RunStatisticsInput,
  RunStatisticsResult,
  WriteManuscriptSectionInput,
  WriteManuscriptSectionResult,
  ExperimentSummary,
  MeasurementRow,
  SampleRow
} from './agent-schemas'

const ID_PATTERN = /^[A-Za-z0-9_-]+$/
const MAX_MEASUREMENT_LIMIT = 1000
const MAX_SAMPLE_LIMIT = 500
const MAX_MANUSCRIPT_CONTENT = 200_000

function assertId(value: string, ctx: string): void {
  if (!value || !ID_PATTERN.test(value) || value.length > 128) {
    throw new Error(`[scientific-tools] ${ctx}: 非法 id '${value}' (仅允许字母数字下划线连字符, 长度 ≤ 128)`)
  }
}

function clamp(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback
  return Math.max(min, Math.min(max, Math.floor(value)))
}

function buildMeasurementCountMap(rows: Array<{ id: number; experiment_id: string }>): Map<string, number> {
  const m = new Map<string, number>()
  for (const r of rows) {
    m.set(r.experiment_id, (m.get(r.experiment_id) ?? 0) + 1)
  }
  return m
}

export class ScientificTools {
  constructor(private readonly getService: () => DatabaseService | null) {}

  listExperiments(input: ListExperimentsInput): ExperimentSummary[] {
    const svc = this.getService()
    if (!svc) return []
    if (input.projectId) assertId(input.projectId, 'listExperiments.projectId')
    const limit = clamp(input.limit ?? 50, 1, 200, 50)
    const where: string[] = []
    const params: unknown[] = []
    if (input.projectId) { where.push('project_id = ?'); params.push(input.projectId) }
    if (input.status) { where.push('status = ?'); params.push(input.status) }
    const sql = `SELECT id, project_id, name, status, created_at FROM experiments ${where.length > 0 ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY created_at DESC LIMIT ?`
    params.push(limit)
    const rows = svc.db.query<{ id: string; project_id: string; name: string; status: string | null; created_at: number }>(sql, params)
    const ids = rows.map((r) => r.id)
    if (ids.length === 0) return []
    const placeholders = ids.map(() => '?').join(',')
    const countRows = svc.db.query<{ id: number; experiment_id: string }>(
      `SELECT id, experiment_id FROM measurements WHERE experiment_id IN (${placeholders})`, ids
    )
    const counts = buildMeasurementCountMap(countRows)
    return rows.map((r) => ({
      id: r.id,
      projectId: r.project_id,
      name: r.name,
      status: r.status,
      createdAt: r.created_at,
      measurementCount: counts.get(r.id) ?? 0
    }))
  }

  getMeasurements(input: GetMeasurementsInput): MeasurementRow[] {
    const svc = this.getService()
    if (!svc) return []
    assertId(input.experimentId, 'getMeasurements.experimentId')
    if (!input.metric || input.metric.length > 64) throw new Error('[scientific-tools] getMeasurements.metric 非法')
    const limit = clamp(input.limit ?? 200, 1, MAX_MEASUREMENT_LIMIT, 200)
    const where: string[] = ['experiment_id = ?', 'metric = ?']
    const params: unknown[] = [input.experimentId, input.metric]
    if (Number.isFinite(input.startTime)) { where.push('timestamp >= ?'); params.push(input.startTime) }
    if (Number.isFinite(input.endTime)) { where.push('timestamp <= ?'); params.push(input.endTime) }
    const sql = `SELECT id, experiment_id, timestamp, metric, value, unit, quality, sample_id FROM measurements WHERE ${where.join(' AND ')} ORDER BY timestamp ASC LIMIT ?`
    params.push(limit)
    return svc.db.query<{ id: number; experiment_id: string; timestamp: number; metric: string; value: number; unit: string | null; quality: string | null; sample_id: string | null }>(sql, params).map((r) => ({
      id: r.id,
      experimentId: r.experiment_id,
      timestamp: r.timestamp,
      metric: r.metric,
      value: r.value,
      unit: r.unit,
      quality: r.quality,
      sampleId: r.sample_id
    }))
  }

  getSamples(input: GetSamplesInput): SampleRow[] {
    const svc = this.getService()
    if (!svc) return []
    assertId(input.experimentId, 'getSamples.experimentId')
    const limit = clamp(input.limit ?? 100, 1, MAX_SAMPLE_LIMIT, 100)
    const where: string[] = ['experiment_id = ?']
    const params: unknown[] = [input.experimentId]
    if (input.batch) { where.push('batch = ?'); params.push(input.batch) }
    const sql = `SELECT id, experiment_id, batch, replicate, condition_label, sampled_at, operator FROM samples WHERE ${where.join(' AND ')} ORDER BY sampled_at DESC LIMIT ?`
    params.push(limit)
    const rows = svc.db.query<{ id: string; experiment_id: string; batch: string | null; replicate: number | null; condition_label: string | null; sampled_at: number; operator: string | null }>(sql, params)
    if (rows.length === 0) return []
    const ids = rows.map((r) => r.id)
    const placeholders = ids.map(() => '?').join(',')
    const countRows = svc.db.query<{ sample_id: string | null }>(
      `SELECT sample_id FROM measurements WHERE sample_id IN (${placeholders}) AND sample_id IS NOT NULL`, ids
    )
    const counts = new Map<string, number>()
    for (const c of countRows) {
      if (c.sample_id) counts.set(c.sample_id, (counts.get(c.sample_id) ?? 0) + 1)
    }
    return rows.map((r) => ({
      id: r.id,
      experimentId: r.experiment_id,
      batch: r.batch,
      replicate: r.replicate,
      conditionLabel: r.condition_label,
      sampledAt: r.sampled_at,
      operator: r.operator,
      measurementCount: counts.get(r.id) ?? 0
    }))
  }

  runKinetic(input: RunKineticInput): RunKineticResult {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    assertId(input.experimentId, 'runKinetic.experimentId')
    const analysisId = svc.analysisEngine.runKinetic(input.experimentId, input.model, input.metric)
    const listed = svc.analysisEngine.listByExperiment(input.experimentId)
    const entry = listed.find((r) => r.id === analysisId)
    if (!entry) throw new Error('分析结果写入失败')
    return {
      analysisId,
      model: input.model,
      parameters: Object.fromEntries(entry.parameters.map((p) => [p.name, p.value])),
      rSquared: entry.confidence ?? 0,
      adjustedRSquared: 0,
      residualError: 0,
      curve: [],
      interpretation: entry.summary ?? ''
    }
  }

  runStatistics(input: RunStatisticsInput): RunStatisticsResult {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    assertId(input.experimentId, 'runStatistics.experimentId')
    return svc.analysisEngine.statistics(input.experimentId, input.metric) as RunStatisticsResult
  }

  writeManuscriptSection(input: WriteManuscriptSectionInput): WriteManuscriptSectionResult {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    assertId(input.projectId, 'writeManuscriptSection.projectId')
    if (!input.section || input.section.length > 64) throw new Error('section 非法 (1-64 字符)')
    if (!input.content || input.content.length > MAX_MANUSCRIPT_CONTENT) {
      throw new Error(`content 长度超限 (≤ ${MAX_MANUSCRIPT_CONTENT})`)
    }
    if (input.citations && input.citations.length > 50) {
      throw new Error('citations 数量超限 (≤ 50)')
    }
    const citations = (input.citations ?? []).map((c) => {
      if (c.analysisId) assertId(c.analysisId, 'citation.analysisId')
      if (c.figureId) assertId(c.figureId, 'citation.figureId')
      if (c.sampleId) assertId(c.sampleId, 'citation.sampleId')
      return c
    })
    const id = `manuscript-${input.projectId}-${input.section}`
    const now = Date.now()
    svc.db.execute(
      `INSERT INTO manuscripts (id, project_id, section, content, updated_at)
       VALUES (?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         section = excludedCLUDed.section,
         content = excludedCLUDed.content,
         updated_at = excludedCLUDed.updated_at`,
      [id, input.projectId, input.section, input.content, now]
    )
    svc.audit.record({ action: 'manuscript.write', module: 'agent', metadata: { projectId: input.projectId, section: input.section, citations: citations.length, id } })
    return {
      manuscriptId: id,
      projectId: input.projectId,
      section: input.section,
      updatedAt: now,
      citationsCount: citations.length
    }
  }
}

export function createScientificTools(getService: () => DatabaseService | null): ScientificTools {
  return new ScientificTools(getService)
}