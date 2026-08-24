// Research Event Bus — 强类型事件发射器。

export type ResearchEventType =
  | 'project.created' | 'project.updated' | 'project.completed'
  | 'task.started' | 'task.completed' | 'task.failed'
  | 'experiment.finished' | 'analysis.finished' | 'paper.generated'
  | 'workflow.started' | 'workflow.completed' | 'workflow.failed'

export const RESEARCH_EVENT_TYPES: readonly ResearchEventType[] = Object.freeze([
  'project.created', 'project.updated', 'project.completed',
  'task.started', 'task.completed', 'task.failed',
  'experiment.finished', 'analysis.finished', 'paper.generated',
  'workflow.started', 'workflow.completed', 'workflow.failed'
])

export interface ResearchEvent {
  type: ResearchEventType
  payload: Record<string, unknown>
  timestamp: number
}

export type EventListener = (event: ResearchEvent) => void

export class ResearchEventBus {
  private listeners: Map<ResearchEventType, Set<EventListener>> = new Map()
  private allListeners: Set<EventListener> = new Map() as never
  private history: ResearchEvent[] = []

  emit(type: ResearchEventType, payload: Record<string, unknown> = {}): ResearchEvent {
    const event: ResearchEvent = { type, payload, timestamp: Date.now() }
    this.history.push(event)
    const set = this.listeners.get(type)
    if (set) {
      for (const fn of [...set]) {
        try { fn(event) } catch { /* listener errors must not break emission */ }
      }
    }
    return event
  }

  subscribe(type: ResearchEventType, listener: EventListener): () => void {
    let set = this.listeners.get(type)
    if (!set) { set = new Set(); this.listeners.set(type, set) }
    set.add(listener)
    return () => { set!.delete(listener) }
  }

  getHistory(): ResearchEvent[] {
    return [...this.history]
  }

  clear(): void {
    this.listeners.clear()
    this.history = []
  }
}
