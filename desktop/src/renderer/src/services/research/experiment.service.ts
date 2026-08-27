// Experiment Service — 实验设计服务层（带适配器模式）。
//
// [类 20.191] 2026-08-27: 删 MOCK_DESIGN + generateHypotheses 假模板.
// 这些假数据曾被 Experiment 页面渲染为"真实实验" (气泡直径/O₃浓度/分组条件).
// 改为: 默认 adapter 抛 NotWiredError, 强制 wire 真实数据源.

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

export class ExperimentNotWiredError extends Error {
  constructor() {
    super(
      '[ExperimentService] No real adapter wired. ' +
      'Mock data was removed in [类 20.191] 2026-08-27 — was previously returning fake "O₃微纳米气泡降解四环素效率优化" design. ' +
      'Real data path: 1) local desktop_experiments table, 2) FastAPI /api/v1/experiments/* ' +
      'Call experimentService.setAdapter(realAdapter) after wiring.'
    )
    this.name = 'ExperimentNotWiredError'
  }
}

const notWiredAdapter: ExperimentAdapter = {
  async getDesign() { throw new ExperimentNotWiredError() },
  async getDesignStatus() { throw new ExperimentNotWiredError() },
  async generateHypotheses() { throw new ExperimentNotWiredError() },
  async updateDesign() { throw new ExperimentNotWiredError() },
}

let currentAdapter: ExperimentAdapter = notWiredAdapter

export const experimentService = {
  setAdapter(a: ExperimentAdapter) { currentAdapter = a },
  isWired(): boolean { return currentAdapter !== notWiredAdapter },
  getDesign: () => currentAdapter.getDesign(),
  getDesignStatus: () => currentAdapter.getDesignStatus(),
  generateHypotheses: (problem: string) => currentAdapter.generateHypotheses(problem),
  updateDesign: (patch: Partial<ExperimentDesign>) => currentAdapter.updateDesign(patch),
}
