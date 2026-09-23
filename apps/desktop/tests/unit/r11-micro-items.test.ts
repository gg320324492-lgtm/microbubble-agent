// R-11 阶段 A 微项 —— ①系统提示补模型身份 ②todowrite 按序号操作
import { describe, expect, it } from 'vitest'
import { buildAgentSystemPrompt } from '@main/agent/agent-loop.service'
import { createTodoWriteTool, TodoStore } from '@main/agent/tools/todowrite'

/** 真实会话级清单 store（与生产同一实现） */
function makeStore(): TodoStore {
  return new TodoStore()
}

type Tool = { execute: (i: Record<string, unknown>, c: Record<string, unknown>) => Promise<{ ok: boolean; summary?: string; data?: unknown }> }

/** 按生产用法调用（AgentTool.execute） */
async function run(tool: Tool, input: Record<string, unknown>): Promise<{ ok: boolean; summary?: string; data?: unknown }> {
  return tool.execute(input, { sessionId: 's1', userId: 'u1', workspaceRoot: '/w' })
}

describe('R-11 微项① — 系统提示标明模型身份', () => {
  it('★ 两个分支（有/无工作区）都含「由 MiMo 大模型驱动」', () => {
    const withWs = buildAgentSystemPrompt('E:/tmp/ws')
    const noWs = buildAgentSystemPrompt(null)
    expect(withWs).toContain('由 MiMo 大模型驱动')
    expect(noWs).toContain('由 MiMo 大模型驱动')
  })

  it('★ 有工作区分支显式禁止自称本地回声/离线模型（R-10 冒烟抓到的身份混乱）', () => {
    const p = buildAgentSystemPrompt('E:/tmp/ws')
    expect(p).toContain('不要自称本地回声')
    expect(p).toContain('离线模型')
  })

  it('提示词其余铁律未被破坏（回归）', () => {
    const p = buildAgentSystemPrompt('E:/tmp/ws')
    expect(p).toContain('工作区根目录')
    expect(p).toContain('.git 目录为禁区')
    expect(p).toContain('回答用中文')
  })
})

describe('R-11 微项② — todowrite 按序号操作', () => {
  it('★ 用 index（从 1 开始）start 指定任务，等价于用 id', async () => {
    const tool = createTodoWriteTool({ store: makeStore() })
    await run(tool as never, { action: 'add', text: '第一步' })
    await run(tool as never, { action: 'add', text: '第二步' })
    // 按序号 2 开始「第二步」
    const r = await run(tool as never, { action: 'start', index: 2 })
    expect(r.ok).toBe(true)
    const items = (r.data as { todos: { text: string; status: string }[] }).todos
    expect(items.find((i) => i.text === '第二步')?.status).toBe('in_progress')
    expect(items.find((i) => i.text === '第一步')?.status).toBe('pending')
  })

  it('★ 序号越界 → 明确报错（不静默操作错的任务）', async () => {
    const tool = createTodoWriteTool({ store: makeStore() })
    await run(tool as never, { action: 'add', text: '唯一任务' })
    const r = await run(tool as never, { action: 'complete', index: 5 })
    expect(r.ok).toBe(false)
    expect(r.summary).toContain('超出范围')
    expect(r.summary).toContain('共 1 项')
  })

  it('★ id 优先于 index（两者都给时以 id 为准）', async () => {
    const tool = createTodoWriteTool({ store: makeStore() })
    const a = await run(tool as never, { action: 'add', text: '甲' })
    await run(tool as never, { action: 'add', text: '乙' })
    const idOfA = (a.data as { todos: { id: string; text: string }[] }).todos.find((i) => i.text === '甲')!.id
    // id 指向「甲」，index=2 指向「乙」→ 应以 id 为准（完成「甲」）
    const r = await run(tool as never, { action: 'complete', id: idOfA, index: 2 })
    expect(r.ok).toBe(true)
    const items = (r.data as { todos: { text: string; status: string }[] }).todos
    expect(items.find((i) => i.text === '甲')?.status).toBe('done')
    expect(items.find((i) => i.text === '乙')?.status).toBe('pending')
  })

  it('两者都缺 → 明确提示缺参数（错误信息同时提到 id 与 index）', async () => {
    const tool = createTodoWriteTool({ store: makeStore() })
    await run(tool as never, { action: 'add', text: 'x' })
    const r = await run(tool as never, { action: 'start' })
    expect(r.ok).toBe(false)
    expect(r.summary).toContain('index')
  })
})
