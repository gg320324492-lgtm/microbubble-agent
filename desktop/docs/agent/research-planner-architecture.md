# Research Planner Architecture (Phase 8-A0)

> **purpose**: Define the architecture of the Research Planner layer that coordinates Model + Knowledge + Tools. Phase 8-A0 ships ONLY the architecture — NO implementation, NO LLM calls, NO tool execution, NO RAG.
> **follows**: Phase 6 (Model) + Phase 7 (Knowledge + Tools) + Phase 7-T5-A (Tool Executor).
> **Phase 8-A0 strict**: architecture only. NO planner runtime. NO LLM SDK calls. NO IPC.

## 1. Scope (Phase 8-A0 frozen)

Phase 8-A0 ships:
- `ResearchPlan` / `ResearchPlanStep` / `StepType` types in `desktop/src/shared/agent/research-plan-schema.ts`
- `AgentAction` / `AgentActionStatus` types
- Dependency-cycle detector (`detectCycle`)
- 6 validators + `assertNoSecret` guard
- Architecture diagram + flow definitions

Phase 8-A0 does **NOT** ship:
- ❌ The actual planner runtime
- ❌ LLM SDK calls (anthropic / openai / etc.)
- ❌ RAG retrieval
- ❌ IPC channels
- ❌ UI changes
- ❌ Backend changes
- ❌ Database storage

## 2. Layer diagram (Phase 8-A0)

```
              ┌────────────────────────────┐
              │       User Request         │
              └─────────────┬──────────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │      Research Planner       │   Phase 8-A0 (this commit)
              │      - understand goal      │   contracts only
              │      - emit ResearchPlan    │
              │      - coordinate steps     │
              └─────────────┬──────────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │       Task Plan            │   ResearchPlan + steps
              └─────────────┬──────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Knowledge  │  │     Tools    │  │    Model    │
   │   Layer     │  │   (Phase 7)  │  │  (Phase 6)  │
   │ (Phase 7-A) │  │              │  │              │
   └──────────────┘  └──────────────┘  └──────────────┘
            │               │               │
            └───────────────┼───────────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │     Final Answer           │
              └────────────────────────────┘
```

Six layers, each with a single responsibility. Phase 8-A0 freezes the planner's contracts; Phase 8+ ships the runtime.

## 3. Planner responsibilities (Phase 8-A0 strict)

The Planner:

- ✅ Takes a user message (string)
- ✅ Understands the goal (semantic interpretation — Phase 8-A0 ships the contract; LLM call is Phase 8+)
- ✅ Emits a `ResearchPlan` (structured task list)
- ✅ Chooses capabilities per step (`StepType`: knowledge / tool / model / analysis / synthesis)
- ✅ Coordinates execution order (respects `dependencies`)

The Planner does NOT:

- ❌ Execute tools directly (Phase 7-T5-A ToolExecutor does this)
- ❌ Store knowledge (Phase 7-A0/7-B+ Knowledge Layer does this)
- ❌ Call models directly (Phase 6 Model Layer does this)
- ❌ Hold API keys (Phase 6-A2 SecretStore does this)
- ❌ Manage chat sessions (Phase 6 chat-stream.service.ts does this)
- ❌ Persist plans to disk (Phase 8-A0: in-memory only)

## 4. Step types (Phase 8-A0)

| StepType | What the executor does | Consumed by |
|----------|------------------------|--------------|
| `knowledge` | Queries the Knowledge Layer (Phase 7-A0/7-B+) | Knowledge Provider (Phase 7+) |
| `tool` | Invokes a registered Tool via the Tool Executor (Phase 7-T5-A) | Tool Executor |
| `model` | Calls the LLM via the Phase 6 Model Layer | Model Layer |
| `analysis` | Pure data transformation (no external IO) | Local sandbox |
| `synthesis` | Combines outputs of multiple prior steps | Local sandbox |

Phase 8-A0 strict: the planner picks the StepType. The actual executor for each StepType ships in Phase 8+.

## 5. Plan structure (Phase 8-A0)

```ts
interface ResearchPlan {
  id: string
  goal: string
  tasks: ResearchPlanStep[]
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  metadata?: Record<string, unknown>  // NO apiKey / NO token (Phase 8-A0 strict)
}

interface ResearchPlanStep {
  id: string
  type: 'knowledge' | 'tool' | 'model' | 'analysis' | 'synthesis'
  description: string
  input: Record<string, unknown>
  output?: Record<string, unknown>
  dependencies: string[]  // step ids that must complete first
}
```

## 6. Agent action state (Phase 8-A0)

```ts
type AgentActionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

interface AgentAction {
  stepId: string
  status: AgentActionStatus
  result?: Record<string, unknown>
  error?: { code: string; message: string }
}
```

The runtime fills this as the executor progresses each step. Phase 8-A0 ships the SHAPE; Phase 8+ ships the runtime.

## 7. Independence boundary (Phase 8-A0 strict)

The Planner schema does NOT import from:

- `desktop/src/main/services/model-provider/`
- `desktop/src/main/services/auth.service.ts`
- `desktop/src/auth/`
- `desktop/src/renderer/auth/`
- `backend/`
- Any LLM SDK package

The Planner schema is pure data shape + pure validator functions. It can be consumed by any runtime.

## 8. Phase 8-A0 strict forbids

- ❌ Implement the planner runtime
- ❌ Call any LLM SDK (anthropic / openai / qwen / etc.)
- ❌ Implement RAG retrieval
- ❌ Implement tool execution (the Tool Executor already does this)
- ❌ Implement knowledge persistence (Knowledge Storage already does this)
- ❌ Add IPC channels
- ❌ Persist plan state to disk
- ❌ Include apiKey / token / cipher / Authorization anywhere

## 9. References

- `docs/agent/research-agent-workflow.md` (Phase 8-A0 — worked example)
- `docs/knowledge/storage-architecture.md` (Phase 7-B0 — Knowledge Storage)
- `docs/tools/tool-adapter-architecture.md` (Phase 7-T2 — Adapters)
- `docs/tools/tool-executor-architecture.md` (Phase 7-T4 — Executor)
- `desktop/src/shared/agent/research-plan-schema.ts` (Phase 8-A0 contracts)

## Status (2026-08-22 Phase 8-A0)

- `ResearchPlan` / `ResearchPlanStep` / `StepType` contracts
- `AgentAction` / `AgentActionStatus` contracts
- 6 validators with assertNoSecret guard
- `detectCycle` dependency-graph algorithm
- 0 implementations (Phase 8-A0 ships ONLY contracts + docs)
- Doc complete (9 sections)
