// Tool Executor Core Runtime (Phase 7-T5-A: Tool Executor Core Runtime).
//
// Phase 7-T5-A: the in-process Tool Executor that:
//   1. Validates incoming requests
//   2. Looks up ToolDefinition via ToolRegistry
//   3. Looks up adapter via injected adapter resolver
//   4. Runs adapter.execute() with timeout + cancellation
//   5. Maintains ToolExecutionRecord lifecycle
//   6. Emits trace events (Phase 7-T4 compatible)
//
// Phase 7-T5-A frozen contract:
//   - ToolExecutor class with 6 methods (submit / validate / execute /
//     cancel / status / listRunning)
//   - Uses ToolRegistry.get(toolId) for ToolDefinition lookup
//   - Uses injected adapterResolver (Phase 7-T5-A: NOT AdapterRegistry class)
//   - Maintains Map<requestId, ToolExecutionRecord> in memory
//   - Timeout via Promise.race + setTimeout (AbortSignal deferred to Phase 7-T+)
//   - Cancellation via AbortController + signal
//   - Emits 4 trace events compatible with TraceTimeline
//
// Phase 7-T5-A strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - NEVER calls any existing application function directly
//   - NEVER imports from model-provider / auth / chat / backend
//   - Process-lifetime state only (no disk persistence)

import {
  type ToolExecutionRequest,
  type ToolExecutionRecord,
  type ToolExecutionStatus,
  type ToolExecutionTracePayload,
  type ToolExecutionTraceEvent,
  isValidToolExecutionRequest
} from '../../../shared/tools/execution-schema'
import {
  assertNoSecret,
  isValidToolResult,
  type ToolResult
} from '../../../shared/tools/tool-schema'
import type { ToolDefinition } from '../../../shared/tools/tool-schema'

import { ToolExecutionQueue } from './execution-queue'
import { ToolExecutionEventEmitter } from './tool-execution-events'

/**
 * Phase 7-T5-A: the function-shaped adapter contract.
 * The Executor calls this with the validated args + ctx; the adapter
 * returns a ToolResult. The Executor wraps the call with timeout +
 * cancellation + lifecycle management.
 */
export type ToolExecutorFn = (
  args: unknown,
  ctx: { requestId: string; abortSignal: AbortSignal; metadata?: Record<string, unknown> }
) => Promise<ToolResult>

/**
 * Phase 7-T5-A: injected adapter resolver.
 * The Executor does NOT know about AdapterRegistry class (Phase 7-T+).
 * Tests inject a function that maps toolId -> ToolExecutorFn.
 */
export type AdapterResolver = (toolId: string) => ToolExecutorFn | null

/**
 * Phase 7-T5-A: injected ToolDefinition resolver.
 * The Executor does NOT know about ToolRegistry class (Phase 7-T+).
 * Tests inject a function that maps toolId -> ToolDefinition.
 */
export type DefinitionResolver = (toolId: string) => ToolDefinition | null

export interface ToolExecutorOptions {
  /** Phase 7-T5-A: resolve a ToolDefinition by id. */
  resolveDefinition: DefinitionResolver
  /** Phase 7-T5-A: resolve an adapter function by id. */
  resolveAdapter: AdapterResolver
  /** Phase 7-T5-A: clock for testability. Defaults to Date.now. */
  clock?: () => number
  /** Phase 7-T5-A: optional event emitter (auto-created if absent). */
  emitter?: ToolExecutionEventEmitter
}

/**
 * Phase 7-T5-A: in-process Tool Executor runtime.
 *
 * Maintains:
 *   - records: Map<requestId, ToolExecutionRecord>
 *   - queue: FIFO pending requestIds
 *   - abortControllers: Map<requestId, AbortController>
 *   - emitter: trace event emitter
 *
 * Does NOT call any existing application function directly. Tests inject
 * an adapter resolver that returns mock ToolExecutorFn.
 */
export class ToolExecutor {
  private readonly records: Map<string, ToolExecutionRecord> = new Map()
  private readonly requests: Map<string, ToolExecutionRequest> = new Map()
  private readonly queue: ToolExecutionQueue = new ToolExecutionQueue()
  private readonly abortControllers: Map<string, AbortController> = new Map()
  private readonly emitter: ToolExecutionEventEmitter
  private readonly resolveDefinition: DefinitionResolver
  private readonly resolveAdapter: AdapterResolver
  private readonly clock: () => number

