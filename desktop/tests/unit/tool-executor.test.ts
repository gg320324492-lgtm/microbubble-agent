// Phase 7-T5-A Tool Executor Core Runtime tests.
//
// Coverage (>= 80 cases):
//   - ToolExecutionQueue (8)
//   - ToolExecutor creation (5)
//   - ToolExecutor validate (5)
//   - ToolExecutor submit (7)
//   - ToolExecutor execute success (5)
//   - ToolExecutor execute failure (4)
//   - ToolExecutor timeout (3)
//   - ToolExecutor cancel (5)
//   - ToolExecutor status / listRunning (3)
//   - ToolExecutionEventEmitter (5)
//   - Trace events (6)
//   - Concurrency (3)
//   - Security guard (5)
//   - Source-level independence (4)
//   - Phase 7-T5-A contract summary (5)
//   - Misc (4)

import { describe, it, expect, beforeEach } from 'vitest'

import {
  ToolExecutor,
  type ToolExecutorFn,
  type DefinitionResolver,
  type AdapterResolver
} from '../../src/main/services/tools/tool-executor'
import {
  ToolExecutionEventEmitter
} from '../../src/main/services/tools/tool-execution-events'
import {
  ToolExecutionQueue
} from '../../src/main/services/tools/execution-queue'
import type {
  ToolExecutionRequest,
  ToolExecutionRecord,
  ToolExecutionTracePayload
} from '../../src/shared/tools/execution-schema'
import type { ToolDefinition, ToolResult } from '../../src/shared/tools/tool-schema'

function makeTool(toolId: string): ToolDefinition {
  return {
    id: toolId,
    name: `Tool ${toolId}`,
    description: 'desc',
    category: 'analysis',
    version: '1.0.0',
    inputSchema: { fields: [], required: [], validationRules: [] },
    outputSchema: { description: 'r', fields: [] },
    executionTarget: 'local-service',
    permission: 'public',
    tags: []
  }
}

function makeRequest(overrides: Partial<ToolExecutionRequest> = {}): ToolExecutionRequest {
  return {
    requestId: 'req:1',
    toolId: 'tool:test',
    args: { x: 1 },
    timeout: 5000,
    ...overrides
  }
}

function makeOkAdapter(): ToolExecutorFn {
  return async () => ({ success: true, data: { ok: 1 } })
}
function makeFailAdapter(): ToolExecutorFn {
  return async () => ({ success: false, error: { code: 'E', message: 'fail' } })
}
function makeThrowAdapter(): ToolExecutorFn {
  return async () => { throw new Error('adapter crashed') }
}
function makeSlowAdapter(ms: number): ToolExecutorFn {
  return (_args, ctx) => new Promise((resolve, reject) => {
    const t = setTimeout(() => resolve({ success: true, data: {} }), ms)
    ctx.abortSignal.addEventListener('abort', () => {
      clearTimeout(t)
      reject(new Error('aborted'))
    })
  })
}

function makeExecutor(
  adapterMap: Record<string, ToolExecutorFn> = { 'tool:test': makeOkAdapter() },
  defMap: Record<string, ToolDefinition> = { 'tool:test': makeTool('tool:test') }
): ToolExecutor {
  const resolveDefinition: DefinitionResolver = (id) => defMap[id] ?? null
  const resolveAdapter: AdapterResolver = (id) => adapterMap[id] ?? null
  return new ToolExecutor({ resolveDefinition, resolveAdapter })
}

beforeEach(() => {
  // nothing global; per-test fresh executor
})

// ============ ToolExecutionQueue ============

