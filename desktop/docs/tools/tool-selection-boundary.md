# Tool Selection Boundary (Phase 7-T3)

> **purpose**: Define the boundary between Tool Capability Matching (Phase 7-T3, this commit) and the rest of the system. Defines WHO calls the matcher, WHEN, and what they get.
> **follows**: `tool-capability-matching.md` (Phase 7-T3) + `tool-registry-runtime.md` (Phase 7-T1) + `tool-adapter-architecture.md` (Phase 7-T2).
> **Phase 7-T3 strict**: boundary contract only. NO execution. NO Agent planner.

## 1. Scope (Phase 7-T3 frozen)

Phase 7-T3 ships the boundary contract:

```
Agent (Phase 7-G)
    │
    ▼
Task (from Agent planner)
    │
    ▼
Tool Matcher (Phase 7-T3, this commit)
    │
    ▼
Tool Registry (Phase 7-T1)
    │
    ▼
Adapter Registry (Phase 7-T2)
    │
    ▼
Executor (Phase 7-T2+)
```

Six-layer stack. Each layer has a single responsibility. Phase 7-T3 freezes the third layer.

## 2. Layer-by-layer responsibility (Phase 7-T3)

| Layer | Phase | Responsibility | What it owns |
|-------|-------|----------------|--------------|
| Agent | 7-G (future) | Decision making | LLM SDK (anthropic / openai / etc.) |
| Task | 7-G | Task extraction from user message | (Phase 7-G) |
| **Tool Matcher** | **7-T3 (this)** | **Score tools against task** | **`ToolMatchResult[]`** |
| Tool Registry | 7-T1 | Metadata store | `ToolDefinition` storage |
| Adapter Registry | 7-T2 | Adapter binding | `ToolAdapter` storage |
| Executor | 7-T2+ | Runtime | `execute(args, ctx)` |

Phase 7-T3 strict: each layer only knows the layer below it. The Matcher knows about Registry, but Registry does NOT know about Matcher.

## 3. Boundary contract (Phase 7-T3)

### Matcher receives (Phase 7-T3 strict)

```
ToolMatchInput:
  - requiredTasks: ToolTaskType[]
  - optionalTasks?: ToolTaskType[]
  - requiredCapabilities: ToolCapability[]

ToolCapabilityProfile[]:
  - one profile per registered Tool
```

The Agent (Phase 7-G) constructs the `ToolMatchInput` from the user's task. Phase 7-T3 strict: the matcher does NOT extract the task — the Agent does.

### Matcher returns (Phase 7-T3 strict)

```
ToolMatchResult[] (sorted by score desc, deterministic):
  - toolId: string
  - score: number
  - reason: string (human-readable, NO secrets)
  - breakdown?: { taskScore, capabilityScore, priorityScore }
```

### The Matcher does NOT (Phase 7-T3 strict)

- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `desktop/src/auth/`
- ❌ Import from `backend/`
- ❌ Call the LLM
- ❌ Execute any tool
- ❌ Persist any data
- ❌ Hold any API key / token / cipher

The Matcher is a PURE FUNCTION. Same input → same output. No side effects.

## 4. Integration flow (Phase 7-T+)

```
Agent (Phase 7-G):
  user_message -> LLM -> task_profile: ResearchTaskProfile

Task (Phase 7-G):
  task_profile -> translation -> ToolMatchInput

Tool Matcher (Phase 7-T3, this commit):
  ToolMatchInput + profiles -> ToolMatchResult[]

Tool Registry (Phase 7-T1):
  ToolMatchResult[].toolId -> get(toolId) -> ToolDefinition

Adapter Registry (Phase 7-T2):
  ToolDefinition -> get(toolId) -> ToolAdapter

Executor (Phase 7-T2+):
  ToolAdapter.execute(args, ctx) -> ToolResult

Result -> Agent -> StreamEvent (Phase 3-B0)
```

Phase 7-T3 ships ONLY the Matcher's pure function. The integration with the Agent (Phase 7-G) is deferred.

