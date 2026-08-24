// Experiment Event Types — 扩展 ResearchEventBus 实验相关事件。
//
// 注意: 这是 ResearchEventBus 的扩展定义，不修改原 bus 实现，
// 通过强制类型转换让 bus 支持新的事件类型（保持向后兼容）。

export type ExperimentEventType =
  | 'experiment.created'
  | 'experiment.started'
  | 'experiment.recorded'
  | 'experiment.completed'
  | 'experiment.optimized'

export const EXPERIMENT_EVENT_TYPES: readonly ExperimentEventType[] = Object.freeze([
  'experiment.created', 'experiment.started', 'experiment.recorded',
  'experiment.completed', 'experiment.optimized'
])

export interface ExperimentCreatedPayload {
  experimentId: string
  projectId: string
  title: string
}

export interface ExperimentStartedPayload {
  experimentId: string
}

export interface ExperimentRecordedPayload {
  experimentId: string
  recordId: string
  operator: string
}

export interface ExperimentCompletedPayload {
  experimentId: string
  confidence: number
}

export interface ExperimentOptimizedPayload {
  experimentId: string
  nextPlanId: string
  suggestedVariables: string[]
}

/**
 * 安全扩展: 把 ExperimentEventType 当作 ResearchEventType 使用。
 * 因为事件总线的 emit 实际是 string-keyed Map, 严格类型仅是 nominal 区分。
 */
export function asResearchEventType(t: ExperimentEventType): string {
  return t
}

export function isExperimentEventType(s: string): s is ExperimentEventType {
  return (EXPERIMENT_EVENT_TYPES as readonly string[]).includes(s)
}

export const __testHelpers = { EXPERIMENT_EVENT_TYPES }