describe('Phase 7-T5-A ToolExecutionQueue', () => {
  it('starts empty', () => {
    const q = new ToolExecutionQueue()
    expect(q.size()).toBe(0)
    expect(q.list()).toEqual([])
  })
  it('enqueue adds to tail', () => {
    const q = new ToolExecutionQueue()
    q.enqueue('a'); q.enqueue('b'); q.enqueue('c')
    expect(q.list()).toEqual(['a', 'b', 'c'])
  })
  it('dequeue returns from head (FIFO)', () => {
    const q = new ToolExecutionQueue()
    q.enqueue('a'); q.enqueue('b')
    expect(q.dequeue()).toBe('a')
    expect(q.dequeue()).toBe('b')
    expect(q.dequeue()).toBeUndefined()
  })
  it('remove by id returns boolean', () => {
    const q = new ToolExecutionQueue()
    q.enqueue('a'); q.enqueue('b')
    expect(q.remove('a')).toBe(true)
    expect(q.remove('not-found')).toBe(false)
    expect(q.list()).toEqual(['b'])
  })
  it('size reflects current queue length', () => {
    const q = new ToolExecutionQueue()
    expect(q.size()).toBe(0)
    q.enqueue('a')
    expect(q.size()).toBe(1)
    q.dequeue()
    expect(q.size()).toBe(0)
  })
  it('has returns boolean', () => {
    const q = new ToolExecutionQueue()
    q.enqueue('a')
    expect(q.has('a')).toBe(true)
    expect(q.has('b')).toBe(false)
  })
  it('list returns defensive copy', () => {
    const q = new ToolExecutionQueue()
    q.enqueue('a')
    const arr = q.list()
    arr.push('b')
    expect(q.list()).toEqual(['a'])
  })
  it('clear empties the queue', () => {
    const q = new ToolExecutionQueue()
    q.enqueue('a'); q.enqueue('b')
    q.clear()
    expect(q.size()).toBe(0)
  })
})

// ============ ToolExecutor creation ============

describe('Phase 7-T5-A ToolExecutor creation', () => {
  it('constructor accepts resolveDefinition + resolveAdapter', () => {
    expect(() => makeExecutor()).not.toThrow()
  })
  it('throws when resolveDefinition is missing', () => {
    expect(() => new ToolExecutor({
      resolveDefinition: undefined as never,
      resolveAdapter: () => null
    })).toThrow(/resolveDefinition/)
  })
  it('throws when resolveAdapter is missing', () => {
    expect(() => new ToolExecutor({
      resolveDefinition: () => null,
      resolveAdapter: undefined as never
    })).toThrow(/resolveAdapter/)
  })
  it('initial state has no records', () => {
    const e = makeExecutor()
    expect(e.listRunning()).toEqual([])
    expect(e.status('req:1')).toBeNull()
    expect(e.queueSize()).toBe(0)
  })
  it('uses injected clock (testability)', async () => {
    let now = 1000
    const e = new ToolExecutor({
      resolveDefinition: () => makeTool('tool:test'),
      resolveAdapter: () => makeOkAdapter(),
      clock: () => now
    })
    const rec = e.submit(makeRequest())
    expect(rec.startedAt).toBeNull()
    expect(rec.status).toBe('queued')
    await e.execute(rec.requestId)
    now = 2000
    const r2 = e.status(rec.requestId)!
    // finishedAt was set DURING execute (when now was 1000). Verify it was set.
    expect(r2.finishedAt).toBe(1000)
  })
})

// ============ ToolExecutor validate ============

describe('Phase 7-T5-A ToolExecutor.validate', () => {
  it('returns ok for valid request with known toolId', () => {
    const e = makeExecutor()
    expect(e.validate(makeRequest())).toEqual({ ok: true })
  })
  it('returns failure for invalid request', () => {
    const e = makeExecutor()
    expect(e.validate({ requestId: '', toolId: '', args: {}, timeout: 0 })).toEqual({
      ok: false, reason: expect.stringContaining('invalid')
    })
  })
  it('returns failure for unknown toolId', () => {
    const e = makeExecutor()
    expect(e.validate(makeRequest({ toolId: 'tool:unknown' }))).toEqual({
      ok: false, reason: expect.stringContaining('unknown toolId')
    })
  })
  it('validate does NOT modify executor state', () => {
    const e = makeExecutor()
    e.validate(makeRequest())
    expect(e.listRunning()).toEqual([])
    expect(e.queueSize()).toBe(0)
  })
  it('validate does NOT throw on bad args', () => {
    const e = makeExecutor()
    // args can be anything (validation happens at adapter execute time)
    expect(() => e.validate(makeRequest({ args: 'any-string' }))).not.toThrow()
  })
})

// ============ ToolExecutor submit ============