  constructor(options: ToolExecutorOptions) {
    if (!options.resolveDefinition) {
      throw new Error('ToolExecutor: resolveDefinition is required (Phase 7-T5-A strict)')
    }
    if (!options.resolveAdapter) {
      throw new Error('ToolExecutor: resolveAdapter is required (Phase 7-T5-A strict)')
    }
    this.resolveDefinition = options.resolveDefinition
    this.resolveAdapter = options.resolveAdapter
    this.clock = options.clock ?? (() => Date.now())
    this.emitter = options.emitter ?? new ToolExecutionEventEmitter()
  }

  /** Phase 7-T5-A: number of pending records (created / validated / queued / running). */
  listRunning(): ToolExecutionRecord[] {
    const out: ToolExecutionRecord[] = []
    for (const r of this.records.values()) {
      const s = r.status
      if (s === 'created' || s === 'validated' || s === 'queued' || s === 'running') {
        out.push(r)
      }
    }
    return out.sort((a, b) => a.requestId.localeCompare(b.requestId))
  }

  /** Phase 7-T5-A: get a record by id. */
  status(requestId: string): ToolExecutionRecord | null {
    return this.records.get(requestId) ?? null
  }

  /**
   * Phase 7-T5-A: validate a request WITHOUT starting execution.
   * Pure check — does NOT modify executor state.
   */
  validate(request: ToolExecutionRequest): { ok: boolean; reason?: string } {
    if (!isValidToolExecutionRequest(request)) {
      return { ok: false, reason: 'invalid ToolExecutionRequest (Phase 7-T5-A strict)' }
    }
    assertNoSecret(request.args, 'validate.args')
    const def = this.resolveDefinition(request.toolId)
    if (!def) {
      return { ok: false, reason: `unknown toolId '${request.toolId}' (Phase 7-T5-A strict)` }
    }
    return { ok: true }
  }

  /**
   * Phase 7-T5-A: submit a request for execution.
   * Creates the record, validates, enqueues, and returns the record.
   * Does NOT start execution synchronously; the Executor processes the
   * queue asynchronously via `execute(requestId)` or auto-drain.
   */
  submit(request: ToolExecutionRequest): ToolExecutionRecord {
    if (!isValidToolExecutionRequest(request)) {
      throw new Error('ToolExecutor.submit: invalid ToolExecutionRequest (Phase 7-T5-A strict)')
    }
    assertNoSecret(request.args, 'submit.args')
    const def = this.resolveDefinition(request.toolId)
    if (!def) {
      throw new Error(`ToolExecutor.submit: unknown toolId '${request.toolId}' (Phase 7-T5-A strict)`)
    }
    const record: ToolExecutionRecord = {
      requestId: request.requestId,
      toolId: request.toolId,
      status: 'queued',
      startedAt: null,
      finishedAt: null
    }
    this.records.set(request.requestId, record)
    this.requests.set(request.requestId, request)
    this.queue.enqueue(request.requestId)
    this.emit('tool_execution_start', record, 'queued')
    return record
  }

  /**
   * Phase 7-T5-A: dequeue and execute the next pending request.
   * Returns the final record, or null when queue is empty.
   *
   * Uses Promise.race against a timeout Promise (Phase 7-T5-A: setTimeout-based).
   * Emits `tool_execution_progress` at start, `tool_execution_complete` on
   * success, or `tool_execution_error` on failure / timeout / cancellation.
   */
  async execute(requestId: string): Promise<ToolExecutionRecord | null> {
    const record = this.records.get(requestId)
    if (!record) return null
    const request = this.requests.get(requestId)
    if (!request) {
      this.fail(requestId, 'INTERNAL_ERROR', 'request not found in store')
      return record
    }
    const def = this.resolveDefinition(record.toolId)
    if (!def) {
      this.fail(requestId, 'adapter-not-found', 'adapter resolution returned null')
      return record
    }
    const adapter = this.resolveAdapter(record.toolId)
    if (!adapter) {
      this.fail(requestId, 'adapter-not-found', 'adapter resolution returned null')
      return record
    }

    // Move status: queued/created/validated -> running
    record.status = 'running'
    record.startedAt = this.clock()
    this.queue.remove(requestId)
    this.emit('tool_execution_progress', record, 'running')

    // Set up cancellation
    const ac = new AbortController()
    this.abortControllers.set(requestId, ac)

    try {
      const result = await this.runWithTimeout(
        request,
        adapter,
        ac.signal
      )
      if (result.success) {
        this.complete(requestId, result)
      } else {
        this.fail(
          requestId,
          'EXECUTION_ERROR',
          result.error?.message ?? 'adapter returned success=false'
        )
      }
    } catch (e) {
      if (ac.signal.aborted) {
        this.cancelInternal(requestId)
      } else if (e instanceof Error && e.message === 'TIMEOUT') {
        this.fail(requestId, 'TIMEOUT', 'execution exceeded timeout')
      } else {
        this.fail(requestId, 'EXECUTION_ERROR',
          e instanceof Error ? e.message : String(e))
      }
    } finally {
      this.abortControllers.delete(requestId)
    }

    return this.records.get(requestId) ?? null
  }

