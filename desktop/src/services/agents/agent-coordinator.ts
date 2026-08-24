// Agent Coordinator — 任务分发与结果聚合。
import type { AgentMessage, AgentTask, AgentRole } from '../../shared/agents/agent-schema'
import { executeLiteratureAgent } from './agents/literature-agent'
import { executeExperimentAgent } from './agents/experiment-agent'
import { executeAnalysisAgent } from './agents/analysis-agent'
import { executeMechanismAgent } from './agents/mechanism-agent'
import { executeWritingAgent } from './agents/writing-agent'
import { executeReviewerAgent } from './agents/reviewer-agent'

export interface CollaborationResult {
  agents: AgentRole[]
  messages: AgentMessage[]
  finalResult: string
  confidence: number
}

function makeMessage(fromAgent: string, toAgent: string, content: string, messageType: AgentMessage['messageType'], seq: number): AgentMessage {
  return { id: `msg-${seq}`, fromAgent, toAgent, content, messageType, timestamp: Date.now() + seq }
}

function executeAgentByRole(role: AgentRole, task: AgentTask): { result: string; confidence: number } {
  switch (role) {
    case 'LiteratureAgent': {
      const out = executeLiteratureAgent(task)
      return { result: out.summary, confidence: out.confidence }
    }
    case 'ExperimentAgent': {
      const out = executeExperimentAgent(task)
      return { result: out.recommendation, confidence: out.confidence }
    }
    case 'DataAnalysisAgent': {
      const out = executeAnalysisAgent(task)
      return { result: out.recommendations.join('；'), confidence: out.confidence }
    }
    case 'MechanismAgent': {
      const out = executeMechanismAgent(task)
      return { result: out.summary, confidence: out.confidence }
    }
    case 'WritingAgent': {
      const out = executeWritingAgent(task)
      return { result: out.highlights.join('；'), confidence: out.confidence }
    }
    case 'ReviewerAgent': {
      const out = executeReviewerAgent(task)
      return { result: `评分 ${out.overallScore.toFixed(2)} 建议 ${out.recommendation}`, confidence: out.confidence }
    }
    default:
      return { result: '未知角色', confidence: 0 }
  }
}

export function coordinate(task: AgentTask): CollaborationResult {
  const query = task.input.toLowerCase()
  const messages: AgentMessage[] = []
  let seq = 0

  // 1. Analyze task — select agents
  const selectedRoles: AgentRole[] = []
  if (query.includes('literature') || query.includes('review') || query.includes('文献') || query.includes('综述')) {
    selectedRoles.push('LiteratureAgent')
  }
  if (query.includes('experiment') || query.includes('design') || query.includes('实验') || query.includes('设计')) {
    selectedRoles.push('ExperimentAgent')
  }
  if (query.includes('data') || query.includes('analysis') || query.includes('模型') || query.includes('分析')) {
    selectedRoles.push('DataAnalysisAgent')
  }
  if (query.includes('mechanism') || query.includes('机理') || query.includes('机理')) {
    selectedRoles.push('MechanismAgent')
  }
  if (query.includes('paper') || query.includes('manuscript') || query.includes('论文')) {
    selectedRoles.push('WritingAgent', 'ReviewerAgent')
  }
  if (selectedRoles.length === 0) {
    selectedRoles.push('LiteratureAgent', 'ExperimentAgent', 'DataAnalysisAgent', 'MechanismAgent')
  }

  // 2. Create workflow
  messages.push(makeMessage('CoordinatorAgent', 'all', `任务：${task.input}`, 'request', seq++))

  // 3. Dispatch messages and collect results
  const results: string[] = []
  let totalConfidence = 0
  for (const role of selectedRoles) {
    const agentId = role.toLowerCase()
    const agentTask: AgentTask = { ...task, id: `${task.id}-${agentId}`, agentId }
    messages.push(makeMessage('CoordinatorAgent', agentId, `委派任务：${task.input}`, 'request', seq++))
    const out = executeAgentByRole(role, agentTask)
    results.push(`[${role}]: ${out.result}`)
    messages.push(makeMessage(agentId, 'CoordinatorAgent', out.result, 'response', seq++))
    totalConfidence += out.confidence
  }

  const confidence = results.length > 0 ? totalConfidence / results.length : 0
  const finalResult = results.join('\n')

  messages.push(makeMessage('CoordinatorAgent', 'all', `协调完成：综合置信度 ${confidence.toFixed(2)}`, 'suggestion', seq++))

  return { agents: selectedRoles, messages, finalResult, confidence }
}
