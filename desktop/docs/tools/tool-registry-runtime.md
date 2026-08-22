# Tool Registry Runtime (Phase 7-T1)

> **purpose**: Document the first runtime foundation of the Tool Layer — the in-process ToolRegistry that stores tool metadata, supports register / unregister / get / list, and is the foundation that Phase 7-T+ will extend with execution.
> **follows**: `tool-schema.ts` (Phase 7-T0 contracts) + `tool-registry-architecture.md` (Phase 7-T0) + `tool-security-boundary.md` (Phase 7-T0) + `builtin-tools.ts` (Phase 7-T1 catalog).
> **Phase 7-T1 frozen contract**: runtime foundation only. NO execution. NO Agent planner. NO IPC.

## 1. Scope (Phase 7-T1 frozen)

Phase 7-T1 ships:
- `ToolRegistry` class (lifecycle / CRUD / lookup)
- 2 custom errors (`ToolAlreadyRegisteredError`, `ToolValidationError`)
- `builtin-tools.ts` (3 example tool declarations)
- `getToolRegistry()` / `initializeBuiltinTools()` / `resetToolRegistry()` / `bootToolLayer()` singleton lifecycle
- Deterministic ordered list (alphabetical by toolId)

Phase 7-T1 does **NOT** ship:
- ❌ Tool execution runtime
- ❌ Agent planner
- ❌ LLM tool-calling integration
- ❌ IPC tool channel
- ❌ Existing application adapter wrappers

## 2. Architecture (Phase 7-T1)

```
                 User Request (Phase 7-G)
                          │
                          ▼
                ┌─────────────────────┐
                │  Tool Registry       │  ← Phase 7-T1 (this commit)
                │  (in-process)        │
                │  - register          │
                │  - unregister        │
                │  - get / list / has  │
                │  - snapshot          │
                └──────────┬──────────┘
                           │
                  ┌────────┴────────┐
                  ↓                 ↓
          ┌──────────────┐   ┌──────────────┐
          │ Built-in     │   │ Phase 7-T+    │
          │ Tool Catalog │   │ Adapters      │
          │ (Phase 7-T1) │   │ (NOT YET)     │
          └──────────────┘   └──────────────┘
```

## 3. Lifecycle (Phase 7-T1)

```
process boot
    │
    ▼
bootToolLayer()                    ← called once in main process boot
    │
    ├─► getToolRegistry()          ← creates singleton (lazy)
    │
    └─► initializeBuiltinTools()    ← registers BUILTIN_TOOLS (3)
              │
              └─► for each ToolDefinition:
                    if !has(id) -> register(def)
                    else         -> skip (idempotent)


testing
    │
    ▼
resetToolRegistry()                ← testing helper
    │
    ├─► _registry.clear()
    └─► _registry = null
```

## 4. Registration flow (Phase 7-T1)

```
register(definition):
  1. assertNoSecret(definition, 'register.input')
     -> throws if sk- / apiKey / cipher / Bearer / token /
        authorization / providerId / modelId substring present
  2. isValidToolDefinition(definition)?
     -> throws ToolValidationError if invalid
  3. tools.has(definition.id)?
     -> throws ToolAlreadyRegisteredError if duplicate
  4. tools.set(definition.id, registration)
     registration = { definition, registeredAt, handle }
```

## 5. Discovery flow (Phase 7-T1)

```
get(toolId)         -> ToolRegistration | null
has(toolId)         -> boolean
lookup(toolId)      -> { found, tool? }
list(options?)      -> ToolRegistration[] (sorted by toolId)
snapshot()          -> { tools, count, timestamp }
size()              -> number
clear()             -> removes all
```

All lookups are O(1) for get / has, O(n) for list. The Registry is process-lifetime in-memory (no disk persistence in Phase 7-T1).

## 6. Built-in tool catalog (Phase 7-T1)

3 example tools shipped as METADATA ONLY:

| id | name | category | permission | executionTarget |
|----|------|----------|------------|------------------|
| `tool:kinetic-analysis` | Kinetic Analysis | analysis | research | local-service |
| `tool:data-visualization` | Data Visualization | visualization | public | local-service |
| `tool:dataset-export` | Dataset Export | export | public | application |

