# Runtime Execution Flow (Phase 8-A1)

> **purpose**: Define the end-to-end runtime execution flow of a ResearchPlan through the ResearchAgentRuntime. Phase 8-A1 ships the flow + one worked example; Phase 8+ ships the runtime populating the flow.
> **follows**: `research-agent-runtime.md` (Phase 8-A1).
> **Phase 8-A1 strict**: worked example only. NO implementation details beyond the flow itself.

## 1. Scope (Phase 8-A1 frozen)

Phase 8-A1 ships:
- The end-to-end runtime flow from `createRun()` → `executePlan()` → final answer
- One worked example (TC degradation analysis)
- Step dispatch trace events
- Failure + cancellation semantics

Phase 8-A1 does **NOT** ship:
- ❌ Real planner runtime (LLM call to produce plans)
- ❌ Real LLM / tool / knowledge callers
- ❌ IPC channels
- ❌ UI changes
- ❌ Database persistence

## 2. End-to-end flow (Phase 8-A1)

```
              ┌─────────────────────┐
              │   User Request      │
              │ "Analyze TC          │
              │  degradation exp."   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   createRun()       │
              │   -> AgentRun        │
              │      status:pending │
              │      events:        │
              │      plan_created   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   executePlan()     │
              │   topologicalOrder  │
              │   status: running  │
              └──────────┬──────────┘
                         │
       ┌────────┬────────┴────────┬────────┐
       │        │                │        │
       ▼        ▼                ▼        ▼
   ┌────────┐┌────────┐    ┌────────┐┌────────┐
   │step:1 ││step:2 │    │step:3 ││step:4 │
   │know-  ││kinetic│    │figure ││write  │
   │ledge  ││-analy-│    │-viz   ││conclu-│
   │       ││sis    │    │       ││sion   │
   └───┬───┘└───┬────┘    └───┬───┘└───┬───┘
       │        │            │        │
       ▼        ▼            ▼        ▼
   step_   step_       step_   step_
   started complete    started started
       │        │            │        │
       │        │            │        │
       └────────┴────────────┴────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  run_completed      │
              │  status: completed  │
              │  result: synthesized│
              └─────────────────────┘
```

## 3. Worked example (Phase 8-A1)

### User request

> "Analyze TC degradation experiment"

### Plan (input to runtime)

```ts
{
  id: 'plan:tc-001',
  goal: 'Analyze TC degradation experiment',
  tasks: [
    {
      id: 'step:1:retrieve-experiment',
      type: 'knowledge',
      description: 'Retrieve the most recent TC degradation experiment',
      input: { entityType: 'experiment', filter: { name: 'TC*' } },
      dependencies: []
    },
    {
      id: 'step:2:kinetic-fit',
      type: 'tool',
      description: 'Fit pseudo-first-order kinetic model',
      input: { toolId: 'tool:kinetic-analysis', time: '...', concentration: '...' },
      dependencies: ['step:1:retrieve-experiment']
    },
    {
      id: 'step:3:generate-figure',
      type: 'tool',
      description: 'Plot the fitted curve',
      input: { toolId: 'tool:data-visualization', plotType: 'kinetic-curve' },
      dependencies: ['step:1:retrieve-experiment', 'step:2:kinetic-fit']
    },
    {
      id: 'step:4:write-conclusion',
      type: 'model',
      description: 'Generate a textual conclusion summarizing the analysis',
      input: { prompt: 'Based on the experiment data and k = {{k}}, conclude: ...' },
      dependencies: ['step:3:generate-figure']
    }
  ]
}
```

### Runtime execution trace

