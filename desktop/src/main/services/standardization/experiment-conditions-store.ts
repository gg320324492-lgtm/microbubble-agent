// Experiment Conditions Schema — Phase 10.6
// 标准化实验条件字段 (Phase 9-C 之上加结构约束)

import type { DatabaseService } from '../database.service'

export interface ExperimentConditions {
  /** 反应器体积 (升) */
  reactorVolumeL?: number
  /** 温度 (°C) */
  temperatureC?: number
  /** 初始 pH */
  pH?: number
  /** 污染物名称 */
  pollutant?: string
  /** 污染物初始浓度 (mg/L) */
  initialConcentrationMgL?: number
  /** 处理技术 (e.g. 'O3-MNB' / 'UV/H₂O₂') */
  technology?: string
  /** 进气流速 (L/min) */
  gasFlowLMin?: number
  /** 反应时间 (min) */
  reactionTimeMin?: number
  /** 搅拌速度 (rpm) */
  stirringRpm?: number
  /** pH 调节剂 (HCl / NaOH / buffer) */
  pHAdjuster?: string
  /** 自由文本备注 */
  notes?: string
}

export interface ExperimentConditionStoreService {
  setConditions(experimentId: string, conditions: ExperimentConditions): void
  getConditions(experimentId: string): ExperimentConditions | null
  deleteConditions(experimentId: string): boolean
  listExperiments(): Array<{ experimentId: string; conditions: ExperimentConditions }>
}

class ExperimentConditionStoreImpl implements ExperimentConditionStoreService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  setConditions(experimentId: string, conditions: ExperimentConditions): void {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    if (!experimentId || experimentId.length > 128) throw new Error('非法 experimentId')
    const filtered: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(conditions)) {
      if (v !== undefined && v !== null) filtered[k] = v
    }
    if (Object.keys(filtered).length === 0) {
      svc.db.execute('DELETE FROM experiment_conditions WHERE experiment_id = ?', [experimentId])
      return
    }
    svc.db.execute(
      `INSERT INTO experiment_conditions (experiment_id, conditions_json, updated_at)
       VALUES (?, ?, ?)
       ON CONFLICT(experiment_id) DO UPDATE SET
         conditions_json = excludedCLUDed.conditions_json,
         updated_at = excludedCLUDed.updated_at`,
      [experimentId, JSON.stringify(filtered), Date.now()]
    )
  }

  getConditions(experimentId: string): ExperimentConditions | null {
    const svc = this.getService()
    if (!svc) return null
    const row = svc.db.queryOne<{ conditions_json: string }>(
      'SELECT conditions_json FROM experiment_conditions WHERE experiment_id = ?', [experimentId]
    )
    if (!row) return null
    try { return JSON.parse(row.conditions_json) as ExperimentConditions } catch { return null }
  }

  deleteConditions(experimentId: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const result = svc.db.execute('DELETE FROM experiment_conditions WHERE experiment_id = ?', [experimentId])
    return result.changes > 0
  }

  listExperiments(): Array<{ experimentId: string; conditions: ExperimentConditions }> {
    const svc = this.getService()
    if (!svc) return []
    const rows = svc.db.query<{ experiment_id: string; conditions_json: string }>(
      'SELECT experiment_id, conditions_json FROM experiment_conditions ORDER BY updated_at DESC'
    )
    const out: Array<{ experimentId: string; conditions: ExperimentConditions }> = []
    for (const r of rows) {
      out.push({
        experimentId: String(r.experiment_id),
        conditions: this.parseSafe(String(r.conditions_json))
      })
    }
    return out
  }

  private parseSafe(s: string): ExperimentConditions {
    try { return JSON.parse(s) as ExperimentConditions } catch { return {} }
  }
}

export function createExperimentConditionStore(getService: () => DatabaseService | null): ExperimentConditionStoreService {
  return new ExperimentConditionStoreImpl(getService)
}
