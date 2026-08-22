// Agent Interaction Model (Phase 5-E: User Action Foundation).
//
// 纯 TypeScript, 0 依赖. 不修改 Phase 3-B0 frozen schema / Chat API / SSE.

export type UserActionType =
  | 'suggestion'
  | 'retry'
  | 'confirm'
  | 'cancel'
  | 'sync'

export interface UserAction {
  id: string
  label: string
  type: UserActionType
  payload?: Record<string, unknown>
  disabled?: boolean
}

export function suggestionAction(id: string, label: string, payload?: Record<string, unknown>): UserAction {
  return { id, label, type: 'suggestion', payload }
}

export function retryAction(id: string, label = '重试'): UserAction {
  return { id, label, type: 'retry' }
}

export function confirmAction(id: string, label: string, payload?: Record<string, unknown>): UserAction {
  return { id, label, type: 'confirm', payload }
}

export function cancelAction(id: string, label = '取消'): UserAction {
  return { id, label, type: 'cancel' }
}

export function syncAction(id: string, label = '重新加载'): UserAction {
  return { id, label, type: 'sync' }
}

export function parseSuggestions(input: unknown): UserAction[] {
  if (!Array.isArray(input)) return []
  const out: UserAction[] = []
  for (let i = 0; i < input.length; i++) {
    const raw = input[i]
    let id = ''
    let label = ''
    if (typeof raw === 'string') {
      id = `s_${i}`
      label = raw
    } else if (raw && typeof raw === 'object') {
      const o = raw as { id?: string; text?: string; label?: string }
      id = o.id ?? `s_${i}`
      label = o.label ?? o.text ?? ''
    } else {
      continue
    }
    if (!label) continue
    out.push(suggestionAction(id, label))
  }
  return out
}

export function mergeUserActions(a: UserAction[], b: UserAction[]): UserAction[] {
  const seen = new Set<string>()
  const out: UserAction[] = []
  for (const x of a) {
    if (!seen.has(x.id)) {
      seen.add(x.id)
      out.push(x)
    }
  }
  for (const x of b) {
    if (!seen.has(x.id)) {
      seen.add(x.id)
      out.push(x)
    }
  }
  return out
}

export interface UserActionSummary {
  total: number
  suggestion: number
  retry: number
  confirm: number
  cancel: number
  sync: number
}

export function summarizeUserActions(items: ReadonlyArray<UserAction>): UserActionSummary {
  const s: UserActionSummary = {
    total: items.length,
    suggestion: 0, retry: 0, confirm: 0, cancel: 0, sync: 0
  }
  for (const it of items) {
    if (it.type === 'suggestion') s.suggestion++
    else if (it.type === 'retry') s.retry++
    else if (it.type === 'confirm') s.confirm++
    else if (it.type === 'cancel') s.cancel++
    else if (it.type === 'sync') s.sync++
  }
  return s
}

export type AgentActionHandler = (
  action: UserAction
) => void | Promise<void>

export interface AgentActionHandlers {
  retry: AgentActionHandler
  cancel: AgentActionHandler
  sync: AgentActionHandler
  action: AgentActionHandler
}
