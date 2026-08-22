# Tool Execution Security (Phase 7-T4)

> **purpose**: Define the security boundary around Tool Execution. The Executor is the runtime — that's also where the most dangerous failure modes live (infinite loops, privilege escalation, secret leakage).
> **follows**: `tool-executor-architecture.md` (Phase 7-T4) + `tool-adapter-security.md` (Phase 7-T2) + `tool-security-boundary.md` (Phase 7-T0).
> **Phase 7-T4 strict**: security model only. NO implementation.

## 1. Scope (Phase 7-T4 frozen)

Phase 7-T4 ships:
- 6-step execution pipeline
- 5 threat-model entries + mitigations
- Timeout + cancellation security rules
- Result sanitization rules

Phase 7-T4 does **NOT** ship:
- ❌ Permission service (Phase 7-T+ ships it)
- ❌ Rate limiting (Phase 7-T+ ships it)
- ❌ Audit log storage (Phase 7-T+ ships it)

## 2. Execution pipeline (Phase 7-T4)

```
                   Tool Match (Phase 7-T3)
                          │
                          ▼
              ┌────────────────────────┐
   1.         │  Registry Lookup       │   Phase 7-T1: get(toolId)
              └─────────┬──────────────┘
                        │
                        ▼
              ┌────────────────────────┐
   2.         │  Adapter Validation   │   Phase 7-T2: has(toolId) + bound?
              └─────────┬──────────────┘
                        │
                        ▼
              ┌────────────────────────┐
   3.         │  Schema Validation     │   Phase 7-T0: validateToolArgs(def, args)
              └─────────┬──────────────┘
                        │
                        ▼
              ┌────────────────────────┐
   4.         │  Permission Check      │   Phase 7-T0: def.permission vs ctx.userRole
              └─────────┬──────────────┘
                        │
                        ▼
              ┌────────────────────────┐
   5.         │  Execution             │   Phase 7-T4: adapter.execute() with timeout
              └─────────┬──────────────┘
                        │
                        ▼
              ┌────────────────────────┐
   6.         │  Result Sanitization   │   Phase 7-T0: isValidToolResult + assertNoSecret
              └────────────────────────┘
```

Each step is a hard gate. Failure at any step → `ToolResult { success: false, error: { code, message } }`.

## 3. Step-by-step security (Phase 7-T4)

### Step 1: Registry Lookup (Phase 7-T1)

The Executor resolves `request.toolId` to a `ToolDefinition`:

- Unknown toolId → reject with `INVALID_TOOL_ID`
- Inactive toolId → reject with `TOOL_INACTIVE` (Phase 7-T+)
- Phase 7-T4 strict: never log `toolId` with secrets (it never has them)

### Step 2: Adapter Validation (Phase 7-T2)

The Executor checks the Adapter Registry:

- No adapter bound → reject with `NO_ADAPTER` (Phase 7-T+)
- Adapter version mismatch → reject with `VERSION_MISMATCH` (Phase 7-T+)
- Phase 7-T4 strict: the Executor does NOT call the Adapter's `validate()` directly — that's the Adapter Registry's job

### Step 3: Schema Validation (Phase 7-T0)

The Executor runs `validateToolArgs(definition, args)`:

- Missing required field → reject with `INVALID_ARGS`
- Wrong type → reject
- Out of range → reject
- Not in enum → reject

### Step 4: Permission Check (Phase 7-T0)

The Executor checks `definition.permission` against `ctx.userContext.role`:

| Permission | Required role |
|------------|---------------|
| `public`   | any (including Phase 7-T4 anonymous dev mode) |
| `research` | `researcher` OR `admin` |
| `admin`    | `admin` |

Permission denied → `ToolResult { success: false, error: { code: 'PERMISSION_DENIED' } }`.

Phase 7-T4 strict: the Executor does NOT touch Auth. The `ctx.userContext` is populated upstream (Phase 7-T+ via auth service).

### Step 5: Execution (Phase 7-T4)

The Executor runs `adapter.execute(args, ctx)` with:

- Timeout: `Promise.race` against `setTimeout(request.timeout)`
- Cancellation: `AbortSignal` linked to `cancel(requestId)`
- Exception catching: any thrown error → `ToolResult { success: false, error: ... }`
- Phase 7-T4 strict: the Adapter NEVER throws (catches its own exceptions per Phase 7-T2 contract)

