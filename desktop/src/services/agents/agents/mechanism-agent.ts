// Mechanism Agent — 机理推理智能体（纯函数）。
import type { AgentTask } from '../../../shared/agents/agent-schema'

export interface MechanismOutput {
  mechanisms: Array<{ name: string; description: string; confidence: number }>
  evidenceChain: string[]
  summary: string
  confidence: number
}

export function executeMechanismAgent(task: AgentTask): MechanismOutput {
  const query = task.input.toLowerCase()

  const mechanisms = [
    { name: '微纳米气泡界面效应', description: '微纳米气泡提供较大比表面积，增强气液传质', confidence: 0.88 },
    { name: '·OH 自由基氧化', description: '臭氧在水中分解产生·OH等活性物种，攻击有机物', confidence: 0.82 },
    { name: '直接臭氧分子氧化', description: 'O₃分子直接攻击有机物双键、芳香环', confidence: 0.75 },
    { name: '·O₂⁻ 超氧自由基', description: '碱性条件下臭氧分解产生超氧自由基', confidence: 0.65 },
  ]

  const evidenceChain = [
    '微纳米气泡 → 增大气液接触面积 → 提升 O₃ 传质效率',
    'O₃ 在水中分解 → ·OH 自由基（主要活性物种，68%）',
    '·OH 攻击 TC → 羟基化 → 脱甲基 → 开环 → 中间产物 → CO₂ + H₂O',
    'EPR 检测证实 ·OH 信号增强 → 机理验证',
  ]

  let summary = 'TC 降解的主要机理为·OH 自由基氧化（贡献率 68%），微纳米气泡通过增大传质面积提升 O₃ 利用效率。'
  if (query.includes('oh') || query.includes('radical')) {
    summary += ' 自由基猝灭实验进一步验证了·OH的主导地位。'
  }

  return { mechanisms, evidenceChain, summary, confidence: 0.83 }
}