  /** Phase 7-T5-A: cancel a running (or queued) execution. */
  cancel(requestId: string): { ok: boolean; reason?: string } {
    const record = this.records.get(requestId)
    if (!record) return { ok: false, reason: 'unknown requestId' }
    if (record.status === 'completed' || record.status === 'failed' || record.status === 'cancelled') {
      return { ok: false, reason: 'already terminal' }
    }
    // queued: remove from queue + mark cancelled
    if (record.status === 'queued' || record.status === 'created' || record.status === 'validated') {
      this.queue.remove(requestId)
      this.cancelInternal(requestId)
      return { ok: true }
    }
    // running: signal abort
    const ac = this.abortControllers.get(requestId)
    if (ac) {
      ac.abort()
      return { ok: true }
    }
    return { ok: false, reason: 'no abort controller' }
  }

  // ---------- private helpers ----------

  private async runWithTimeout(
    request: ToolExecutionRequest,
    adapter: ToolExecutorFn,
    abortSignal: AbortSignal
  ): Promise<ToolResult> {
    const ctx = {
      requestId: request.requestId,
      abortSignal,
      ...(request.metadata !== undefined ? { metadata: request.metadata } : {})
    }
    const work = adapter(request.args, ctx)
    if (request.timeout <= 0) {
      return await work
    }
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null
    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutHandle = setTimeout(() => reject(new Error('TIMEOUT')), request.timeout)
    })
    try {
      return await Promise.race([work, timeoutPromise])
    } finally {
      if (timeoutHandle !== null) clearTimeout(timeoutHandle)
    }
  }

  private complete(requestId: string, result: ToolResult): void {
    const record = this.records.get(requestId)
    if (!record) return
    if (!isValidToolResult(result)) {
      this.fail(requestId, 'SANITIZATION_FAILED', 'result failed isValidToolResult')
      return
    }
    assertNoSecret(result, 'complete.result')
    record.status = 'completed'
    record.finishedAt = this.clock()
    record.result = result
    this.emit('tool_execution_complete', record, 'completed')
  }

  private fail(requestId: string, code: string, message: string): void {
    const record = this.records.get(requestId)
    if (!record) return
    record.status = 'failed'
    record.finishedAt = this.clock()
    record.error = message
    this.emit('tool_execution_error', record, 'failed', message)
    void code  // code reserved for Phase 7-T+
  }

  private cancelInternal(requestId: string): void {
    const record = this.records.get(requestId)
    if (!record) return
    record.status = 'cancelled'
    record.finishedAt = this.clock()
    record.error = 'CANCELLED'
    this.emit('tool_execution_error', record, 'cancelled', 'CANCELLED')
    this.abortControllers.delete(requestId)
  }

  private emit(
    event: ToolExecutionTraceEvent,
    record: ToolExecutionRecord,
    status: ToolExecutionStatus,
    error?: string
  ): void {
    const payload: ToolExecutionTracePayload = {
      toolId: record.toolId,
      requestId: record.requestId,
      emittedAt: this.clock(),
      status,
      ...(error !== undefined ? { error } : {})
    }
    try {
      this.emitter.emitTrace(event, payload)
    } catch (e) {
      // Phase 7-T5-A strict: a payload-validation failure must NOT crash
      // the Executor. Swallow and continue.
      void e
    }
  }

  /** Phase 7-T5-A: get the event emitter (Phase 7-T+ IPC integration point). */
  getEmitter(): ToolExecutionEventEmitter {
    return this.emitter
  }

  /** Phase 7-T5-A: get the queue size (testing helper). */
  queueSize(): number {
    return this.queue.size()
  }
}
