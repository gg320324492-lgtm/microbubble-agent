# Model Runtime Routing (Phase 6-A5)

> **purpose**: Connect the Phase 6-A1~A4 Model Provider stack into the live chat-stream runtime via a runtime router with feature-flag-controlled legacy fallback.
> **follows**: Phase 6-A1 (foundation, f7f197447), Phase 6-A2 (SecretStore + IPC, 5a17cab97), Phase 6-A3 (Provider Factory + Registry, adda703e1), Phase 6-A4 (Settings + ConfigStore, 8ecb303f2).

## 1. Scope (Phase 6-A5 frozen)

- `ActiveProviderStore`: persisted non-secret active provider state (`{ providerId, model, enabled }`)
- `RuntimeRouter`: decides routing per request — `legacy` (default) or `provider`
- `MODEL_RUNTIME_MODE` feature flag (env var + setter): default `'legacy'`, opt-in `'provider'`
- `ChatStreamRequest.modelContext` (optional, additive) — when set, request routes to provider runtime
- `runProviderRuntime()` — provider-runtime streaming entry, pushes Phase 3-B0 `StreamEvent` through same `webContents.send` channels as legacy
- 25 unit tests (>= 20 spec requirement)
- **NO** real production API calls; **NO** changes to chat:* IPC contract; **NO** changes to Phase 3-B0 StreamEvent schema; **NO** changes to backend

## 2. Files (Phase 6-A5)

```
desktop/src/main/services/model-provider/
  - active-provider-store.ts           (NEW)  non-secret active provider persistence
  - runtime-router.ts                   (NEW)  routing decision + provider runtime entry

desktop/src/main/services/chat/
  - chat-stream.service.ts              (MODIFY)  +5 lines: route decision before runStream

desktop/src/shared/
  - chat-types.ts                       (MODIFY)  ChatStreamRequest + optional modelContext

desktop/tests/unit/
  - model-runtime-router.test.ts        (NEW)  25 cases

desktop/docs/desktop-conversion/
  - model-runtime-routing.md            (NEW)  this file
```

## 3. Runtime architecture

```
                            chat:start-stream (chat:* IPC unchanged)
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │ chat-stream.service.ts  │
                          │  startChatStream(req)   │
                          └─────────────────────────┘
                                       │
                  routeChatRequest(req.modelContext)
                                       │
                                       ▼
                ┌──────────────────────────────────────┐
                │   RuntimeRouter                      │
                │   runtimeFeatureFlag.getMode()       │
                └──────────────────────────────────────┘
                          │                    │
                mode=='legacy'          mode=='provider'
                          │                    │
                          ▼                    ▼
                ┌───────────────────┐  ┌─────────────────────────────┐
                │  legacy path      │  │  resolveActiveProvider      │
                │  runStream()      │  │   ├─ ActiveProviderStore    │
                │  fetch FastAPI    │  │   ├─ provider-config-store  │
                │  /chat/stream     │  │   ├─ model-secret-store     │
                │  (UNCHANGED)      │  │   └─ registry.getProvider   │
                └───────────────────┘  └─────────────────────────────┘
                                                  │
                                                  ▼
                                       runProviderRuntime()
                                          provider.buildRequest
                                          provider.parseChunk
                                                  │
                                                  ▼
                                       pushChunk / pushEnd / pushError
                                       (same webContents.send channels)
```

The renderer is **unaware** of the routing decision — it receives the same `chat:stream-chunk` / `chat:stream-end` / `chat:stream-error` events with the same `StreamContext` (`streamId` + `sessionId`).

## 4. Legacy / provider dual-path

### Legacy path (default, Phase 6-A5 strict unchanged)

```
runStream(streamId, req, signal, attempt):
  POST {backendUrl}/chat/stream
  Bearer <access_token>
  body = JSON.stringify(req)
  read SSE stream → pushChunk
  401 → performRefresh + retry (attempt=2)
```

This path is **byte-identical** to pre-Phase-6-A5 behavior. The only added dependency is `runtimeRouter.routeChatRequest(...)` evaluated at the top of `startChatStream` — when the flag is `legacy` (default), the router returns immediately with `{ mode: 'legacy' }` and `runStream` proceeds.

