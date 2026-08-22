# Tool Adapter Architecture (Phase 7-T2)

> **purpose**: Define the architecture that bridges the Tool Registry (Phase 7-T1) to the existing application functions. The Adapter is the boundary that turns a registered `ToolDefinition` into an actual capability.
> **follows**: `tool-registry-runtime.md` (Phase 7-T1) + `application-adapter-design.md` (Phase 7-T0).
> **Phase 7-T2 frozen contract**: architecture only. NO real execution. NO IPC. NO existing function changes.

## 1. Scope (Phase 7-T2 frozen)

Phase 7-T2 ships:
- `ToolAdapter` interface (toolId + version + execute + validate + metadata)
- `AdapterRegistry` interface (Phase 7-T2+ binds Adapters to ToolDefinitions)
- `ToolExecutionContext` (requestId + userContext + projectContext + metadata)
- `ToolExecutionResult` (re-uses Phase 7-T0 ToolResult shape)
- 3 validators (`isValidToolAdapter` / `isValidUserContext` / `isValidProjectContext`)
- Architecture diagrams + flow descriptions

Phase 7-T2 does **NOT** ship:
- ❌ Real adapter implementations
- ❌ An `execute()` runtime
- ❌ Wrapping existing functions
- ❌ IPC for tool execution
- ❌ LLM function-calling integration

## 2. The 3-layer mental model (Phase 7-T2)

```
                          Agent (Phase 7-G)
                              │
                              ▼
              ┌──────────────────────────────┐
              │      Tool Registry           │   Phase 7-T1
              │      - what exists           │   (metadata store)
              │      - get / list / search   │
              └──────────────┬───────────────┘
                             │ Phase 7-T2 boundary
                             ▼
              ┌──────────────────────────────┐
              │      Adapter Registry        │   Phase 7-T2
              │      - what binds to what     │
              │      - validate args         │
              │      - sanitize results      │
              └──────────────┬───────────────┘
                             │ Phase 7-T2+ boundary
                             ▼
              ┌──────────────────────────────┐
              │      Executor                │   Phase 7-T2+
              │      - run adapter.execute()  │   (NOT IN 7-T2)
              │      - handle errors         │
              │      - emit ToolResult       │
              └──────────────┬───────────────┘
                             │
                             ▼
                  Existing Application
                    (Functions / Services)
```

Three layers, each with a single responsibility:

- **Registry**: what tools exist (storage)
- **Adapter**: how capability connects (translation)
- **Executor**: when tools run (runtime — Phase 7-T2+)

## 3. Registry ↔ Adapter separation (Phase 7-T2 strict)

| Concern | Owned by |
|---------|----------|
| Tool metadata (name / description / version / schema) | **Registry** (Phase 7-T1) |
| Tool execution contract (function shape) | **Adapter** (Phase 7-T2) |
| Tool runtime (when + how to call execute) | **Executor** (Phase 7-T2+) |
| Tool validation (Phase 7-T0 schema) | **Registry** (Phase 7-T1) |
| Tool domain validation (Phase 7-T2) | **Adapter** (Phase 7-T2) |
| Output sanitization | **Executor** (Phase 7-T2+) |

The Registry NEVER knows about Adapter. The Adapter NEVER knows about Executor.

## 4. Adapter contract (Phase 7-T2)

```ts
interface ToolAdapter {
  toolId: string           // matches ToolDefinition.id
  version: string          // semver
  execute: AdapterExecuteFn
  validate?: AdapterValidateFn
  metadata?: AdapterMetadata
}
```

### Why this shape

- `toolId`: enforces binding to a specific `ToolDefinition`. The AdapterRegistry uses this to bind the Adapter to its Definition at registration time.
- `version`: separate from `ToolDefinition.version`. The Adapter may evolve independently of the schema.
- `execute`: function-shaped contract. Phase 7-T2 ships ONLY the type. Phase 7-T+ implements it.
- `validate`: optional domain-specific checks beyond Phase 7-T0 schema. Examples (Phase 7-T+): "dataset must exist in Knowledge", "outputPath must be in user-data".
- `metadata`: free-form. Examples (Phase 7-T+): `{ underlyingFunction: 'analyzeKinetics', library: 'numpy' }`.

## 5. AdapterRegistry contract (Phase 7-T2)

```ts
interface AdapterRegistry {
  register(adapter: ToolAdapter, definition: ToolDefinition): void
  unregister(toolId: string): boolean
  get(toolId: string): ToolAdapter | null
  has(toolId: string): boolean
  list(): ToolAdapter[]
  size(): number
}
```

### Registration flow (Phase 7-T2 design)

```
AdapterRegistry.register(adapter, definition):
  1. assertNoSecret(adapter, 'adapter')
  2. assertNoSecret(definition, 'definition')
  3. isValidToolDefinition(definition)        -> throws if invalid
  4. isValidToolAdapter(adapter)              -> throws if invalid
  5. adapter.toolId === definition.id         -> throws if mismatch
  6. validateAdapterInputsMatch(adapter, definition)  -> throws if schema mismatch
  7. has(adapter.toolId)                      -> throws if duplicate
  8. store adapter + definition pair
```

### Why bind adapter to definition?

The Adapter is meaningless without its `ToolDefinition`. Binding them at registration time:

- prevents an Adapter from being used without its schema
- prevents a `ToolDefinition` from being used without its Adapter
- makes the binding atomic (both registered together or not at all)

## 6. Adapter ↔ ToolDefinition schema consistency

Phase 7-T2 strict: an Adapter's `execute` MUST consume args that conform to the bound `ToolDefinition.inputSchema`.

Validation strategy (Phase 7-T2 design):

