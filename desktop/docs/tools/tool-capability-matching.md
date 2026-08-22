# Tool Capability Matching (Phase 7-T3)

> **purpose**: Define how the Tool Layer matches research tasks to tool capabilities. The matcher is pure (no IO, no execution) — Phase 7-T3 ships the algorithm + contracts.
> **follows**: `tool-adapter-schema.ts` (Phase 7-T2) + `tool-registry-runtime.md` (Phase 7-T1) + `research-task.ts` (Phase 7-C2) + `research-capability.ts` (Phase 7-C1).
> **Phase 7-T3 strict**: pure matching algorithm. NO executor. NO IPC. NO existing function changes.

## 1. Scope (Phase 7-T3 frozen)

Phase 7-T3 ships:
- `ToolTaskType` enum (8 task types)
- `ToolCapabilityProfile` type (per-tool capability metadata)
- `ToolMatchResult` type (matching output)
- `matchToolsForTask(input, profiles)` pure matching function
- 3 validators with `assertNoSecret` guard

Phase 7-T3 does **NOT** ship:
- ❌ Real Tool matching integration with the Registry (Phase 7-T+)
- ❌ LLM-based task extraction (Phase 7-G)
- ❌ Tool execution (Phase 7-T2+)
- ❌ IPC for matched results

## 2. Layer diagram (Phase 7-T3)

```
                Research Task Profile (Phase 7-C2)
                          │
                          ▼
              ┌──────────────────────────────┐
              │      Tool Matcher           │   Phase 7-T3 (this commit)
              │      (pure function)         │
              │      - score = task*10 +     │
              │                caps*5 +     │
              │                priority     │
              └──────────────┬───────────────┘
                             │
                             ▼
                       ToolMatchResult[]
                             │
                             ▼
              ┌──────────────────────────────┐
              │      Tool Registry           │   Phase 7-T1
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │      Adapter Registry        │   Phase 7-T2
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │      Executor                │   Phase 7-T2+
              └──────────────────────────────┘
```

Three independent layers, each with a single responsibility:
- **Matcher** (Phase 7-T3, this commit): pure scoring
- **Registry / Adapter**: storage + translation
- **Executor**: runtime

## 3. Capability independence (Phase 7-T3 strict)

| Concern | Owned by |
|---------|----------|
| Research-domain taxonomy | `ResearchCapability` (Phase 7-A0/7-C1) |
| LLM API surface | `ModelCapability` (Phase 6-A1) |
| Tool category (broad) | `ToolCategory` (Phase 7-T0) |
| **Tool-specific capability tags** | **`ToolCapability` (Phase 7-T3)** |

Phase 7-T3 strict: `ToolCapability` is a STRING list (not an enum) so the Tool Layer is free to define its own tags without coupling to the research taxonomy. The Matcher does NOT consult `ResearchCapability`.

```
Research Capability (Phase 7-C1)        Tool Capability (Phase 7-T3)
      │                                          │
      └─ Model provider routing ──── ◇ ──── Tool selection
                                     │
                                  INDEPENDENT
```

## 4. Tool Task taxonomy (8 types)

| Type | Used by |
|------|---------|
| `literature-processing` | paper digest, abstract generation |
| `data-analysis` | kinetic / stats / trend detection |
| `experiment-analysis` | results interpretation, QC |
| `visualization` | plots, figures |
| `simulation` | CFD, model runs |
| `calculation` | unit conversion, formula evaluation |
| `export` | CSV / JSON / Parquet / PDF |
| `preprocessing` | data cleaning, normalization |

Phase 7-T3 strict: these are TOOL-LAYER tasks (different from ResearchTaskType which is RESEARCH-domain tasks). They may overlap semantically but the taxonomies are independent.

## 5. ToolCapabilityProfile shape

```ts
interface ToolCapabilityProfile {
  toolId: string                   // matches ToolDefinition.id
  requiredCapabilities: string[]  // Tool-layer capability tags
  optionalCapabilities: string[]
  supportedTasks: ToolTaskType[]   // which tasks this tool can perform
  priority: number                  // 0-10; higher = preferred when tied
}
```

