# Tool Registry Architecture (Phase 7-T0)

> **purpose**: Define the Tool Registry that connects the Agent to existing application functions. Phase 7-T0 ships the architecture — NO implementation.
> **follows**: `existing-tool-audit.md` (Phase 7-T0 Step 1) + `tool-schema.ts` (Phase 7-T0 contracts).
> **Phase 7-T0 strict**: architecture only. NO tool executor runtime. NO Agent planner.

## 1. Scope (Phase 7-T0 frozen)

Phase 7-T0 ships the architecture for:

- `ToolRegistry` interface (Phase 7+ implementation)
- Registration / lookup / list / validation flow
- Independence boundary (no LLM SDK, no Auth, no Chat Runtime)

Phase 7-T0 explicitly does **NOT** ship:
- ❌ A concrete `ToolRegistry` implementation
- ❌ A tool executor runtime
- ❌ LLM tool-calling integration
- ❌ Existing-function wrappers
- ❌ IPC handlers

## 2. Layer diagram (Phase 7-T0)

```
                      Agent (Phase 7-G)
                           │
                           ▼
                    Tool Registry
                           │
       ┌───────────┬───────┴────────┬───────────┐
       ↓           ↓                ↓           ↓
   Analysis    Simulation   Data-Processing   ...
       │           │                │
       └───────────┴────────┬───────┘
                           │
                           ▼
                   Existing Application
                     (Functions / Services)
```

Three independent layers:

- **Agent**: picks which tool to call (Phase 7-G)
- **Tool Registry**: stores / validates / routes (Phase 7-T+)
- **Existing Application Functions**: business logic (unchanged)

## 3. ToolRegistry interface (Phase 7+ sketch)

```ts
interface ToolRegistry {
  // ===== Lifecycle =====
  initialize(): Promise<void>
  shutdown(): Promise<void>

  // ===== Registration =====
  register(definition: ToolDefinition, executor: ToolExecutor): void
  unregister(toolId: string): void

  // ===== Lookup =====
  get(toolId: string): ToolRegistration | null
  list(options?: { category?: ToolCategory; permission?: ToolPermission }): ToolRegistration[]
  search(query: { text?: string; tags?: string[] }): ToolDefinition[]

  // ===== Validation =====
  validateArgs(toolId: string, args: unknown): string | null

  // ===== Phase 7+ execution (Phase 7-T0: signature only) =====
  execute(toolId: string, args: unknown, ctx: ToolExecutionContext): Promise<ToolResult>
}

interface ToolRegistration {
  definition: ToolDefinition
  executor: ToolExecutor
  registeredAt: number
}

interface ToolExecutor {
  (args: unknown, ctx: ToolExecutionContext): Promise<ToolResult>
}

interface ToolExecutionContext {
  /** Phase 7+ user identity (Phase 7-T0: empty) */
  userId: string
  /** Phase 7+ trace id (Phase 7-T0: empty) */
  traceId: string
  /** Phase 7+ timeout in ms (default 30s) */
  timeoutMs: number
}
```

Phase 7-T0 ships ONLY the interface shape. Phase 7-T+ ships the implementation.

## 4. Registration flow (Phase 7-T+ contract)

```
register(definition, executor):
  1. Validate definition (isValidToolDefinition)
  2. Validate executor is a function
  3. Wrap executor + definition in ToolRegistration
  4. Store in Map<toolId, ToolRegistration>
  5. (Phase 7+ persist via ToolStorageProvider if available)
```

```
unregister(toolId):
  1. Remove from Map
  2. (Phase 7+ mark as disabled in storage, do NOT delete — version history)
```

## 5. Lookup flow

```
get(toolId):
  return Map[toolId] ?? null

list({ category?, permission? }):
  return all registrations matching filters

search({ text?, tags? }):
  return registrations whose definition.name / description / tags match
```

Phase 7-T0 strict: `get` and `list` are PURE lookups. NO execution side effects.

## 6. Validation flow

```
validateArgs(toolId, args):
  1. get(toolId) -> registration
  2. if !registration -> error("unknown toolId")
  3. validateToolArgs(definition, args)
  4. return error message or null
```

This is the SAME validator that runs at execution time. Phase 7-T0 ships it as a pure function.

## 7. Execution flow (Phase 7-T+ — NOT IMPLEMENTED in Phase 7-T0)

```
execute(toolId, args, ctx):
  1. validateArgs(toolId, args) -> error if invalid
  2. lookup permission(ctx.userId) vs definition.permission
     -> 'public': allow all
     -> 'research': allow researcher
     -> 'admin': allow admin only
  3. call registration.executor(args, ctx) with timeout
  4. catch errors -> ToolResult { success: false, error: ... }
  5. validate result (isValidToolResult)
  6. return ToolResult
```

Phase 7-T0 strict: NO executor code. Phase 7-T+ ships `execute`.

## 8. Tool Registry responsibilities (Phase 7-T0)

| Responsibility | Phase |
|----------------|-------|
| register | 7-T+ |
| unregister | 7-T+ |
| lookup (get / list / search) | 7-T+ |
| validateArgs | 7-T0 (pure function) |
| execute | 7-T+ |

## 9. Tool Registry does NOT (Phase 7-T0 strict)

- ❌ Execute LLM calls
- ❌ Store API keys
- ❌ Manage models
- ❌ Manage providers (Phase 6-A3 is the source of truth)
- ❌ Manage chat sessions
- ❌ Persist data outside its own Map (Phase 7-T+ may integrate with Knowledge Storage)
- ❌ Touch the database
- ❌ Talk to the FastAPI backend directly

## 10. Independence boundary (Phase 7-T0 strict)

Tool Registry depends ONLY on:
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)

Tool Registry does NOT import:
- ❌ `desktop/src/main/services/model-provider/`
- ❌ `desktop/src/main/services/auth.service.ts`
- ❌ `desktop/src/auth/`
- ❌ `desktop/src/renderer/auth/`
- ❌ `backend/`

This is verified at runtime by the import-graph test (Phase 7+).

## 11. Phase 7-T0 strict forbids

- ❌ Implement any concrete ToolRegistry class
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from any LLM SDK package
- ❌ Add IPC handlers
- ❌ Wrap existing business functions
- ❌ Persist any data
- ❌ Connect to a database

## 12. References

- `docs/tools/existing-tool-audit.md` (Phase 7-T0 Step 1 — what's already there)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 — permission model)
- `docs/tools/agent-tool-interface.md` (Phase 7-T0 — Agent integration)
- `docs/tools/application-adapter-design.md` (Phase 7-T0 — adapter pattern)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)
- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 — Knowledge ↔ Tool coupling)

## Status (2026-08-22 Phase 7-T0)

- ToolRegistry interface (8 methods: lifecycle / register / unregister / lookup / validateArgs / execute)
- ToolRegistration / ToolExecutor / ToolExecutionContext types
- 5-step registration flow + 3-step lookup flow + 6-step execution flow
- "Tool Registry does NOT" enumeration (8 forbidden concerns)
- 0 implementations (Phase 7-T0 ships ONLY the architecture)
- Doc complete (12 sections)
