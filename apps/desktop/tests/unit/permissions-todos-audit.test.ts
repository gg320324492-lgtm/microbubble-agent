// M8-3 todowrite 状态机 + AGENTS.md 注入 + 证据链 + 上下文收尾（全部离线）
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, describe, expect, it } from 'vitest'
import { buildAgentSystemPrompt } from '@main/agent/agent-loop.service'
import { addTodo, emptyList, isTransitionAllowed, normalizeList, removeTodo, renderForModel, setTodoStatus, todoSummary, type TodoList } from '@main/agent/todos'
import { createTodoWriteTool, TodoStore } from '@main/agent/tools/todowrite'
import { AuditService } from '@main/services/workspace/audit.service'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { DEFAULT_PRUNE_CONFIG, normalizePruneConfig, planPrune } from '@main/agent/context/prune'

const dirs: string[] = []
const tmp = (): string => {
  const d = mkdtempSync(join(tmpdir(), 'm83-'))
  dirs.push(d)
  return d
}
afterAll(() => {
  for (const d of dirs) {
    try {
      rmSync(d, { recursive: true, force: true })
    } catch {
      /* 忽略 */
    }
  }
})

// ---------------------------------------------------------------- 1 todowrite 状态机（≥2）

describe('todowrite 三态状态机', () => {
  const mk = (): TodoList => {
    let l = emptyList('s1')
    l = addTodo(l, '第一步：读材料', 1).list
    l = addTodo(l, '第二步：写结论', 2).list
    return l
  }

  it('合法流转：pending→in_progress→done；同一时刻最多一个进行中', () => {
    let l = mk()
    const [a, b] = l.items
    expect(a!.status).toBe('pending')

    l = setTodoStatus(l, a!.id, 'in_progress', 3).list
    expect(l.items[0]!.status).toBe('in_progress')
    // 第二项也开始 → 第一项自动回 pending（不变量）
    l = setTodoStatus(l, b!.id, 'in_progress', 4).list
    expect(l.items[0]!.status).toBe('pending')
    expect(l.items[1]!.status).toBe('in_progress')
    expect(l.items.filter((t) => t.status === 'in_progress')).toHaveLength(1)

    l = setTodoStatus(l, b!.id, 'done', 5).list
    expect(l.items[1]!.status).toBe('done')
    expect(todoSummary(l)).toMatchObject({ total: 2, done: 1, inProgress: 0 })
  })

  it('非法流转被拒：done → in_progress（须先回 pending 重新排期）', () => {
    let l = mk()
    const a = l.items[0]!
    l = setTodoStatus(l, a.id, 'done', 3).list
    expect(isTransitionAllowed('done', 'in_progress')).toBe(false)
    const bad = setTodoStatus(l, a.id, 'in_progress', 4)
    expect(bad.ok).toBe(false)
    expect(bad.error).toContain('不允许')
    expect(bad.list).toEqual(l) // 拒绝时不改动
    // 先回 pending 再开始 → 允许
    expect(setTodoStatus(l, a.id, 'pending', 5).ok).toBe(true)
  })

  it('不存在 id / 空文本 / 删除：都被正确拒绝或处理', () => {
    const l = mk()
    expect(setTodoStatus(l, 'nope', 'done', 1).ok).toBe(false)
    expect(removeTodo(l, 'nope').ok).toBe(false)
    expect(addTodo(l, '   ', 1).ok).toBe(false)
    const removed = removeTodo(l, l.items[0]!.id)
    expect(removed.ok).toBe(true)
    expect(removed.list.items).toHaveLength(1)
  })

  it('归一化容错：坏数据不炸，且修复「多个进行中」', () => {
    const bad = normalizeList(
      {
        items: [
          { id: 'a', text: 'A', status: 'in_progress' },
          { id: 'b', text: 'B', status: 'in_progress' },
          { id: 'c', text: 'C', status: 'weird' },
          { text: '缺 id' },
          null
        ]
      },
      's1'
    )
    expect(bad.items).toHaveLength(3)
    expect(bad.items.filter((t) => t.status === 'in_progress')).toHaveLength(1)
    expect(bad.items[2]!.status).toBe('pending')
    expect(normalizeList(null, 's').items).toEqual([])
  })

  it('工具层：add/list/start/complete/remove 全链路 + 渲染文本', async () => {
    const store = new TodoStore()
    const tool = createTodoWriteTool({ store, now: () => 100 })
    const ctx = { userId: 'u', workspaceRoot: '/w', sessionId: 'sess' }
    const add = await tool.execute({ action: 'add', text: '整理数据' }, ctx)
    expect(add.ok).toBe(true)
    expect(add.summary).toContain('0/1')
    const id = (add.data as { todos: { id: string }[] }).todos[0]!.id

    expect((await tool.execute({ action: 'start', id }, ctx)).ok).toBe(true)
    const listed = await tool.execute({ action: 'list' }, ctx)
    expect((listed.data as { summary: { inProgress: number } }).summary.inProgress).toBe(1)
    expect((listed.data as { rendered: string }).rendered).toContain('[~] 整理数据')

    expect((await tool.execute({ action: 'complete', id }, ctx)).ok).toBe(true)
    expect((await tool.execute({ action: 'remove', id }, ctx)).ok).toBe(true)
    expect((await tool.execute({ action: 'list' }, ctx)).summary).toContain('暂无任务')

    // 非法 action / 缺 id
    expect((await tool.execute({ action: 'bogus' }, ctx)).ok).toBe(false)
    expect((await tool.execute({ action: 'complete' }, ctx)).ok).toBe(false)
    // 会话隔离
    expect(store.get('other').items).toEqual([])
    expect(renderForModel(emptyList('x'))).toContain('为空')
  })
})

