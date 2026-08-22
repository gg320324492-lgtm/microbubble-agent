# Tool Security Boundary (Phase 7-T0)

> **purpose**: Define the security boundary around the Tool Layer. Tools bridge the Agent to existing application functions — that's also the attack surface.
> **follows**: `tool-registry-architecture.md` (Phase 7-T0) + `tool-schema.ts` (Phase 7-T0 contracts).
> **Phase 7-T0 strict**: security model only. NO implementation.

## 1. Scope (Phase 7-T0 frozen)

Phase 7-T0 ships:
- 5 security rules
- Permission model
- Argument validation pipeline
- Output sanitization rules
- Secret-handling rules

Phase 7-T0 does **NOT** ship:
- ❌ The actual permission service (Phase 7-T+)
- ❌ Authentication / authorization implementation
- ❌ Rate-limiting code
- ❌ Audit log storage

## 2. Security flow (Phase 7-T0)

```
                  Agent
                    │
                    ▼
              ┌─────────────┐
              │ Tool Lookup  │ <- get / list / search
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ Permission   │ <- definition.permission vs ctx.userId
              │   Check     │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ Argument     │ <- validateToolArgs(def, args)
              │ Validation  │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │  Execution  │ <- registration.executor(args, ctx)
              │   (timeout)  │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │  Result      │ <- isValidToolResult
              │ Validation  │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ Sanitization │ <- strip secrets / paths / tokens
              └──────┬──────┘
                     │
                     ▼
                ToolResult
```

Each gate is a strict gate. Failure at any gate → `ToolResult { success: false, error: { code, message } }`.

## 3. The 5 security rules (Phase 7-T0 strict)

### Rule 1: LLM cannot directly access application services

The LLM only sees the **Tool Registry** — never the application services directly.

```
WRONG:
  LLM -> AppService.someMethod()    <- LLM has direct app access

RIGHT (Phase 7-T+):
  LLM -> ToolRegistry.execute(toolId, args) -> AppService.someMethod(args)
  ^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^
  see     validated by isValidToolDefinition     unchanged business logic
  only                                            (Phase 7-T+ adapter)
  ToolDefinition
```

Phase 7-T0 strict: `desktop/src/shared/tools/tool-schema.ts` has zero imports from `model-provider/`, `auth/`, or `app/services/`.

### Rule 2: Every tool requires schema validation

Every tool call MUST pass `validateToolArgs(definition, args)` before execution.

- Missing required field → reject
- Wrong type → reject
- Out of range → reject
- Not in enum → reject

`validateToolArgs` returns a `string | null` error message. The Tool Registry converts this into `ToolResult { success: false, error: { code: 'INVALID_ARGS', message } }`.

### Rule 3: Every tool has a permission level

Every `ToolDefinition` carries a `permission: 'public' | 'research' | 'admin'`. The Tool Registry checks the caller's permission against the tool's required level.

| Permission | Allowed callers | Example tools |
|------------|-----------------|----------------|
| `public` | any (including Phase 7-T0 anonymous dev mode) | `tool:kinetic-analysis`, `tool:dataset-format` |
| `research` | researchers (Phase 7+) | `tool:experiment-list`, `tool:task-list` |
| `admin` | lab admins only | `tool:user-list`, `tool:db-reset` |

Phase 7-T0 strict: the permission enum is the ONLY permission shape. No roles, no groups, no custom claims in Phase 7-T0. Phase 7+ may extend.

### Rule 4: Tool results must be sanitized

The result envelope (`ToolResult`) is the ONLY thing that crosses back to the Agent / Renderer.

Sanitization checklist:
- ✅ `isValidToolResult(result)` — schema check
- ✅ `assertNoSecret(result)` — no apiKey / token / cipher
- ✅ No file paths outside `<userData>` / lab workspace
- ✅ No internal stack traces (replace with `[REDACTED]` placeholder)
- ✅ Truncate large outputs (Phase 7+ default: 100 KB per field)
- ✅ No localhost URLs with credentials

Phase 7-T0 strict: `isValidToolResult` runs `assertNoSecret`. Phase 7-T+ extends with path / URL / size checks.

### Rule 5: Secrets never enter the Tool Layer

