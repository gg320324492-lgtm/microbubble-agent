# Planner vs Runtime (Phase 8-B0)

> **purpose**: Explain the WHAT / HOW separation that keeps the research agent extensible.
> **follows**: `research-agent-runtime.md` (Phase 8-A1) + `research-intent-planner.md` (Phase 8-B0).

## 1. The two halves

```
 Planner (decides WHAT)                    Runtime (executes HOW)
 ┌────────────────────────────┐            ┌────────────────────────────┐
 │ ResearchPlan               │   plan     │ ResearchAgentRuntime       │
 │  goal: "Analyze water..."  │ ────────►  │  topologicalOrder()        │
 │  tasks: [...rule chain...] │            │  executeStep() / dispatch()│
 │  metadata: {domain, task}  │            │  knowledge.query()         │
 └────────────────────────────┘            │  tool.execute()            │
      no tool calls                          │  model.complete()          │
      no execution state                     │  synthesis/analysis       │
                                             └────────────────────────────┘
```

| Concern | Planner | Runtime |
|---------|---------|---------|
| What should be done | ✔ decides the plan | ❌ |
| How each step runs | ❌ | ✔ |
| Chooses steps / ordering | ✔ (templates + dependencies) | ✔ (topological execution of the given plan) |
| Knows tool ids / prompts | ✔ (writes step `input`) | ✔ (dispatches exact `input` to callers) |
| Tracks run state | ❌ | ✔ (`AgentRun` / steps / timestamps) |
| Emits trace events | ❌ | ✔ (`RuntimeEvent` stream) |
| Cancellation / failure | ❌ | ✔ |
| Calls LLM / tools / knowledge | ❌ (never executes) | ✔ (through injected callers) |
| Imports the other? | MUST NOT import runtime | MUST NOT import planner |

## 2. Reasoning (why the separation matters)

1. **Independent evolution** — a new planner strategy (e.g. a Phase 8+ LLM planner) only changes `PlannerDecision` production; the runtime and its 1500+ tests are untouched.
2. **Independent testing** — the planner is testable as a pure function (deterministic outputs, no IO); the runtime is testable with injected mock callers.
3. **Security boundary** — the planner touches request text and plan metadata; the runtime touches caller execution. Neither may hold secrets, and neither depends on `model-provider` / `auth` / `backend`.
4. **Determinism** — the Phase 8-B0 planner is 100% deterministic (keyword rules + content-hash plan ids), so the same request always yields the same plan. The runtime is deterministic in ordering given a plan.
5. **Decide-then-execute** — `plan()` produces a full `PlannerDecision` and hands it to `createRun()`; the runtime then executes. This lets the agent layer validate the plan (structure + cycles + resolvable deps) before committing to execution.

## 3. Golden flow (end to end)

```
user text
   │
   ▼ ResearchPlanner.analyzeIntent        → ResearchIntent
   ▼ ResearchPlanner.createPlan           → ResearchPlan (status: pending)
   ▼ ResearchPlanner.validatePlan         → { ok },
   ▼ ResearchPlanner.estimateConfidence   → number (0..1)
   ▼ ResearchPlanner.plan                 → PlannerDecision { plan, confidence, reasoningSummary }
   │
   ▼ ResearchAgentRuntime.createRun       → AgentRun (pending)
   ▼ ResearchAgentRuntime.executePlan     → AgentRun (completed / failed / cancelled)
```

## 4. Contract glue (no coupling)

| Boundary | Type |
|----------|------|
| Planner → Runtime | `ResearchPlan` (Phase 8-A0 schema) |
| Runtime → callers | `KnowledgeCaller` / `ModelCaller` / `ToolCaller` (injected) |
| Planner context | `PlannerContext` (tool capability profiles from Phase 7-T3) |
| Shared security | `assertNoSecret` guard (same 8 forbidden substrings) |

## 5. Tests that enforce the separation (`research-planner.test.ts`)

- source scan: `research-planner.ts` contains no `agent-runtime` import
- source scan: `agent-runtime.ts` contains no `planner` / `intent-classifier` import
- runtime integration: plans produced by the planner run to `completed` through the Phase 8-A1 runtime (literature-review / experiment-analysis / data-analysis / paper-writing templates)

## 6. References

- `docs/agent/research-intent-planner.md` (Phase 8-B0 planner)
- `docs/agent/research-agent-runtime.md` (Phase 8-A1 runtime)
- `docs/agent/runtime-execution-flow.md` (Phase 8-A1 execution + worked example)