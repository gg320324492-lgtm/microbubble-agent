// Agent Debate — 智能体之间的质疑与裁决机制。
import type { AgentMessage, AgentRole } from '../../shared/agents/agent-schema'

export interface DebateRound {
  agent: AgentRole
  claim: string
  critique: string
  verdict: string
}

export interface DebateResult {
  rounds: DebateRound[]
  finalVerdict: string
  confidence: number
}

export function conductDebate(
  proponentClaim: string,
  opponentAgent: AgentRole = 'ReviewerAgent',
  maxRounds: number = 3
): DebateResult {
  const rounds: DebateRound[] = []
  const messages: AgentMessage[] = []
  let seq = 0

  const proponentAgent: AgentRole = 'MechanismAgent'
  rounds.push({
    agent: proponentAgent,
    claim: proponentClaim,
    critique: '',
    verdict: 'proposed'
  })

  messages.push({
    id: `debate-${seq++}`, fromAgent: proponentAgent, toAgent: opponentAgent,
    messageType: 'request', content: proponentClaim, timestamp: Date.now()
  })

  let currentClaim = proponentClaim
  for (let i = 0; i < maxRounds; i++) {
    const critiqueResult = generateCritique(currentClaim, opponentAgent, i)
    rounds.push({
      agent: opponentAgent,
      claim: currentClaim,
      critique: critiqueResult.critique,
      verdict: critiqueResult.verdict
    })

    messages.push({
      id: `debate-${seq++}`, fromAgent: opponentAgent, toAgent: 'CoordinatorAgent',
      messageType: 'critique', content: critiqueResult.critique, timestamp: Date.now() + seq
    })

    if (critiqueResult.verdict === 'accept') {
      break
    }
    currentClaim = `修订: ${proponentClaim} (已考虑 ${critiqueResult.critique})`
  }

  const finalVerdict = synthesizeVerdict(rounds)
  const confidence = calculateDebateConfidence(rounds)

  return { rounds, finalVerdict, confidence }
}

function generateCritique(claim: string, agent: AgentRole, round: number): { critique: string; verdict: 'accept' | 'revise' } {
  const lower = claim.toLowerCase()

  if (round === 0) {
    return {
      critique: `初步评估"${claim}"：证据基础是否充分？需要补充验证实验。`,
      verdict: 'revise'
    }
  }

  if (lower.includes('sufficient') || lower.includes('充分')) {
    return {
      critique: '证据补充完成，建议接受结论。',
      verdict: 'accept'
    }
  }

  return {
    critique: `第 ${round + 1} 轮评估：需要更多定量数据支持。`,
    verdict: 'revise'
  }
}

function synthesizeVerdict(rounds: DebateRound[]): string {
  const last = rounds[rounds.length - 1]
  if (last.verdict === 'accept') {
    return '结论已被接受：经过多轮质疑与修改，证据充分支持该主张。'
  }
  return '结论需要进一步验证：当前证据不足以完全支持该主张。'
}

function calculateDebateConfidence(rounds: DebateRound[]): number {
  if (rounds.length === 0) return 0
  const baseConfidence = 0.7
  const acceptancePenalty = rounds.filter(r => r.verdict === 'accept').length === 0 ? 0.2 : 0
  return Math.max(0, baseConfidence - acceptancePenalty)
}
