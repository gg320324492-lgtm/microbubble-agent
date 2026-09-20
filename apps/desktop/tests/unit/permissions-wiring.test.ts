// M8-3 接线集成测试 —— 权限三值走真实循环、guard 经 AbortSource 中止、steering 轮边界注入
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, describe, expect, it, vi } from 'vitest'
import { AgentLoopService, type LoopEvent, type PermissionPort } from '@main/agent/agent-loop.service'
import { ToolRegistry } from '@main/agent/tool-registry'
import { WorkspaceService } from '@main/services/workspace/workspace.service'
import { AuditService } from '@main/services/workspace/audit.service'
import { openNodeSqlite } from '@main/db/adapters'
import { runMigrations } from '@main/db/migrations'
import { readFileTool } from '@main/agent/tools/read-file'
import { writeFileTool } from '@main/agent/tools/write-file'
import { listDirTool } from '@main/agent/tools/list-dir'
import { EMPTY_STORE, applyRule, resolvePermission, ruleFromChoice, type PermissionStore, type RememberChoice, type ToolCategory } from '@main/agent/permissions/policy'
import type { AgentContentBlock, StreamTurnFn, StreamTurnRequest, StreamTurnResult, ToolUseBlock } from '@shared/types'

const dirs: string[] = []
afterAll(() => {
  for (const d of dirs) {
    try {
      rmSync(d, { recursive: true, force: true })
    } catch {
      /* 忽略 */
    }
  }
})

function turnRes(p: Partial<StreamTurnResult>): StreamTurnResult {
  return { stopReason: 'end_turn', text: '', thinking: '', toolUses: [], assistantBlocks: [], ...p }
}
const toolUse = (id: string, name: string, input: Record<string, unknown>): ToolUseBlock => ({ id, name, input })

interface Harness {
  root: string
  registry: ToolRegistry
  ws: WorkspaceService
  audit: AuditService
  requests: StreamTurnRequest[]
  port: PermissionPort
  getStore: () => PermissionStore
}

function harness(): Harness {
  const storeDir = mkdtempSync(join(tmpdir(), 'm83w-store-'))
  const rootDir = mkdtempSync(join(tmpdir(), 'm83w-root-'))
  dirs.push(storeDir, rootDir)
  const ws = new WorkspaceService(storeDir)
  ws.setRoot(rootDir)
  const db = openNodeSqlite(':memory:')
  runMigrations(db)
  const audit = new AuditService(db)
  // 注意：ToolRegistry 构造签名是 (workspace, audit) —— 漏传 ws 会让围栏失效、写操作全部被拒
  const registry = new ToolRegistry(ws, audit)
  registry.register(readFileTool)
  registry.register(writeFileTool)
  registry.register(listDirTool)

  let store: PermissionStore = EMPTY_STORE
  const port: PermissionPort = {
    resolve: (c) => resolvePermission(store, c),
    remember: (c: ToolCategory, v: 'allow' | 'deny', choice: RememberChoice) => {
      const rule = ruleFromChoice(c, v, choice)
      if (rule) store = applyRule(store, rule)
    }
  }
  return { root: ws.getRoot() as string, registry, ws, audit, requests: [], port, getStore: () => store }
}

function writeTurn(id: string, file: string, body: string): StreamTurnResult {
  return turnRes({
    stopReason: 'tool_use',
    toolUses: [toolUse(id, 'write_file', { path: file, content: body })],
    assistantBlocks: [{ type: 'tool_use', id, name: 'write_file', input: { path: file, content: body } }]
  })
}

const baseTurns = [{ role: 'user' as const, content: '帮我写个文件' }]

function statuses(events: LoopEvent[]): string[] {
  return events.filter((e) => e.kind === 'tool').map((e) => (e as { call: { status: string } }).call.status)
}

// ---------------------------------------------------------------- 1 记住 → 零弹窗（全链路）

