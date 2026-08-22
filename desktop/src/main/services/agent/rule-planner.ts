// Rule-Based Planner (Phase 8-B0: Research Intent Understanding + Planner Core).
//
// Phase 8-B0: turns a ResearchIntent into a deterministic ResearchPlan by
// expanding a fixed rule template for the detected task type. NO LLM call.
//
// Templates (StepType chain — Phase 8-B0 rules):
//   experiment-analysis: knowledge -> tool(analysis) -> tool(visualization) -> synthesis
//   literature-review:   knowledge -> synthesis
//   data-analysis:       knowledge -> analysis -> tool(visualization) -> synthesis
//   simulation:          knowledge -> tool(simulation) -> analysis -> tool(visualization) -> synthesis
//   paper-writing:       knowledge -> model -> synthesis
//
// Phase 8-B0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import model-provider / auth / chat / backend
//   - Deterministic: same intent => same plan (id derived from intent content)

import type { ResearchPlan, ResearchPlanStep, StepType } from '../../../shared/agent/research-plan-schema'
import { isValidResearchPlan } from '../../../shared/agent/research-plan-schema'
import type {
  ResearchIntent,
  PlannerTaskType
} from '../../../shared/agent/planner-schema'
import { PLANNER_TASK_TYPES } from '../../../shared/agent/planner-schema'

// ============ Rule templates ============

/**
 * Phase 8-B0: the deterministic step-type chain per task type.
 */
export const TEMPLATE_CHAINS: Readonly<Record<PlannerTaskType, readonly StepType[]>> = Object.freeze({
  'experiment-analysis': Object.freeze(['knowledge', 'tool', 'tool', 'synthesis'] as const),
  'literature-review': Object.freeze(['knowledge', 'synthesis'] as const),
  'data-analysis': Object.freeze(['knowledge', 'analysis', 'tool', 'synthesis'] as const),
  simulation: Object.freeze(['knowledge', 'tool', 'analysis', 'tool', 'synthesis'] as const),
  'paper-writing': Object.freeze(['knowledge', 'model', 'synthesis'] as const)
})

/** Phase 8-B0: which knowledge entity type each task queries first. */
const ENTITY_FOR_TASK: Readonly<Record<PlannerTaskType, string>> = Object.freeze({
  'literature-review': 'paper',
  'experiment-analysis': 'experiment',
  'data-analysis': 'dataset',
  simulation: 'experiment',
  'paper-writing': 'paper'
})

// ============ Deterministic helpers ============

/** djb2 — deterministic content hash for stable plan ids (no randomness). */
function hashStr(s: string): string {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = ((h * 33) ^ s.charCodeAt(i)) >>> 0
  }
  return h.toString(36).padStart(8, '0').slice(0, 8)
}

// ============ Step builders ============

function buildStep(params: {
  stepId: string
  type: StepType
  description: string
  input: Record<string, unknown>
  dependencies: string[]
}): ResearchPlanStep {
  return {
    id: params.stepId,
    type: params.type,
    description: params.description,
    input: params.input,
    dependencies: params.dependencies
  }
}

/**
 * Phase 8-B0: expand an intent into a plan using the task template.
 * Throws on invalid intent (missing topic/goal/taskType). Deterministic.
 */
export function createPlanFromIntent(intent: ResearchIntent): ResearchPlan {
  if (!intent || typeof intent !== 'object') {
    throw new Error('rule planner: intent required (Phase 8-B0 strict)')
  }
  if (typeof intent.topic !== 'string' || intent.topic.length === 0) {
    throw new Error('rule planner: intent.topic must be a non-empty string (Phase 8-B0 strict)')
  }
  if (typeof intent.goal !== 'string' || intent.goal.length === 0) {
    throw new Error('rule planner: intent.goal must be a non-empty string (Phase 8-B0 strict)')
  }
  if (!PLANNER_TASK_TYPES.includes(intent.taskType)) {
    throw new Error(`rule planner: unknown taskType '${String(intent.taskType)}' (Phase 8-B0 strict)`)
  }

  const chain = TEMPLATE_CHAINS[intent.taskType]
  const entityType = ENTITY_FOR_TASK[intent.taskType]
  const topic = intent.topic
  const goal = intent.goal
  const steps: ResearchPlanStep[] = []
  const completedIds: string[] = []
  const depsOf = (): string[] => (completedIds.length > 0 ? [completedIds[completedIds.length - 1]] : [])

  chain.forEach((type, idx) => {
    const stepId = `step:${idx + 1}:${type}`
    const deps = depsOf()
    let step: ResearchPlanStep

    switch (type) {
      case 'knowledge':
        step = buildStep({
          stepId,
          type,
          description: `Retrieve ${entityType} knowledge for topic '${topic}'`,
          input: { entityType, query: goal },
          dependencies: deps
        })
        break
      case 'tool':
        if (intent.taskType === 'simulation' && idx === 1) {
          step = buildStep({
            stepId,
            type,
            description: `Run simulation for '${topic}'`,
            input: { capability: 'simulation', params: { topic, goal } },
            dependencies: deps
          })
        } else if (intent.taskType === 'experiment-analysis' && idx === 1) {
          step = buildStep({
            stepId,
            type,
            description: `Analyze experiment for '${topic}'`,
            input: { toolId: 'tool:dataset-analysis', params: { query: goal } },
            dependencies: deps
          })
        } else {
          step = buildStep({
            stepId,
            type,
            description: `Visualize results for '${topic}'`,
            input: { toolId: 'tool:data-visualization', params: { plotType: 'result-plot' } },
            dependencies: deps
          })
        }
        break
      case 'model':
        step = buildStep({
          stepId,
          type,
          description: `Generate text for '${topic}'`,
          input: { prompt: `Write about '${topic}'. ${goal}` },
          dependencies: deps
        })
        break
      case 'analysis': {
        const sourceId = completedIds[completedIds.length - 1] ?? stepId.replace(':analysis:', ':knowledge:')
        step = buildStep({
          stepId,
          type,
          description: `Summarize source step '${sourceId}'`,
          input: { sourceStepId: sourceId, mode: 'summary' },
          dependencies: deps
        })
        break
      }
      case 'synthesis': {
        const sources = completedIds.length > 0 ? [...completedIds] : []
        step = buildStep({
          stepId,
          type,
          description: `Synthesize final answer for '${topic}'`,
          input: { format: 'summary', sourceStepIds: sources },
          dependencies: deps
        })
        break
      }
      default:
        throw new Error(`rule planner: unsupported step type '${String(type)}' (Phase 8-B0 strict)`)
    }

    steps.push(step)
    completedIds.push(stepId)
  })

  const plan: ResearchPlan = {
    id: `plan:${intent.taskType}:${hashStr(intent.topic + intent.goal)}`,
    goal: intent.goal,
    tasks: steps,
    status: 'pending',
    metadata: {
      planner: 'rule:v1',
      domain: intent.domain,
      taskType: intent.taskType,
      topic: intent.topic,
      constraints: intent.constraints
    }
  }

  if (!isValidResearchPlan(plan)) {
    throw new Error('rule planner: generated plan failed Phase 8-A0 validation (Phase 8-B0 strict)')
  }
  return plan
}

export const __testHelpers = {
  TEMPLATE_CHAINS,
  ENTITY_FOR_TASK,
  hashStr
}