# Tool Executor Architecture (Phase 7-T4)

> **purpose**: Define the runtime architecture for Tool execution. The Executor is the layer that actually runs an Adapter. Phase 7-T4 ships the architecture + contracts — NO implementation.
> **follows**: `tool-capability-schema.ts` (Phase 7-T3) + `tool-adapter-schema.ts` (Phase 7-T2) + `tool-registry-runtime.md` (Phase 7-T1).
> **Phase 7-T4 strict**: architecture only. NO real execution. NO IPC.

## 1. Scope (Phase 7-T4 frozen)

Phase 7-T4 ships:
- `ToolExecutionStatus` enum (7 lifecycle states)
- `ToolExecutionRequest` type
- `ToolExecutionRecord` type
- `ToolExecutionTraceEvent` enum (4 events)
- `ToolExecutionTracePayload` type
- 5 validators with `assertNoSecret` guard

Phase 7-T4 does **NOT** ship:
- ❌ A concrete Executor class
- ❌ An event emitter / observer implementation
- ❌ IPC for execution events
- ❌ A timeout scheduler
- ❌ Real adapter execution

## 2. 6-layer stack (Phase 7-T4)

```
                  Agent (Phase 7-G)
                      │
                      ▼
              Tool Matcher (Phase 7-T3)
                      │
                      ▼
              Tool Registry (Phase 7-T1)
                      │
                      ▼
            Adapter Registry (Phase 7-T2)
                      │
                      ▼
        ┌──────────────────────────────┐
        │      Tool Executor           │   Phase 7-T4 (this commit)
        │      - lifecycle             │
        │      - timeout               │
        │      - error handling        │
        │      - cancellation          │
        │      - trace events          │
        └──────────────┬───────────────┘
                       │
                       ▼
              Existing Application
                (Functions / Services)
```

Six layers, each with a single responsibility. Phase 7-T4 freezes the fifth layer.

## 3. ToolExecutor interface (Phase 7-T4)

```ts
interface ToolExecutor {
  submit(request: ToolExecutionRequest): Promise<ToolExecutionRecord>
  validate(request: ToolExecutionRequest): Promise<{ ok: boolean; reason?: string }>
  execute(requestId: string): Promise<ToolExecutionRecord>
  cancel(requestId: string): Promise<{ ok: boolean; reason?: string }>
  status(requestId: string): Promise<ToolExecutionRecord | null>
}
```

### Method responsibilities (Phase 7-T4)

| Method | Returns | Phase 7-T4 contract |
|--------|---------|---------------------|
| `submit` | `Promise<ToolExecutionRecord>` | Validates + executes asynchronously |
| `validate` | `{ ok, reason? }` | Pure validation (no side effects) |
| `execute` | `Promise<ToolExecutionRecord>` | Runs the adapter (after `submit` or directly) |
| `cancel` | `{ ok, reason? }` | Cancels a running execution (best-effort) |
| `status` | `ToolExecutionRecord \| null` | Returns current state |

## 4. Lifecycle (Phase 7-T4)

```
                ┌──────────┐
                │ created  │  request received
                └────┬─────┘
                     │ validate()
                     ▼
                ┌──────────┐
                │validated │  schema + permission checks passed
                └────┬─────┘
                     │ enqueue()
                     ▼
                ┌──────────┐
                │  queued  │  waiting for executor slot
                └────┬─────┘
                     │ executor picks up
                     ▼
                ┌──────────┐
                │ running  │  adapter.execute() in progress
                └────┬─────┘
            ┌────────┼────────┐
            │        │        │
            ▼        ▼        ▼
       ┌─────────┐ ┌──────┐ ┌─────────┐
       │completed│ │failed│ │cancelled│
       └─────────┘ └──────┘ └─────────┘
```

Five valid transitions + one off-path (cancelled at any point before completed).

## 5. Executor responsibilities (Phase 7-T4 strict)

The Executor:

- ✅ Takes a `ToolExecutionRequest`
- ✅ Validates args via `validateToolArgs(definition, args)` (Phase 7-T0)
- ✅ Enforces `request.timeout` via `AbortSignal.timeout()` (Phase 7-T+)
- ✅ Catches all exceptions → `ToolResult { success: false, error }`
- ✅ Calls `isValidToolResult(result)` + `assertNoSecret(result)`
- ✅ Emits `ToolExecutionTraceEvent` on each lifecycle transition
- ✅ Tracks state in a `ToolExecutionRecord`
- ✅ Handles cancellation via `cancel(requestId)`

The Executor does NOT:

- ❌ Select tools (Phase 7-T3 Matcher does this)
- ❌ Call LLM models (Phase 7-G Agent does this)
- ❌ Manage Knowledge entities (Phase 7-A0/7-B+)
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Hold apiKey / token / cipher

## 6. Trace event timeline (Phase 7-T4)

A single execution emits up to 4 events:

```
T0  submit()             -> (validate inline)             no event (synchronous)
T1  validate()           -> ok                             no event (synchronous)
T2  enqueue()            -> status: queued                 event: tool_execution_start
T3  executor picks up    -> status: running               event: tool_execution_progress (optional)
T4  adapter.execute()    -> status: completed             event: tool_execution_complete
                                                               OR
                            status: failed                event: tool_execution_error
```

Phase 7-T4 strict: the trace event names use the `tool_execution_*` prefix to remain compatible with the existing `TraceTimeline` component (Phase 6-C1).

## 7. Timeout policy (Phase 7-T4 strict)

The Executor enforces `request.timeout` via:

```
Promise.race([
  adapter.execute(args, ctx),
  new Promise((_, reject) =>
    setTimeout(() => reject(new Error('TIMEOUT')), request.timeout)
  )
])
```

When `request.timeout` elapses:
1. The adapter's `execute()` Promise is cancelled (Phase 7-T+: via AbortController)
2. The record's status becomes `failed` with `error: 'TIMEOUT'`
3. A `tool_execution_error` trace event is emitted

Phase 7-T4 strict: timeout is enforced by the Executor, NOT by the Adapter.

## 8. Cancellation policy (Phase 7-T4 strict)

`cancel(requestId)` is best-effort:

- If `status = 'queued'`: remove from queue → `status = 'cancelled'`
- If `status = 'running'`: send abort signal to the adapter → `status = 'failed'` with `error: 'CANCELLED'`
- If `status ∈ {'completed', 'failed', 'cancelled'}`: return `{ ok: false, reason: 'already terminal' }`

## 9. Phase 7-T4 strict forbids

- ❌ Implement a concrete Executor class
- ❌ Add IPC for execution events
- ❌ Wrap any existing function
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `backend/`
- ❌ Connect to a database

## 10. References

- `docs/tools/tool-capability-matching.md` (Phase 7-T3)
- `docs/tools/tool-adapter-architecture.md` (Phase 7-T2)
- `docs/tools/tool-registry-runtime.md` (Phase 7-T1)
- `desktop/src/shared/tools/execution-schema.ts` (Phase 7-T4 — THIS COMMIT)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0)
- `desktop/src/shared/tools/tool-adapter-schema.ts` (Phase 7-T2)

## Status (2026-08-22 Phase 7-T4)

- `ToolExecutionStatus` enum (7 lifecycle states)
- `ToolExecutionRequest` type
- `ToolExecutionRecord` type
- `ToolExecutionTraceEvent` enum (4 events compatible with TraceTimeline)
- `ToolExecutionTracePayload` type
- 5 validators with assertNoSecret guard
- 0 implementations (Phase 7-T4 ships ONLY the architecture + contracts)
- Doc complete (10 sections)
