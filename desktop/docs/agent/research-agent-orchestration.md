# Research Agent Orchestration (Phase 8-E0)

> **purpose**: Compose every research-agent subsystem behind one `run(request)` entry point and emit a single `ResearchAgentResponse`.
> **follows**: `research-planner-architecture.md` (B0), `research-agent-runtime.md` (A1), `rag-context-builder.md` (C3), `model-gateway.md` (D0).

## 1. Architecture

```
                                User
                                  |
                                  v
                          ResearchAgent.run(request)
                                  |
        +-------------------------+----------------------+
        |                         |                      |
        v                         v                      v

   PlannerService          RuntimeService         Subsystems
   (Phase 8-B0)             (Phase 8-A1)         injected via DI
        |                         |                      |
        v                         v                      v
   ResearchPlan ----------> AgentRun ---------------> Step execution
        |                         |                      |
        |                         +------------+-----------+
        |                                      |
        v                                      v
   (plan + confidence)             KnowledgeToolModel (per-step)
                                    |     |     |
                                    v     v     v
                          ResearchContextProvider  ToolExecutor  ResearchModelProvider
```

The orchestrator **does NOT** dispatch steps itself. Phase 8-A1's `ResearchAgentRuntime` already does per-step dispatch via injected `KnowledgeCaller` / `ModelCaller` / `ToolCaller`. The orchestrator simply:

1. validates the request
2. calls `planner.plan(question)`
3. calls `runtime.createRun(...)` + `runtime.executePlan(...)`
4. aggregates `AgentRun` into `ResearchAgentResponse`
5. emits lifecycle events on `AgentEventEmitter`
6. exposes `cancelRun(requestId)` for cooperative cancellation

## 2. Modules (Phase 8-E0 — all NEW, no existing source modified)

| Module | File | Responsibility |
|--------|------|----------------|
| Contracts | `src/shared/agent/research-agent-schema.ts` | `ResearchAgentRequest` / `ResearchAgentResponse` / `AgentRunStatus` / `AgentEventType` / `AgentEvent` + secret guard |
| Orchestrator | `src/main/services/agent/research-agent.ts` | `ResearchAgent` class + `AgentEventEmitter` |

## 3. Lifecycle

```
 agent_started
       |
       v
   planning ----- (planner.plan)
       |  (success: planner.plan returned a valid plan)
       v
 plan_created
       |
       v
   executing --- (runtime.createRun + runtime.executePlan)
       |
       v
 generating  --- (aggregate answer / citations / usage)
       |
       v
 agent_completed            agent_failed            (cancelled path)

Other events: context_retrieved / tool_started / tool_completed /
model_started / model_completed are emitted by the orchestrator as
forwarded runtime signals (subscribers only).
```

`cancelRun(requestId)`:
- Sets the request's `cancelled` flag immediately.
- Sets internal status to `'cancelled'`.
- Calls `runtime.cancelRun(requestId)` so any in-flight execution also exits.
- Emits `'agent_failed'` with `payload.reason = 'cancelled'`.
- `run()` checks the flag **after each major step** (after plan, after execution) so cancellation is observable and produces a cancelled response without throwing.

## 4. Dependency graph

`ResearchAgent` is constructed with **5 injected dependencies** (no singletons, no hidden globals):

```
constructor({
  planner:          PlannerLike,           // Phase 8-B0
  runtime:          RuntimeLike,           // Phase 8-A1
  contextProvider:  ContextProviderLike,   // Phase 8-C3
  modelProvider:    ModelProviderLike,     // Phase 8-D0
  toolExecutor:     ToolExecutorLike       // Phase 7-T5
})
```

All 5 are required (throws if missing). At runtime, only `planner` and `runtime` are called from `run()` directly — `contextProvider`, `modelProvider`, and `toolExecutor` are accepted in DI for **forwarding/observation hooks** (subscribers, status checks, future direct-call paths) without the orchestrator coupling to them today. Removing any of the 5 fails the constructor.

## 5. Failure recovery

| Failure point | Behavior |
|---------------|----------|
| invalid `ResearchAgentRequest` | `run()` throws `invalid ResearchAgentRequest (Phase 8-E0 strict)`. No events emitted. |
| `planner.plan` returns invalid plan | Emits `agent_failed` then throws. |
| `runtime.executePlan` rejects / throws | Emits `agent_failed`, sets status `'failed'`, rethrows. |
| Any step throws inside the runtime | Same: runtime's own error → orchestrator's catch → `agent_failed` event + rethrow. |
| Cancellation flag set before/during run | `run()` returns a `ResearchAgentResponse` with empty `answer`, empty `toolResults`, `confidence: 0`, status `'cancelled'`. Emits `agent_failed{reason:'cancelled'}`. |

## 6. Cancellation

- Pre-planning: `cancelRun(id)` before `run(id)` → `run()` exits immediately with `cancelled` response (the flag is set in DI, but `run()` checks it AFTER planning). To cancel before any work, set the flag synchronously before `await`.
- During execution: runtime receives `cancelRun(id)` and exits its current step at the next `cancelled`-safe point (per Phase 8-A1). Orchestrator's `run()` returns the partial run with empty answer.
- After execution: `run()` already returned. `cancelRun(id)` is a no-op for that id (returns `{ok:false, reason:'unknown requestId'}`).

## 7. Security boundary

- The orchestrator's request/response schemas run a string-only secret guard that walks leaf values (keys are identifiers and can't carry secrets).
- Forbidden substrings: `'sk-'`, `'apiKey'`, `'secret'`, `'token value'`, `'cipher'`, `'authorization'`, `'Bearer '`, `'providerId/'`.
- The orchestrator never embeds provider credentials, never logs request bodies, and never constructs `Authorization` headers — those live inside the model adapters (Phase 8-D0).

## 8. References

- `docs/agent/agent-runtime-vs-orchestrator.md` (responsibility split)
- `src/shared/agent/research-agent-schema.ts`
- `src/main/services/agent/research-agent.ts`
- `src/shared/agent/{research-planner-schema,research-plan-schema,agent-runtime-schema}.ts`
- `src/shared/knowledge/context-schema.ts`
- `src/shared/agent/model-gateway-schema.ts`