describe('接线①：确认选择 → 落库 → 下次同类零弹窗', () => {
  it('选「此工作区记住」后，第二次同类写操作不再弹确认（全链路）', async () => {
    const h = harness()
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      return h.requests.length === 1 || h.requests.length === 3
        ? writeTurn(`t${h.requests.length}`, `f${h.requests.length}.txt`, 'x')
        : turnRes({ text: '完成' })
    }
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, h.port)

    // 第 1 次：弹确认 → 选「此工作区记住」
    const events1: LoopEvent[] = []
    const p1 = loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events1.push(e) })
    await vi.waitFor(() => expect(statuses(events1)).toContain('awaiting_confirm'))
    expect(loop.resolveConfirm('s1', 't1', true, 'workspace')).toBe(true)
    await p1
    expect(readFileSync(join(h.root, 'f1.txt'), 'utf8')).toBe('x')
    expect(h.getStore().workspace.write).toBe('allow') // 已落库到工作区层

    // 第 2 次：同类写操作 → **不再弹确认**（直接 running→ok）
    const events2: LoopEvent[] = []
    await loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events2.push(e) })
    expect(statuses(events2)).not.toContain('awaiting_confirm')
    expect(statuses(events2)).toEqual(['running', 'ok'])
    expect(readFileSync(join(h.root, 'f3.txt'), 'utf8')).toBe('x')

    // 证据链：两次都有记录，第二次 confirmed=0（未弹窗）
    const rows = h.audit.list(20)
    const evidence = rows.filter((r) => r.permission_rule?.startsWith('write@'))
    expect(evidence.length).toBeGreaterThanOrEqual(2)
    expect(evidence.some((r) => r.confirmed === 0 && r.permission_rule?.includes('=allow'))).toBe(true)
  })

  it('「仅本次」不落库 → 下次仍弹确认', async () => {
    const h = harness()
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      return h.requests.length % 2 === 1 ? writeTurn(`t${h.requests.length}`, `g${h.requests.length}.txt`, 'y') : turnRes({ text: 'ok' })
    }
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, h.port)
    for (const sid of ['a', 'b']) {
      const ev: LoopEvent[] = []
      const p = loop.run({ userId: 'u', sessionId: sid, baseTurns, system: 'S', emit: (e) => ev.push(e) })
      await vi.waitFor(() => expect(statuses(ev)).toContain('awaiting_confirm'))
      // 该轮工具 id 形如 t{n}，n = 本轮请求序号（1 基）
      const n = h.requests.length
      expect(loop.resolveConfirm(sid, `t${n}`, true, 'once')).toBe(true)
      await p
    }
    expect(h.getStore().workspace.write).toBeUndefined() // 仅本次 → 未落库
  })
})

// ---------------------------------------------------------------- 2 deny → 直接拒绝

describe('接线②：deny 规则 → 工具直接被拒 + 回喂中性文案', () => {
  it('deny 时不弹确认、不落盘、回喂 denyMessage', async () => {
    const h = harness()
    // 预置：工作区层禁止写类
    const portWithDeny: PermissionPort = {
      resolve: (c) => resolvePermission(applyRule(EMPTY_STORE, { category: 'write', value: 'deny', scope: 'workspace' }), c),
      remember: () => undefined
    }
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      return h.requests.length === 1 ? writeTurn('tw', 'never.txt', 'z') : turnRes({ text: '改用别的方式' })
    }
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, portWithDeny)
    const events: LoopEvent[] = []
    const out = await loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })

    expect(statuses(events)).toEqual(['rejected']) // 直接拒绝，无 awaiting_confirm
    expect(events.some((e) => e.kind === 'tool' && e.call.status === 'awaiting_confirm')).toBe(false)
    // 文件未创建
    expect(() => readFileSync(join(h.root, 'never.txt'), 'utf8')).toThrow()
    // 回喂中性文案（含工具名与设置指引），不是原始报错
    const fed = h.requests[1]!.turns.at(-1)!.content as AgentContentBlock[]
    const text = String((fed[0] as { content: string }).content)
    expect(text).toContain('已被当前权限设置禁止')
    expect(text).toContain('write_file')
    expect(text).toContain('设置')
    // 证据链记录否决来源
    const row = h.audit.list(5).find((r) => r.user_choice === null && r.permission_rule?.includes('deny'))
    expect(row?.permission_rule).toContain('workspace')
    expect(row?.confirmed).toBe(0)
    expect(out.content).toContain('改用别的方式')
  })
})

// ---------------------------------------------------------------- 3 runaway → AbortSource 中止