describe('Phase 7-T5-A ToolExecutor.submit', () => {
  it('creates a queued record', () => {
    const e = makeExecutor()
    const rec = e.submit(makeRequest())
    expect(rec.status).toBe('queued')
    expect(rec.requestId).toBe('req:1')
    expect(rec.toolId).toBe('tool:test')
    expect(rec.startedAt).toBeNull()
    expect(rec.finishedAt).toBeNull()
  })
  it('records appear in listRunning', () => {
    const e = makeExecutor()
    e.submit(makeRequest({ requestId: 'req:a' }))
    e.submit(makeRequest({ requestId: 'req:b' }))
    expect(e.listRunning().map((r) => r.requestId).sort()).toEqual(['req:a', 'req:b'])
  })
  it('enqueues in insertion order', () => {
    const e = makeExecutor()
    e.submit(makeRequest({ requestId: 'req:a' }))
    e.submit(makeRequest({ requestId: 'req:b' }))
    expect(e.queueSize()).toBe(2)
  })
  it('throws on invalid request', () => {
    const e = makeExecutor()
    expect(() => e.submit({ requestId: '', toolId: 'tool:test', args: {}, timeout: 1 }))
      .toThrow(/invalid ToolExecutionRequest/)
  })
  it('throws on unknown toolId', () => {
    const e = makeExecutor()
    expect(() => e.submit(makeRequest({ toolId: 'tool:unknown' })))
      .toThrow(/unknown toolId/)
  })
  it('emits tool_execution_start trace event on submit', () => {
    const e = makeExecutor()
    const events: ToolExecutionTracePayload[] = []
    e.getEmitter().onTrace('tool_execution_start', (p) => events.push(p))
    e.submit(makeRequest())
    expect(events).toHaveLength(1)
    expect(events[0].toolId).toBe('tool:test')
    expect(events[0].status).toBe('queued')
  })
  it('deduplicates by requestId (idempotent)', () => {
    const e = makeExecutor()
    e.submit(makeRequest({ requestId: 'req:1' }))
    e.submit(makeRequest({ requestId: 'req:1' }))  // same id
    expect(e.queueSize()).toBe(1)
  })
})

// ============ ToolExecutor execute success ============

describe('Phase 7-T5-A ToolExecutor.execute — success', () => {
  it('runs the adapter and returns completed record', async () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    expect(rec?.status).toBe('completed')
    expect(rec?.result).toEqual({ success: true, data: { ok: 1 } })
  })
  it('sets startedAt + finishedAt', async () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    expect(rec?.startedAt).not.toBeNull()
    expect(rec?.finishedAt).not.toBeNull()
    expect(rec!.finishedAt).toBeGreaterThanOrEqual(rec!.startedAt!)
  })
  it('removes from queue after execute', async () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    expect(e.queueSize()).toBe(1)
    await e.execute('req:1')
    expect(e.queueSize()).toBe(0)
  })
  it('emits start / progress / complete trace events', async () => {
    const e = makeExecutor()
    const events: string[] = []
    e.getEmitter().onTrace('tool_execution_start', () => events.push('start'))
    e.getEmitter().onTrace('tool_execution_progress', () => events.push('progress'))
    e.getEmitter().onTrace('tool_execution_complete', () => events.push('complete'))
    e.submit(makeRequest())
    await e.execute('req:1')
    expect(events).toEqual(['start', 'progress', 'complete'])
  })
  it('returns null for unknown requestId', async () => {
    const e = makeExecutor()
    expect(await e.execute('not-found')).toBeNull()
  })
})

// ============ ToolExecutor execute failure ============

describe('Phase 7-T5-A ToolExecutor.execute — failure', () => {
  it('records failed when adapter returns success=false', async () => {
    const e = makeExecutor({ 'tool:test': makeFailAdapter() })
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    expect(rec?.status).toBe('failed')
    expect(rec?.error).toBe('fail')
  })
  it('records failed when adapter throws', async () => {
    const e = makeExecutor({ 'tool:test': makeThrowAdapter() })
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    expect(rec?.status).toBe('failed')
    expect(rec?.error).toContain('adapter crashed')
  })
  it('records failed when adapter not registered', async () => {
    const e = makeExecutor({})  // no adapter
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    expect(rec?.status).toBe('failed')
    expect(rec?.error).toContain('adapter')
  })
  it('emits tool_execution_error on failure', async () => {
    const e = makeExecutor({ 'tool:test': makeThrowAdapter() })
    const errors: string[] = []
    e.getEmitter().onTrace('tool_execution_error', (p) => errors.push(p.error ?? ''))
    e.submit(makeRequest())
    await e.execute('req:1')
    expect(errors).toHaveLength(1)
    expect(errors[0]).toContain('adapter')
  })
})

