# Runtime vs. Orchestrator (Phase 8-E0)

> **purpose**: Document the responsibility split between Phase 8-A1 `ResearchAgentRuntime` (executes plans) and the new Phase 8-E0 `ResearchAgent` orchestrator (decides when/how to use every subsystem).
> **follows**: `research-agent-runtime.md` (A1) + `research-agent-orchestration.md` (E0).

## 1. The split in one line

| Layer | Responsibility |
|-------|----------------|
| **Runtime (Phase 8-A1)** | "Execute this plan" — runs steps in topological order, dispatches each step type to the right subsystem, emits `RuntimeEvent`s for the active run. |
| **Orchestrator (Phase 8-E0)** | "Decide when/how to use every subsystem" — validates the request, calls planner + runtime, aggregates results into a `ResearchAgentResponse`, tracks lifecycle status, handles cancellation, emits `AgentEvent`s. |

## 2. What each layer knows

| Concern | Runtime | Orchestrator |
|---------|---------|---------------|
| Step dispatch (knowledge/tool/model) | ✔ | ❌ |
| Per-step error recovery | ✔ | ❌ |
| `AgentRun` state machine | ✔ | ❌ |
| Cancellation flag inside one run | ✔ (via `cancelRun`) | propagates / observes |
| Multi-run lifecycle status | ❌ | ✔ |
| Cross-subsystem validation | ❌ | ✔ |
| Aggregation → `ResearchAgentResponse` | ❌ | ✔ |
| High-level `AgentEvent` stream | ❌ | ✔ (forwards runtime events where useful) |
| DI composition | ❌ (already composed by tests) | ✔ (`ResearchAgentDependencies`) |

## 3. The runtime never grows upward

`ResearchAgentRuntime` stays the source of truth for **how** a plan executes. The orchestrator does not reroute any step — that would re-create Phase 8-A1's dispatch inside a higher layer. New high-level coordination lives in the orchestrator; new per-step behavior lives in the runtime.

## 4. The orchestrator never leaks downward

The orchestrator does not import any Phase 8-A1 dispatcher symbol directly. It depends on the runtime **only via a structural shape** (`RuntimeLike` — `createRun` / `executePlan` / `cancelRun` / `onEvent`). The same goes for the planner (`PlannerLike`) and the providers (`ContextProviderLike` / `ModelProviderLike` / `ToolExecutorLike`).

If we ever add Phase 8-F0+ subsystems (e.g. an evaluation layer), the orchestrator grows new dependencies in `ResearchAgentDependencies` — the runtime stays untouched.

## 5. Event-flow responsibility

| Event type | Emitted by | Forwarded by orchestrator? |
|------------|------------|------------------------------|
| `plan_created` (Phase 8-B0) | planner (indirectly) | ✅ orchestrator emits its own |
| `step_started` / `step_completed` / `step_failed` (Phase 8-A1) | runtime | forwarded (subscribers only) |
| `agent_started` / `agent_completed` / `agent_failed` (Phase 8-E0) | orchestrator | n/a |
| `context_retrieved` / `tool_started` / `tool_completed` / `model_started` / `model_completed` (Phase 8-E0) | orchestrator | n/a |

The orchestrator's `AgentEvent` names are intentionally orthogonal to the runtime's `RuntimeEvent`. They tell a different story — the lifecycle of one `ResearchAgent.run()` request, not the lifecycle of one `AgentRun`.

## 6. References

- `docs/agent/research-agent-orchestration.md` (Phase 8-E0 architecture + lifecycle)
- `src/main/services/agent/agent-runtime.ts` (Phase 8-A1)
- `src/main/services/agent/research-agent.ts` (Phase 8-E0)
- `src/shared/agent/research-agent-schema.ts` (Phase 8-E0 contracts)