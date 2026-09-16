// C-3 confirm 链路 — 假网关驱动：批准 / 拒绝 / 停止取消三路径 + meta 回写（全部离线）
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { AuditService } from '@main/services/workspace/audit.service'
import { ChatService, parseMessageMeta } from '@main/services/chat.service'
import { WorkspaceService } from '@main/services/workspace/workspace.service'
import { ToolRegistry } from '@main/agent/tool-registry'
import { AgentLoopService, type LoopEvent } from '@main/agent/agent-loop.service'
import type { ToolContext } from '@main/agent/tool-registry'
import { listDirTool } from '@main/agent/tools/list-dir'
import { writeFileTool } from '@main/agent/tools/write-file'
import type { AgentContentBlock, MessageMeta, StreamTurnFn, StreamTurnRequest, StreamTurnResult, ToolUseBlock } from '@shared/types'
import type { ChatTurn } from '@main/services/model-gateway.service'

const cleanup: string[] = []

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
  root: string
  ctx: ToolContext
}

function makeHarness(): Harness {
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const audit = new AuditService(db)
  const store = mkdtempSync(join(tmpdir(), 'c3-c-store-'))
  const root = mkdtempSync(join(tmpdir(), 'c3-c-root-'))
  cleanup.push(store, root)
  const ws = new WorkspaceService(store)
  ws.setRoot(root)
  const registry = new ToolRegistry(ws, audit)
  registry.register(listDirTool)
  registry.register(writeFileTool)
  return { ws, registry, audit, requests: [], root: ws.getRoot() as string, ctx: { userId: "u1", workspaceRoot: ws.getRoot() as string } }
}

function scriptStream(h: Harness, script: Array<() => StreamTurnResult>): StreamTurnFn {
  let call = 0
  return async (_userId, _sessionId, req) => {
    h.requests.push(req)
    const step = script[Math.min(call, script.length - 1)]
    call++
    return step()
  }
}

const writeTurn = (id: string, path: string, content: string): StreamTurnResult =>
  turnRes({
    stopReason: 'tool_use',
    toolUses: [toolUse(id, 'write_file', { path, content })],
    assistantBlocks: [{ type: 'tool_use', id, name: 'write_file', input: { path, content } }]
  })

const baseTurns: ChatTurn[] = [{ role: 'user', content: '帮我写个文件' }]

afterEach(() => {
  vi.useRealTimers()
})

afterAll(() => {
  for (const dir of cleanup) {
    try {
      rmSync(dir, { recursive: true, force: true })
    } catch {
      /* Windows 句柄延迟释放时忽略 */
    }
  }
})

function toolStatuses(events: LoopEvent[]): string[] {
  return events.filter((e) => e.kind === 'tool').map((e) => (e.kind === 'tool' ? e.call.status : ''))
}

