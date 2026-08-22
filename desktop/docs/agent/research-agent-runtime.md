# Research Agent Runtime (Phase 8-A1)

> **purpose**: Define the runtime architecture that orchestrates a ResearchPlan. Phase 8-A1 ships ONLY the contracts + in-process implementation — NO LLM SDK, NO IPC, NO UI, NO RAG.
> **follows**: `research-planner-architecture.md` (Phase 8-A0) + `research-plan-schema.ts` (Phase 8-A0).
> **Phase 8-A1 strict**: runtime orchestration only. NO planner runtime changes. NO tool execution changes. NO model-provider import.

## 1. Scope (Phase 8-A1 frozen)

Phase 8-A1 ships:
- `ResearchAgentRuntime` class (6 public methods: createRun / executePlan / executeStep / cancelRun / getRun / listRuns)
- `AgentRun` / `AgentStepExecution` / `RuntimeEvent` / `RuntimeStatus` / `AgentStepStatus` types
- Step dispatcher (5 cases: knowledge / tool / model / analysis / synthesis)
- In-memory run store (process-lifetime)
- EventEmitter for trace events
- `topologicalOrder` helper (Kahn's algorithm)
- `cancelRun` flow

Phase 8-A1 does **NOT** ship:
- ❌ LLM SDK calls (Phase 8-A1: only injected ModelCaller interface)
- ❌ RAG retrieval (Phase 7-A0/7-B+)
- ❌ IPC channels
- ❌ UI changes
- ❌ Database persistence (in-memory only)
- ❌ Auth / permission enforcement
- ❌ Vector store integration

## 2. Layer diagram (Phase 8-A1)

```
              ┌────────────────────┐
              │   User Request     │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │  createRun()       │   Phase 8-A1
              │  planId -> AgentRun│
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │  executePlan()     │   Phase 8-A1
              │  topologicalOrder  │
              └─────────┬──────────┘
                        │
       ┌────────────────┼────────────────┐
       │                │                │
       ▼                ▼                ▼
  ┌─────────┐    ┌─────────┐    ┌─────────┐
  │ know-   │    │  tool   │    │  model  │   Phase 8-A1 dispatch
  │ ledge   │    │ dispatch│    │ dispatch│
  └────┬────┘    └────┬────┘    └────┬────┘
       │              │              │
       ▼              ▼              ▼
  ┌─────────┐   ┌─────────┐    ┌─────────┐
  │ Know-  │   │  Tool    │   │ Model   │
  │ ledge  │   │ Executor │   │ Layer   │
  │ Layer  │   │ (P 7-T5) │   │ (P 6)   │
  └────┬────┘   └────┬────┘    └────┬────┘
       │              │              │
       └──────────────┴──────────────┘
                      │
                      ▼
              ┌────────────────────┐
              │  Result Collector │   Phase 8-A1
              │  + synthesis step │
              └─────────┬──────────┘
                        │
                        ▼
              ┌────────────────────┐
              │  Final Answer      │
              └────────────────────┘
```

## 3. Lifecycle (Phase 8-A1)

```
                ┌─────────────────────┐
                │ createRun()         │  creates AgentRun in 'pending' status
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ executePlan()       │  status -> 'running'
                └──────────┬──────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
       ┌─────────┐    ┌─────────┐    ┌─────────┐
       │ start   │    │ run     │    │ finish  │
       │ step    │    │ step    │    │ step    │
       └────┬────┘    └────┬────┘    └────┬────┘
            │              │              │
            ▼              ▼              ▼
       ┌─────────┐    ┌─────────┐    ┌─────────┐
       │ compl. │    │ compl. │    │ compl. │
       └────┬────┘    └────┬────┘    └────┬────┘
            │              │              │
            └──────────────┴──────────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ all steps done      │
                └──────────┬──────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
        ┌───────────────┐     ┌───────────────┐
        │ all completed │     │ any failed    │
        └───────┬───────┘     └───────┬───────┘
                │                     │
                ▼                     ▼
        ┌───────────────┐     ┌───────────────┐
        │ status:       │     │ status:       │
        │ 'completed'  │     │ 'failed'      │
        └───────────────┘     └───────────────┘
```

`cancelled` is reachable at any point via `cancelRun()`.

## 4. Step dispatcher (Phase 8-A1)

```
dispatch(step, run):
  switch (step.type):
    case 'knowledge': return knowledge.query(...)
    case 'tool':       return tool.execute(step.input)  // rethrows on failure
    case 'model':      return model.complete(prompt, options)
    case 'analysis':   return pureFn(step.input, run.steps)
    case 'synthesis':  return pureFn(step.input, run.steps)
```

Phase 8-A1 strict: the dispatcher is the ONLY place that maps StepType → caller. It uses injected interfaces (`KnowledgeCaller` / `ToolCaller` / `ModelCaller`) — NO direct imports.

## 5. Failure recovery (Phase 8-A1)

| Error type | Behavior |
|-----------|----------|
| Step throws / caller rejects | `step.status = 'failed'`, `run.status = 'failed'`, break out |
| Step throws `CANCELLED` | `step.status = 'cancelled'`, `run.status = 'cancelled'`, break out |
| User calls `cancelRun(runId)` mid-execution | All pending + running steps → `cancelled`, `run.status = 'cancelled'` |
| Step is `analysis` with missing input.sourceStepId | throw; `step.status = 'failed'` |
| Step is `synthesis` with no preceding outputs | returns empty sections (graceful) |

Phase 8-A1 strict: no automatic retries. The caller decides retry policy. The runtime just executes what it's told and records the outcome.

## 6. Cancellation (Phase 8-A1)

`cancelRun(runId)`:

- If `status` is terminal (`completed` / `failed` / `cancelled`): returns `{ ok: false, reason: 'already terminal' }`
- Otherwise: marks `run.status = 'cancelled'`, marks all pending + running steps as cancelled, sets `completedAt`, emits `run_completed` with `{ status: 'cancelled' }`
- Returns `{ ok: true }`

The currently-executing step is NOT interrupted mid-flight (Phase 8-A1 strict: no AbortController). It completes naturally; the next iteration sees `run.status === 'cancelled'` and marks itself cancelled.

## 7. Security boundary (Phase 8-A1 strict)

The runtime NEVER contains:
- `apiKey` / `token` / `cipher` / `Authorization` / `providerId` / `modelId`

The runtime NEVER imports from:
- `desktop/src/main/services/model-provider/` (no model-provider import)
- `desktop/src/main/services/auth.service.ts` (no auth import)
- `desktop/src/auth/` (no auth import)
- `backend/` (no backend import)
- `desktop/src/renderer/auth/` (no renderer auth import)

Phase 8-A1 strict: ALL model / tool / knowledge interactions go through injected interfaces — the runtime never holds credentials.

## 8. Phase 8-A1 strict forbids

- ❌ Import from model-provider / auth / chat / backend
- ❌ Call any LLM SDK (anthropic / openai / qwen / etc.)
- ❌ Persist run state to disk (in-memory only)
- ❌ Implement retry policy (Phase 8+ handles this)
- ❌ Implement permission checking (Phase 8+ handles this)
- ❌ Implement RAG retrieval
- ❌ Add IPC channels
- ❌ Modify UI components

## 9. References

- `docs/agent/research-planner-architecture.md` (Phase 8-A0 — Planner)
- `docs/agent/research-agent-workflow.md` (Phase 8-A0 — Workflow)
- `desktop/src/shared/agent/research-plan-schema.ts` (Phase 8-A0 contracts)
- `desktop/src/shared/agent/agent-runtime-schema.ts` (Phase 8-A1 contracts)
- `desktop/src/main/services/agent/agent-runtime.ts` (Phase 8-A1 implementation)

## Status (2026-08-22 Phase 8-A1)

- `ResearchAgentRuntime` class (6 methods + EventEmitter)
- 3 injected callers (KnowledgeCaller / ModelCaller / ToolCaller)
- Step dispatcher (5 cases)
- `topologicalOrder` helper
- In-memory run store with cancelRun
- 5 RuntimeEvent types (plan_created / step_started / step_completed / step_failed / run_completed)
- 0 imports from model-provider / auth / chat / backend
- Doc complete (9 sections)
