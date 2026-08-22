# Tool Trace Integration (Phase 7-T4)

> **purpose**: Define how the Tool Executor's trace events integrate with the existing TraceTimeline component (Phase 6-C1) and the broader StreamEvent shape (Phase 3-B0 frozen).
> **follows**: `tool-executor-architecture.md` (Phase 7-T4) + `chat-trace-timeline.md` (Phase 6-C1).
> **Phase 7-T4 strict**: integration design only. NO implementation. NO IPC.

## 1. Scope (Phase 7-T4 frozen)

Phase 7-T4 ships:
- 4 `ToolExecutionTraceEvent` names (compatible with TraceTimeline)
- `ToolExecutionTracePayload` shape
- Integration flow with the existing TraceTimeline component
- Compatibility assertions with Phase 3-B0 StreamEvent

Phase 7-T4 does **NOT** ship:
- ❌ A concrete Executor that emits trace events
- ❌ IPC channels for trace events
- ❌ Modifications to TraceTimeline.vue
- ❌ Modifications to the StreamEvent shape

## 2. TraceTimeline compatibility (Phase 7-T4 strict)

The existing `TraceTimeline` component (Phase 6-C1) consumes `TraceEvent` shapes. Phase 7-T4 trace events use the SAME naming convention (`tool_*`) so the renderer can route them through the existing `TraceTimeline` without schema changes.

### Existing TraceEvent names (Phase 6-C1)

```
- tool_call
- tool_result
- trace_step
- agent_thinking
- knowledge_lookup
- (others...)
```

### New ToolExecutionTraceEvent names (Phase 7-T4)

```
- tool_execution_start
- tool_execution_progress
- tool_execution_complete
- tool_execution_error
```

These names follow the `tool_*` prefix that TraceTimeline already recognizes. Phase 7-T4 strict: the new names do NOT collide with Phase 6-C1 names.

## 3. Trace event lifecycle (Phase 7-T4)

```
T0  submit()
T1  validate()                    -> ok (synchronous; no event)
T2  enqueue()                     -> status: queued
                                   event: tool_execution_start { requestId, toolId, status: 'queued' }
T3  executor picks up             -> status: running
                                   event: tool_execution_progress (optional; progress=0)
T4  adapter.execute() running     -> status: running
                                   event: tool_execution_progress (optional; progress=N)
T5  adapter returns success        -> status: completed
                                   event: tool_execution_complete { status: 'completed', result: {...} }
                                   OR
T5' adapter returns failure       -> status: failed
                                   event: tool_execution_error { status: 'failed', error: '...' }
T6  user cancels                  -> status: cancelled
                                   event: tool_execution_error { status: 'cancelled', error: 'CANCELLED' }
```

## 4. ToolExecutionTracePayload (Phase 7-T4)

```ts
interface ToolExecutionTracePayload {
  toolId: string                  // matches ToolExecutionRequest.toolId
  requestId: string               // matches ToolExecutionRecord.requestId
  emittedAt: number               // epoch ms
  status: ToolExecutionStatus      // status at event time
  progress?: number               // [0, 100]; only on tool_execution_progress
  error?: string                  // only on tool_execution_error
}
```

Phase 7-T4 strict: the payload NEVER carries `args.data` (only metadata). Args themselves are logged at `submit` time only.

## 5. StreamEvent integration (Phase 3-B0 frozen)

The existing `StreamEvent` type (Phase 3-B0) has shape:

```ts
interface StreamEvent {
  type: StreamEventType
  delta?: string
  tool_name?: string
  tool_use_id?: string
  tool_input?: Record<string, unknown>
  tool_output?: Record<string, unknown>
  reasoning?: string
  block?: Record<string, unknown>
  error_code?: string
  message?: string
  finish_reason?: string
  usage?: Record<string, number>
}
```

Phase 7-T4 strict: StreamEvent shape is NOT modified. Tool execution trace events are SEPARATE from StreamEvent — they flow through a dedicated IPC channel (Phase 7-T+).

## 6. TraceTimeline component integration (Phase 7-T4 strict)

The existing `TraceTimeline` component (Phase 6-C1) consumes `TraceEvent[]`. Phase 7-T4 trace events are designed to fit this shape:

```ts
interface TraceEvent {
  type: string                     // e.g. 'tool_execution_start'
  payload: Record<string, unknown> // contains the ToolExecutionTracePayload
  emittedAt: number                // epoch ms
}
```

The Phase 7-T+ integration translates `ToolExecutionTraceEvent` + `ToolExecutionTracePayload` into this `TraceEvent` shape. Phase 7-T4 ships ONLY the upstream contract.

## 7. Renderer integration (Phase 7-T4 strict)

When the renderer receives a `tool_execution_*` trace event:

1. The chat-stream Pinia store (Phase 6-C1) routes it to `TraceTimeline.vue`
2. TraceTimeline displays the event with:
   - `toolId` as the agent / tool name
   - `status` as the lifecycle state
   - `progress` as a progress bar (if present)
   - `error` as an inline error badge (if present)

Phase 7-T4 strict: the renderer NEVER sees `args.data` in the trace. Only `metadata` (e.g. latencyMs, latency).

## 8. Event name registry (Phase 7-T4)

Phase 7-T4 ships 4 trace events:

| Event name | Phase | Status |
|------------|-------|--------|
| `tool_execution_start` | 7-T4 | new (Phase 7-T4) |
| `tool_execution_progress` | 7-T4 | new (Phase 7-T4) |
| `tool_execution_complete` | 7-T4 | new (Phase 7-T4) |
| `tool_execution_error` | 7-T4 | new (Phase 7-T4) |

The existing `tool_call` and `tool_result` (Phase 6-C1) are NOT replaced. They remain for the legacy LLM-level tool calling. The new events are at the EXECUTOR level (one layer above).

## 9. Phase 7-T4 strict forbids

- ❌ Modify the existing TraceTimeline component
- ❌ Modify the existing StreamEvent shape (Phase 3-B0 frozen)
- ❌ Add IPC channels for trace events (Phase 7-T+)
- ❌ Replace the existing `tool_call` / `tool_result` events
- ❌ Couple trace events to model-provider / auth / chat

## 10. References

- `docs/tools/tool-executor-architecture.md` (Phase 7-T4 — Executor)
- `docs/tools/tool-execution-security.md` (Phase 7-T4 — Security)
- `docs/chat-trace-timeline.md` (Phase 6-C1 — TraceTimeline)
- `desktop/src/shared/tools/execution-schema.ts` (Phase 7-T4 — THIS COMMIT)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0)
- `docs/desktop-conversion/chat-trace-timeline.md` (Phase 6-C1 — frozen contract)

## Status (2026-08-22 Phase 7-T4)

- 4 ToolExecutionTraceEvent names compatible with TraceTimeline
- ToolExecutionTracePayload shape (no args leak)
- Integration flow with Phase 6-C1 TraceTimeline (no source modification)
- StreamEvent (Phase 3-B0) compatibility asserted (NOT modified)
- 0 implementations (Phase 7-T4 ships ONLY the integration design)
- Doc complete (10 sections)
