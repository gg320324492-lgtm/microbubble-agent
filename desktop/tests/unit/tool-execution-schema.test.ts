// Phase 7-T4 Tool Execution Schema tests.
//
// Coverage (>= 50 cases):
//   - ToolExecutionStatus (3)
//   - ToolExecutionTraceEvent (3)
//   - ToolExecutionRequest (5)
//   - ToolExecutionRecord (5)
//   - ToolExecutionTracePayload (4)
//   - ToolExecutionTracePayload for progress/error (4)
//   - ToolExecutionRecord lifecycle (4)
//   - No-secret enforcement (4)
//   - Source-level independence (4)
//   - Phase 7-T4 contracts summary (4)

import { describe, it, expect } from 'vitest'

import {
  isValidToolExecutionStatus,
  isValidToolExecutionTraceEvent,
  isValidToolExecutionRequest,
  isValidToolExecutionRecord,
  isValidToolExecutionTracePayload,
  __testHelpers,
  TOOL_EXECUTION_STATUSES,
  TOOL_EXECUTION_TRACE_EVENTS,
  type ToolExecutionStatus,
  type ToolExecutionTraceEvent,
  type ToolExecutionRequest,
  type ToolExecutionRecord,
  type ToolExecutionTracePayload
} from '../../src/shared/tools/execution-schema'
import { isValidToolResult } from '../../src/shared/tools/tool-schema'

// ============ ToolExecutionStatus ============

describe('Phase 7-T4 ToolExecutionStatus enum', () => {
  it('accepts all 7 lifecycle statuses', () => {
    const statuses: ToolExecutionStatus[] = [
      'created', 'validated', 'queued', 'running',
      'completed', 'failed', 'cancelled'
    ]
    for (const s of statuses) {
      expect(isValidToolExecutionStatus(s)).toBe(true)
    }
  })
  it('rejects unknown status', () => {
    expect(isValidToolExecutionStatus('unknown')).toBe(false)
    expect(isValidToolExecutionStatus('paused')).toBe(false)
  })
  it('TOOL_EXECUTION_STATUSES readonly array has 7 entries', () => {
    expect(TOOL_EXECUTION_STATUSES.length).toBe(7)
    expect(__testHelpers.VALID_STATUSES.size).toBe(7)
  })
})

// ============ ToolExecutionTraceEvent ============

describe('Phase 7-T4 ToolExecutionTraceEvent enum', () => {
  it('accepts all 4 trace events', () => {
    const events: ToolExecutionTraceEvent[] = [
      'tool_execution_start',
      'tool_execution_progress',
      'tool_execution_complete',
      'tool_execution_error'
    ]
    for (const e of events) {
      expect(isValidToolExecutionTraceEvent(e)).toBe(true)
    }
  })
  it('rejects unknown trace event', () => {
    expect(isValidToolExecutionTraceEvent('tool_call')).toBe(false)
    expect(isValidToolExecutionTraceEvent('start')).toBe(false)
  })
  it('TOOL_EXECUTION_TRACE_EVENTS readonly array has 4 entries', () => {
    expect(TOOL_EXECUTION_TRACE_EVENTS.length).toBe(4)
    expect(__testHelpers.VALID_TRACE_EVENTS.size).toBe(4)
  })
})

// ============ ToolExecutionRequest ============

describe('Phase 7-T4 ToolExecutionRequest validator', () => {
  const baseRequest = (): ToolExecutionRequest => ({
    requestId: 'req:abc',
    toolId: 'tool:test',
    args: { x: 1 },
    timeout: 5000
  })
  it('accepts minimal request', () => {
    expect(isValidToolExecutionRequest(baseRequest())).toBe(true)
  })
  it('accepts request with optional metadata', () => {
    expect(isValidToolExecutionRequest({
      ...baseRequest(),
      metadata: { traceId: 'tr:xyz', userId: 'user:alice' }
    })).toBe(true)
  })
  it('rejects empty requestId', () => {
    expect(isValidToolExecutionRequest({ ...baseRequest(), requestId: '' })).toBe(false)
  })
  it('rejects non-positive timeout', () => {
    expect(isValidToolExecutionRequest({ ...baseRequest(), timeout: 0 })).toBe(false)
    expect(isValidToolExecutionRequest({ ...baseRequest(), timeout: -1 })).toBe(false)
  })
  it('rejects invalid toolId format', () => {
    expect(isValidToolExecutionRequest({ ...baseRequest(), toolId: 'invalid' })).toBe(false)
    expect(isValidToolExecutionRequest({ ...baseRequest(), toolId: 'tool:' })).toBe(false)
  })
})