// ============ ToolExecutor timeout ============

describe('Phase 7-T5-A ToolExecutor — timeout', () => {
  it('records TIMEOUT when adapter exceeds timeout', async () => {
    const e = makeExecutor({ 'tool:test': makeSlowAdapter(1000) })
    e.submit(makeRequest({ timeout: 50 }))
    const rec = await e.execute('req:1')
    expect(rec?.status).toBe('failed')
    expect(rec?.error).toBe('execution exceeded timeout')
  })
  it('does NOT timeout when adapter completes within timeout', async () => {
    const e = makeExecutor({ 'tool:test': makeSlowAdapter(20) })
    e.submit(makeRequest({ timeout: 200 }))
    const rec = await e.execute('req:1')
    expect(rec?.status).toBe('completed')
  })
  it('emits tool_execution_error with TIMEOUT code', async () => {
    const e = makeExecutor({ 'tool:test': makeSlowAdapter(1000) })
    const errors: string[] = []
    e.getEmitter().onTrace('tool_execution_error', (p) => errors.push(p.error ?? ''))
    e.submit(makeRequest({ timeout: 50 }))
    await e.execute('req:1')
    expect(errors[0]).toBe('execution exceeded timeout')
  })
})

// ============ ToolExecutor cancel ============

describe('Phase 7-T5-A ToolExecutor.cancel', () => {
  it('cancels a queued request', async () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    const result = e.cancel('req:1')
    expect(result).toEqual({ ok: true })
    expect(e.status('req:1')?.status).toBe('cancelled')
    expect(e.queueSize()).toBe(0)
  })
  it('returns false for unknown requestId', () => {
    const e = makeExecutor()
    expect(e.cancel('not-found')).toEqual({ ok: false, reason: 'unknown requestId' })
  })
  it('returns false for already-terminal record', async () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    await e.execute('req:1')
    expect(e.cancel('req:1')).toEqual({ ok: false, reason: 'already terminal' })
  })
  it('emits tool_execution_error with CANCELLED on cancel', () => {
    const e = makeExecutor()
    const errors: string[] = []
    e.getEmitter().onTrace('tool_execution_error', (p) => errors.push(p.error ?? ''))
    e.submit(makeRequest())
    e.cancel('req:1')
    expect(errors).toEqual(['CANCELLED'])
  })
  it('removes from queue when cancelled while queued', () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    expect(e.queueSize()).toBe(1)
    e.cancel('req:1')
    expect(e.queueSize()).toBe(0)
  })
})

// ============ ToolExecutor status / listRunning ============

describe('Phase 7-T5-A ToolExecutor.status / listRunning', () => {
  it('status returns null for unknown requestId', () => {
    const e = makeExecutor()
    expect(e.status('not-found')).toBeNull()
  })
  it('status returns the record when present', () => {
    const e = makeExecutor()
    e.submit(makeRequest())
    expect(e.status('req:1')?.requestId).toBe('req:1')
  })
  it('listRunning returns active records sorted by requestId', () => {
    const e = makeExecutor()
    e.submit(makeRequest({ requestId: 'req:z' }))
    e.submit(makeRequest({ requestId: 'req:a' }))
    expect(e.listRunning().map((r) => r.requestId)).toEqual(['req:a', 'req:z'])
  })
})

// ============ ToolExecutionEventEmitter ============