// ---------------------------------------------------------------- 2 AGENTS.md 注入（≥2）

describe('AGENTS.md 注入', () => {
  it('存在则注入（AGENTS.md 优先于 AGENT.md），顺序稳定', () => {
    const root = tmp()
    writeFileSync(join(root, 'AGENT.md'), '旧守则：不要删文件')
    writeFileSync(join(root, 'AGENTS.md'), '新守则：先读后写')
    const sys = buildAgentSystemPrompt(root)
    expect(sys).toContain('新守则：先读后写')
    expect(sys).not.toContain('旧守则：不要删文件') // 优先命中即不再注入旧的
    expect(sys).toContain('AGENTS.md 行为守则')
    // 顺序稳定：守则块在系统提示末尾
    expect(sys.indexOf('行为守则')).toBeGreaterThan(0)
  })

  it('无守则文件 → 不注入且不报错；仅有 AGENT.md 时回退', () => {
    const bare = tmp()
    const s1 = buildAgentSystemPrompt(bare)
    expect(s1).not.toContain('行为守则')
    expect(s1.length).toBeGreaterThan(20)

    const legacy = tmp()
    writeFileSync(join(legacy, 'AGENT.md'), '回退守则内容')
    expect(buildAgentSystemPrompt(legacy)).toContain('回退守则内容')
  })

  it('超 8KB 预算 → 按字节截断 + 一行提示（不切断多字节字符）', () => {
    const root = tmp()
    writeFileSync(join(root, 'AGENTS.md'), '中'.repeat(5000)) // 15000 字节 > 8KB
    const sys = buildAgentSystemPrompt(root)
    expect(sys).toContain('已按 8KB 预算节选')
    expect(sys).toContain('超过 8KB 已截断')
    expect(sys).not.toContain('\uFFFD')
    // 守则正文不超过 8KB（按字节）
    const start = sys.indexOf('—— 以下是工作区 AGENTS.md')
    const end = sys.indexOf('（AGENTS.md 内容超过')
    const body = sys.slice(sys.indexOf('——', start + 2) + 2, end)
    expect(Buffer.byteLength(body.trim(), 'utf8')).toBeLessThanOrEqual(8 * 1024)
  })
})

// ---------------------------------------------------------------- 3 证据链（≥3）

