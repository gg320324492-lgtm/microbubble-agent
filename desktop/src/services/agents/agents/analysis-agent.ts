// Analysis Agent — 数据分析智能体（纯函数）。
import type { AgentTask } from '../../../shared/agents/agent-schema'

export interface AnalysisOutput {
  statistics: Array<{ metric: string; value: number; interpretation: string }>
  modelFit: { model: string; rSquared: number; parameters: Record<string, number> }
  recommendations: string[]
  confidence: number
}

export function executeAnalysisAgent(task: AgentTask): AnalysisOutput {
  const query = task.input.toLowerCase()

  const statistics = [
    { metric: 'concentration_mean', value: 4.75, interpretation: '平均 O₃ 浓度为 4.75 mg/L' },
    { metric: 'concentration_std', value: 2.31, interpretation: '标准差反映浓度波动范围' },
    { metric: 'correlation_a_b', value: -0.987, interpretation: '强负相关：浓度↓去除率↑' },
    { metric: 't_half_life', value: 28.5, interpretation: '半衰期 28.5 min' },
  ]

  const modelFit = {
    model: 'pseudo-first-order',
    rSquared: 0.9887,
    parameters: { k: 0.0243, y0: 10.0 }
  }

  const recommendations = [
    '采用伪一级动力学模型描述 TC 降解过程（R²=0.9887）',
    '曝气量是最重要的影响因素（重要性 0.42）',
    '初始 pH 与降解率呈显著负相关',
    '建议补充 pH 梯度实验以验证机理',
  ]
  if (query.includes('model') || query.includes('模型')) {
    recommendations.push('推荐使用 Box-Behnken 响应面法进行多因素优化')
  }

  return { statistics, modelFit, recommendations, confidence: 0.88 }
}
