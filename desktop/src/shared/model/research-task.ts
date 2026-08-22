// Research Task Model (Phase 6-C2: Agent Capability Router).
//
// Phase 6-C2: typed research tasks that map to required ResearchCapabilities.
// The Agent Router (Phase 6-C2 capability-router.ts) consumes these to pick
// the best provider+model for a given task.
//
// Phase 6-C2 frozen contract:
//   - ResearchTaskType = 9-tag enum (research workflow taxonomy)
//   - ResearchTaskProfile = typed task descriptor
//   - BUILT_IN_TASK_PROFILES = canonical mapping taskType -> required caps
//   - NEVER contains apiKey / token / cipher

import {
  type ResearchCapability,
  isValidResearchCapability
} from './research-capability'

/**
 * Phase 6-C2: research task taxonomy.
 *
 * Distinct from ResearchCapability (which describes WHAT a model can do).
 * ResearchTaskType describes WHAT the user wants to do. The router uses
 * BUILT_IN_TASK_PROFILES to translate task -> required capabilities.
 */
export type ResearchTaskType =
  | 'literature-review'
  | 'paper-writing'
  | 'coding'
  | 'matlab'
  | 'python-analysis'
  | 'cfd-analysis'
  | 'image-analysis'
  | 'experiment-design'
  | 'data-analysis'

/**
 * Phase 6-C2: renderable label for UI.
 */
export function researchTaskLabel(t: ResearchTaskType): string {
  switch (t) {
    case 'literature-review': return 'Literature Review'
    case 'paper-writing': return 'Paper Writing'
    case 'coding': return 'Coding'
    case 'matlab': return 'MATLAB'
    case 'python-analysis': return 'Python Analysis'
    case 'cfd-analysis': return 'CFD Analysis'
    case 'image-analysis': return 'Image Analysis'
    case 'experiment-design': return 'Experiment Design'
    case 'data-analysis': return 'Data Analysis'
  }
}

/**
 * Phase 6-C2: validate ResearchTaskType shape.
 */
export function isValidResearchTaskType(t: unknown): t is ResearchTaskType {
  return (
    t === 'literature-review' ||
    t === 'paper-writing' ||
    t === 'coding' ||
    t === 'matlab' ||
    t === 'python-analysis' ||
    t === 'cfd-analysis' ||
    t === 'image-analysis' ||
    t === 'experiment-design' ||
    t === 'data-analysis'
  )
}

/**
 * Phase 6-C2: research task descriptor — the input to the Agent Router.
 *
 * `requiredCapabilities` MUST contain at least one valid ResearchCapability.
 * `optionalCapabilities` adds extra capability that boosts the score but
 * is not strictly required (e.g. 'paper-writing' is required but
 * 'data-analysis' is optional for a literature review that may include
 * citation stats).
 */
export interface ResearchTaskProfile {
  taskType: ResearchTaskType
  requiredCapabilities: ResearchCapability[]
  optionalCapabilities?: ResearchCapability[]
  /** Priority 0-10; higher = prefer this task's picks. Default 5. */
  priority?: number
}

/**
 * Phase 6-C2: validate a ResearchTaskProfile shape.
 *
 * Phase 6-C2 strict: rejects payloads containing apiKey / cipher.
 */
export function isValidResearchTaskProfile(p: unknown): p is ResearchTaskProfile {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (!isValidResearchTaskType(o.taskType)) return false
  if (!Array.isArray(o.requiredCapabilities) || o.requiredCapabilities.length === 0) return false
  for (const cap of o.requiredCapabilities) {
    if (!isValidResearchCapability(cap)) return false
  }
  if (o.optionalCapabilities !== undefined && !Array.isArray(o.optionalCapabilities)) return false
  if (o.optionalCapabilities !== undefined) {
    for (const cap of o.optionalCapabilities) {
      if (!isValidResearchCapability(cap)) return false
    }
  }
  if (o.priority !== undefined && (typeof o.priority !== 'number' || o.priority < 0 || o.priority > 10)) return false
  const dump = JSON.stringify(p)
  if (dump.includes('sk-') || dump.includes('apiKey') || dump.includes('cipher')) return false
  return true
}

/**
 * Phase 6-C2: built-in canonical task -> required capabilities mapping.
 * Used by the Agent Router to translate a task type into a capability spec.
 *
 * Phase 6-C2 strict: this table is the single source of truth for task routing.
 * Any new task type MUST be added here AND in ResearchTaskType.
 */
export const BUILT_IN_TASK_PROFILES: Readonly<Record<ResearchTaskType, ResearchTaskProfile>> = Object.freeze({
  'literature-review': {
    taskType: 'literature-review',
    requiredCapabilities: ['literature'],
    optionalCapabilities: ['paper-writing'],
    priority: 5
  },
  'paper-writing': {
    taskType: 'paper-writing',
    requiredCapabilities: ['paper-writing'],
    optionalCapabilities: ['literature'],
    priority: 5
  },
  'coding': {
    taskType: 'coding',
    requiredCapabilities: ['coding'],
    optionalCapabilities: ['python'],
    priority: 5
  },
  'matlab': {
    taskType: 'matlab',
    requiredCapabilities: ['matlab'],
    optionalCapabilities: ['math'],
    priority: 5
  },
  'python-analysis': {
    taskType: 'python-analysis',
    requiredCapabilities: ['python', 'data-analysis'],
    optionalCapabilities: ['math'],
    priority: 5
  },
  'cfd-analysis': {
    taskType: 'cfd-analysis',
    requiredCapabilities: ['cfd'],
    optionalCapabilities: ['math', 'python'],
    priority: 5
  },
  'image-analysis': {
    taskType: 'image-analysis',
    requiredCapabilities: ['image-analysis'],
    priority: 5
  },
  'experiment-design': {
    taskType: 'experiment-design',
    requiredCapabilities: ['coding'],
    optionalCapabilities: ['data-analysis', 'math'],
    priority: 5
  },
  'data-analysis': {
    taskType: 'data-analysis',
    requiredCapabilities: ['data-analysis'],
    optionalCapabilities: ['python', 'math'],
    priority: 5
  }
})

/**
 * Phase 6-C2: resolve a ResearchTaskType -> ResearchTaskProfile.
 * Falls back to a generic chat profile if the type is unknown.
 */
export function resolveTaskProfile(taskType: ResearchTaskType): ResearchTaskProfile {
  return BUILT_IN_TASK_PROFILES[taskType] ?? {
    taskType,
    requiredCapabilities: ['chat'],
    priority: 5
  }
}