describe('confirm 链路（循环层拦截）', () => {
  it('批准 — invoke 执行 + 审计前后各一条 + 卡片 ok + diff 不进回喂', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(
      scriptStream(h, [() => writeTurn('tw', 'c3-approved.txt', 'hello c3'), () => turnRes({ text: '已写入。' })]),
      h.registry,
      h.ws,
      h.audit
    )
    const events: LoopEvent[] = []
    const runP = loop.run({ userId: 'u1', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })
    await vi.waitFor(() => {
      expect(events.some((e) => e.kind === 'tool' && e.call.status === 'awaiting_confirm')).toBe(true)
    })
    expect(loop.resolveConfirm('s1', 'tw', true)).toBe(true)
    const out = await runP

    expect(readFileSync(join(h.root, 'c3-approved.txt'), 'utf8')).toBe('hello c3') // 真实落盘
    expect(out.meta.tools?.[0]).toMatchObject({ id: 'tw', status: 'ok' })
    expect((out.meta.tools?.[0].data as { created: boolean }).created).toBe(true)
    expect(toolStatuses(events)).toEqual(['awaiting_confirm', 'running', 'ok'])
    expect(h.audit.list(10)).toHaveLength(2) // invoke 前后各一，无拒绝留痕
    // 回喂 ok；diff 留在卡片数据，不进模型上下文
    const fed = h.requests[1].turns[2].content as AgentContentBlock[]
    expect(fed[0]).toMatchObject({ type: 'tool_result', tool_use_id: 'tw', is_error: false })
    const fedText = String((fed[0] as { content: string }).content)
    expect(fedText).toContain('"ok":true')
    expect(fedText).not.toContain('diff')
  })

  it('拒绝 — 文件未动 + 拒绝留痕（ok:0）+ 回喂明确拒绝语义，循环可继续', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(
      scriptStream(h, [() => writeTurn('tr', 'c3-rejected.txt', '不应落盘'), () => turnRes({ text: '好的，不写了。' })]),
      h.registry,
      h.ws,
      h.audit
    )
    const events: LoopEvent[] = []
    const runP = loop.run({ userId: 'u1', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })
    await vi.waitFor(() => {
      expect(events.some((e) => e.kind === 'tool' && e.call.status === 'awaiting_confirm')).toBe(true)
    })
    loop.resolveConfirm('s1', 'tr', false)
    const out = await runP

    expect(existsSync(join(h.root, 'c3-rejected.txt'))).toBe(false) // 未执行
    expect(out.meta.tools?.[0]).toMatchObject({ status: 'rejected', summary: '用户拒绝执行' })
    expect(toolStatuses(events)).toEqual(['awaiting_confirm', 'rejected'])
    const rows = h.audit.list(10)
    expect(rows).toHaveLength(1) // 仅拒绝留痕一条
    expect(rows[0]).toMatchObject({ tool: 'write_file', ok: 0 })
    expect(rows[0].input_summary).toContain('用户拒绝')
    const fed = h.requests[1].turns[2].content as AgentContentBlock[]
    expect(fed[0]).toMatchObject({ type: 'tool_result', tool_use_id: 'tr', is_error: true })
    expect(String((fed[0] as { content: string }).content)).toContain('"denied":true')
    expect(out.content).toContain('不写了') // 循环未被卡死
  })

  it('停止取消等待 — 按停止收尾，不执行、无拒绝留痕、已产生内容保留', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(
      scriptStream(h, [() => writeTurn('ts', 'c3-stopped.txt', '不应落盘'), () => turnRes({ text: '不应到达' })]),
      h.registry,
      h.ws,
      h.audit
    )
    const events: LoopEvent[] = []
    const runP = loop.run({ userId: 'u1', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })
    await vi.waitFor(() => {
      expect(events.some((e) => e.kind === 'tool' && e.call.status === 'awaiting_confirm')).toBe(true)
    })
    loop.stop('s1') // 用户在等待确认时按 Esc
    const out = await runP

    expect(out.meta.stopped).toBe(true)
    expect(existsSync(join(h.root, 'c3-stopped.txt'))).toBe(false)
    expect(h.audit.list(10)).toHaveLength(0)
    expect(h.requests).toHaveLength(1)
    expect(out.meta.tools?.[0].status).toBe('awaiting_confirm') // 未决确认原样保留（UI 降级展示）
  })

  it('resolveConfirm 幂等保护 — 重复/过期确认返回 false', async () => {
    const h = makeHarness()
    const loop = new AgentLoopService(async (_u, _s, req) => {
      h.requests.push(req)
      return turnRes({ text: 'done' })
    }, h.registry, h.ws, h.audit)
    expect(loop.resolveConfirm('s1', 'ghost', true)).toBe(false)
  })
})

describe('meta 回写与未决确认持久化', () => {
  it('未决确认原样存库；patchToolCall 回写卡片状态（回滚/拒绝落库）', async () => {
    const db = openNodeSqlite(':memory:')
    runMigrations(db)
    const chat = new ChatService(db)
    const s = chat.createSession('user-a')
    const meta: MessageMeta = {
      tools: [{ id: 'tw', name: 'write_file', input: { path: 'x' }, status: 'awaiting_confirm', summary: '等待确认' }]
    }
    await chat.send('user-a', s.id, '问题', async () => ({ content: '答', meta }))
    const rows = chat.listMessages('user-a', s.id)
    const assistant = rows.find((r) => r.role === 'assistant')
    expect(parseMessageMeta(assistant?.meta)?.tools?.[0].status).toBe('awaiting_confirm')

    const messageId = assistant!.id
    expect(chat.patchToolCall('user-a', s.id, messageId, 'tw', { status: 'rejected', summary: '用户拒绝执行' })).toBe(true)
    const after = chat.getMessage('user-a', s.id, messageId)
    expect(parseMessageMeta(after?.meta)?.tools?.[0]).toMatchObject({ status: 'rejected', summary: '用户拒绝执行' })
    expect(chat.patchToolCall('user-a', s.id, messageId, 'ghost', { status: 'rejected' })).toBe(false)
    expect(chat.getMessage('user-a', s.id, 'm-nope')).toBeNull()
    db.close()
  })

  it('write_file 成功后回滚链路数据完整 — data 含 backupPath 供回滚', async () => {
    const h = makeHarness()
    writeFileSync(join(h.root, 'rb.txt'), '原始内容')
    const res = await h.registry.invoke('write_file', { path: 'rb.txt', content: '新内容' }, h.ctx)
    const data = res.data as { backupPath: string; rolledBack?: boolean }
    expect(data.backupPath).toBeTruthy()
    expect(readFileSync(join(h.root, data.backupPath), 'utf8')).toBe('原始内容')
    // 模拟回滚后的 meta 标记
    expect(h.registry.get('write_file')?.permission).toBe('confirm')
    expect(data.rolledBack).toBeUndefined()
  })
})