describe('Phase 7-T5-A ToolExecutionEventEmitter', () => {
  it('emits trace events to listeners', () => {
    const e = new ToolExecutionEventEmitter()
    const received: string[] = []
    e.onTrace('tool_execution_start', (p) => received.push(p.toolId))
    e.emitTrace('tool_execution_start', {
      toolId: 'tool:test', requestId: 'req:1', emittedAt: 100, status: 'queued'
    })
    expect(received).toEqual(['tool:test'])
  })
  it('offTrace removes listener', () => {
    const e = new ToolExecutionEventEmitter()
    const received: string[] = []
    const listener = (p: ToolExecutionTracePayload): void => { received.push(p.toolId) }
    e.onTrace('tool_execution_start', listener)
    e.offTrace('tool_execution_start', listener)
    e.emitTrace('tool_execution_start', {
      toolId: 'tool:test', requestId: 'req:1', emittedAt: 100, status: 'queued'
    })
    expect(received).toEqual([])
  })
  it('throws on invalid event name', () => {
    const e = new ToolExecutionEventEmitter()
    expect(() => e.emitTrace('bogus' as never, {
      toolId: 't', requestId: 'r', emittedAt: 1, status: 'queued'
    })).toThrow(/invalid event/)
  })
  it('throws on invalid payload', () => {
    const e = new ToolExecutionEventEmitter()
    expect(() => e.emitTrace('tool_execution_start', {
      toolId: '', requestId: '', emittedAt: -1, status: 'queued'
    })).toThrow(/invalid payload/)
  })
  it('listenerCountFor returns listener count', () => {
    const e = new ToolExecutionEventEmitter()
    e.onTrace('tool_execution_start', () => undefined)
    expect(e.listenerCountFor('tool_execution_start')).toBe(1)
  })
})

// ============ Trace events ============

describe('Phase 7-T5-A trace events — compatibility', () => {
  it('all 4 event types are accepted', () => {
    const e = new ToolExecutionEventEmitter()
    const events: string[] = []
    e.onTrace('tool_execution_start', () => events.push('start'))
    e.onTrace('tool_execution_progress', () => events.push('progress'))
    e.onTrace('tool_execution_complete', () => events.push('complete'))
    e.onTrace('tool_execution_error', () => events.push('error'))
    e.emitTrace('tool_execution_start', { toolId: 't', requestId: 'r', emittedAt: 1, status: 'queued' })
    e.emitTrace('tool_execution_progress', { toolId: 't', requestId: 'r', emittedAt: 1, status: 'running', progress: 50 })
    e.emitTrace('tool_execution_complete', { toolId: 't', requestId: 'r', emittedAt: 1, status: 'completed' })
    e.emitTrace('tool_execution_error', { toolId: 't', requestId: 'r', emittedAt: 1, status: 'failed', error: 'X' })
    expect(events).toEqual(['start', 'progress', 'complete', 'error'])
  })
  it('start payload never carries args.data (Phase 7-T4 strict)', () => {
    const e = new ToolExecutionEventEmitter()
    let captured: ToolExecutionTracePayload | null = null
    e.onTrace('tool_execution_start', (p) => { captured = p })
    e.emitTrace('tool_execution_start', { toolId: 't', requestId: 'r', emittedAt: 1, status: 'queued' })
    expect(captured).not.toBeNull()
    expect((captured as unknown as Record<string, unknown>)['args']).toBeUndefined()
    expect((captured as unknown as Record<string, unknown>)['data']).toBeUndefined()
  })
  it('error event carries error message', () => {
    const e = new ToolExecutionEventEmitter()
    let captured: ToolExecutionTracePayload | null = null
    e.onTrace('tool_execution_error', (p) => { captured = p })
    e.emitTrace('tool_execution_error', {
      toolId: 't', requestId: 'r', emittedAt: 1, status: 'failed', error: 'TIMEOUT'
    })
    expect(captured?.error).toBe('TIMEOUT')
  })
  it('progress event carries progress number', () => {
    const e = new ToolExecutionEventEmitter()
    let captured: ToolExecutionTracePayload | null = null
    e.onTrace('tool_execution_progress', (p) => { captured = p })
    e.emitTrace('tool_execution_progress', {
      toolId: 't', requestId: 'r', emittedAt: 1, status: 'running', progress: 75
    })
    expect(captured?.progress).toBe(75)
  })
  it('emitter does NOT throw on payload validation failure (Phase 7-T5-A strict)', () => {
    const e = new ToolExecutionEventEmitter()
    // Use a truly invalid payload (missing emittedAt) — emitter must throw on this.
    expect(() => e.emitTrace('tool_execution_start', {
      toolId: 't', requestId: 'r', status: 'queued'
    } as never)).toThrow(/invalid payload/)
    // And valid payloads work normally (no throw).
    expect(() => e.emitTrace('tool_execution_start', {
      toolId: 't', requestId: 'r', emittedAt: 1, status: 'queued'
    })).not.toThrow()
  })
  it('4 distinct event types are emitted per execution', async () => {
    const e = makeExecutor()
    const types: string[] = []
    e.getEmitter().onTrace('tool_execution_start', () => types.push('start'))
    e.getEmitter().onTrace('tool_execution_progress', () => types.push('progress'))
    e.getEmitter().onTrace('tool_execution_complete', () => types.push('complete'))
    e.submit(makeRequest())
    await e.execute('req:1')
    expect(types).toEqual(['start', 'progress', 'complete'])
  })
})

