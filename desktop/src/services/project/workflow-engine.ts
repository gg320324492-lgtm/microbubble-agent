// Workflow Engine — 科研工作流执行器。
import type { ScientificWorkflow, WorkflowStep, WorkflowStatus } from '../../shared/project/workflow-schema'
import type { ProjectTask } from '../../shared/project/project-schema'
import { coordinate } from '../agents/agent-coordinator'
import type { AgentTask } from '../../shared/agents/agent-schema'

export interface WorkflowExecutionResult {
  workflowId: string
  status: WorkflowStatus
  executedSteps: string[]
  outputs: Record<string, string>
  confidence: number
  errors: string[]
}

export class WorkflowEngine {
  execute(workflow: ScientificWorkflow, projectContext: { name: string; domain: string }): WorkflowExecutionResult {
    const executed: string[] = []
    const outputs: Record<string, string> = {}
    const errors: string[] = []
    let totalConfidence = 0
    let confidenceCount = 0
    const completedSteps = new Set<string>()

    let currentStepIds = workflow.steps.filter(s => s.nextSteps.length === 0).map(s => s.id)
    if (currentStepIds.length === 0) currentStepIds = workflow.steps.map(s => s.id)

    const reversed = currentStepIds.length > 0 && workflow.steps[0]?.nextSteps.includes(currentStepIds[0])
    const processingOrder = reversed ? [...workflow.steps].reverse() : workflow.steps

    for (const step of processingOrder) {
      try {
        const agentTask: AgentTask = {
          id: `wtask-${step.id}`,
          agentId: step.agent.toLowerCase(),
          input: `${step.type}: ${projectContext.name} - ${projectContext.domain}`,
          status: 'completed',
          confidence: 0.8
        }
        const result = coordinate(agentTask)
        executed.push(step.id)
        outputs[step.id] = result.finalResult
        totalConfidence += result.confidence
        confidenceCount++
        completedSteps.add(step.id)
      } catch (e) {
        errors.push(`Step ${step.id}: ${(e as Error).message}`)
      }
    }

    const finalConfidence = confidenceCount > 0 ? totalConfidence / confidenceCount : 0
    const status: WorkflowStatus = errors.length === 0 ? 'completed' : errors.length === processingOrder.length ? 'failed' : 'paused'

    return { workflowId: workflow.id, status, executedSteps: executed, outputs, confidence: finalConfidence, errors }
  }
}
