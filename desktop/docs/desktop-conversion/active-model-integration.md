# Active Model Integration (Phase 6-B)

> **purpose**: Connect the Phase 6-A provider runtime into the user-facing chat experience: per-session model binding, chat-header ModelSelector widget, AgentStatusBadge model display, and chat-store integration.
> **follows**: Phase 6-A1 (foundation, f7f197447), Phase 6-A2 (SecretStore + IPC, 5a17cab97), Phase 6-A3 (Provider Factory + Registry, adda703e1), Phase 6-A4 (Settings + ConfigStore, 8ecb303f2), Phase 6-A5 (Runtime Routing, ac1e4a3b4), Phase 6-A6 (E2E Runtime, 4b2181b99).

## 1. Scope (Phase 6-B frozen)

- `ConversationModelContext` shared type — non-secret `{ providerId, model, displayName?, capabilities? }`
- `ChatSessionOut.modelContext?` — optional session-level binding (backward-compatible)
- `ChatStreamRequest.modelContext` — unified to use `ConversationModelContext` (was an inline shape in Phase 6-A5)
- `useModelSelectorStore` Pinia store — chat-side selection + per-session overrides
- `ModelSelector.vue` chat-header widget — picker with capability chips
- `AgentStatusBadge.vue` extended — displays current model alongside state hint
- Chat store `sendUserMessageStream` — injects `modelContext` from selector (per-session override wins)
- 26 unit tests (>= 25 spec requirement)
- **NO** changes to backend, chat:* IPC contract, Phase 3-B0 StreamEvent; **NO** legacy chat fallback broken

## 2. Files (Phase 6-B)

```
desktop/src/shared/model/
  - conversation-model.ts                (NEW)  ConversationModelContext type + isValidConversationModelContext

desktop/src/shared/
  - chat-types.ts                         (MODIFY) ChatSessionOut.modelContext + ChatStreamRequest.modelContext unification

desktop/src/renderer/src/
  - stores/model-selector.ts              (NEW)  Pinia store (no apiKey field)
  - components/chat/ModelSelector.vue     (NEW)  chat-header widget
  - components/chat/AgentStatusBadge.vue  (MODIFY) +currentModel prop, shows "<model> · <state>"
  - stores/chat.ts                        (MODIFY) +5 lines: inject modelContext into startStream

desktop/tests/unit/
  - model-selector.test.ts                (NEW)  26 cases

desktop/docs/desktop-conversion/
  - active-model-integration.md           (NEW)  this file
```

## 3. Session model binding

```
ChatSessionOut (Phase 6-B additive):
  + modelContext?: ConversationModelContext    // optional, non-secret
                                              // absent = use active selection
                                              //   or legacy fallback
```

Three resolution rules (renderer-side, model-selector store):

```
resolveForSession(sessionId):
  1. if sessionId in sessionOverrides   -> override
  2. else if selected is set             -> global selection
  3. else                                -> null (legacy fallback)
```

The chat store reads `modelSelector.resolveForSession(currentSessionId)` and passes the result as `modelContext` to `window.api.chat.startStream`. Main process sees the same shape in `ChatStreamRequest.modelContext` (Phase 6-A5 unified to `ConversationModelContext`).

## 4. Selector architecture

```
[Renderer Pinia store: model-selector]
   - available: AvailableProvider[]     (Phase 6-A4 IPC listConfigs)
   - selected: ConversationModelContext | null
   - sessionOverrides: Map<sessionId, ConversationModelContext>
   ↓
[Renderer chat store]
   - sendUserMessageStream()
     resolves modelContext = resolveForSession(currentSessionId)
     passes to window.api.chat.startStream({ message, session_id, modelContext })
   ↓
[Preload contextBridge]
   - chat:start-stream unchanged contract
   - payload: { message, session_id, modelContext? } (backward-compatible)
   ↓
[Main process: chat-stream.service.ts]
   - Phase 6-A5: routeChatRequest(modelContext)
     mode=='legacy'  -> legacy FastAPI /chat/stream (default)
     mode=='provider'-> runProviderRuntime (Phase 6-A6: real HTTP fetch)
```

Phase 6-B adds the renderer-side selection; the main process decision tree from Phase 6-A5/A6 is unchanged.

## 5. UI contract

### ModelSelector.vue (chat-header widget)

Trigger button: `🧠 <displayName> · <model> ▾`

Hover dropdown:
```
Available providers
  OpenAI           gpt-4o-mini    🔑
  Ollama           qwen3:8b       ⚠ no key   (disabled)

[ Use default (legacy) ]

Capabilities
  [streaming] [tools] [vision]
```

Phase 6-B strict: provider rows without an API key are `disabled` (cannot pick). The "Use default (legacy)" button clears the global selection, returning to FastAPI /chat/stream.

### AgentStatusBadge.vue (Phase 6-B extended)

Before: `🧠 thinking...`
After (with currentModel): `🧠 OpenAI · gpt-4o-mini · thinking...`

If `currentModel` is null/undefined, falls back to plain state label (Phase 5-C behavior preserved).

## 6. Capability gating

Phase 6-B ships capability **display** (Phase 6-A4 IPC + conversation-model caps). Phase 6-C will ship capability **gating** (e.g. vision-only providers filter vision requests).

UI surface in Phase 6-B:
- ModelSelector dropdown shows capability chips per provider
- AgentStatusBadge displays model name
- Future (Phase 6-C): capability mismatch returns a friendly error to the user

