# Existing Application Adapter Design (Phase 7-T0)

> **purpose**: Define how the Tool Layer wraps existing application functions WITHOUT modifying them. Existing business logic stays as-is; the Adapter is a thin translation layer.
> **follows**: `tool-schema.ts` (Phase 7-T0) + `tool-registry-architecture.md` (Phase 7-T0).
> **Phase 7-T0 strict**: design only. NO actual adapter code. NO business logic changes.

## 1. Scope (Phase 7-T0 frozen)

Phase 7-T0 ships:
- The Adapter pattern (existing function ↔ Tool Contract)
- One worked example (`analyzeKinetics` → `kinetic-analysis` tool)
- 6 rules for Adapter implementation (Phase 7-T+)

Phase 7-T0 does **NOT** ship:
- ❌ Any concrete adapter code
- ❌ Any wrapper that touches existing business logic
- ❌ Changes to any existing function signature

## 2. The Adapter pattern (Phase 7-T0)

```
       Existing Application                  Tool Contract
       (unchanged)                           (Phase 7-T0)

┌──────────────────────┐             ┌──────────────────────┐
│ analyzeKinetics(data)│             │ ToolDefinition       │
│  - scientific logic  │             │  - id                │
│  - returns result    │             │  - inputSchema       │
│  - throws on error   │             │  - outputSchema      │
└──────────┬───────────┘             │  - permission        │
           │                         └──────────┬───────────┘
           │                                    │
           │         Adapter (Phase 7-T+)       │
           │                                    │
           └────────────► ┌──────────┐ ◄────────┘
                          │ wrap()  │
                          └────┬─────┘
                               │
                               ▼
                    ToolExecutor(args, ctx)
                               │
                               ▼
                       ToolResult { success, data }
```

The Adapter is a **thin translation layer**. It:
- takes typed args (Phase 7-T0 inputSchema)
- calls the existing function
- converts the return to `ToolResult`
- catches exceptions → `ToolResult { success: false, error: ... }`

It does NOT:
- duplicate logic
- modify the existing function
- cache state (that's the Registry's job)

## 3. Worked example: `analyzeKinetics` → `kinetic-analysis` tool

### Existing function (UNCHANGED)

```python
# backend/app/agents/scientific_tools/kinetics.py (Phase 4+ Python)
def analyzeKinetics(data: np.ndarray, model: str = 'first-order') -> KineticResult:
    """Fit kinetic models to TC degradation data."""
    ...
```

Phase 7-T0 strict: this function is NOT migrated to desktop in Phase 7-T0. The Python implementation stays on the backend for legacy Agent callers.

### Phase 7-T+ Adapter (FUTURE)

```ts
// desktop/src/main/services/tools/adapters/kinetic-analysis.ts (Phase 7-T+)
import { analyzeKinetics } from '../../../legacy/kinetics'    // wrapped Python call (Phase 7-T+)
import type { ToolExecutor } from '@shared/tools/tool-schema'

export const kineticAnalysisExecutor: ToolExecutor = async (args, ctx) => {
  const validated = validateKineticArgs(args)
  try {
    const result = await analyzeKinetics(validated.dataset, validated.model)
    return {
      success: true,
      data: {
        k_obs: result.k_obs,
        r_squared: result.r_squared,
        half_life: result.half_life
      },
      metadata: { latencyMs: Date.now() - ctx.traceStartMs }
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
}
```

### Tool Definition (Phase 7-T+ future)

```ts
const kineticAnalysisDefinition: ToolDefinition = {
  id: 'tool:kinetic-analysis',
  name: 'Kinetic Analysis',
  description: 'Fit kinetic models to time-series concentration data.',
  category: 'analysis',
  version: '1.0.0',
  inputSchema: {
    fields: [
      { name: 'dataset', type: 'object', required: true,
        description: 'A Dataset entity from the Knowledge Layer' },
      { name: 'model', type: 'string', required: false, enum: ['first-order', 'second-order', 'zero-order'] }
    ],
    required: ['dataset'],
    validationRules: ['dataset must be a valid Dataset entity (isValidDataset)']
  },
  outputSchema: {
    description: 'KineticResult { k_obs, r_squared, half_life }',
    fields: ['k_obs', 'r_squared', 'half_life']
  },
  executionTarget: 'local-service',
  permission: 'research',
  tags: ['kinetics', 'ozone', 'microbubble']
}
```