Phase 7-T+ extends `ToolDefinition` with this profile. Phase 7-T3 ships the type.

## 6. Matching algorithm (Phase 7-T3 pure function)

```ts
score =
    (# requiredTasks hit)        * 10
  + (# optionalTasks hit)        *  2
  + (# requiredCapabilities hit)*  5
  + profile.priority              (0..10)
```

**Tie-breaker**: alphabetical by `toolId` (deterministic).

**Filter**: profiles with `score === 0` are excluded.

### Worked example

Given profiles:
- `tool:kinetic-analysis`: tasks=`['data-analysis']`, requiredCaps=`['kinetic-fit']`, priority=`5`
- `tool:data-viz`: tasks=`['data-analysis', 'visualization']`, requiredCaps=`['plot-render']`, priority=`3`
- `tool:export-csv`: tasks=`['export']`, requiredCaps=`['csv-write']`, priority=`2`

Task: requiredTasks=`['data-analysis', 'visualization']`, requiredCaps=`['kinetic-fit']`

Scoring:
- `tool:kinetic-analysis`: taskHits=`['data-analysis']`(1) * 10 + capHits=`['kinetic-fit']`(1) * 5 + 5 = **20**
- `tool:data-viz`: taskHits=`['data-analysis', 'visualization']`(2) * 10 + capHits=`[]`(0) * 5 + 3 = **23**
- `tool:export-csv`: taskHits=`[]`(0) * 10 + capHits=`[]`(0) * 5 + 2 = **2** (excluded: score > 0 required)

Top match: `tool:data-viz` (23).

## 7. ToolMatchResult shape

```ts
interface ToolMatchResult {
  toolId: string
  score: number
  reason: string                       // human-readable; NEVER includes secrets
  breakdown?: {                        // Phase 7-T+ uses for debug UI
    taskScore: number
    capabilityScore: number
    priorityScore: number
  }
}
```

## 8. Boundary contract (Phase 7-T3 strict)

The Matcher:
- ✅ Takes `ToolMatchInput` + `ToolCapabilityProfile[]`
- ✅ Returns `ToolMatchResult[]` (sorted by score desc, deterministic)
- ✅ Runs `assertNoSecret` on every output
- ✅ Pure function (no IO, no state)

The Matcher does NOT:
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `backend/`
- ❌ Call the LLM
- ❌ Execute any tool
- ❌ Persist any data

## 9. Phase 7-T3 strict forbids

- ❌ Implement Tool selection integration with the Registry (Phase 7-T+)
- ❌ Implement an Agent planner
- ❌ Call any LLM SDK
- ❌ Add IPC handlers
- ❌ Modify any existing function
- ❌ Couple ToolCapability to Phase 7-C1 ResearchCapability
- ❌ Couple ToolTaskType to Phase 7-C2 ResearchTaskType
- ❌ Connect to a database

## 10. References

- `docs/tools/tool-registry-runtime.md` (Phase 7-T1)
- `docs/tools/tool-adapter-architecture.md` (Phase 7-T2)
- `docs/tools/tool-adapter-security.md` (Phase 7-T2)
- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0)
- `docs/knowledge/agent-capability-router.md` (Phase 7-C2)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0)
- `desktop/src/shared/tools/tool-adapter-schema.ts` (Phase 7-T2)
- `desktop/src/shared/tools/tool-capability-schema.ts` (Phase 7-T3 — THIS COMMIT)

## Status (2026-08-22 Phase 7-T3)

- `ToolTaskType` enum (8 types) + `TOOL_TASK_TYPES` readonly array
- `ToolCapabilityProfile` type (per-tool capability metadata)
- `ToolMatchResult` type (matching output with optional breakdown)
- `matchToolsForTask(input, profiles)` pure function (deterministic)
- 3 validators with assertNoSecret guard (8 forbidden substrings)
- 0 implementations (Phase 7-T3 ships ONLY the algorithm + contracts)
- Doc complete (10 sections)
