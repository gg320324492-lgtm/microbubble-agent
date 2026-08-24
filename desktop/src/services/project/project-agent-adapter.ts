// Project Agent Adapter — 集成 ProjectManager ↔ AgentCoordinator。
import type { ProjectTask } from '../../shared/project/project-schema'
import type { AgentTask, AgentRole } from '../../shared/agents/agent-schema'
import { coordinate } from '../agents/agent-coordinator'
import type { ProjectManager } from './project-manager'

export function dispatchProjectTask(task: ProjectTask, manager: ProjectManager): { output: string; confidence: number } {
  const agentTask: AgentTask = {
    id: `agenttask-${task.id}`,
    agentId: task.agentRole.toLowerCase(),
    input: task.input || task.title,
    status: 'completed',
    confidence: 0.8
  }
  const result = coordinate(agentTask)
  manager.updateTaskStatus(task.id, 'completed', result.finalResult)
  return { output: result.finalResult, confidence: result.confidence }
}

export function dispatchAllReady(projectId: string, manager: ProjectManager): { executed: number; avgConfidence: number } {
  const project = manager.getProject(projectId)
  if (!project) return { executed: 0, avgConfidence: 0 }
  const completedIds = new Set<string>()
  for (const m of project.milestones) {
    void m
  }
  for (const t of project.tasks) {
    if (t.status === 'completed') completedIds.add(t.id)
  }
  let totalConfidence = 0
  let count = 0
  for (const task of project.tasks) {
    if (task.status !== 'pending') continue
    if (task.dependencies.every(d => completedIds.has(d))) {
      const result = dispatchProjectTask(task, manager)
      totalConfidence += result.confidence
      count++
    }
  }
  return { executed: count, avgConfidence: count > 0 ? totalConfidence / count : 0 }
}

export function validAgentRole(r: string): boolean {
  const valid: AgentRole[] = ['LiteratureAgent', 'ExperimentAgent', 'DataAnalysisAgent', 'MechanismAgent', 'WritingAgent', 'ReviewerAgent', 'CoordinatorAgent']
  return valid.includes(r as AgentRole)
}
