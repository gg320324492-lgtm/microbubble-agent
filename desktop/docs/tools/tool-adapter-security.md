# Tool Adapter Security (Phase 7-T2)

> **purpose**: Define the security boundary between the Tool Adapter (Phase 7-T2) and the existing application functions. Adapters are the bridge — that's also the attack surface.
> **follows**: `tool-adapter-architecture.md` (Phase 7-T2) + `tool-security-boundary.md` (Phase 7-T0).
> **Phase 7-T2 strict**: security model only. NO implementation.

## 1. Scope (Phase 7-T2 frozen)

Phase 7-T2 ships:
- 5-step validation pipeline
- Adapter-level security rules
- Output sanitization rules
- No-secret enforcement on Adapter contracts

Phase 7-T2 does **NOT** ship:
- ❌ Real adapter implementations
- ❌ Real sanitization logic
- ❌ The `execute()` runtime
- ❌ Auth / permission enforcement

## 2. Validation pipeline (Phase 7-T2)

```
                Tool Request
                     │
                     ▼
        ┌────────────────────────┐
   1.   │  Schema Validation     │  Phase 7-T0: isValidToolDefinition
        └─────────┬──────────────┘
                  │
                  ▼
        ┌────────────────────────┐
   2.   │  Schema Arg Validation │  Phase 7-T0: validateToolArgs(def, args)
        └─────────┬──────────────┘
                  │
                  ▼
        ┌────────────────────────┐
   3.   │  Adapter Validation    │  Phase 7-T2: adapter.validate(args) (optional)
        └─────────┬──────────────┘
                  │
                  ▼
        ┌────────────────────────┐
   4.   │  Execution             │  Phase 7-T2+: adapter.execute(args, ctx)
        └─────────┬──────────────┘
                  │
                  ▼
        ┌────────────────────────┐
   5.   │  Result Sanitization   │  Phase 7-T0/T2+: isValidToolResult + assertNoSecret
        └────────────────────────┘
```

Each step is a hard gate. Failure at any step → `ToolResult { success: false, error: { code, message } }`.

## 3. Step-by-step rules (Phase 7-T2)

### Step 1: Schema Validation (Phase 7-T0)

The `ToolDefinition` must pass `isValidToolDefinition` before registration. This is enforced by the Registry (Phase 7-T1).

- id format: `^tool:[a-z][a-z0-9_\-:]{0,63}$`
- category / executionTarget / permission must be valid enums
- tags must be string array
- inputSchema / outputSchema must be well-formed

### Step 2: Schema Arg Validation (Phase 7-T0)

At execute time, `validateToolArgs(definition, args)` runs:

- Type checking per field
- Required field check
- Range check (number)
- Enum check (string)
- `assertNoSecret` on the whole payload

### Step 3: Adapter Validation (Phase 7-T2)

The Adapter MAY add a `validate(args)` hook for domain-specific checks:

- Dataset entity must exist in the Knowledge Layer (Phase 7-T+ future)
- Output path must be under `<userData>/exports/`
- Numeric parameters must be physically reasonable (e.g. pH 0..14)

If `validate()` returns a string, execute() is skipped and `ToolResult { success: false, error: { code: 'INVALID_INPUT' } }` is returned.

### Step 4: Execution (Phase 7-T2+)

The Adapter's `execute(args, ctx)` runs. Phase 7-T2 strict:

- The Adapter catches ALL exceptions and returns `ToolResult { success: false, error }`
- The Adapter NEVER lets an exception escape
- The Adapter NEVER throws
- The Adapter does NOT mutate `args` (treat as immutable)

### Step 5: Result Sanitization (Phase 7-T0/T2+)

The Adapter's return value is validated:

- `isValidToolResult(result)` (Phase 7-T0)
- `assertNoSecret(result)` (Phase 7-T0) — throws on sk- / apiKey / cipher / Bearer / token / authorization / providerId / modelId
- (Phase 7-T2+) Path / URL / size checks (NOT IMPLEMENTED in 7-T2)

If sanitization fails, the result is replaced with `ToolResult { success: false, error: { code: 'SANITIZATION_FAILED', message: 'result rejected by security' } }`.

