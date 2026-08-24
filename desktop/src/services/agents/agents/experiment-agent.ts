// Experiment Agent — 实验设计智能体（纯函数）。
import type { AgentTask } from '../../../shared/agents/agent-schema'

export interface ExperimentOutput {
  variables: Array<{ name: string; type: 'independent' | 'dependent' | 'control'; range: string; unit: string }>
  groups: Array<{ name: string; condition: string; purpose: string }>
  metrics: string[]
  recommendation: string
  confidence: number
}

export function executeExperimentAgent(task: AgentTask): ExperimentOutput {
  const query = task.input.toLowerCase()

  const variables = [
    { name: '气泡直径', type: 'independent' as const, range: '50 – 500 nm', unit: 'nm' },
    { name: '臭氧浓度', type: 'independent' as const, range: '5 – 25 mg/L', unit: 'mg/L' },
    { name: 'pH', type: 'control' as const, range: '5.0 – 9.0', unit: '' },
    { name: 'TC 去除率', type: 'dependent' as const, range: '0 – 100%', unit: '%' },
    { name: '温度', type: 'control' as const, range: '15 – 35', unit: '°C' },
  ]

  const groups = [
    { name: '对照组', condition: '常规曝气（无微纳米气泡）', purpose: '基线对比' },
    { name: '实验组 1', condition: '200 nm 微纳米气泡 + 10 mg/L O₃', purpose: '中等条件' },
    { name: '实验组 2', condition: '100 nm 微纳米气泡 + 15 mg/L O₃', purpose: '较高条件' },
    { name: '实验组 3', condition: '50 nm 微纳米气泡 + 20 mg/L O₃', purpose: '最优条件' },
  ]

  const metrics = [
    'TC 去除率 (%)',
    'TOC 去除率 (%)',
    '一级动力学常数 kobs (min⁻¹)',
    '半衰期 t₁/₂ (min)',
    '·OH 自由基浓度 (μM)',
  ]

  let recommendation = '建议采用正交实验设计 L9(3⁴)，考察气泡直径、O₃ 浓度、pH 三因素对 TC 降解的影响。'
  if (query.includes('mechanism') || query.includes('机理')) {
    recommendation += ' 增加自由基猝灭实验以验证主要活性物种。'
  }
  if (query.includes('optim') || query.includes('优化')) {
    recommendation += ' 使用响应面法 (RSM) 寻找最优工艺参数组合。'
  }

  const confidence = variables.length > 0 && groups.length > 0 ? 0.85 : 0.3

  return { variables, groups, metrics, recommendation, confidence }
}
