# Research Agent Workflow (Phase 8-A0)

> **purpose**: Define the user-facing flow of the Research Agent — from raw user message through Plan emission, step execution, to final answer. Phase 8-A0 ships the flow as a design; Phase 8+ ships the runtime.
> **follows**: `research-planner-architecture.md` (Phase 8-A0).
> **Phase 8-A0 strict**: worked example only. NO implementation. NO LLM call.

## 1. Scope (Phase 8-A0 frozen)

Phase 8-A0 ships:
- The end-to-end flow from user message → final answer
- One worked example (TC degradation experiment analysis)
- Step dependency rules
- Failure recovery semantics

Phase 8-A0 does **NOT** ship:
- ❌ The planner runtime
- ❌ LLM SDK calls
- ❌ Tool execution (already shipped in Phase 7-T5-A)
- ❌ Knowledge retrieval (Phase 7-A0/7-B+)

## 2. End-to-end flow (Phase 8-A0)

```
                  ┌──────────────────┐
                  │  User Message    │   "Analyze TC degradation experiment"
                  └────────┬─────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │      Research Planner       │   Phase 8-A0 contract only
              │      - understand goal      │
              │      - emit ResearchPlan    │
              └────────┬───────────────────┘
                       │
                       ▼
              ┌────────────────────────────┐
              │       ResearchPlan          │
              │       - tasks[]             │
              │       - dependencies[]     │
              │       - status             │
              └────────┬───────────────────┘
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
   ┌─────────────────┐  ┌─────────────────┐
   │  Step Executor  │  │  Step Executor  │
   │  (Phase 7-T5-A)  │  │  (Phase 8+)     │
   └────────┬─────────┘  └────────┬─────────┘
            │                     │
            ▼                     ▼
   ┌─────────────────┐  ┌─────────────────┐
   │  Knowledge      │  │  Tool Executor  │
   │  (Phase 7-A0/7-B)│  │  (Phase 7-T5-A)  │
   └────────┬─────────┘  └────────┬─────────┘
            │                     │
            └──────────┬──────────┘
                       │
                       ▼
              ┌────────────────────────────┐
              │      Final Answer           │
              │      (StreamEvent)          │
              └────────────────────────────┘
```

## 3. Worked example (Phase 8-A0)

### User message

> "Analyze TC degradation experiment"

### Generated ResearchPlan

```ts
{
  id: 'plan:001',
  goal: 'Analyze TC degradation experiment',
  status: 'pending',
  tasks: [
    {
      id: 'step:1:retrieve-experiment',
      type: 'knowledge',
      description: 'Retrieve the most recent TC degradation experiment from Knowledge Layer',
      input: { entityType: 'experiment', filter: { name: 'TC*' } },
      dependencies: []
    },
    {
      id: 'step:2:kinetic-fit',
      type: 'tool',
      description: 'Fit pseudo-first-order kinetic model to the experiment data',
      input: {
        toolId: 'tool:kinetic-analysis',
        args: { /* bound from step:1 output */ }
      },
      dependencies: ['step:1:retrieve-experiment']
    },
    {
      id: 'step:3:generate-figure',
      type: 'tool',
      description: 'Plot the fitted curve with experimental data',
      input: {
        toolId: 'tool:data-visualization',
        args: { /* bound from step:1 + step:2 output */ }
      },
      dependencies: ['step:1:retrieve-experiment', 'step:2:kinetic-fit']
    },
    {
      id: 'step:4:write-conclusion',
      type: 'model',
      description: 'Generate a textual conclusion summarizing the kinetic analysis',
      input: {
        promptTemplate: 'Based on the experiment data and k = {{k}}, R^2 = {{rSquared}}, conclude: ...',
        contextBindings: ['step:1:retrieve-experiment', 'step:2:kinetic-fit', 'step:3:generate-figure']
      },
      dependencies: ['step:3:generate-figure']
    }
  ],
  metadata: {
    createdBy: 'planner:Phase8-A0',
    estimatedTokens: 4000,
    userMessageLength: 32
  }
}
```

### Step dependency graph

```
step:1:retrieve-experiment   → step:2:kinetic-fit   → step:4:write-conclusion
                          ↘                    ↗
                            step:3:generate-figure
```

The graph is **acyclic** — required for `detectCycle` to return null.

## 4. Step execution semantics (Phase 8-A0)

### Per-step lifecycle

```
pending
   │ submit
   ▼
running
   │
   ├─ success → completed (output populated)
   │
   ├─ error → failed (error populated)
   │
   └─ cancel → cancelled
```

### Status transitions (Phase 8-A0 strict)

```
pending → running     (Phase 8+ Executor picks the step up)
running → completed   (Phase 8+ step completed successfully)
running → failed      (Phase 8+ step raised an exception OR adapter returned success=false)
running → cancelled   (Phase 8+ user / system cancelled the step)
completed → (terminal)
failed → (terminal)
cancelled → (terminal)
```

Phase 8-A0 strict: no `pending → completed` direct transition. A step must transition through `running`.

### Plan-level status (Phase 8-A0)

```
pending → running     (Phase 8+ Executor picks the plan up)
running → completed   (Phase 8+ all steps completed)
running → failed      (Phase 8+ at least one terminal step is failed)
running → cancelled   (Phase 8+ user / system cancelled the plan)
```

A plan is `completed` only if **all** its steps are `completed`.

## 5. Failure recovery (Phase 8-A0)

### Per-step retry (Phase 8+)

| Error type | Behavior |
|-----------|----------|
| `INVALID_ARGS` | Do NOT retry. Surface immediately to user. |
| `PERMISSION_DENIED` | Do NOT retry. Surface immediately. |
| `TIMEOUT` | Retry up to N times with exponential backoff (Phase 8+). |
| `EXECUTION_ERROR` | Retry up to N times. |
| `NETWORK_ERROR` | Retry with backoff. |
| `CANCELLED` | Terminal. No retry. |

Phase 8-A0 strict: the plan does NOT auto-retry the entire plan. It retries individual steps based on the error code.

### Plan-level retry

If a step has exhausted its retry budget and is still `failed`:
- Phase 8-A0 strict: the plan moves to `failed` status
- The user is presented with the partial result (any steps that did succeed)
- The user can choose to: skip-and-continue, retry-the-failed-step, or cancel

## 6. Phase 8-A0 strict forbids

- ❌ Implement the planner runtime
- ❌ Implement the executor runtime (the Tool Executor already does this — Phase 7-T5-A)
- ❌ Implement the LLM call (the Model Layer already does this — Phase 6)
- ❌ Implement knowledge retrieval (Phase 7-A0/7-B+)
- ❌ Add IPC channels
- ❌ Persist plan state to disk (in-memory only)
- ❌ Include apiKey / token / secret in any plan field

## 7. References

- `docs/agent/research-planner-architecture.md` (Phase 8-A0 — Planner contracts)
- `docs/tools/tool-executor-architecture.md` (Phase 7-T4 — Step execution runtime)
- `docs/tools/tool-capability-matching.md` (Phase 7-T3 — Tool selection)
- `docs/knowledge/storage-architecture.md` (Phase 7-B0 — Knowledge Layer)
- `desktop/src/shared/agent/research-plan-schema.ts` (Phase 8-A0 contracts)

## Status (2026-08-22 Phase 8-A0)

- End-to-end flow documented (user → planner → plan → executors → final answer)
- Worked example (TC degradation analysis, 4 steps)
- Step dependency graph (acyclic)
- Lifecycle transitions (pending → running → completed | failed | cancelled)
- Failure recovery semantics (per-step retry + plan-level retry)
- Doc complete (7 sections)