## 4. Adapter-level security rules (Phase 7-T2 strict)

### Rule 1: Adapter does NOT touch credentials

The Adapter NEVER:

- reads `Authorization` headers
- holds tokens
- constructs apiKey fields
- logs apiKey values

### Rule 2: Adapter does NOT touch provider / model configuration

The Adapter NEVER:

- imports from `desktop/src/main/services/model-provider/`
- knows about `providerId` / `modelId`
- decides which LLM to call

### Rule 3: Adapter signature is pure

```
execute(args: unknown, ctx: ToolExecutionContext) -> Promise<ToolResult>
```

- `args` is opaque (the Adapter validates via Phase 7-T0 + adapter.validate)
- `ctx` is read-only (the Adapter does NOT mutate ctx)
- Return is `Promise<ToolResult>` (never throws)

### Rule 4: Adapter does NOT mutate the ToolDefinition

The Adapter is registered alongside a `ToolDefinition`. The Adapter MAY NOT modify the ToolDefinition after registration. The Registry stores references; mutations would corrupt the Registry.

### Rule 5: Adapter does NOT persist data

The Adapter returns data via `ToolResult`. The Adapter does NOT call a database, does NOT write to disk, does NOT modify the Knowledge Storage. Persistence is the Executor's job (Phase 7-T2+).

## 5. Output sanitization rules (Phase 7-T2 strict)

Every `ToolResult` returned by an Adapter must:

- have `success: boolean`
- on success: `data?: Record<string, unknown>` (object only, NOT array)
- on failure: `error?: { code: string, message: string }` (both non-empty)
- `metadata?` is optional, must be an object if present

Sanitization checks:

- ✅ No `sk-` substring
- ✅ No `apiKey` substring
- ✅ No `cipher` substring
- ✅ No `Bearer ` substring
- ✅ No `token` substring
- ✅ No `authorization` substring
- ✅ No `providerId` substring
- ✅ No `modelId` substring
- (Phase 7-T2+) No file paths outside `<userData>/`
- (Phase 7-T2+) No localhost URLs with credentials
- (Phase 7-T2+) Truncate large outputs (100 KB default)

## 6. Threat model (Phase 7-T2)

| Threat | Mitigation |
|--------|------------|
| LLM passes wrong-typed args | Phase 7-T0 `validateToolArgs` |
| LLM passes malicious args (path traversal) | Phase 7-T2+ path sanitization |
| LLM passes args with secrets | Phase 7-T0 + Phase 7-T2 `assertNoSecret` |
| Adapter throws exception | Adapter catches → `ToolResult { success: false }` |
| Adapter returns malformed result | `isValidToolResult` |
| Adapter returns secret in result | `assertNoSecret` throws |
| Adapter takes too long | Phase 7-T2+ `ctx.timeoutMs` (Phase 7-T2 contract only) |
| Adapter reads Authorization | Phase 6-A2 auth service (NOT IMPLEMENTED in 7-T2) |
| Concurrent invocations | Phase 7-T2+ queue per tool |

## 7. Phase 7-T2 strict forbids

- ❌ Implement any sanitization function
- ❌ Add permission enforcement
- ❌ Read `Authorization` headers
- ❌ Hold tokens
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `desktop/src/auth/`
- ❌ Import from `backend/`

## 8. References

- `docs/tools/tool-adapter-architecture.md` (Phase 7-T2 — adapter contract)
- `docs/tools/tool-registry-runtime.md` (Phase 7-T1 — Registry)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 — Security)
- `docs/tools/application-adapter-design.md` (Phase 7-T0 — Adapter pattern)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)
- `desktop/src/shared/tools/tool-adapter-schema.ts` (Phase 7-T2 contracts)

## Status (2026-08-22 Phase 7-T2)

- 5-step validation pipeline documented
- 5 adapter-level security rules
- 8-entry output sanitization rules (5 Phase 7-T2 strict + 3 Phase 7-T2+)
- 9-entry threat model + mitigations
- 0 implementations (Phase 7-T2 ships ONLY the security model)
- Doc complete (8 sections)
