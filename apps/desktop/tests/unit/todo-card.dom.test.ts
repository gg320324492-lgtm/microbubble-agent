// M8-3 §6 任务清单卡片 —— 真挂载 DOM 断言
//
// 为什么必须有这条：M8-2 的教训是**模板结构性错误 typecheck 与普通单测都抓不到**
// （漏一个闭合标签 → 整块渲染失败，只有真机/真挂载才暴露）。故卡片 UI 必须真挂载验证。
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ToolCard from '@renderer/components/chat/ToolCard.vue'
import type { ToolCallRecord } from '@shared/types'

function todoCall(todos: { id: string; text: string; status: 'pending' | 'in_progress' | 'done' }[]): ToolCallRecord {
  return {
    id: 'tw',
    name: 'todowrite',
    input: { action: 'add' },
    status: 'ok',
    summary: '任务清单已更新',
    data: { todos, summary: { total: todos.length, done: todos.filter((t) => t.status === 'done').length, inProgress: 0, text: `1/${todos.length} 已完成` } }
  } as unknown as ToolCallRecord
}

describe('清单卡片 — 真挂载', () => {
  it('渲染三态条目：状态点 class + 完成项删除线', () => {
    const w = mount(ToolCard, {
      props: {
        call: todoCall([
          { id: 'a', text: '读材料', status: 'done' },
          { id: 'b', text: '写结论', status: 'in_progress' },
          { id: 'c', text: '校对', status: 'pending' }
        ]),
        live: false,
        interactive: false
      }
    })
    // 结构性：列表存在且有 3 条
    const list = w.find('[data-testid="todo-list"]')
    expect(list.exists()).toBe(true)
    expect(list.findAll('li')).toHaveLength(3)
    // 三态各自带对应 class（供样式区分颜色/删除线）
    expect(w.find('[data-testid="todo-done"]').exists()).toBe(true)
    expect(w.find('[data-testid="todo-in_progress"]').exists()).toBe(true)
    expect(w.find('[data-testid="todo-pending"]').exists()).toBe(true)
    expect(w.find('[data-testid="todo-done"]').classes()).toContain('todo-done')
    // 文本渲染
    expect(w.text()).toContain('读材料')
    expect(w.text()).toContain('写结论')
    // 摘要行
    expect(w.find('[data-testid="todo-summary"]').text()).toContain('已完成')
  })

  it('非 todowrite 调用不渲染清单（不误伤其它工具卡片）', () => {
    const w = mount(ToolCard, {
      props: {
        call: { id: 'x', name: 'read_file', input: { path: 'a' }, status: 'ok', summary: '已读取' } as unknown as ToolCallRecord,
        live: false,
        interactive: false
      }
    })
    expect(w.find('[data-testid="todo-list"]').exists()).toBe(false)
  })

  it('坏数据不炸（todos 非数组 / 缺字段）', () => {
    const w = mount(ToolCard, {
      props: {
        call: { id: 'tw', name: 'todowrite', input: {}, status: 'ok', summary: 's', data: { todos: 'oops' } } as unknown as ToolCallRecord,
        live: false,
        interactive: false
      }
    })
    expect(w.find('[data-testid="todo-list"]').exists()).toBe(false)
    const w2 = mount(ToolCard, {
      props: {
        call: todoCall([{ id: 'a', text: 'A', status: 'pending' }]),
        live: false,
        interactive: false
      }
    })
    expect(w2.findAll('li')).toHaveLength(1)
  })
})