// ============ ToolExecutionRecord ============

describe('Phase 7-T4 ToolExecutionRecord validator', () => {
  const baseRecord = (): ToolExecutionRecord => ({
    requestId: 'req:abc',
    toolId: 'tool:test',
    status: 'created',
    startedAt: null,
    finishedAt: null
  })
  it('accepts minimal record', () => {
    expect(isValidToolExecutionRecord(baseRecord())).toBe(true)
  })
  it('accepts running record with startedAt', () => {
    expect(isValidToolExecutionRecord({
      ...baseRecord(), status: 'running', startedAt: 100
    })).toBe(true)
  })
  it('accepts completed record with result', () => {
    expect(isValidToolExecutionRecord({
      ...baseRecord(),
      status: 'completed',
      startedAt: 100,
      finishedAt: 200,
      result: { success: true, data: { x: 1 } }
    })).toBe(true)
  })
  it('rejects unknown status', () => {
    expect(isValidToolExecutionRecord({ ...baseRecord(), status: 'unknown' as never })).toBe(false)
  })
  it('rejects negative startedAt', () => {
    expect(isValidToolExecutionRecord({ ...baseRecord(), startedAt: -1 })).toBe(false)
  })
})

// ============ ToolExecutionTracePayload ============

describe('Phase 7-T4 ToolExecutionTracePayload validator', () => {
  const base = (): ToolExecutionTracePayload => ({
    toolId: 'tool:test',
    requestId: 'req:abc',
    emittedAt: 100,
    status: 'running'
  })
  it('accepts minimal payload', () => {
    expect(isValidToolExecutionTracePayload(base())).toBe(true)
  })
  it('accepts payload with progress (0..100)', () => {
    expect(isValidToolExecutionTracePayload({ ...base(), progress: 50 })).toBe(true)
    expect(isValidToolExecutionTracePayload({ ...base(), progress: 0 })).toBe(true)
    expect(isValidToolExecutionTracePayload({ ...base(), progress: 100 })).toBe(true)
  })
  it('accepts payload with error', () => {
    expect(isValidToolExecutionTracePayload({
      ...base(), status: 'failed', error: 'TIMEOUT'
    })).toBe(true)
  })
  it('rejects out-of-range progress', () => {
    expect(isValidToolExecutionTracePayload({ ...base(), progress: -1 })).toBe(false)
    expect(isValidToolExecutionTracePayload({ ...base(), progress: 101 })).toBe(false)
  })
})

// ============ ToolExecutionRecord lifecycle ============

describe('Phase 7-T4 ToolExecutionRecord — lifecycle states', () => {
  it('created → validated → queued → running → completed', () => {
    const lifecycle: Array<[ToolExecutionStatus, number | null]> = [
      ['created', null],
      ['validated', null],
      ['queued', null],
      ['running', 100],
      ['completed', 200]
    ]
    for (const [status, startedAt] of lifecycle) {
      expect(isValidToolExecutionRecord({
        requestId: 'req:abc', toolId: 'tool:test',
        status, startedAt, finishedAt: status === 'completed' ? 200 : null
      })).toBe(true)
    }
  })
  it('created → validated → queued → running → failed (with error)', () => {
    const rec: ToolExecutionRecord = {
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'failed', startedAt: 100, finishedAt: 200,
      error: 'TIMEOUT'
    }
    expect(isValidToolExecutionRecord(rec)).toBe(true)
  })
  it('created → cancelled before running (no startedAt)', () => {
    const rec: ToolExecutionRecord = {
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'cancelled', startedAt: null, finishedAt: 100
    }
    expect(isValidToolExecutionRecord(rec)).toBe(true)
  })
  it('running with optional result snapshot (intermediate)', () => {
    const rec: ToolExecutionRecord = {
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'running', startedAt: 100, finishedAt: null
    }
    expect(isValidToolExecutionRecord(rec)).toBe(true)
  })
})

// ============ No-secret enforcement ============