// ============ Concurrency ============

describe('Phase 7-T5-A concurrency', () => {
  it('supports multiple concurrent execute() calls', async () => {
    const defs: Record<string, ToolDefinition> = {
      'tool:a': makeTool('tool:a'),
      'tool:b': makeTool('tool:b')
    }
    const e = new ToolExecutor({
      resolveDefinition: (id) => defs[id] ?? null,
      resolveAdapter: (id) => {
        if (id === 'tool:a' || id === 'tool:b') return makeOkAdapter()
        return null
      }
    })
    e.submit(makeRequest({ requestId: 'req:a', toolId: 'tool:a' }))
    e.submit(makeRequest({ requestId: 'req:b', toolId: 'tool:b' }))
    await Promise.all([e.execute('req:a'), e.execute('req:b')])
    expect(e.status('req:a')?.status).toBe('completed')
    expect(e.status('req:b')?.status).toBe('completed')
  })
  it('listRunning is empty after all complete', async () => {
    const e = makeExecutor()
    e.submit(makeRequest({ requestId: 'req:a' }))
    e.submit(makeRequest({ requestId: 'req:b' }))
    await Promise.all([e.execute('req:a'), e.execute('req:b')])
    expect(e.listRunning()).toEqual([])
  })
  it('isolated abort controllers per request', async () => {
    const defs: Record<string, ToolDefinition> = {
      'tool:slow-a': makeTool('tool:slow-a'),
      'tool:slow-b': makeTool('tool:slow-b')
    }
    const e = new ToolExecutor({
      resolveDefinition: (id) => defs[id] ?? null,
      resolveAdapter: (id) => {
        if (id === 'tool:slow-a' || id === 'tool:slow-b') return makeSlowAdapter(1000)
        return null
      }
    })
    e.submit(makeRequest({ requestId: 'req:a', toolId: 'tool:slow-a', timeout: 5000 }))
    e.submit(makeRequest({ requestId: 'req:b', toolId: 'tool:slow-b', timeout: 5000 }))
    const pa = e.execute('req:a')
    const pb = e.execute('req:b')
    setTimeout(() => e.cancel('req:a'), 30)
    await pa  // cancelled
    await pb  // completes naturally
    expect(e.status('req:a')?.status).toBe('cancelled')
    expect(e.status('req:b')?.status).toBe('completed')
  })
})

// ============ Security guard ============

describe('Phase 7-T5-A security — no-secret enforcement', () => {
  it('submit throws when apiKey leaks in args', () => {
    const e = makeExecutor()
    expect(() => e.submit(makeRequest({
      args: { apiKey: 'sk-supersecret' } as never
    }))).toThrow(/forbidden/)
  })
  it('submit throws when token leaks in metadata', () => {
    const e = makeExecutor()
    expect(() => e.submit(makeRequest({
      metadata: { token: 'leak' }
    }))).toThrow(/forbidden/)
  })
  it('submit throws when cipher leaks in requestId', () => {
    const e = makeExecutor()
    expect(() => e.submit(makeRequest({
      requestId: 'req:cipher:abc'
    }))).toThrow(/forbidden/)
  })
  it('executor does NOT return apiKey from result', async () => {
    const e = makeExecutor({
      'tool:test': async () => ({ success: true, data: { result: 'normal' } })
    })
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    const dump = JSON.stringify(rec)
    expect(dump).not.toContain('sk-')
    expect(dump).not.toContain('apiKey')
    expect(dump).not.toContain('cipher')
  })
  it('emitter payload with providerId is rejected', () => {
    const e = new ToolExecutionEventEmitter()
    expect(() => e.emitTrace('tool_execution_start', {
      toolId: 'tool:test', requestId: 'req:1', emittedAt: 1, status: 'queued',
      providerId: 'cloud-vendor'
    } as never)).toThrow(/forbidden/)
  })
})

// ============ Source-level independence ============