Phase 7-T1 strict: these are NOT connected to any function. Phase 7-T+ ships adapters that wrap existing functions and register them with the Registry.

## 7. Security boundary (Phase 7-T1 strict)

### Tool Registry does NOT contain

- ❌ apiKey
- ❌ token
- ❌ secret / cipher
- ❌ Authorization
- ❌ providerId
- ❌ modelId

`assertNoSecret(definition, ctx)` runs on every `register()` call. The throw message includes the offending substring.

### Tool Registry does NOT import

- ❌ `desktop/src/main/services/model-provider/`
- ❌ `desktop/src/main/services/auth.service.ts`
- ❌ `desktop/src/auth/`
- ❌ `desktop/src/renderer/auth/`
- ❌ `backend/`
- ❌ Any LLM SDK package

The independence is verified by Phase 7-T1 source-level tests (`fs.readFileSync` of the source file).

## 8. Future execution extension (Phase 7-T+ — NOT in 7-T1)

```
Phase 7-T1 ships:
  ToolRegistry
    - register(definition)              -> void
    - unregister(toolId)                -> boolean
    - get(toolId)                       -> ToolRegistration | null
    - lookup(toolId)                    -> ToolLookupResult
    - list(options?)                    -> ToolRegistration[]
    - has(toolId)                       -> boolean
    - size()                            -> number
    - clear()                           -> void
    - snapshot()                        -> ToolRegistrySnapshot

Phase 7-T+ adds:
  - bind(toolId, executor)             -> associates a ToolExecutor
  - execute(toolId, args, ctx)         -> Promise<ToolResult>
  - subscribe(event, handler)         -> EventEmitter integration
  - persist() / restore()             -> Knowledge Storage integration (Phase 7-B+)
  - search({ text, tags })             -> text + tag search
```

Phase 7-T+ will ship adapters that wrap existing application functions (e.g. `analyzeKinetics`) and bind them to these built-in tool declarations.

## 9. Phase 7-T1 strict forbids

- ❌ Implement `execute(toolId, args)` in this commit
- ❌ Wrap existing business functions
- ❌ Add IPC handlers for tool calls
- ❌ Connect to a database
- ❌ Persist to disk
- ❌ Import LLM SDK packages
- ❌ Add an Agent planner
- ❌ Mutate `ToolDefinition` after registration (the registry stores references; mutating the input would corrupt the registry)

## 10. References

- `docs/tools/existing-tool-audit.md` (Phase 7-T0)
- `docs/tools/tool-registry-architecture.md` (Phase 7-T0)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0)
- `docs/tools/agent-tool-interface.md` (Phase 7-T0)
- `docs/tools/application-adapter-design.md` (Phase 7-T0)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)
- `desktop/src/shared/tools/tool-registry-types.ts` (Phase 7-T1 types)
- `desktop/src/shared/tools/builtin-tools.ts` (Phase 7-T1 catalog)
- `desktop/src/main/services/tools/tool-registry.ts` (Phase 7-T1 implementation)
- `desktop/src/main/services/tools/index.ts` (Phase 7-T1 lifecycle)

## Status (2026-08-22 Phase 7-T1)

- `ToolRegistry` class with 9 methods (register / unregister / get / lookup / list / has / size / clear / snapshot)
- 2 custom errors (ToolAlreadyRegisteredError / ToolValidationError)
- 3 built-in tool declarations (kinetic-analysis / data-visualization / dataset-export)
- Singleton lifecycle (lazy init / idempotent initBuiltinTools / reset for tests)
- Deterministic alphabetical list ordering
- assertNoSecret guard on every register
- 0 implementations of execute / bind / persist (Phase 7-T+)
- 53 unit tests PASSED (exceeds spec >= 50)
- 0 changes to backend / web / Phase 3-B0 / Phase 6 Model Layer / chat:* IPC / Phase 7-T0 contracts
- Doc complete (10 sections)