### Provider path (opt-in)

```
runProviderRuntimeStream(streamId, req, resolved, signal):
  runProviderRuntime(req, resolved, callbacks, signal)
    provider.buildRequest({ messages, model, stream: true }, cfg)  // vendor payload
    for each chunk:
      provider.parseChunk(raw) -> StreamEvent
      callbacks.onChunk(event)
    callbacks.onEnd()
```

The provider path does **NOT** call FastAPI. It uses the configured provider's factory (Phase 6-A3) and the user's stored API key (Phase 6-A2 SecretStore).

### Phase 6-A5 stub

`runProviderRuntime()` currently emits a confirmation chunk + done event to prove the path works end-to-end. **No real network calls**. Phase 6-A6 will wire the actual HTTP fetch.

## 5. Feature flag

### `MODEL_RUNTIME_MODE` env var

| Value | Behavior |
|-------|----------|
| `legacy` (default if unset) | All chat requests use FastAPI /chat/stream. `req.modelContext` is ignored. |
| `provider` | Chat requests route via runtime router. Falls back to `legacy` if no active provider / config / factory / key. |

### Programmatic override (test-only)

```ts
import { runtimeFeatureFlag } from '.../runtime-router'
runtimeFeatureFlag.setMode('provider')  // test override
runtimeFeatureFlag.setMode('legacy')    // reset
```

Phase 6-A5 strict: the programmatic override is for tests only. Production should use the env var.

## 6. Provider selection flow

```
User opens /settings/models (Phase 6-A4):
  1. Add provider (id + endpoint + defaultModel + capabilities) → ConfigStore
  2. Add API key (encrypted via SecretStore)
  3. Test connection → registry.ping
  4. Set as default → Pinia store activeProviderId + activeModel

(Pinia store state on renderer; main process owns truth via ActiveProviderStore)
```

When the user issues a chat request:

```
chat:start-stream arrives at main process
  → startChatStream(req)
    → routeChatRequest(req.modelContext)
        if mode == 'legacy': return { mode: 'legacy' }
        if mode == 'provider':
            if req.modelContext?.providerId:
                try resolve → provider (or legacy fallback)
            else:
                try resolve active provider → provider (or legacy fallback)
    → if 'provider': runProviderRuntimeStream
    → else: runStream (legacy, unchanged)
```

## 7. Security boundary (Phase 6-A5 strict)

The apiKey is **NEVER**:

- Logged (no `console.log` includes `apiKey`)
- Included in `RouteDecision.reason` strings
- Included in StreamEvent payloads
- Sent over chat:* IPC channels (those carry `StreamEvent` only)
- Persisted to ActiveProviderStore (no field for it)

The apiKey IS:

- Read from SecretStore.get() inside `resolveActiveProvider()` (main process only)
- Held in `ResolvedProvider.apiKey` for the duration of one stream
- Passed to `provider.ping()` for connectivity testing
- (Phase 6-A6) Passed to the actual HTTP `Authorization: Bearer` header

Test enforcement (`tests/unit/model-runtime-router.test.ts`):

- "routeChatRequest legacy reason NEVER contains apiKey"
- "routeChatRequest provider reason NEVER contains apiKey"
- "active-provider-store NEVER accepts apiKey field"
- "runProviderRuntime emits chunk + done" — JSON.stringify'd chunks must not contain `sk-`, `apiKey`, or `cipher`

## 8. Backward compatibility

`ChatStreamRequest` gained one optional field:

```ts
interface ChatStreamRequest {
  message: string              // unchanged
  session_id: string           // unchanged
  model?: string               // unchanged (Phase 2)
  thinking_mode?: 'fast' | 'balanced' | 'deep' | null  // unchanged
  modelContext?: {             // NEW (Phase 6-A5) — optional
    providerId?: string
    model?: string
  }
}
```

Existing renderer code that sends `{ message, session_id }` continues to work identically. The `modelContext` field is additive — omitting it triggers the active-provider path (or legacy fallback).

`StreamEvent` shape: **0 changes**. Phase 3-B0 schema untouched.

`chat:*` IPC channels: **0 changes**. Same `chat:stream-chunk`, `chat:stream-end`, `chat:stream-error` events with same `StreamContext`.