The Tool Layer NEVER sees:
- `apiKey`
- `Authorization` header value
- `cipher:...`
- `Bearer ...`
- `token=...`
- `providerId` (Phase 6-A3 secret-adjacent)
- `modelId`

The Phase 7-T0 contracts enforce this via `assertNoSecret` on every validator. The runtime also enforces it via:
- Tool args are validated against the schema (unknown fields rejected)
- Tool results are validated via `isValidToolResult`
- `ToolDefinition.id` does NOT carry any of the above substrings

## 4. Permission enforcement (Phase 7-T+ sketch)

```ts
function checkPermission(definition: ToolDefinition, ctx: ToolExecutionContext): boolean {
  switch (definition.permission) {
    case 'public':     return true
    case 'research':   return ctx.userRole === 'researcher' || ctx.userRole === 'admin'
    case 'admin':      return ctx.userRole === 'admin'
  }
}
```

Phase 7-T0: the permission enum is defined. Phase 7-T+ ships the check + the role mapping.

## 5. Argument validation pipeline (Phase 7-T0 strict)

Every tool call goes through `validateToolArgs(def, args)`:

```
1. type check (string / number / boolean / array / object)
2. required field check
3. range check (number)
4. enum check (string)
5. nested field check (object)
6. assertNoSecret (defense in depth)
```

The validator returns `null` (valid) or an error message string. The Tool Registry converts the message into a structured `ToolResult { success: false, error }`.

## 6. Output sanitization pipeline (Phase 7-T0 strict)

```
1. isValidToolResult(result)
2. assertNoSecret(result)
3. (Phase 7+) truncate / redact file paths / strip credentials
4. return to Agent
```

Phase 7-T0 strict: only `isValidToolResult` + `assertNoSecret`. Phase 7-T+ adds path / URL / size sanitization.

## 7. Audit trail (Phase 7-T+ sketch — NOT IMPLEMENTED)

Every tool call MUST log:

```
{
  toolId: 'tool:kinetic-analysis',
  callerId: 'user:alice',
  argsHash: 'sha256:...',
  resultCode: 'success' | 'invalid_args' | 'permission_denied' | 'execution_error' | 'timeout',
  latencyMs: 1234,
  savedAt: 1726358400000
}
```

The audit log is NON-SECRET (no apiKey, no payload). Phase 7-T+ ships the audit storage.

## 8. Threat model (Phase 7-T0)

| Threat | Mitigation |
|--------|------------|
| LLM invents a tool that doesn't exist | `validateArgs` requires registration lookup; unknown toolId rejected |
| LLM passes wrong-typed args | `validateArgs` type check |
| LLM passes malicious args (path traversal) | Phase 7-T+ adds path / URL sanitization |
| Tool executor throws | `try / catch` wraps result in `ToolResult { success: false, error }` |
| Tool executor leaks secret | `assertNoSecret(result)` rejects |
| Tool executor takes too long | Phase 7-T+ enforces `ctx.timeoutMs` via AbortController |
| User invokes admin tool without permission | `checkPermission(definition, ctx)` blocks |
| Concurrent invocations of same tool | Phase 7-T+ adds rate limiting / lock per tool |

## 9. Phase 7-T0 strict forbids

- ❌ Implement the permission service
- ❌ Implement role mapping
- ❌ Implement rate limiting
- ❌ Implement audit log storage
- ❌ Add `Authorization` header parsing
- ❌ Add API key handling
- ❌ Import from `desktop/src/main/services/auth.service.ts`
- ❌ Import from `desktop/src/auth/`
- ❌ Import from `desktop/src/renderer/auth/`
- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `backend/`

## 10. References

- `docs/tools/existing-tool-audit.md` (Phase 7-T0 Step 1)
- `docs/tools/tool-registry-architecture.md` (Phase 7-T0 Step 6)
- `docs/tools/agent-tool-interface.md` (Phase 7-T0 Step 8)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)
- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 — Tool ↔ Knowledge)

## Status (2026-08-22 Phase 7-T0)

- 5 security rules documented
- 3-level permission model (public / research / admin)
- 6-step argument validation pipeline
- 4-step output sanitization pipeline
- 8-entry threat model + mitigations
- Audit trail contract sketched (Phase 7-T+)
- 0 implementations (Phase 7-T0 ships ONLY the security model)
- Doc complete (10 sections)
