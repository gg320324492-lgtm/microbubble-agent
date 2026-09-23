// todowrite 工具 + 会话级清单存储（工单 M8-3 §7）— 第 10 个工具。
//
// 存储语义：**会话内持久** —— 一次会话期间跨轮次、跨消息保留；应用退出即清空
// （工单口径「会话内持久（IPC 存储）」，不做跨会话持久化）。
// 渲染层通过 IPC 读取同一份数据渲染清单卡片。

import type { AgentTool, ToolResult } from '../tool-registry'
import { addTodo, emptyList, normalizeList, removeTodo, renderForModel, setTodoStatus, todoSummary, type TodoList, type TodoStatus } from '../todos'

/** 会话级清单存储（内存；进程退出即清空） */
export class TodoStore {
  private readonly bySession = new Map<string, TodoList>()

  get(sessionId: string): TodoList {
    return this.bySession.get(sessionId) ?? emptyList(sessionId)
  }

  set(list: TodoList): void {
    this.bySession.set(list.sessionId, normalizeList(list, list.sessionId))
  }

  clear(sessionId: string): void {
    this.bySession.delete(sessionId)
  }
}

export interface TodoToolDeps {
  store: TodoStore
  now?: () => number
}

const ACTIONS = ['add', 'start', 'complete', 'reopen', 'remove', 'list'] as const
type TodoAction = (typeof ACTIONS)[number]

function parseStatus(action: TodoAction): TodoStatus | null {
  if (action === 'start') return 'in_progress'
  if (action === 'complete') return 'done'
  if (action === 'reopen') return 'pending'
  return null
}

/**
 * 工具工厂：需要注入 store（会话级共享），故不是单例常量。
 * 参数刻意保持最小：action + text/id，降低模型用错的概率。
 */
export function createTodoWriteTool(deps: TodoToolDeps): AgentTool {
  const now = deps.now ?? ((): number => Date.now())
  return {
    name: 'todowrite',
    description:
      '维护本次会话的任务清单（三态：待办/进行中/已完成）。多步任务开始时先 add 列出步骤，' +
      '开始一步用 start、完成用 complete；同一时刻只会有一个「进行中」。action=list 可查看当前清单。',
    permission: 'auto',
    parameters: {
      type: 'object',
      properties: {
        action: { type: 'string', description: `操作：${ACTIONS.join(' / ')}`, enum: [...ACTIONS] },
        text: { type: 'string', description: 'action=add 时的任务内容' },
        id: { type: 'string', description: 'start/complete/reopen/remove 时的任务 id' }
      },
      required: ['action']
    },
    async execute(input, ctx): Promise<ToolResult> {
      const action = String(input['action'] ?? '') as TodoAction
      if (!(ACTIONS as readonly string[]).includes(action)) {
        return { ok: false, summary: `未知 action: ${action || '(空)'}`, error: 'action 非法' }
      }
      const sessionId = ctx.sessionId ?? ctx.userId
      let list = deps.store.get(sessionId)
      const t = now()

      if (action === 'add') {
        const res = addTodo(list, String(input['text'] ?? ''), t)
        if (!res.ok) return { ok: false, summary: res.error ?? '新增失败', error: res.error }
        list = res.list
      } else if (action === 'list') {
        // 与其它分支保持一致的输出形状（此前漏了 rendered，测试抓到）
        return {
          ok: true,
          summary: `任务清单：${todoSummary(list).text}`,
          data: { todos: list.items, summary: todoSummary(list), rendered: renderForModel(list) }
        }
      } else {
        let id = String(input['id'] ?? '')
        // R-11 微项：允许按序号操作（从 1 开始，对应 list 输出顺序）——
        // 模型记 id 容易错，按序号更稳。id 优先，index 兜底。
        if (!id) {
          const rawIndex = input['index']
          const idx = typeof rawIndex === 'number' ? rawIndex : Number(rawIndex)
          if (Number.isFinite(idx) && idx >= 1 && idx <= list.items.length) {
            id = list.items[idx - 1]!.id
          } else if (rawIndex !== undefined) {
            return {
              ok: false,
              summary: `序号 ${String(rawIndex)} 超出范围（当前共 ${list.items.length} 项）`,
              error: '序号非法'
            }
          }
        }
        if (!id) return { ok: false, summary: '缺少 id 或 index 参数', error: '缺少 id/index' }
        const res =
          action === 'remove' ? removeTodo(list, id) : setTodoStatus(list, id, parseStatus(action) ?? 'pending', t)
        if (!res.ok) return { ok: false, summary: res.error ?? '操作失败', error: res.error }
        list = res.list
      }

      deps.store.set(list)
      const summary = todoSummary(list)
      return {
        ok: true,
        summary: `任务清单已更新：${summary.text}`,
        data: {
          todos: list.items,
          summary,
          rendered: renderForModel(list)
        }
      }
    }
  }
}
