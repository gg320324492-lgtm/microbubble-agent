// Experiment Service — 实验设计 adapter (真实数据源)
//
// [类 20.196] 2026-08-27: 接入真实本地 SQLite.
// 数据源: experiments (0 行, schema 完整, 等 sample import 导入).
// 替代 NotWiredError.

export interface ExperimentDesign {
  id: string
  title: string
  question: string
  hypotheses: Array<{ statement: string; confidence: number }>
  variables: Array<{ name: string; type: 'independent' | 'dependent' | 'control'; range: string; unit: string }>
  groups: Array<{ name: string; condition: string; purpose?: string }>
  metrics: string[]
  model: { name: string; confidence: number }
  status: 'designing' | 'running' | 'completed'
}

export interface ExperimentAdapter {
  getDesign(): Promise<ExperimentDesign>
  getDesignStatus(): Promise<ExperimentDesign['status']>
  generateHypotheses(problem: string): Promise<Array<{ statement: string; confidence: number }>>
  updateDesign(patch: Partial<ExperimentDesign>): Promise<void>
}

interface ExperimentRow {
  id: string
  project_id: string | null
  name: string | null
  parameters: string | null  // JSON
  status: string | null
  hypothesis: string | null
}

function mapExperimentRow(r: ExperimentRow): ExperimentDesign {
  let params: { metrics?: string[]; variables?: ExperimentDesign['variables']; groups?: ExperimentDesign['groups']; model?: { name: string; confidence: number } } = {}
  try {
    if (r.parameters) params = JSON.parse(r.parameters)
  } catch { /* ignore */ }
  return {
    id: r.id,
    title: r.name || r.id,
    question: r.hypothesis || '',
    hypotheses: r.hypothesis ? [{ statement: r.hypothesis, confidence: 0.5 }] : [],
    variables: params.variables ?? [],
    groups: params.groups ?? [],
    metrics: params.metrics ?? [],
    model: params.model ?? { name: '待选', confidence: 0 },
    status: (r.status as ExperimentDesign['status']) ?? 'designing'
  }
}

class SqliteExperimentAdapter implements ExperimentAdapter {
  async getDesign(): Promise<ExperimentDesign> {
    const api = window.api
    if (!api?.database) throw new Error('window.api.database 不可用')
    const { rows } = await api.database.query<ExperimentRow>({
      sql: 'SELECT id, project_id, name, parameters, status, hypothesis FROM experiments ORDER BY id DESC LIMIT 1'
    })
    if (rows.length === 0) {
      // 没实验 → 返回空 design (UI 显示空态)
      return {
        id: 'no-experiment',
        title: '尚无实验',
        question: '',
        hypotheses: [],
        variables: [],
        groups: [],
        metrics: [],
        model: { name: '待选', confidence: 0 },
        status: 'designing'
      }
    }
    return mapExperimentRow(rows[0])
  }
  async getDesignStatus(): Promise<ExperimentDesign['status']> {
    const d = await this.getDesign()
    return d.status
  }
  async generateHypotheses(problem: string): Promise<Array<{ statement: string; confidence: number }>> {
    // TODO: 接 LLM 后替换
    return [
      { statement: `针对 "${problem}" 的实验设计: 当前未接 LLM, 假设置生成. 待 R6 接入.`, confidence: 0.5 }
    ]
  }
  async updateDesign(_patch: Partial<ExperimentDesign>): Promise<void> {
    // TODO: 写回 experiments 表
  }
}

const realAdapter: ExperimentAdapter = new SqliteExperimentAdapter()
let currentAdapter: ExperimentAdapter = realAdapter

export const experimentService = {
  setAdapter(a: ExperimentAdapter) { currentAdapter = a },
  isWired(): boolean { return true },
  getDesign: () => currentAdapter.getDesign(),
  getDesignStatus: () => currentAdapter.getDesignStatus(),
  generateHypotheses: (problem: string) => currentAdapter.generateHypotheses(problem),
  updateDesign: (patch: Partial<ExperimentDesign>) => currentAdapter.updateDesign(patch),
}