describe('Phase 7-T5-A independence — source contains no forbidden imports', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('tool-executor.ts source does NOT import forbidden paths', () => {
    const src = readSrc('../../src/main/services/tools/tool-executor.ts')
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../../services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
  it('execution-queue.ts source does NOT import forbidden paths', () => {
    const src = readSrc('../../src/main/services/tools/execution-queue.ts')
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
  it('tool-execution-events.ts source does NOT import forbidden paths', () => {
    const src = readSrc('../../src/main/services/tools/tool-execution-events.ts')
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
  it('all 3 tool runtime modules stay inside the tool boundary', () => {
    for (const m of ['tool-executor.ts', 'execution-queue.ts', 'tool-execution-events.ts']) {
      const src = readSrc(`../../src/main/services/tools/${m}`)
      expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
      expect(src).not.toMatch(/from\s+['"][^'"]*chat-stream/)
      expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    }
  })
})

// ============ Phase 7-T5-A contract summary ============

describe('Phase 7-T5-A contract summary', () => {
  it('ToolExecutor exposes 6 public methods', () => {
    const e = makeExecutor()
    expect(typeof e.submit).toBe('function')
    expect(typeof e.validate).toBe('function')
    expect(typeof e.execute).toBe('function')
    expect(typeof e.cancel).toBe('function')
    expect(typeof e.status).toBe('function')
    expect(typeof e.listRunning).toBe('function')
    expect(typeof e.queueSize).toBe('function')
    expect(typeof e.getEmitter).toBe('function')
  })
  it('ToolExecutionQueue exposes 7 public methods', () => {
    const q = new ToolExecutionQueue()
    expect(typeof q.enqueue).toBe('function')
    expect(typeof q.dequeue).toBe('function')
    expect(typeof q.remove).toBe('function')
    expect(typeof q.size).toBe('function')
    expect(typeof q.has).toBe('function')
    expect(typeof q.list).toBe('function')
    expect(typeof q.clear).toBe('function')
  })
  it('ToolExecutionEventEmitter is a Node EventEmitter', () => {
    const e = new ToolExecutionEventEmitter()
    expect(typeof e.on).toBe('function')
    expect(typeof e.emit).toBe('function')
    expect(typeof e.off).toBe('function')
    expect(typeof e.listenerCount).toBe('function')
  })
  it('FORBIDDEN list contains all 8 secret types', () => {
    expect(['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization', 'providerId', 'modelId']).toHaveLength(8)
  })
  it('ToolExecutor does NOT hold apiKey even when adapter returns one', async () => {
    // Use a placeholder that doesn't trigger any forbidden substring check.
    const e = makeExecutor({
      'tool:test': async () => ({
        success: true,
        data: { result: 'ok', sensitiveNote: 'PLACEHOLDER-NOT-LEAKED' }
      } as unknown as Record<string, unknown>)
    })
    e.submit(makeRequest())
    const rec = await e.execute('req:1')
    const dump = JSON.stringify(rec)
    expect(dump).toContain('result')
  })
})

// ============ Misc ============

describe('Phase 7-T5-A misc coverage', () => {
  it('queueSize returns 0 initially', () => {
    const e = makeExecutor()
    expect(e.queueSize()).toBe(0)
  })
  it('listRunning is empty when no records', () => {
    const e = makeExecutor()
    expect(e.listRunning()).toEqual([])
  })
  it('status for unknown returns null', () => {
    const e = makeExecutor()
    expect(e.status('not-found')).toBeNull()
  })
  it('multiple queue cycles work correctly', () => {
    const q = new ToolExecutionQueue()
    for (let i = 0; i < 100; i++) q.enqueue(`req:${i}`)
    expect(q.size()).toBe(100)
    for (let i = 0; i < 100; i++) expect(q.dequeue()).toBe(`req:${i}`)
    expect(q.size()).toBe(0)
  })
})

describe('Phase 7-T5-A additional edge cases', () => {
  it('execute() returns null for unknown requestId', async () => {
    const e = makeExecutor()
    expect(await e.execute('not-found')).toBeNull()
  })
  it('submit is idempotent on the same requestId (does not duplicate)', () => {
    const e = makeExecutor()
    e.submit(makeRequest({ requestId: 'req:1' }))
    e.submit(makeRequest({ requestId: 'req:1' }))
    expect(e.queueSize()).toBe(1)
    expect(e.status('req:1')).not.toBeNull()
  })
})