```
T0  createRun('Analyze TC degradation experiment', plan)
    -> run.id = 'run:001'
    -> status = 'pending'
    -> events: plan_created

T1  executePlan('run:001', plan)
    -> status = 'running'
    -> topologicalOrder: [step:1, step:2, step:3, step:4]
    -> events: (none yet — step_started fires per step)

T2  executeStep(run, step:1)
    -> type=knowledge
    -> dispatch: knowledge.query({ entityType: 'experiment', filter: { name: 'TC*' } })
    -> output: { experiment: { id: 'exp:tc-2024', time: [...], concentration: [...] } }
    -> status = 'completed'
    -> events: step_started, step_completed

T3  executeStep(run, step:2)
    -> type=tool
    -> dispatch: tool.execute({ toolId: 'tool:kinetic-analysis', time: ..., concentration: ... })
    -> output: { k: 0.05, rSquared: 0.97, curve: [...], model: 'pseudo-first-order' }
    -> status = 'completed'
    -> events: step_started, step_completed

T4  executeStep(run, step:3)
    -> type=tool
    -> dispatch: tool.execute({ toolId: 'tool:data-visualization', plotType: 'kinetic-curve' })
    -> output: { figureId: 'fig:kinetic-curve:001', format: 'svg', ... }
    -> status = 'completed'
    -> events: step_started, step_completed

T5  executeStep(run, step:4)
    -> type=model
    -> dispatch: model.complete(prompt, options)
    -> output: { text: 'Based on k=0.05/min and R²=0.97, the experiment shows...', usage: { tokens: 450 } }
    -> status = 'completed'
    -> events: step_started, step_completed

T6  run completion
    -> status = 'completed'
    -> result = synthesize(plan, run) // assembles sections from each step
    -> events: run_completed { status: 'completed' }
```

### Final AgentRun

```ts
{
  id: 'run:001',
  userRequest: 'Analyze TC degradation experiment',
  planId: 'plan:tc-001',
  status: 'completed',
  startedAt: 1000,
  completedAt: 5000,
  steps: [
    { stepId: 'step:1', status: 'completed', input: {...}, output: {...}, startedAt: 1100, completedAt: 1200 },
    { stepId: 'step:2', status: 'completed', input: {...}, output: {...}, startedAt: 1300, completedAt: 2400 },
    { stepId: 'step:3', status: 'completed', input: {...}, output: {...}, startedAt: 2500, completedAt: 2600 },
    { stepId: 'step:4', status: 'completed', input: {...}, output: {...}, startedAt: 2700, completedAt: 4900 }
  ],
  result: {
    format: 'summary',
    sections: {
      'step:1': { experiment: {...} },
      'step:2': { k: 0.05, rSquared: 0.97, ... },
      'step:3': { figureId: 'fig:kinetic-curve:001', ... },
      'step:4': { text: 'Based on k=0.05/min ...', usage: {...} }
    },
    userRequest: 'Analyze TC degradation experiment'
  }
}
```

## 4. Failure + cancellation trace (Phase 8-A1)

### Failure mid-execution

```
T0  createRun + executePlan
T1  step:1 starts -> completed
T2  step:2 starts -> FAILS (e.g. tool execution error)
    -> step:2.status = 'failed'
    -> run.status = 'failed'
    -> break out of loop
T3  step:3, step:4 NEVER START
T4  run_completed { status: 'failed' }
```

### Cancellation mid-execution

```
T0  createRun + executePlan
T1  step:1 starts -> running
T2  user calls cancelRun('run:001')
    -> run.status = 'cancelled'
    -> step:1.status = 'cancelled' (after current iteration completes)
T3  loop checks run.status === 'cancelled', breaks out
T4  run_completed { status: 'cancelled' }
```

## 5. Phase 8-A1 strict forbids

- ❌ Real LLM / tool / knowledge callers (Phase 8-A1 uses injected interfaces only)
- ❌ Real planner runtime (Phase 8+ populates this)
- ❌ Database persistence (in-memory only)
- ❌ IPC channels
- ❌ UI changes
- ❌ Automatic retries (caller decides)

## 6. References

- `docs/agent/research-planner-architecture.md` (Phase 8-A0 — Planner)
- `docs/agent/research-agent-runtime.md` (Phase 8-A1 — Runtime)
- `desktop/src/shared/agent/research-plan-schema.ts` (Phase 8-A0 contracts)
- `desktop/src/shared/agent/agent-runtime-schema.ts` (Phase 8-A1 contracts)
- `desktop/src/main/services/agent/agent-runtime.ts` (Phase 8-A1 implementation)
