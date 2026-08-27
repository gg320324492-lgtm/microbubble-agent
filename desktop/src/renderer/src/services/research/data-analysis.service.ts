// Data Analysis Service — 数据分析 adapter (真实数据源)
//
// [类 20.196] 2026-08-27: 接入真实本地 SQLite.
// 数据源: analysis_results (0 行, schema 完整, 等 sample import 导入).
// 替代 NotWiredError.

import type { AnalysisReport, VariableImportance } from './data-analysis.service'

interface AnalysisResultRow {
  id: string
  experiment_id: string | null
  run_type: string | null
  status: string | null
  metrics_json: string | null
  model: string | null
  summary: string | null
  finished_at: number | null
}

function parseJson<T = unknown>(raw: string | null): T | null {
  if (!raw) return null
  try { return JSON.parse(raw) as T } catch { return null }
}

class SqliteDataAnalysisAdapter {
  async getAnalysisReport(): Promise<AnalysisReport> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<AnalysisResultRow>({
      sql: `SELECT id, experiment_id, run_type, status, metrics_json, model, summary, finished_at
            FROM analysis_results WHERE status = 'completed' ORDER BY finished_at DESC LIMIT 1`
    })
    if (rows.length === 0) {
      return {
        quality: { completeness: 0, missingValues: {}, outliers: {}, warnings: ['[类 20.196] 本地 SQLite analysis_results 表空, 等 sample import 导入真实数据'] },
        statistics: [],
        models: [],
        figures: [],
        conclusions: []
      }
    }
    const r = rows[0]
    const metrics = parseJson<Record<string, number>>(r.metrics_json) ?? {}
    const summaryText = r.summary ?? '无摘要'
    return {
      quality: {
        completeness: Object.keys(metrics).length > 0 ? 1 : 0,
        missingValues: {},
        outliers: {},
        warnings: []
      },
      statistics: Object.entries(metrics).map(([metric, value]) => ({
        metric,
        value: typeof value === 'number' ? value : 0,
        interpretation: summaryText.slice(0, 200)
      })),
      models: r.model ? [{ model: r.model, parameters: {}, rSquared: 0, residualError: 0 }] : [],
      figures: [],
      conclusions: summaryText ? [{ observation: summaryText, interpretation: '待 R6 接入后生成', confidence: 0.5 }] : []
    }
  }
  async getVariableImportance(): Promise<VariableImportance[]> {
    return []
  }
}

const realAdapter = new SqliteDataAnalysisAdapter()
let currentAdapter = realAdapter
export const realDataAnalysisAdapter = realAdapter

export const dataAnalysisService = {
  setAdapter(a: typeof realAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  getAnalysisReport: () => currentAdapter.getAnalysisReport(),
  getVariableImportance: () => currentAdapter.getVariableImportance(),
  fitModels: (_d: string, _x: string, _y: string) => {
    throw new Error('[类 20.196] fitModels 待接真实分析引擎 (当前 analysis_results 表空)')
  },
  interpretResults: (r: AnalysisReport) => currentAdapter.getAnalysisReport().then(() => r.conclusions)
}
