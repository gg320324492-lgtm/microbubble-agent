# Agent Tool Calling Interface (Phase 7-T0)

> **purpose**: Define how the Agent calls Tools. Phase 7-T0 ships the flow + interfaces — NO planner, NO LLM SDK calls.
> **follows**: `tool-registry-architecture.md` (Phase 7-T0) + `tool-security-boundary.md` (Phase 7-T0) + `tool-schema.ts` (Phase 7-T0).
> **Phase 7-T0 strict**: interface only. NO Agent planner implementation.

## 1. Scope (Phase 7-T0 frozen)

Phase 7-T0 ships:
- Future Agent tool-calling flow (diagram + 6-step sequence)
- `AgentToolRequest` / `AgentToolResponse` types (Phase 7+ future)
- LLM tool-calling JSON shape (Phase 7+ future)
- Boundary between Agent planner and Tool Registry

Phase 7-T0 does **NOT** ship:
- ❌ An Agent planner implementation
- ❌ LLM tool-call parsing
- ❌ ReAct / function-calling loop
- ❌ Tool result aggregation strategy

## 2. Tool calling flow (Phase 7-T0 design)

```
            User Request
                 │
                 ▼
        ┌──────────────────┐
        │  Agent Planner   │   Phase 7-G
        │  (NOT 7-T0)      │
        └────────┬─────────┘
                 │
                 ▼ (decides "call tool:kinetic-analysis with these args")
        ┌──────────────────┐
        │  Tool Selection  │   Phase 7-G
        │  (lookup get)    │
        └────────┬─────────┘
                 │
                 ▼ (ToolDefinition, args)
        ┌──────────────────┐
        │  Tool Registry   │   Phase 7-T+
        │  .execute(...)   │
        └────────┬─────────┘
                 │
                 ├─► Permission check
                 ├─► validateToolArgs
                 ├─► Permission check passes?
                 ├─► registry.executor(args, ctx)
                 ├─► isValidToolResult(result)
                 ├─► assertNoSecret(result)
                 ▼
           ┌──────────────────┐
           │   Tool Result    │
           │   (sanitized)    │
           └────────┬─────────┘
                    │
                    ▼
           ┌──────────────────┐
           │ Agent Reasoning  │   Phase 7-G
           │ (uses result)    │
           └────────┬─────────┘
                    │
                    ▼
            StreamEvent response
           (Phase 3-B0 frozen)
```

## 3. `AgentToolRequest` type (Phase 7+ sketch)

```ts
interface AgentToolRequest {
  /** Tool id (e.g. 'tool:kinetic-analysis') */
  toolId: string
  /** Validated args */
  args: Record<string, unknown>
  /** Trace id (Phase 7-G decision context) */
  traceId: string
}
```

Phase 7-T0 ships ONLY the type. Phase 7-G ships the planner that constructs this.

## 4. `AgentToolResponse` type (Phase 7+ sketch)

```ts
interface AgentToolResponse {
  toolId: string
  result: ToolResult     // sanitized, non-secret
  latencyMs: number
}
```

Phase 7-T0 ships ONLY the type. Phase 7-G consumes it for next reasoning step.

## 5. LLM tool-calling JSON shape (Phase 7+ future)

When the LLM decides to call a tool, it emits a JSON like:

```json
{
  "name": "kinetic-analysis",
  "arguments": {
    "dataset": "ds:tcd-2024-09-15",
    "model": "first-order"
  }
}
```

The format depends on the LLM provider (OpenAI / Anthropic / Qwen / Ollama). Phase 7-T0 ships ONLY the LLM-agnostic shape:

```ts
interface LLMToolCall {
  /** LLM-supplied function name; mapped to toolId via tool registry lookup */
  name: string
  /** LLM-supplied arguments; validated against ToolDefinition */
  arguments: Record<string, unknown>
}
```

The Phase 7-G planner maps `LLMToolCall.name → toolId` (via the Registry) and `LLMToolCall.arguments → AgentToolRequest.args`.

## 6. Boundary between Agent and Tool Registry

The Agent (Phase 7-G) NEVER:
- calls `ToolDefinition`-validation directly (it asks the Registry to do it)
- holds `ToolExecutor` references (those are Registry-internal)
- builds `ToolResult` directly (the Registry builds it from the executor's return)
- imports from `desktop/src/main/services/model-provider/`

The Tool Registry (Phase 7-T+) NEVER:
- calls the LLM
- holds model / provider config
- imports from `desktop/src/main/services/model-provider/`
- imports from `backend/`

## 7. Multi-step tool calling (Phase 7-T0 design)

A single user request may need multiple tool calls in sequence. Phase 7-T0 defines the flow:

```
Planner -> Tool 1 -> Result 1 -> Planner -> Tool 2 -> Result 2 -> ... -> Answer
```

Each step:
1. Tool Registry executes the tool (with permission + validation + sanitization)
2. Agent uses the result for the next reasoning step
3. Loop until the Agent decides it has enough context, OR hits a depth limit

Phase 7-G ships the planner. Phase 7-T0 ships the contract.

## 8. Error handling (Phase 7-T0 design)

Every tool call returns one of:

```
Success:          ToolResult { success: true, data: {...} }
InvalidArgs:      ToolResult { success: false, error: { code: 'INVALID_ARGS', ... } }
PermissionDenied: ToolResult { success: false, error: { code: 'PERMISSION_DENIED', ... } }
ExecutionError:   ToolResult { success: false, error: { code: 'EXECUTION_ERROR', ... } }
Timeout:          ToolResult { success: false, error: { code: 'TIMEOUT', ... } }
```

The Agent interprets `success=false` as a recoverable error (try a different tool, ask the user, etc.). `success=true` continues the reasoning loop.

## 9. Phase 7-T0 strict forbids

- ❌ Implement the Agent planner
- ❌ Implement a ReAct loop
- ❌ Parse LLM tool-call JSON
- ❌ Implement error recovery strategies
- ❌ Implement multi-step orchestration
- ❌ Import from any LLM SDK package
- ❌ Import from `desktop/src/main/services/model-provider/`

## 10. References

- `docs/tools/tool-registry-architecture.md` (Phase 7-T0 Step 6)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 Step 7)
- `docs/tools/application-adapter-design.md` (Phase 7-T0 Step 9)
- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 — Tool ↔ Knowledge)
- `docs/knowledge/rag-extension-plan.md` (Phase 7-A0 — RAG plugs into Agent ↔ Tool flow)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)
- `desktop/docs/desktop-conversion/model-runtime-routing.md` (Phase 6-A5 — frozen StreamEvent)

## Status (2026-08-22 Phase 7-T0)

- Agent tool-calling flow documented (6-step sequence)
- `AgentToolRequest` / `AgentToolResponse` types sketched (Phase 7-G)
- LLM-agnostic `LLMToolCall` shape (Phase 7-G)
- Multi-step tool calling flow (Phase 7-G)
- 5 error codes defined
- 0 implementations (Phase 7-T0 ships ONLY the interface)
- Doc complete (10 sections)