### Step 6: Result Sanitization (Phase 7-T0)

The Executor runs on the adapter's return value:

- `isValidToolResult(result)` (Phase 7-T0)
- `assertNoSecret(result)` (Phase 7-T0) — throws on forbidden substrings
- (Phase 7-T+) path / URL / size checks

If sanitization fails → `ToolResult { success: false, error: { code: 'SANITIZATION_FAILED', message: '...' } }`.

## 4. Timeout policy (Phase 7-T4 strict)

The Executor enforces `request.timeout` via:

```
Promise.race([
  adapter.execute(args, ctx),
  new Promise((_, reject) =>
    setTimeout(() => reject(new Error('TIMEOUT')), request.timeout)
  )
])
```

When the timeout fires:

1. The Executor marks the record's `status = 'failed'` and `error = 'TIMEOUT'`
2. The Executor emits `tool_execution_error` with `error: 'TIMEOUT'`
3. The Executor returns `ToolResult { success: false, error: { code: 'TIMEOUT' } }`

Phase 7-T4 strict: the Adapter does NOT enforce its own timeout. The Executor does.

## 5. Cancellation policy (Phase 7-T4 strict)

`cancel(requestId)`:

- If `status = 'queued'`: remove from queue → `status = 'cancelled'`
- If `status = 'running'`: signal the adapter to abort (via `ctx.abortSignal`) → eventually `status = 'failed'` with `error: 'CANCELLED'`
- If `status ∈ {'completed', 'failed', 'cancelled'}`: return `{ ok: false, reason: 'already terminal' }`

Cancellation is best-effort. The Executor does NOT forcibly terminate the adapter.

## 6. Threat model (Phase 7-T4)

| Threat | Mitigation |
|--------|------------|
| Invalid arguments | Phase 7-T0 `validateToolArgs` |
| Infinite execution | Executor enforces `request.timeout` via `Promise.race` |
| Privilege escalation | Phase 7-T0 `permission` field checked against `ctx.userContext.role` |
| Secret leakage (config) | `assertNoSecret` on `ToolExecutionRequest` |
| Secret leakage (result) | `assertNoSecret` on `ToolResult` |
| Malicious result (path traversal) | Phase 7-T+ path sanitization |
| Malicious result (oversized) | Phase 7-T+ size cap (100 KB) |
| Concurrent invocations | Phase 7-T+ queue per tool (Phase 7-T4 ships the contract) |
| Cancellation ignored | Phase 7-T+ AbortController escalation |
| Trace log leak | Phase 7-T4 strict: trace payload NEVER includes args.data (only metadata) |

## 7. Result sanitization (Phase 7-T4 strict)

Every `ToolResult` returned to the renderer goes through:

- `isValidToolResult(result)` — schema check
- `assertNoSecret(result)` — throws on sk- / apiKey / cipher / Bearer / token / authorization / providerId / modelId
- (Phase 7-T+) path / URL / size checks

The renderer NEVER sees raw adapter output. The Executor always returns the sanitized `ToolResult`.

## 8. Phase 7-T4 strict forbids

- ❌ Implement a concrete Executor class
- ❌ Add IPC for execution events (Phase 7-T+ ships them)
- ❌ Implement permission service (Phase 7-T+)
- ❌ Implement rate limiting (Phase 7-T+)
- ❌ Implement audit log storage (Phase 7-T+)
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `backend/`
- ❌ Connect to a database

## 9. References

- `docs/tools/tool-executor-architecture.md` (Phase 7-T4 — Executor interface)
- `docs/tools/tool-adapter-security.md` (Phase 7-T2 — Adapter security)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 — Security foundation)
- `desktop/src/shared/tools/execution-schema.ts` (Phase 7-T4 — THIS COMMIT)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0)
- `desktop/src/shared/tools/tool-adapter-schema.ts` (Phase 7-T2)

## Status (2026-08-22 Phase 7-T4)

- 6-step execution pipeline documented
- 10-entry threat model + mitigations
- Timeout + cancellation policy (Phase 7-T4 strict)
- 3-rule result sanitization (Phase 7-T0 reuse + Phase 7-T+ extensions)
- 0 implementations (Phase 7-T4 ships ONLY the security model)
- Doc complete (9 sections)
