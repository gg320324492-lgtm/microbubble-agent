// Agent 循环契约（工单 C-2 §5）— 全部用假网关脚本化驱动，离线运行；
// 工具走真实 ToolRegistry + 真实临时目录工作区 + node:sqlite 审计
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { AuditService } from '@main/services/workspace/audit.service'
import { WorkspaceService } from '@main/services/workspace/workspace.service'
import { ToolRegistry } from '@main/agent/tool-registry'
import { AgentLoopService, MAX_AGENT_ROUNDS, buildAgentSystemPrompt, type LoopEvent } from '@main/agent/agent-loop.service'
import { listDirTool } from '@main/agent/tools/list-dir'
import { readFileTool } from '@main/agent/tools/read-file'
import type { AgentContentBlock, StreamTurnFn, StreamTurnRequest, StreamTurnResult, ToolUseBlock } from '@shared/types'
import type { ChatTurn } from '@main/services/model-gateway.service'

const fixtureRoot = mkdtempSync(join(tmpdir(), 'c2-loop-root-'))
const cleanup: string[] = []

beforeAll(() => {
  // AGENT.md 先于 setRoot 写入 — 验证「存在即跳过」且内容注入 system
  writeFileSync(join(fixtureRoot, 'AGENT.md'), 'AGENT-MARKER 自定义守则')
  writeFileSync(join(fixtureRoot, 'notes.md'), '工作区笔记')
})

afterAll(() => {
  for (const dir of [fixtureRoot, ...cleanup]) {
    try {
      rmSync(dir, { recursive: true, force: true })
    } catch {
      /* Windows 句柄延迟释放时忽略 */
    }
  }
})

function toolUse(id: string, name: string, input: Record<string, unknown>): ToolUseBlock {
  return { id, name, input }
}

function turnRes(partial: Partial<StreamTurnResult>): StreamTurnResult {
  return { stopReason: 'end_turn', text: '', thinking: '', toolUses: [], assistantBlocks: [], ...partial }
}

interface Harness {
  ws: WorkspaceService
  registry: ToolRegistry
  audit: AuditService
  requests: StreamTurnRequest[]
}

function makeHarness(opts: { withRoot?: boolean } = {}): Harness {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const audit = new AuditService(db)
  const store = mkdtempSync(join(tmpdir(), 'c2-loop-store-'))
  cleanup.push(store)
  const ws = new WorkspaceService(store)
  if (opts.withRoot !== false) ws.setRoot(fixtureRoot)
  const registry = new ToolRegistry(ws, audit)
  registry.register(listDirTool)
  registry.register(readFileTool)
  return { ws, registry, audit, requests: [] }
}

/** 假网关 — 按脚本逐轮流式返回；所有请求被记录供断言回喂结构 */
function scriptStream(h: Harness, script: Array<(call: number) => StreamTurnResult>): StreamTurnFn {
  let call = 0
  return async (_userId, _sessionId, req) => {
    h.requests.push(req)
    const step = script[Math.min(call, script.length - 1)]
    call++
    return step(call)
  }
}

const baseTurns: ChatTurn[] = [{ role: 'user', content: '看看工作区' }]
const run = (loop: AgentLoopService, emit: (e: LoopEvent) => void = () => undefined) =>
  loop.run({ userId: 'u1', sessionId: 's1', baseTurns, system: 'SYS', emit })

