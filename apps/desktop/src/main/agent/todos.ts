// 任务清单三态状态机（工单 M8-3 §7）— 纯函数，零 Electron / 零依赖。
//
// 三态：pending（待办）/ in_progress（进行中）/ done（完成）
// 约束（工单要求「合法流转 / 非法流转拒绝」）：
//   · 同一时刻**最多一个** in_progress（模型多步任务的心智模型就是「一次做一件」）
//   · 合法流转：pending→in_progress→done，以及任意态回 pending（重新排期）
//   · 非法流转：done→in_progress（已完成的不要复活，避免清单来回跳）；
//     pending→done 允许（一步到位的小项）；done→pending 允许（返工）

export type TodoStatus = 'pending' | 'in_progress' | 'done'

export interface TodoItem {
  id: string
  text: string
  status: TodoStatus
  createdAt: number
  updatedAt: number
}

export interface TodoList {
  sessionId: string
  items: TodoItem[]
}

/** 合法流转表 */
const ALLOWED: Record<TodoStatus, readonly TodoStatus[]> = {
  pending: ['in_progress', 'done', 'pending'],
  in_progress: ['done', 'pending', 'in_progress'],
  done: ['pending'] // 已完成不允许直接复活为进行中（要先回 pending 重新排期）
}

export function isTransitionAllowed(from: TodoStatus, to: TodoStatus): boolean {
  return ALLOWED[from].includes(to)
}

export function emptyList(sessionId: string): TodoList {
  return { sessionId, items: [] }
}

export interface TodoMutationResult {
  ok: boolean
  list: TodoList
  /** 非法时给出中性原因（供模型改正） */
  error?: string
}

/** 新增一项（默认 pending；插入顺序即展示顺序） */
export function addTodo(list: TodoList, text: string, now: number, id?: string): TodoMutationResult {
  const trimmed = text.trim()
  if (!trimmed) return { ok: false, list, error: '任务内容不能为空' }
  const item: TodoItem = {
    id: id ?? `todo_${now}_${list.items.length + 1}`,
    text: trimmed,
    status: 'pending',
    createdAt: now,
    updatedAt: now
  }
  return { ok: true, list: { ...list, items: [...list.items, item] } }
}

/** 改状态（含「最多一个 in_progress」约束） */
export function setTodoStatus(list: TodoList, id: string, status: TodoStatus, now: number): TodoMutationResult {
  const idx = list.items.findIndex((t) => t.id === id)
  if (idx < 0) return { ok: false, list, error: `任务不存在: ${id}` }
  const current = list.items[idx]!
  if (!isTransitionAllowed(current.status, status)) {
    return { ok: false, list, error: `不允许从「${current.status}」直接变为「${status}」（已完成的请先回到 pending 再重新开始）` }
  }

  let items = list.items.map((t, i) => (i === idx ? { ...t, status, updatedAt: now } : t))
  // 最多一个 in_progress：新置进行中时，其它进行中的自动回 pending
  if (status === 'in_progress') {
    items = items.map((t, i) => (i === idx || t.status !== 'in_progress' ? t : { ...t, status: 'pending' as TodoStatus, updatedAt: now }))
  }
  return { ok: true, list: { ...list, items } }
}

/** 删除一项 */
export function removeTodo(list: TodoList, id: string): TodoMutationResult {
  const items = list.items.filter((t) => t.id !== id)
  if (items.length === list.items.length) return { ok: false, list, error: `任务不存在: ${id}` }
  return { ok: true, list: { ...list, items } }
}

/** 归一化（IPC 反序列化容错：坏数据不炸 UI） */
export function normalizeList(raw: unknown, sessionId: string): TodoList {
  const src = (raw ?? {}) as { items?: unknown }
  const items: TodoItem[] = []
  if (Array.isArray(src.items)) {
    for (const it of src.items) {
      const o = it as Partial<TodoItem>
      if (typeof o?.id !== 'string' || typeof o?.text !== 'string') continue
      const status: TodoStatus = o.status === 'in_progress' || o.status === 'done' ? o.status : 'pending'
      items.push({
        id: o.id,
        text: o.text,
        status,
        createdAt: typeof o.createdAt === 'number' ? o.createdAt : 0,
        updatedAt: typeof o.updatedAt === 'number' ? o.updatedAt : 0
      })
    }
  }
  // 不变量：最多一个 in_progress（坏数据可能带多个）
  let seenInProgress = false
  for (const it of items) {
    if (it.status === 'in_progress') {
      if (seenInProgress) it.status = 'pending'
      seenInProgress = true
    }
  }
  return { sessionId, items }
}

/** 进度摘要（回喂模型 / 卡片标题） */
export function todoSummary(list: TodoList): { total: number; done: number; inProgress: number; text: string } {
  const total = list.items.length
  const done = list.items.filter((t) => t.status === 'done').length
  const inProgress = list.items.filter((t) => t.status === 'in_progress').length
  const head = list.items.find((t) => t.status === 'in_progress')
  const text = total === 0 ? '暂无任务' : `${done}/${total} 已完成${head ? ` · 进行中：${head.text}` : ''}`
  return { total, done, inProgress, text }
}

/** 供模型阅读的清单文本 */
export function renderForModel(list: TodoList): string {
  if (list.items.length === 0) return '（任务清单为空）'
  const mark = (s: TodoStatus): string => (s === 'done' ? '[x]' : s === 'in_progress' ? '[~]' : '[ ]')
  return list.items.map((t) => `${mark(t.status)} ${t.text}`).join('\n')
}
