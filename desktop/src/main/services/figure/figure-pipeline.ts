// Figure Generation Pipeline — Phase 10.6
// 序列化 figure 数据 → ECharts-compatible options. 支持 5 种 chart 类型.

import type { KineticParams } from '../standardization/kinetic-units'
import type { DatabaseService } from '../database.service'

export type FigureType = 'line' | 'scatter' | 'bar' | 'histogram' | 'boxplot'

export interface FigureSeries {
  name: string
  data: Array<{ x: number; y: number; label?: string }>
  unitX?: string
  unitY?: string
}

export interface FigureOptions {
  title: string
  xLabel: string
  yLabel: string
  type: FigureType
  series: FigureSeries[]
}

export interface GeneratedFigure {
  options: object
  type: FigureType
  title: string
  seriesCount: number
  pointCount: number
}

export function generateFigure(opts: FigureOptions): GeneratedFigure {
  if (opts.series.length === 0) throw new Error('至少需要一个 series')
  const echartsSeries = opts.series.map((s) => ({
    name: s.name,
    type: opts.type === 'histogram' ? 'bar' : opts.type,
    data: s.data.map((p) => [p.x, p.y]),
    symbolSize: opts.type === 'scatter' ? 6 : 4
  }))
  return {
    options: {
      title: { text: opts.title, left: 'center' },
      tooltip: { trigger: 'axis' },
      legend: { top: 24, data: opts.series.map((s) => s.name) },
      grid: { left: 56, right: 24, top: 56, bottom: 48, containLabel: true },
      xAxis: { type: 'value', name: opts.xLabel, nameLocation: 'middle', nameGap: 28 },
      yAxis: { type: 'value', name: opts.yLabel, nameLocation: 'middle', nameGap: 42 },
      series: echartsSeries
    },
    type: opts.type,
    title: opts.title,
    seriesCount: opts.series.length,
    pointCount: opts.series.reduce((n, s) => n + s.data.length, 0)
  }
}

export function generateFitCurve(params: KineticParams, data: Array<{ x: number; y: number }>): FigureOptions {
  const fit: FigureSeries = {
    name: `${params.model} fit (R²=${params.rSquared.toFixed(3)})`,
    data: data.map((p) => ({ x: p.x, y: params.k * p.x + (params.halfLife || 0) })),
    unitX: 'min',
    unitY: 'mg/L'
  }
  const obs: FigureSeries = {
    name: 'observed',
    data,
    unitX: 'min',
    unitY: 'mg/L'
  }
  return {
    title: `${params.model} kinetic fit (R²=${params.rSquared.toFixed(3)})`,
    xLabel: 'time (min)',
    yLabel: 'concentration (mg/L)',
    type: 'line',
    series: [obs, fit]
  }
}

export interface FigurePipelineService {
  generate(opts: FigureOptions): GeneratedFigure
  generateFromKinetic(params: KineticParams, data: Array<{ x: number; y: number }>): GeneratedFigure
  saveToDb(figure: GeneratedFigure, experimentId: string, analysisId: string | null): Promise<string>
}

class FigurePipelineServiceImpl implements FigurePipelineService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  generate(opts: FigureOptions): GeneratedFigure {
    return generateFigure(opts)
  }

  generateFromKinetic(params: KineticParams, data: Array<{ x: number; y: number }>): GeneratedFigure {
    return generateFigure(generateFitCurve(params, data))
  }

  async saveToDb(figure: GeneratedFigure, experimentId: string, analysisId: string | null): Promise<string> {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const id = `fig-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const now = Date.now()
    svc.db.execute(
      `INSERT INTO figures (id, experiment_id, analysis_id, figure_type, title, series_json, rendered_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [id, experimentId, analysisId, figure.type, figure.title, JSON.stringify(figure.options), now]
    )
    svc.audit.record({ action: 'figure.generate', module: 'figure', metadata: { id, type: figure.type, pointCount: figure.pointCount } })
    return id
  }
}

export function createFigurePipelineService(getService: () => DatabaseService | null): FigurePipelineService {
  return new FigurePipelineServiceImpl(getService)
}
