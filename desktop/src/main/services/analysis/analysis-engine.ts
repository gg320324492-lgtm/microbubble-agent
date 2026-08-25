// Analysis Engine — Phase 8-M1-D
// Orchestrator: 接收 measurement list, 调用 4 个 pure service, 持久化到 analysis_results / model_params / figures.

import type { SQLiteDatabase } from '../../database'
import type { DataPoint, FitParameters, KineticModelKind, RegressionDegree, CurveFamily } from './types'
import { fitKinetic } from './kinetics.service'
import { fitRegression } from './regression.service'
import { computeCorrelation } from './correlation.service'
import { computeStatistics } from './statistics.service'
import { fitCurve } from './curve-fitting.service'

export interface AnalysisEngine {
  /** 读 measurements 列表, 返回 (x, y) DataPoint[] */
  loadSeries(experimentId: string, metric: string, yMetric?: string): DataPoint[]
  /** 描述性统计 */
  statistics(experimentId: string, metric: string): {
    summary: ReturnType<typeof computeStatistics>
    n: number
  }
  /** 一级 / 零级 / 拟二级动力学拟合, 持久化 */
  runKinetic(experimentId: string, model: KineticModelKind, metric: string, runType?: string): string
  /** 多项式回归, 持久化 */
  runRegression(experimentId: string, xMetric: string, yMetric: string, degree: RegressionDegree, runType?: string): string
  /** Pearson 相关, 持久化 */
  runCorrelation(experimentId: string, xMetric: string, yMetric: string, runType?: string): string
  /** 通用曲线族拟合, 持久化 */
  runCurve(experimentId: string, family: CurveFamily, metric: string, runType?: string): string
  /** 列出某 experiment 的所有分析结果 + 关联 model_params */
  listByExperiment(experimentId: string): Array<{
    id: string
    runType: string
    status: string | null
    model: string | null
    startedAt: number
    finishedAt: number | null
    summary: string | null
    diagnostics: Record<string, unknown> | null
    confidence: number | null
    parameters: Array<{ name: string; value: number; unit: string | null; stdError: number | null; pValue: number | null }>
  }>
}

class AnalysisEngineImpl implements AnalysisEngine {
  constructor(private readonly db: SQLiteDatabase, private readonly analysisRepo: import('../../repositories').AnalysisResultRepository) {}

  loadSeries(experimentId: string, metric: string, yMetric?: string): DataPoint[] {
    const yCol = yMetric ?? metric
    const rows = this.db.query<{ ts: number; v: number; quality: string | null }>(
      'SELECT timestamp AS ts, value AS v, quality FROM measurements WHERE experiment_id = ? AND metric = ? AND timestamp IS NOT NULL ORDER BY timestamp ASC',
      [experimentId, yCol]
    )
    if (yMetric && yMetric !== metric) {
      // 双指标相关: 用 timestamp 配对
      const xRows = this.db.query<{ ts: number; v: number }>(
        'SELECT timestamp AS ts, value AS v FROM measurements WHERE experiment_id = ? AND metric = ? ORDER BY timestamp ASC',
        [experimentId, metric]
      )
      const xMap = new Map<number, number>()
      for (const r of xRows) xMap.set(r.ts, r.v)
      return rows.filter((r) => xMap.has(r.ts)).map((r) => ({
        x: xMap.get(r.ts) ?? 0,
        y: r.v,
        valid: Number.isFinite(r.v) && (r.quality === null || r.quality === 'good')
      }))
    }
    // 单变量时间序列: x = timestamp(ms), y = value
    if (rows.length === 0) return []
    const t0 = rows[0]!.ts
    return rows.map((r) => ({
      x: (r.ts - t0) / 1000, // seconds
      y: r.v,
      valid: Number.isFinite(r.v) && (r.quality === null || r.quality === 'good')
    }))
  }

  statistics(experimentId: string, metric: string) {
    const data = this.loadSeries(experimentId, metric)
    const summary = computeStatistics(metric, data)
    return { summary, n: data.length }
  }