## 9. Test coverage (25 / 25 PASSED, exceeds spec >= 20)

| describe | cases |
|----------|-------|
| feature flag (3) | default 'legacy', setMode('provider'), setMode('legacy') resets |
| active-provider-store (5) | null initially, round-trip, reject invalid providerId, reject empty model, clearActive |
| resolveActiveProvider (5) | no active / no config / no factory / no key / fully configured |
| routeChatRequest legacy (2) | legacy flag overrides active, reason string clean |
| routeChatRequest provider (4) | active + key → provider, modelContext override → provider, bad id → legacy, missing key → legacy |
| runProviderRuntime (3) | success emits chunk + done, abort before start, apiKey never in chunks |
| apiKey isolation (3) | legacy reason clean, provider reason clean, active-store no apiKey field |
| **Total** | **25** |

## 10. Forbidden patterns (permanent)

- ❌ Modify `chat:start-stream` / `chat:cancel-stream` IPC payloads. (Reason: stable contract.)
- ❌ Add fields to `StreamEvent`. (Reason: Phase 3-B0 frozen.)
- ❌ Log the apiKey. (Reason: dev tools console is world-readable.)
- ❌ Include apiKey in any string that crosses IPC. (Reason: defense-in-depth; every return value is grep-tested.)
- ❌ Auto-flip `MODEL_RUNTIME_MODE` to `provider` based on user having a config. (Reason: explicit opt-in only — silent behavior change breaks user expectations.)
- ❌ Throw on provider lookup failure. (Reason: router must always fall back to legacy so chat still works.)
- ❌ Persist active provider on the renderer side. (Reason: cross-session contamination; main process owns truth.)

## 11. Phase 6-B migration plan

Phase 6-A6 (next):

- Wire `runProviderRuntime()` to actually `fetch(provider.buildRequest(canonical, cfg), { Authorization: Bearer apiKey })`.
- Add timeout + retry logic for the provider HTTP call.
- Add `runProviderRuntime` end-to-end tests with mock fetch.

Phase 6-B (later):

- Settings UI exposes active-provider dropdown (already wired in Phase 6-A4 via Pinia store; needs IPC bridge to call `setActiveProvider`).
- ChatView emits `modelContext: { providerId, model }` when active is set; omits when not.
- Live e2e: Ollama + Qwen + OpenAI all reachable from the desktop chat.

Phase 6-C (later):

- Phase 6-B completion + per-provider capability gating (e.g. vision-only providers filter to vision requests).

## 12. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| 6-A2 SecretStore + IPC | safeStorage vault + 4 IPC channels + window.api.model + 44 tests | done (5a17cab97) |
| 6-A3 Provider Factory + Registry | registry + openai-compatible + ollama + 66 tests | done (adda703e1) |
| 6-A4 Model Settings + Provider Management | ConfigStore + 4 IPC + Pinia store + UI + 58 tests | done (8ecb303f2) |
| **6-A5 Model Runtime Integration** | ActiveProviderStore + RuntimeRouter + feature flag + 25 tests | **this commit** |
| 6-A6 E2E | real HTTP fetch + retry/timeout + e2e Ollama + docs | next |
| 6-B Settings UI active provider + chat integration | follow | later |
| 6-C capability gating | follow | later |

## 13. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1, f7f197447)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2, 5a17cab97)
- `docs/desktop-conversion/provider-factory.md` (Phase 6-A3, adda703e1)
- `docs/desktop-conversion/model-settings.md` (Phase 6-A4, 8ecb303f2)
- `docs/desktop-conversion/security.md` (token storage principles)

## Status (2026-08-22 Phase 6-A5)

- 1 ActiveProviderStore (non-secret active state)
- 1 RuntimeRouter (legacy/provider routing + provider runtime entry)
- 1 feature flag (MODEL_RUNTIME_MODE)
- 5 lines added to chat-stream.service.ts (route decision before runStream)
- 1 additive optional field on ChatStreamRequest (backward-compatible)
- 25 unit tests PASSED (exceeds spec >= 20)
- 0 changes to chat:* IPC contract, Phase 3-B0 StreamEvent, backend
- Doc complete (13 sections)