## 7. Security boundary (Phase 6-B strict)

The `ConversationModelContext` type and all renderer-visible state NEVER contain:

- API key (plaintext or cipher)
- Authorization header
- Tokens / refresh tokens

The renderer-side store has no `apiKey` field at all. The `isValidConversationModelContext` validator rejects payloads containing `sk-` / `apiKey` / `cipher` substrings.

Test enforcement (`tests/unit/model-selector.test.ts`):

- "store state dump NEVER contains apiKey substring" (JSON.stringify $state + grep)
- "isValidConversationModelContext rejects payloads with apiKey field"
- "availableProvider shape NEVER contains apiKey field"
- Chat-stream payload via `window.api.chat.startStream` is grep-tested in the store-level mock

## 8. Backward compatibility

| Change | Compatibility |
|--------|---------------|
| `ChatSessionOut.modelContext?` | Old sessions without field still work. |
| `ChatStreamRequest.modelContext` shape | Unified to `ConversationModelContext` (was inline `{ providerId?, model? }` in Phase 6-A5). Same fields; renderer + main both updated. |
| `model-selector` Pinia store | New; chat store falls back to legacy if store not loaded. |
| ModelSelector.vue | New; chat header renders without it (legacy path). |
| AgentStatusBadge.vue +currentModel prop | Optional prop with default null; old callers unchanged. |
| Chat store `sendUserMessageStream` | Injects `modelContext` only when available; legacy path unaffected. |

## 9. Test coverage (26 / 26 PASSED, exceeds spec >= 25)

| describe | cases |
|----------|-------|
| Initial state (2) | empty / getters reflect empty |
| loadAvailable (5) | success / capabilities parse / IPC error / loading flag / clear on empty |
| select / clear (4) | defaultModel / explicit model / unknown id throws / clear() |
| selectForSession (4) | set override / null removes / empty id no-op / independent sessions |
| resolveForSession (3) | null when nothing / global selection / per-session override wins |
| Capability display (3) | capabilityLabel stable / capabilityList / fallback to [] |
| Security (4) | state dump clean / validator rejects apiKey / validator accepts clean / availableProvider no apiKey |
| reset (1) | clears all state |
| **Total** | **26** |

## 10. Forbidden patterns (permanent)

- ❌ Add `apiKey` field to any Pinia store. (Reason: defense-in-depth — never even define the field.)
- ❌ Log `ConversationModelContext` from renderer without the no-secret guard. (Reason: dev tools console is world-readable.)
- ❌ Pass `modelContext` from renderer to chat stream when the user has no API key configured. (Reason: runtime router would still attempt provider mode and fail; better to fall back to legacy.)
- ❌ Auto-select a provider on store load. (Reason: explicit user choice only.)
- ❌ Bypass session override via global selection. (Reason: per-session override exists for a reason.)
- ❌ Persist `selected` to localStorage / sessionStorage. (Reason: cross-session contamination; main process owns truth via ActiveProviderStore.)
- ❌ Add new `StreamEventType` variants. (Reason: Phase 3-B0 frozen.)
- ❌ Replace the legacy FastAPI chat path. (Reason: legacy users continue to work.)

## 11. Phase 6-C transition

Phase 6-C (next):

- Capability gating: vision-only providers filter to vision requests (request-time capability check).
- Live e2e from desktop chat: Ollama + OpenAI both reachable with stored key.
- ChatView emits modelContext even when only legacy is selected (so server-side can echo it back for status display).
- Capability mismatch → friendly error in AgentStatusBadge (e.g. "This model doesn't support vision").

## 12. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| 6-A2 SecretStore + IPC | safeStorage vault + 4 IPC channels + window.api.model + 44 tests | done (5a17cab97) |
| 6-A3 Provider Factory + Registry | registry + openai-compatible + ollama + 66 tests | done (adda703e1) |
| 6-A4 Model Settings + Provider Management | ConfigStore + 4 IPC + Pinia store + UI + 58 tests | done (8ecb303f2) |
| 6-A5 Model Runtime Integration | ActiveProviderStore + RuntimeRouter + feature flag + 25 tests | done (ac1e4a3b4) |
| 6-A6 Model Provider Runtime E2E | real HTTP fetch + SSE/NDJSON + mock server + 33 tests | done (4b2181b99) |
| **6-B Active Model Integration** | ConversationModelContext + selector store + UI + 26 tests | **this commit** |
| 6-C Capability gating + live e2e | follow | next |

## 13. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2)
- `docs/desktop-conversion/provider-factory.md` (Phase 6-A3)
- `docs/desktop-conversion/model-settings.md` (Phase 6-A4)
- `docs/desktop-conversion/model-runtime-routing.md` (Phase 6-A5)
- `docs/desktop-conversion/model-provider-runtime-e2e.md` (Phase 6-A6)

## Status (2026-08-22 Phase 6-B)

- `ConversationModelContext` shared type + validator
- `ChatSessionOut.modelContext?` + `ChatStreamRequest.modelContext` unified
- `useModelSelectorStore` Pinia (no apiKey field)
- `ModelSelector.vue` chat-header widget (capability chips, hasKey indicator)
- `AgentStatusBadge.vue` extended (+currentModel prop)
- Chat store injects modelContext on `sendUserMessageStream`
- 26 unit tests PASSED (exceeds spec >= 25)
- 0 changes to chat:* IPC, Phase 3-B0 StreamEvent, backend, legacy FastAPI path
- Doc complete (13 sections)