  private persistResult(experimentId: string, runType: string, model: string | null, parameters: FitParameters, r2: number, interpretation: string, diagnostics: Record<string, unknown>): string {
    const id = `analysis-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const startedAt = Date.now()
    this.db.execute(
      `INSERT INTO analysis_results (id, experiment_id, run_type, status, started_at, finished_at, model, summary, diagnostics, confidence)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, experimentId, runType, 'completed', startedAt, startedAt, model, interpretation, JSON.stringify(diagnostics), r2]
    )
    for (const [name, value] of Object.entries(parameters)) {
      if (typeof value === 'number' && Number.isFinite(value)) {
        this.analysisRepo.addModelParam({ analysisId: id, name, value, unit: null, stdError: null, pValue: null })
      }
    }
    return id
  }

  runKinetic(experimentId: string, model: KineticModelKind, metric: string, runType: string = 'kinetic'): string {
    const data = this.loadSeries(experimentId, metric)
    const fit = fitKinetic(model, data)
    return this.persistResult(
      experimentId, runType, model,
      fit.parameters, fit.rSquared, fit.interpretation,
      { adjustedRSquared: fit.adjustedRSquared, residualError: fit.residualError, iterations: fit.iterations, converged: fit.converged, curve: fit.curve }
    )
  }

  runRegression(experimentId: string, xMetric: string, yMetric: string, degree: RegressionDegree, runType: string = 'regression'): string {
    const data = this.loadSeries(experimentId, xMetric, yMetric)
    const fit = fitRegression(degree, data)
    return this.persistResult(
      experimentId, runType, `polynomial-${degree}`,
      { ...Object.fromEntries(fit.coefficients.map((c, i) => [`c${i}`, c])) },
      fit.rSquared, fit.interpretation,
      { adjustedRSquared: fit.adjustedRSquared, residualError: fit.residualError, coefficients: fit.coefficients, curve: fit.curve }
    )
  }

  runCorrelation(experimentId: string, xMetric: string, yMetric: string, runType: string = 'correlation'): string {
    const data = this.loadSeries(experimentId, xMetric, yMetric)
    const result = computeCorrelation(xMetric, yMetric, data)
    return this.persistResult(
      experimentId, runType, 'pearson',
      { pearsonR: result.pearsonR, pearsonP: result.pearsonP, strength: result.strength },
      Math.abs(result.pearsonR), result.interpretation,
      { n: result.n }
    )
  }

  runCurve(experimentId: string, family: CurveFamily, metric: string, runType: string = 'curve'): string {
    const data = this.loadSeries(experimentId, metric)
    const fit = fitCurve(family, data)
    return this.persistResult(
      experimentId, runType, family,
      fit.parameters, fit.rSquared, fit.interpretation,
      { curve: fit.curve }
    )
  }

  listByExperiment(experimentId: string) {
    const rows = this.db.query<Record<string, unknown>>(
      'SELECT * FROM analysis_results WHERE experiment_id = ? ORDER BY started_at DESC', [experimentId]
    )
    return rows.map((r) => {
      const id = String(r['id'])
      const params = this.analysisRepo.listModelParams(id)
      let diagnostics: Record<string, unknown> | null = null
      const raw = r['diagnostics']
      if (raw && typeof raw === 'string') {
        try { diagnostics = JSON.parse(raw) as Record<string, unknown> } catch { diagnostics = null }
      }
      return {
        id,
        runType: String(r['run_type']),
        status: r['status'] == null ? null : String(r['status']),
        model: r['model'] == null ? null : String(r['model']),
        startedAt: Number(r['started_at']),
        finishedAt: r['finished_at'] == null ? null : Number(r['finished_at']),
        summary: r['summary'] == null ? null : String(r['summary']),
        diagnostics,
        confidence: r['confidence'] == null ? null : Number(r['confidence']),
        parameters: params.map((p) => ({
          name: p.name, value: p.value, unit: p.unit, stdError: p.stdError, pValue: p.pValue
        }))
      }
    })
  }
}

export function createAnalysisEngine(db: SQLiteDatabase, analysisRepo: import('../../repositories').AnalysisResultRepository): AnalysisEngine {
  return new AnalysisEngineImpl(db, analysisRepo)
}