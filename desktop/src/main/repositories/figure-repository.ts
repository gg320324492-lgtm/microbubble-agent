// FigureRepository — Phase 8-M1-C
// 持久化渲染后的图表引用 (ECharts options 序列化), 支持按 experiment / analysis 检索.

import type { SQLiteDatabase, SqlParams } from '../database'

export type FigureType = 'line' | 'scatter' | 'bar' | 'heatmap' | 'histogram' | 'boxplot' | 'surface' | 'other'

export interface Figure {
  id: string
  experimentId: string
  analysisId: string | null
  figureType: FigureType | string
  title: string | null
  xVariable: string | null
  yVariable: string | null
  seriesJson: string | null
  renderedAt: number | null
}

export interface FigureRepository {
  create(figure: Omit<Figure, 'renderedAt'> & { renderedAt?: number }): Figure
  findById(id: string): Figure | undefined
  listByExperiment(experimentId: string): Figure[]
  listByAnalysis(analysisId: string): Figure[]
  update(id: string, patch: Partial<Omit<Figure, 'id' | 'experimentId'>>): Figure | undefined
  delete(id: string): boolean
  count(): number
}

class FigureRepositoryImpl implements FigureRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  create(input: Omit<Figure, 'renderedAt'> & { renderedAt?: number }): Figure {
    const renderedAt = input.renderedAt ?? Date.now()
    this.db.execute(
      `INSERT INTO figures (id, experiment_id, analysis_id, figure_type, title, x_variable, y_variable, series_json, rendered_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [input.id, input.experimentId, input.analysisId, input.figureType, input.title, input.xVariable, input.yVariable, input.seriesJson, renderedAt]
    )
    return { ...input, renderedAt }
  }

  findById(id: string): Figure | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM figures WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  listByExperiment(experimentId: string): Figure[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM figures WHERE experiment_id = ? ORDER BY rendered_at DESC', [experimentId]
    ).map((r) => this.mapRow(r))
  }

  listByAnalysis(analysisId: string): Figure[] {
    return this.db.query<Record<string, unknown>>(
      'SELECT * FROM figures WHERE analysis_id = ? ORDER BY rendered_at DESC', [analysisId]
    ).map((r) => this.mapRow(r))
  }

  update(id: string, patch: Partial<Omit<Figure, 'id' | 'experimentId'>>): Figure | undefined {
    const fields: string[] = []
    const params: SqlParams = []
    if (patch.analysisId !== undefined) { fields.push('analysis_id = ?'); params.push(patch.analysisId) }
    if (patch.figureType !== undefined) { fields.push('figure_type = ?'); params.push(patch.figureType) }
    if (patch.title !== undefined) { fields.push('title = ?'); params.push(patch.title) }
    if (patch.xVariable !== undefined) { fields.push('x_variable = ?'); params.push(patch.xVariable) }
    if (patch.yVariable !== undefined) { fields.push('y_variable = ?'); params.push(patch.yVariable) }
    if (patch.seriesJson !== undefined) { fields.push('series_json = ?'); params.push(patch.seriesJson) }
    if (patch.renderedAt !== undefined) { fields.push('rendered_at = ?'); params.push(patch.renderedAt) }
    if (fields.length === 0) return this.findById(id)
    params.push(id)
    this.db.execute(`UPDATE figures SET ${fields.join(', ')} WHERE id = ?`, params)
    return this.findById(id)
  }

  delete(id: string): boolean {
    const result = this.db.execute('DELETE FROM figures WHERE id = ?', [id])
    return result.changes > 0
  }

  count(): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM figures')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): Figure {
    return {
      id: String(row['id']),
      experimentId: String(row['experiment_id']),
      analysisId: row['analysis_id'] == null ? null : String(row['analysis_id']),
      figureType: String(row['figure_type']),
      title: row['title'] == null ? null : String(row['title']),
      xVariable: row['x_variable'] == null ? null : String(row['x_variable']),
      yVariable: row['y_variable'] == null ? null : String(row['y_variable']),
      seriesJson: row['series_json'] == null ? null : String(row['series_json']),
      renderedAt: row['rendered_at'] == null ? null : Number(row['rendered_at'])
    }
  }
}

export function createFigureRepository(db: SQLiteDatabase): FigureRepository {
  return new FigureRepositoryImpl(db)
}