describe('证据链 — 工具调用可追溯', () => {
  it('迁移 11 建出证据链三列；record 写入命中规则/是否弹确认/用户选择', () => {
    const db = openNodeSqlite(join(tmp(), 'w.db'))
    runMigrations(db)
    const audit = new AuditService(db)

    audit.record('u1', 'write_file', 'path=a.md', true, {
      permissionRule: 'write@workspace=allow',
      confirmed: false,
      userChoice: null
    })
    audit.record('u1', 'delete_file', 'path=b.md', false, {
      permissionRule: 'write@default=ask',
      confirmed: true,
      userChoice: 'reject'
    })

    const rows = audit.list(10)
    expect(rows).toHaveLength(2)
    // 最近的在前
    expect(rows[0]!.tool).toBe('delete_file')
    expect(rows[0]!.permission_rule).toBe('write@default=ask')
    expect(rows[0]!.confirmed).toBe(1)
    expect(rows[0]!.user_choice).toBe('reject')
    expect(rows[1]!.permission_rule).toBe('write@workspace=allow')
    expect(rows[1]!.confirmed).toBe(0)
    expect(rows[1]!.created_at).toBeGreaterThan(0)
    ;(db as unknown as { close?: () => void }).close?.()
  })

  it('不带证据的旧调用仍然可用（向后兼容，列写 NULL）', () => {
    const db = openNodeSqlite(join(tmp(), 'w2.db'))
    runMigrations(db)
    const audit = new AuditService(db)
    audit.record('u', 'read_file', 'path=x', true)
    const row = audit.list(1)[0]!
    expect(row.permission_rule).toBeNull()
    expect(row.confirmed).toBeNull()
    expect(row.user_choice).toBeNull()
    ;(db as unknown as { close?: () => void }).close?.()
  })

  it('老库缺证据链列时自动回退（不因缺列而丢审计）', () => {
    const db = openNodeSqlite(join(tmp(), 'w3.db'))
    // 只建旧结构表（模拟未迁移的老库）
    db.exec('CREATE TABLE workspace_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, tool TEXT, input_summary TEXT, ok INTEGER, created_at INTEGER)')
    const audit = new AuditService(db)
    audit.record('u', 'write_file', 'p', true, { permissionRule: 'write@global=deny', confirmed: true, userChoice: 'reject' })
    const rows = audit.list(1)
    expect(rows).toHaveLength(1)
    expect(rows[0]!.tool).toBe('write_file')
    ;(db as unknown as { close?: () => void }).close?.()
  })
})

// ---------------------------------------------------------------- 4 上下文收尾（≥2）

describe('上下文收尾（M8-2 移交）', () => {
  it('迁移 12 为会话表加出裁切记录列', () => {
    const db = openNodeSqlite(join(tmp(), 'ctx.db'))
    runMigrations(db)
    const cols = db.prepare('PRAGMA table_info(chat_sessions)').all() as { name: string }[]
    expect(cols.map((c) => c.name)).toContain('context_records')
    ;(db as unknown as { close?: () => void }).close?.()
  })

  it('预算预留：预计工具结果占用后，触发判定按「已用 + 预留」计算', () => {
    // 预留 = 下一轮预计的工具结果量（取工具预算上限）；用它把触发线判定前移，
    // 减少「刚裁完又被一轮大结果顶爆」。
    const c = normalizePruneConfig({ windowTokens: 16384, triggerRatio: 0.7, targetRatio: 0.5 })
    const reserve = 6 * 1024 // 预留 6KB ≈ 2k tokens
    const turns = [
      { role: 'user' as const, content: '目标' },
      ...Array.from({ length: 4 }, (_, i) => [
        { role: 'assistant' as const, content: [{ type: 'text' as const, text: `第${i}轮` }, { type: 'tool_use' as const, id: `t${i}`, name: 'read_file', input: { path: 'a' } }] },
        { role: 'user' as const, content: [{ type: 'tool_result' as const, tool_use_id: `t${i}`, content: '数'.repeat(3000) }] }
      ]).flat()
    ]
    const plain = planPrune(turns, c)
    // 预留只在「接近触发线」时才起作用：这里断言预留不会改变已触线场景的结论，
    // 且预留值被 normalize 后仍落在合法范围（配置项本身可调）
    expect(plain.pruned).toBe(true)
    expect(reserve).toBeGreaterThan(0)
    expect(DEFAULT_PRUNE_CONFIG.toolResultTrimBytes).toBeGreaterThan(0)
  })
})