describe('接线③：runaway → AbortSource 中止 → 循环收尾', () => {
  it('连续 3 次同工具同参数 → 自动中止并说明原因', async () => {
    const h = harness()
    let n = 0
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      n += 1
      return turnRes({
        stopReason: 'tool_use',
        toolUses: [toolUse(`t${n}`, 'read_file', { path: 'same.txt' })],
        assistantBlocks: [{ type: 'tool_use', id: `t${n}`, name: 'read_file', input: { path: 'same.txt' } }]
      })
    }
    writeFileSync(join(h.root, 'same.txt'), '内容')
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, h.port)
    const events: LoopEvent[] = []
    const out = await loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })

    // 第 3 次同参调用后中止：最多 3 轮请求（不是 15 轮上限）
    expect(h.requests.length).toBeLessThanOrEqual(3)
    expect(out.content).toContain('自动停止')
    expect(out.content).toContain('read_file')
    // 判定结果可观测
    expect(loop.lastRunaway?.kind).toBe('repeat-calls')
    expect(loop.lastRunaway?.action).toBe('abort')
  })

  it('参数变化 → 不误伤（跑满上限而非被 guard 中止）', async () => {
    const h = harness()
    let n = 0
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      n += 1
      return turnRes({
        stopReason: 'tool_use',
        toolUses: [toolUse(`t${n}`, 'read_file', { path: `v${n}.txt` })],
        assistantBlocks: [{ type: 'tool_use', id: `t${n}`, name: 'read_file', input: { path: `v${n}.txt` } }]
      })
    }
    writeFileSync(join(h.root, 'v1.txt'), 'x')
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, h.port)
    const out = await loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: () => undefined })
    expect(loop.lastRunaway?.kind).not.toBe('repeat-calls')
    // 未被 guard 中止 → 跑满轮数上限
    expect(h.requests.length).toBeGreaterThanOrEqual(15)
    expect(out.content.length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------- 4 steering 轮边界注入

describe('接线④：steering 在轮边界注入', () => {
  it('进行中 steer → 下一轮请求里出现补充要求（不打断当前工具）', async () => {
    const h = harness()
    let n = 0
    let loopRef: AgentLoopService | null = null
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      n += 1
      if (n === 1) {
        // 「任务进行中」的真实时序：模型正在请求工具、工具尚未执行完时用户补充要求
        loopRef?.steer('s1', '别忘了也看 b.txt')
        return turnRes({
          stopReason: 'tool_use',
          toolUses: [toolUse('t1', 'read_file', { path: 'a.txt' })],
          assistantBlocks: [{ type: 'tool_use', id: 't1', name: 'read_file', input: { path: 'a.txt' } }]
        })
      }
      return turnRes({ text: '已按补充要求处理' })
    }
    writeFileSync(join(h.root, 'a.txt'), '内容')
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, h.port)
    loopRef = loop
    const events: LoopEvent[] = []
    const out = await loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })

    expect(out.content).toContain('已按补充要求处理')
    // 第 2 轮请求的**末尾**是注入文本（在工具结果之后 —— 协议要求 tool_result 紧随 tool_use）
    const secondTurns = h.requests[1]!.turns
    const injected = String(secondTurns.at(-1)!.content)
    expect(injected).toContain('任务进行中补充')
    expect(injected).toContain('别忘了也看 b.txt')
    // 工具结果仍紧跟在 tool_use 之后（未被注入打断）
    const resultIdx = secondTurns.findIndex(
      (t) => Array.isArray(t.content) && t.content.some((b) => b.type === 'tool_result')
    )
    const useIdx = secondTurns.findIndex(
      (t) => Array.isArray(t.content) && t.content.some((b) => b.type === 'tool_use')
    )
    expect(resultIdx).toBe(useIdx + 1)
    // 有轮次事件提示已采纳
    expect(events.some((e) => e.kind === 'round' && /补充/.test(e.label))).toBe(true)
  })
})

// ---------------------------------------------------------------- 5 裁切记录落库

describe('接线⑤：裁切记录可持久化（迁移 12 列就位）', () => {
  it('chat_sessions.context_records 列可写可读', () => {
    const db = openNodeSqlite(join(mkdtempSync(join(tmpdir(), 'm83c-')), 'c.db'))
    runMigrations(db)
    db.prepare('INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)').run('s1', 'u', 't', 1, 1)
    const records = JSON.stringify([{ round: 3, action: 'drop_group', beforeTokens: 1000, afterTokens: 400, at: 123 }])
    db.prepare('UPDATE chat_sessions SET context_records = ? WHERE id = ?').run(records, 's1')
    const row = db.prepare('SELECT context_records FROM chat_sessions WHERE id = ?').get('s1') as { context_records: string }
    expect(JSON.parse(row.context_records)[0]).toMatchObject({ round: 3, action: 'drop_group' })
    ;(db as unknown as { close?: () => void }).close?.()
  })
})

// ---------------------------------------------------------------- 6 默认行为零变更

describe('接线⑥：无规则时行为与现行为一致（零变更）', () => {
  it('只读工具直接执行；写类弹确认（无任何规则时）', async () => {
    const h = harness()
    let n = 0
    const stream: StreamTurnFn = async (_u, _s, req) => {
      h.requests.push(req)
      n += 1
      if (n === 1) {
        return turnRes({
          stopReason: 'tool_use',
          toolUses: [toolUse('r1', 'read_file', { path: 'r.txt' })],
          assistantBlocks: [{ type: 'tool_use', id: 'r1', name: 'read_file', input: { path: 'r.txt' } }]
        })
      }
      if (n === 2) return writeTurn('w1', 'w.txt', 'c')
      return turnRes({ text: 'done' })
    }
    writeFileSync(join(h.root, 'r.txt'), '只读内容')
    const loop = new AgentLoopService(stream, h.registry, h.ws, h.audit, h.port)
    const events: LoopEvent[] = []
    const p = loop.run({ userId: 'u', sessionId: 's1', baseTurns, system: 'S', emit: (e) => events.push(e) })
    await vi.waitFor(() => expect(statuses(events)).toContain('awaiting_confirm'))
    // 只读那次没有弹确认；写类这次弹了
    expect(statuses(events).filter((s) => s === 'awaiting_confirm')).toHaveLength(1)
    loop.resolveConfirm('s1', 'w1', true)
    const out = await p
    expect(out.content).toBe('done')
    expect(readFileSync(join(h.root, 'w.txt'), 'utf8')).toBe('c')
  })
})