Phase 7-T0 strict: this is a SKETCH. The actual adapter ships in Phase 7-T+.

## 4. Adapter rules (Phase 7-T+ strict)

### Rule 1: The existing function signature does NOT change

The Adapter only ADDS a translation layer. The existing function is called with its original signature.

### Rule 2: All Adapter input comes through `validateToolArgs`

The Adapter does NOT accept raw `args`. It first validates via `validateToolArgs(definition, args)`, then maps to the function's expected input.

### Rule 3: All Adapter output goes through `isValidToolResult`

The Adapter does NOT return raw function results. It converts to `ToolResult { success, data | error }` and validates via `isValidToolResult`.

### Rule 4: Adapter catches all exceptions

Any exception thrown by the existing function becomes `ToolResult { success: false, error: { code: 'EXECUTION_ERROR', message } }`. The Adapter NEVER lets an exception escape.

### Rule 5: Adapter is the ONLY place that calls the existing function

The Registry calls `executor(args, ctx)`. The executor is the Adapter. The Adapter calls the existing function. Nothing else calls the existing function through the Tool Layer.

### Rule 6: Adapter does NOT log apiKey / secrets

The Adapter may log timing / args shape / function name. It does NOT log args values that may contain secrets.

## 5. Adapter patterns (Phase 7-T+ sketches — NOT IMPLEMENTED)

### Pattern A: Direct function wrap (in-process)

```ts
const directWrap = (fn: (...args: any[]) => any) => async (args, ctx) => {
  try {
    const result = await fn(...Object.values(args))
    return { success: true, data: result }
  } catch (e) {
    return { success: false, error: { code: 'EXECUTION_ERROR', message: String(e) } }
  }
}
```

### Pattern B: HTTP fetch (FastAPI backend)

```ts
const httpWrap = (endpoint: string) => async (args, ctx) => {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${ctx.userToken}` },
    body: JSON.stringify(args),
    signal: ctx.abortSignal
  })
  return { success: response.ok, data: await response.json() }
}
```

### Pattern C: Worker thread (CPU-heavy)

```ts
const workerWrap = (workerPath: string) => async (args, ctx) => {
  return new Promise((resolve) => {
    const worker = new Worker(workerPath)
    worker.postMessage(args)
    worker.onmessage = (e) => {
      worker.terminate()
      resolve({ success: true, data: e.data })
    }
  })
}
```

Phase 7-T0 strict: these are SKETCHES. Phase 7-T+ picks which patterns to ship.

## 6. Existing application adapter (Phase 7-T0)

The Adapter is the bridge. It MUST NOT modify the existing function. It MUST validate inputs. It MUST catch exceptions.

The existing function (e.g. `analyzeKinetics`) does NOT change:
- Same signature
- Same return type
- Same error semantics (caught by Adapter)

The Adapter is **additive**, not a replacement.

## 7. Phase 7-T0 strict forbids

- ❌ Modify any existing function signature
- ❌ Move existing functions to a different location
- ❌ Refactor existing functions to match Tool Contract
- ❌ Add new parameters to existing functions
- ❌ Remove existing parameters from existing functions
- ❌ Cache existing function results in Tool Layer
- ❌ Wrap existing function calls with auth checks (Adapter does not check auth)

## 8. References

- `docs/tools/tool-registry-architecture.md` (Phase 7-T0 Step 6 — ToolExecutor interface)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 Step 7 — output sanitization)
- `docs/tools/agent-tool-interface.md` (Phase 7-T0 Step 8 — Agent ↔ Tool flow)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)

## Status (2026-08-22 Phase 7-T0)

- Adapter pattern documented (existing function ↔ Tool Contract)
- Worked example: `analyzeKinetics` → `kinetic-analysis` tool (sketch)
- 6 Adapter rules documented
- 3 Adapter pattern sketches (direct / HTTP / worker)
- 0 implementations (Phase 7-T0 ships ONLY the design)
- Doc complete (8 sections)
