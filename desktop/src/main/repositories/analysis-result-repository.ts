// AnalysisResultRepository — Phase 8-M1-C
// 持久化 LLM / 数值分析的运行结果. 支持 model_params (子表).

import type { SQLiteDatabase, SqlParams } from '../database'

export interface AnalysisResult {
  id: string
  experimentId: string
  runType: string
  status: string | null
  startedAt: number
  finishedAt: number | null
  model: string | null
  summary: string | null
  diagnostics: Record<string, unknown> | null
  confidence: number | null
}

export interface ModelParam {
  id?: number
  analysisId: string
  name: string
  value: number
  unit: string | null
  stdError: number | null
  pValue: number | null
}

export interface AnalysisResultRepository {
  create(result: Omit<AnalysisResult, 'startedAt'> & { startedAt?: number }): AnalysisResult
  findById(id: string): AnalysisResult | undefined
  listByExperiment(experimentId: string): AnalysisResult[]
  update(id: string, patch: Partial<Omit<AnalysisResult, 'id' | 'experimentId'>>): AnalysisResult | undefined
  delete(id: string): boolean
  addModelParam(param: Omit<ModelParam, 'id'>): ModelParam
  listModelParams(analysisId: string): ModelParam[]
  count(): number
}

class AnalysisResultRepositoryImpl implements AnalysisResultRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  create(input: Omit<AnalysisResult, 'startedAt'> & { startedAt?: number }): AnalysisResult {
    const startedAt = input.startedAt ?? Date.now()
    const diagnosticsJson = input.diagnostics ? JSON.stringify(input.diagnostics) : null
    this.db.execute(
      `INSERT INTO analysis_results (id, experiment_id, run_type, status, started_at, finished_at, model, summary, diagnostics, confidence)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [input.id, input.experimentId, input.runType, input.status, startedAt, input.finishedAt, input.model, input.summary, diagnosticsJson, input.confidence]
    )
    return { ...input, startedAt, diagnostics: input.diagnostics ?? null }
  }

  findById(id: string): AnalysisResult | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM analysis_results WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  listByExperiment(experimentId: string): AnalysisResult[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM analysis_results WHERE experiment_id = ? ORDER BY started_at DESC', [experimentId]
    ).map((r) => this.mapRow(r))
  }

  update(id: string, patch: Partial<Omit<AnalysisResult, 'id' | 'experimentId'>>): AnalysisResult | undefined {
    const fields: string[] = []
    const params: SqlParams = []
    if (patch.runType !== undefined) { fields.push('run_type = ?'); params.push(patch.runType) }
    if (patch.status !== undefined) { fields.push('status = ?'); params.push(patch.status) }
    if (patch.finishedAt !== undefined) { fields.push('finished_at = ?'); params.push(patch.finishedAt) }
    if (patch.model !== undefined) { fields.push('model = ?'); params.push(patch.model) }
    if (patch.summary !== undefined) { fields.push('summary = ?'); params.push(patch.summary) }
    if (patch.confidence !== undefined) { fields.push('confidence = ?'); params.push(patch.confidence) }
    if (patch.diagnostics !== undefined) {
      fields.push('diagnostics = ?')
      params.push(patch.diagnostics ? JSON.stringify(patch.diagnostics) : null)
    }
    if (fields.length === 0) return this.findById(id)
    params.push(id)
    this.db.execute(`UPDATE analysis_results SET ${fields.join(', ')} WHERE id = ?`, params)
    return this.findById(id)
  }

  delete(id: string): boolean {
    const result = this.db.execute('DELETE FROM analysis_results WHERE id = ?', [id])
    return result.changes > 0
  }

  addModelParam(param: Omit<ModelParam, 'id'>): ModelParam {
    const result = this.db.execute(
      `INSERT INTO model_params (analysis_id, name, value, unit, std_error, p_value)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [param.analysisId, param.name, param.value, param.unit, param.stdError, param.pValue]
    )
    return { ...param, id: Number(result.lastInsertRowid) }
  }

  listModelParams(analysisId: string): ModelParam[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM model_params WHERE analysis_id = ? ORDER BY name ASC', [analysisId]
    ).map((r) => this.mapParamRow(r))
  }

  count(): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM analysis_results')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): AnalysisResult {
    const diagnosticsRaw = row['diagnostics']
    let diagnostics: Record<string, unknown> | null = null
    if (diagnosticsRaw && typeof diagnosticsRaw === 'string') {
      try { diagnostics = JSON.parse(diagnosticsRaw) as Record<string, unknown> } catch { diagnostics = null }
    }
    return {
      id: String(row['id']),
      experimentId: String(row['experiment_id']),
      runType: String(row['run_type']),
      status: row['status'] == null ? null : String(row['status']),
      startedAt: Number(row['started_at']),
      finishedAt: row['finished_at'] == null ? null : Number(row['finished_at']),
      model: row['model'] == null ? null : String(row['model']),
      summary: row['summary'] == null ? null : String(row['summary']),
      diagnostics,
      confidence: row['confidence'] == null ? null : Number(row['confidence'])
    }
  }

  private mapParamRow(row: Record<string, unknown>): ModelParam {
    return {
      id: Number(row['id']),
      analysisId: String(row['analysis_id']),
      name: String(row['name']),
      value: Number(row['value']),
      unit: row['unit'] == null ? null : String(row['unit']),
      stdError: row['std_error'] == null ? null : Number(row['std_error']),
      pValue: row['p_value'] == null ? null : Number(row['p_value'])
    }
  }
}

export function createAnalysisResultRepository(db: SQLiteDatabase): AnalysisResultRepository {
  return new AnalysisResultRepositoryImpl(db)
}