## 5. Matcher inputs and outputs (Phase 7-T3)

```
INPUT:
  ToolMatchInput {
    requiredTasks: ['data-analysis'],
    optionalTasks?: ['visualization'],
    requiredCapabilities: ['kinetic-fit']
  }

  ToolCapabilityProfile[]:
    [
      { toolId: 'tool:kinetic-analysis',
        requiredCapabilities: ['kinetic-fit'],
        optionalCapabilities: [],
        supportedTasks: ['data-analysis'],
        priority: 5 },
      { toolId: 'tool:data-viz',
        requiredCapabilities: ['plot-render'],
        optionalCapabilities: [],
        supportedTasks: ['data-analysis', 'visualization'],
        priority: 3 }
    ]


OUTPUT:
  ToolMatchResult[]:
    [
      { toolId: 'tool:kinetic-analysis',
        score: 20,
        reason: 'tasks=[data-analysis] caps=[kinetic-fit] priority=5',
        breakdown: { taskScore: 10, capabilityScore: 5, priorityScore: 5 } },
      { toolId: 'tool:data-viz',
        score: 23,
        reason: 'tasks=[data-analysis,visualization] caps=[] priority=3',
        breakdown: { taskScore: 20, capabilityScore: 0, priorityScore: 3 } }
    ]


SORTED:
  tool:data-viz (23) > tool:kinetic-analysis (20)
```

Phase 7-T+ uses the sorted result to pick the top-K tools.

## 6. Security boundary (Phase 7-T3 strict)

| Item | Lives in | NEVER crosses to |
|------|----------|------------------|
| apiKey | (none — Tool Layer has none) | Tool Matcher, Tool Registry, Renderer |
| Token | (none) | Tool Matcher, Tool Registry, Renderer |
| Authorization | (none) | Tool Matcher, Tool Registry, Renderer |
| Provider credentials | (none — Phase 6 Layer only) | Tool Matcher, Tool Registry, Renderer |
| Match results | Tool Matcher | Renderer (only sanitized version) |
| Capability metadata | Tool Layer | Renderer (only sanitized version) |

`assertNoSecret(matchResult, 'matchToolsForTask')` runs on every output. Throws on sk- / apiKey / cipher / Bearer / token / authorization / providerId / modelId.

## 7. Phase 7-T3 strict forbids

- ❌ Implement the Agent planner
- ❌ Implement LLM task extraction
- ❌ Implement Tool selection integration with the Registry
- ❌ Implement IPC for matched results
- ❌ Couple ToolCapability to ResearchCapability (Phase 7-C1)
- ❌ Couple ToolTaskType to ResearchTaskType (Phase 7-C2)
- ❌ Modify any existing function
- ❌ Add IPC handlers
- ❌ Connect to a database

## 8. References

- `docs/tools/tool-capability-matching.md` (Phase 7-T3 — Matcher algorithm)
- `docs/tools/tool-registry-runtime.md` (Phase 7-T1 — Registry)
- `docs/tools/tool-adapter-architecture.md` (Phase 7-T2 — Adapter)
- `docs/tools/tool-adapter-security.md` (Phase 7-T2 — Security)
- `docs/knowledge/agent-capability-router.md` (Phase 7-C2 — independent)
- `desktop/src/shared/tools/tool-capability-schema.ts` (Phase 7-T3 — THIS COMMIT)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0)
- `desktop/src/shared/tools/tool-adapter-schema.ts` (Phase 7-T2)

## Status (2026-08-22 Phase 7-T3)

- 6-layer stack diagram (Agent / Task / Matcher / Registry / Adapter / Executor)
- Boundary contract (inputs / outputs / forbidden)
- Integration flow (Phase 7-T+ future)
- Worked example (kinetic-analysis vs data-viz)
- Security boundary table
- 0 implementations (Phase 7-T3 ships ONLY the boundary contract + pure algorithm)
- Doc complete (8 sections)