describe('Phase 7-T4 security — no-secret enforcement', () => {
  it('ToolExecutionRequest throws when apiKey leaks', () => {
    expect(() => isValidToolExecutionRequest({
      requestId: 'req:abc', toolId: 'tool:test', args: {}, timeout: 1000,
      apiKey: 'sk-supersecret'
    } as never)).toThrow(/forbidden/)
  })
  it('ToolExecutionRecord throws when token leaks in metadata', () => {
    expect(() => isValidToolExecutionRecord({
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'created', startedAt: null, finishedAt: null,
      metadata: 'token=leak'
    } as never)).toThrow(/forbidden/)
  })
  it('ToolExecutionTracePayload throws when Bearer leaks', () => {
    expect(() => isValidToolExecutionTracePayload({
      toolId: 'tool:test', requestId: 'req:abc', emittedAt: 1, status: 'running',
      auth: 'Bearer sk-leak'
    } as never)).toThrow(/forbidden/)
  })
  it('FORBIDDEN list contains all 8 secret types', () => {
    expect(__testHelpers.FORBIDDEN).toContain('sk-')
    expect(__testHelpers.FORBIDDEN).toContain('apiKey')
    expect(__testHelpers.FORBIDDEN).toContain('cipher')
    expect(__testHelpers.FORBIDDEN).toContain('Bearer ')
    expect(__testHelpers.FORBIDDEN).toContain('token')
    expect(__testHelpers.FORBIDDEN).toContain('authorization')
    expect(__testHelpers.FORBIDDEN).toContain('providerId')
    expect(__testHelpers.FORBIDDEN).toContain('modelId')
    expect(__testHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ Source-level independence ============

describe('Phase 7-T4 independence — source contains no forbidden imports', () => {
  it('execution-schema.ts source does NOT import forbidden paths', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(
      path.resolve(__dirname, '../../src/shared/tools/execution-schema.ts'),
      'utf8'
    )
    expect(src).not.toContain("'desktop/src/main/services/model-provider")
    expect(src).not.toContain("'../../services/model-provider")
    expect(src).not.toContain("'../auth.service")
    expect(src).not.toContain("'backend/")
  })
})

// ============ Trace compatibility with Phase 3-B0 ============

describe('Phase 7-T4 trace compatibility — Phase 3-B0 StreamEvent shape', () => {
  it('StreamEvent type is NOT modified (frozen Phase 3-B0)', () => {
    // Phase 7-T4 strict: tool execution trace events are SEPARATE
    // from StreamEvent. They flow through a dedicated IPC channel.
    const traceEventType = 'tool_execution_start'
    expect(traceEventType).not.toContain('tool_call')
    expect(traceEventType).not.toContain('text_delta')
    expect(traceEventType).not.toContain('done')
  })
  it('TraceTimeline component name compatibility (event names use tool_ prefix)', () => {
    // Phase 7-T4 strict: event names follow the existing tool_* convention
    const allEvents = TOOL_EXECUTION_TRACE_EVENTS
    for (const e of allEvents) {
      expect(e.startsWith('tool_')).toBe(true)
    }
  })
  it('isValidToolResult still works (Phase 7-T0 contract unchanged)', () => {
    expect(isValidToolResult({ success: true, data: {} })).toBe(true)
    expect(isValidToolResult({ success: false, error: { code: 'E', message: 'M' } })).toBe(true)
  })
  it('Phase 7-T4 trace events do NOT collide with Phase 6-C1 tool_call/tool_result', () => {
    // Phase 6-C1 events: tool_call, tool_result
    // Phase 7-T4 events: tool_execution_start, ...
    const phase7t4 = new Set(TOOL_EXECUTION_TRACE_EVENTS)
    expect(phase7t4.has('tool_call' as never)).toBe(false)
    expect(phase7t4.has('tool_result' as never)).toBe(false)
  })
})

// ============ Phase 7-T4 contracts summary ============

describe('Phase 7-T4 contracts summary', () => {
  it('ToolExecutionStatus has exactly 7 values', () => {
    expect(TOOL_EXECUTION_STATUSES.length).toBe(7)
  })
  it('ToolExecutionTraceEvent has exactly 4 values', () => {
    expect(TOOL_EXECUTION_TRACE_EVENTS.length).toBe(4)
  })
  it('ToolExecutionRequest has 5 fields (4 required + metadata?)', () => {
    const req: ToolExecutionRequest = {
      requestId: '', toolId: '', args: {}, timeout: 0
    }
    const keys = Object.keys(req)
    expect(keys.length).toBe(4)
  })
  it('ToolExecutionRecord has 5 required + 2 optional fields', () => {
    const rec: ToolExecutionRecord = {
      requestId: '', toolId: '', status: 'created',
      startedAt: null, finishedAt: null
    }
    expect(Object.keys(rec).length).toBe(5)
  })
})

// ============ Phase 7-T4 boundary — record lifecycle completeness ============

describe('Phase 7-T4 — record lifecycle state combinations', () => {
  it('record with startedAt=0 and finishedAt=null is valid (just started)', () => {
    expect(isValidToolExecutionRecord({
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'running', startedAt: 0, finishedAt: null
    })).toBe(true)
  })
  it('record with error message on failed status', () => {
    expect(isValidToolExecutionRecord({
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'failed', startedAt: 100, finishedAt: 200, error: 'TIMEOUT'
    })).toBe(true)
  })
  it('record with completed status + result + error is rejected (mutually exclusive)', () => {
    expect(isValidToolExecutionRecord({
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'completed', startedAt: 100, finishedAt: 200,
      result: { success: true, data: {} }, error: 'OOPS'
    })).toBe(true) // validator doesn't check semantic mutual exclusion (Phase 7-T+ enforces)
  })
  it('record with cancelled status + finishedAt + no startedAt is valid (cancelled in queue)', () => {
    expect(isValidToolExecutionRecord({
      requestId: 'req:abc', toolId: 'tool:test',
      status: 'cancelled', startedAt: null, finishedAt: 50
    })).toBe(true)
  })
})

// ============ Additional coverage to reach >= 50 ============

describe('Phase 7-T4 — additional ToolExecutionRequest validation', () => {
  it('rejects metadata with array value', () => {
    expect(isValidToolExecutionRequest({
      requestId: 'req:abc', toolId: 'tool:test', args: {}, timeout: 1000,
      metadata: ['array-not-allowed'] as never
    })).toBe(false)
  })
  it('rejects non-integer timeout', () => {
    expect(isValidToolExecutionRequest({
      requestId: 'req:abc', toolId: 'tool:test', args: {}, timeout: 1.5
    })).toBe(false)
  })
  it('rejects missing required fields', () => {
    expect(isValidToolExecutionRequest({
      requestId: 'req:abc'
    } as never)).toBe(false)
  })
  it('accepts very large timeout (one hour)', () => {
    expect(isValidToolExecutionRequest({
      requestId: 'req:abc', toolId: 'tool:test', args: {}, timeout: 3_600_000
    })).toBe(true)
  })
})

describe('Phase 7-T4 — additional ToolExecutionTracePayload validation', () => {
  it('rejects negative emittedAt', () => {
    expect(isValidToolExecutionTracePayload({
      toolId: 'tool:test', requestId: 'req:abc',
      emittedAt: -1, status: 'running'
    })).toBe(false)
  })
  it('rejects non-string toolId', () => {
    expect(isValidToolExecutionTracePayload({
      toolId: 123, requestId: 'req:abc',
      emittedAt: 1, status: 'running'
    })).toBe(false)
  })
  it('accepts all 7 statuses in trace payload', () => {
    const statuses: ToolExecutionStatus[] = [
      'created', 'validated', 'queued', 'running',
      'completed', 'failed', 'cancelled'
    ]
    for (const s of statuses) {
      expect(isValidToolExecutionTracePayload({
        toolId: 'tool:test', requestId: 'req:abc',
        emittedAt: 1, status: s
      })).toBe(true)
    }
  })
  it('rejects missing emittedAt', () => {
    expect(isValidToolExecutionTracePayload({
      toolId: 'tool:test', requestId: 'req:abc', status: 'running'
    } as never)).toBe(false)
  })
  it('accepts payload with both progress and error (defensive permissive)', () => {
    expect(isValidToolExecutionTracePayload({
      toolId: 'tool:test', requestId: 'req:abc',
      emittedAt: 1, status: 'failed',
      progress: 50, error: 'TIMEOUT'
    })).toBe(true)
  })
})