describe('AgentLoopService 全链路（ReAct）', () => {
  it('tool_use 停止 → 真实 invoke → tool_result 回喂 → end_turn，thinking 独立不混正文', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(
      scriptStream(h, [
        () =>
          turnRes({
            stopReason: 'tool_use',
            text: '我先看看目录。',
            thinking: '需要列出根目录内容',
            toolUses: [toolUse('t1', 'list_dir', { path: '.' })],
            assistantBlocks: [
              { type: 'text', text: '我先看看目录。' },
              { type: 'tool_use', id: 't1', name: 'list_dir', input: { path: '.' } }
            ]
          }),
        () =>
          turnRes({
            text: '目录里有 notes.md。',
            assistantBlocks: [{ type: 'text', text: '目录里有 notes.md。' }]
          })
      ]),
      h.registry,
      h.ws,
      h.audit
    )
    const events: LoopEvent[] = []
    const out = await run(loop, (e) => events.push(e))

    expect(out.content).toBe('我先看看目录。\n\n目录里有 notes.md。')
    expect(out.meta.thinking).toBe('需要列出根目录内容')
    expect(out.meta.rounds).toBe(2)
    expect(out.meta.tools?.[0]).toMatchObject({ id: 't1', name: 'list_dir', status: 'ok' })

    // 第二轮请求：assistant 回放 tool_use 块 + 相邻 user tool_result（ok）
    expect(h.requests).toHaveLength(2)
    const turns2 = h.requests[1].turns
    const asstBlocks = turns2[1].content as AgentContentBlock[]
    expect(turns2[1].role).toBe('assistant')
    expect(asstBlocks.some((b) => b.type === 'tool_use' && b.id === 't1')).toBe(true)
    const fed = turns2[2].content as AgentContentBlock[]
    expect(turns2[2].role).toBe('user')
    expect(fed[0]).toMatchObject({ type: 'tool_result', tool_use_id: 't1', is_error: false })
    expect(String((fed[0] as { content: string }).content)).toContain('"ok":true')

    // 工具卡片状态流转 + 轮次事件 + 审计前后各一条
    const toolStatuses = events.filter((e) => e.kind === 'tool').map((e) => (e.kind === 'tool' ? e.call.status : ''))
    expect(toolStatuses).toEqual(['running', 'ok'])
    expect(events.some((e) => e.kind === 'round' && e.round === 2)).toBe(true)
    expect(h.audit.list(10)).toHaveLength(2)
  })

  it('一次响应多个 tool_use 块 — 全部执行、结果按 id 顺序回喂', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(
      scriptStream(h, [
        () =>
          turnRes({
            stopReason: 'tool_use',
            toolUses: [toolUse('ta', 'list_dir', { path: '.' }), toolUse('tb', 'read_file', { path: 'notes.md' })],
            assistantBlocks: [
              { type: 'tool_use', id: 'ta', name: 'list_dir', input: { path: '.' } },
              { type: 'tool_use', id: 'tb', name: 'read_file', input: { path: 'notes.md' } }
            ]
          }),
        () => turnRes({ text: '都看完了。', assistantBlocks: [{ type: 'text', text: '都看完了。' }] })
      ]),
      h.registry,
      h.ws,
      h.audit
    )
    const out = await run(loop)
    expect(out.meta.tools?.map((t) => t.status)).toEqual(['ok', 'ok'])
    const fed = h.requests[1].turns[2].content as AgentContentBlock[]
    expect(fed.map((b) => (b.type === 'tool_result' ? b.tool_use_id : ''))).toEqual(['ta', 'tb'])
    expect(h.audit.list(10)).toHaveLength(4) // 2 工具 × 前后各一
    expect(out.content).toBe('都看完了。')
  })

  it('未注册工具 — catch 后回喂 ok:false 的 tool_result，循环继续到 end_turn', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(
      scriptStream(h, [
        () =>
          turnRes({
            stopReason: 'tool_use',
            toolUses: [toolUse('tz', 'no_such_tool', {})],
            assistantBlocks: [{ type: 'tool_use', id: 'tz', name: 'no_such_tool', input: {} }]
          }),
        () => turnRes({ text: '好的，没有这个工具。', assistantBlocks: [{ type: 'text', text: '好的，没有这个工具。' }] })
      ]),
      h.registry,
      h.ws,
      h.audit
    )
    const out = await run(loop)
    expect(out.meta.tools?.[0].status).toBe('error')
    const fed = h.requests[1].turns[2].content as AgentContentBlock[]
    expect(fed[0]).toMatchObject({ type: 'tool_result', tool_use_id: 'tz', is_error: true })
    expect(String((fed[0] as { content: string }).content)).toContain('"ok":false')
    expect(h.requests).toHaveLength(2) // 循环未被中断
    expect(out.content).toContain('没有这个工具')
  })

  it(`15 轮上限 — 第 ${MAX_AGENT_ROUNDS} 次请求后优雅终止并说明`, async () => {
    const h = makeHarness()
    let n = 0
    const loop = new AgentLoopService(
      async (_userId, _sessionId, req) => {
        h.requests.push(req)
        n++
        const id = `t${n}`
        return turnRes({
          stopReason: 'tool_use',
          toolUses: [toolUse(id, 'list_dir', { path: '.' })],
          assistantBlocks: [{ type: 'tool_use', id, name: 'list_dir', input: { path: '.' } }]
        })
      },
      h.registry,
      h.ws,
      h.audit
    )
    const out = await run(loop)
    expect(h.requests).toHaveLength(MAX_AGENT_ROUNDS)
    expect(out.meta.rounds).toBe(MAX_AGENT_ROUNDS)
    expect(out.meta.hitRoundCap).toBe(true)
    expect(out.content).toContain('15 轮')
  })

  it('用户停止 — 停在流式环节时部分内容保留，工具不再执行', async () => {
    const h = makeHarness()
    let loop!: AgentLoopService
    loop = new AgentLoopService(
      scriptStream(h, [
        () => {
          loop.stop('s1') // 模拟用户在第一轮流式期间按 Esc
          return turnRes({ stopReason: 'tool_use', text: '第一轮的部分内容', assistantBlocks: [{ type: 'text', text: '第一轮的部分内容' }] })
        },
        () => turnRes({ text: '不应到达' })
      ]),
      h.registry,
      h.ws,
      h.audit
    )
    const out = await run(loop)
    expect(out.meta.stopped).toBe(true)
    expect(out.content).toBe('第一轮的部分内容') // 已产生内容不丢
    expect(h.requests).toHaveLength(1) // 循环随即终止
    expect(out.meta.tools).toBeUndefined()
  })

  it('无工作区降级 — 不携带工具单轮收束，meta 标记 toolsAvailable=false', async () => {
    const h = makeHarness({ withRoot: false })
    const loop = new AgentLoopService(
      scriptStream(h, [() => turnRes({ text: '纯对话回答' })]),
      h.registry,
      h.ws,
      h.audit
    )
    const out = await run(loop)
    expect(out.content).toBe('纯对话回答')
    expect(out.meta.toolsAvailable).toBe(false)
    expect(out.meta.rounds).toBe(1)
    expect(h.requests[0].tools).toHaveLength(0)
  })
})

describe('Agent 系统提示词与工具定义', () => {
  it('system 注入工作区根、相对路径约定与 AGENT.md 节选', () => {
    const sys = buildAgentSystemPrompt(fixtureRoot)
    expect(sys).toContain(fixtureRoot)
    expect(sys).toContain('相对工作区')
    expect(sys).toContain('AGENT-MARKER')
    expect(buildAgentSystemPrompt(null)).toContain('未设置工作区')
  })

  it('buildToolDefs — registry 工具转 Anthropic input_schema 形状；无工作区返回空', () => {
    const h = makeHarness()
    const loop = new AgentLoopService(async () => turnRes({}), h.registry, h.ws, h.audit)
    const defs = loop.buildToolDefs()
    expect(defs).toHaveLength(2)
    for (const d of defs) {
      expect(Object.keys(d).sort()).toEqual(['description', 'input_schema', 'name'])
      expect(d.input_schema).toMatchObject({ type: 'object' })
    }
    const bare = makeHarness({ withRoot: false })
    expect(new AgentLoopService(async () => turnRes({}), bare.registry, bare.ws, bare.audit).buildToolDefs()).toEqual([])
  })
})