1. The Registry validates `ToolDefinition.inputSchema` at registration (Phase 7-T0)
2. The AdapterRegistry validates the Adapter is shaped correctly
3. **At execute time (Phase 7-T2+):**
   - Executor calls `validateToolArgs(definition, args)` (Phase 7-T0)
   - If valid, calls `adapter.execute(args, ctx)`
   - If invalid, returns `ToolResult { success: false, error: { code: 'INVALID_ARGS' } }`

Phase 7-T2 strict: the Adapter does NOT re-implement Phase 7-T0 validation. It MAY add domain-specific checks via `validate(args)`.

## 7. Execution context (Phase 7-T2)

```ts
interface ToolExecutionContext {
  requestId: string          // trace id
  userContext?: UserContext    // Phase 7-T2: optional; Phase 7-T+: populated
  projectContext?: ProjectContext  // Phase 7-T2: optional; Phase 7-T+: populated
  metadata?: Record<string, unknown>
}

interface UserContext {
  userId: string             // Phase 7-T2 strict: empty string
  role: string               // Phase 7-T2 strict: empty string
  permissions: string[]      // Phase 7-T2 strict: empty array
}

interface ProjectContext {
  projectId: string          // Phase 7-T2 strict: empty string
  permissions: string[]      // Phase 7-T2 strict: empty array
}
```

Phase 7-T2 strict: the Adapter NEVER reads `Authorization` headers, NEVER holds tokens, NEVER constructs user contexts.

## 8. Execution result (Phase 7-T2)

```ts
type ToolExecutionResult = ToolResult  // re-uses Phase 7-T0 ToolResult
```

The Adapter's `execute()` returns a `ToolResult`. The Executor wraps the Adapter and:

- catches exceptions → `ToolResult { success: false, error: ... }`
- validates via `isValidToolResult(result)`
- runs `assertNoSecret(result)` (Phase 7-T0)
- (Phase 7-T2+) runs path / URL / size sanitization

## 9. Worked example (Phase 7-T2 design — NOT IMPLEMENTED)

### Existing function (UNCHANGED)

```python
# backend/app/agents/scientific_tools/kinetics.py
def analyzeKinetics(data, model='first-order'):
    ...
```

### Tool Definition (Phase 7-T0 — already shipped)

```ts
// builtin-tools.ts: KINETIC_ANALYSIS_TOOL
```

### Adapter (Phase 7-T+ — sketch)

```ts
// desktop/src/main/services/tools/adapters/kinetic-analysis.ts
import { analyzeKinetics } from '../../../legacy/kinetics'  // wrapped Python call
import type { ToolAdapter } from '@shared/tools/tool-adapter-schema'

export const kineticAnalysisAdapter: ToolAdapter = {
  toolId: 'tool:kinetic-analysis',
  version: '1.0.0',
  validate: (args) => {
    // Phase 7-T+ domain-specific checks (e.g. dataset must be valid)
    if (!isValidDataset((args as { dataset?: unknown }).dataset)) {
      return 'dataset must be a valid Dataset entity'
    }
    return null
  },
  execute: async (args, ctx) => {
    const { dataset, model } = args as { dataset: Dataset; model?: string }
    try {
      const result = await analyzeKinetics(dataset, model ?? 'first-order')
      return {
        success: true,
        data: {
          k_obs: result.k_obs,
          r_squared: result.r_squared,
          half_life: result.half_life
        },
        metadata: {
          requestId: ctx.requestId,
          userId: ctx.userContext?.userId ?? ''
        }
      }
    } catch (e) {
      return {
        success: false,
        error: {
          code: 'EXECUTION_ERROR',
          message: e instanceof Error ? e.message : String(e)
        }
      }
    }
  },
  metadata: {
    underlyingFunction: 'analyzeKinetics',
    library: 'numpy'
  }
}
```

### Adapter registration (Phase 7-T+)

```ts
AdapterRegistry.register(kineticAnalysisAdapter, KINETIC_ANALYSIS_TOOL)
```

Phase 7-T2 strict: this code is a SKETCH. Phase 7-T+ ships the real implementation.

## 10. Phase 7-T2 strict forbids

- ❌ Implement any adapter (Phase 7-T+ ships them)
- ❌ Implement AdapterRegistry class (Phase 7-T+ ships it)
- ❌ Implement execute() runtime (Phase 7-T+ ships it)
- ❌ Wrap any existing function
- ❌ Modify any existing function signature
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `desktop/src/auth/`
- ❌ Import from `backend/`
- ❌ Add IPC handlers
- ❌ Connect to a database

## 11. References

- `docs/tools/tool-registry-runtime.md` (Phase 7-T1 — Registry)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 — Security)
- `docs/tools/agent-tool-interface.md` (Phase 7-T0 — Agent ↔ Tool)
- `docs/tools/application-adapter-design.md` (Phase 7-T0 — Adapter pattern)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)
- `desktop/src/shared/tools/tool-registry-types.ts` (Phase 7-T1 types)
- `desktop/src/shared/tools/tool-adapter-schema.ts` (Phase 7-T2 contracts — THIS COMMIT)
- `desktop/src/shared/tools/builtin-tools.ts` (Phase 7-T1 catalog)
- `desktop/src/main/services/tools/tool-registry.ts` (Phase 7-T1 implementation)

## Status (2026-08-22 Phase 7-T2)

- `ToolAdapter` interface (toolId / version / execute / validate / metadata)
- `AdapterRegistry` interface (register / unregister / get / has / list / size)
- `ToolExecutionContext` (requestId + userContext + projectContext + metadata)
- `ToolExecutionResult` (re-uses ToolResult)
- 3 validators with assertNoSecret guard
- 3-layer mental model (Registry / Adapter / Executor)
- Worked example sketch (kinetic-analysis)
- 0 implementations (Phase 7-T2 ships ONLY the contracts + architecture)
- Doc complete (11 sections)
