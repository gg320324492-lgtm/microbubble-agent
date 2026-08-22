# Provider Factory + Registry (Phase 6-A3)

> **purpose**: Multi-model provider layer. Each vendor (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM / openai-compatible) gets its own factory implementing `ModelProvider`. A central registry resolves `providerId` -> factory and caches the resulting provider.
> **follows**: Phase 6-A1 (foundation types + interface + normalizer, f7f197447), Phase 6-A2 (SecretStore + IPC, 5a17cab97).
> **Phase 6-A3 strictly**: no real production keys, no real network in production code paths; ping only fires with explicit fetcher injection.

## 1. Scope (Phase 6-A3 frozen)

- `ProviderRegistry`: in-process `Map<providerId, factory>` with lazy-build cache
- `openai-compatible-provider`: works for OpenAI / MiniMax / Qwen / Mimo / vLLM (openai mode) — uses `data: {json}\n\n` SSE
- `ollama-provider`: NDJSON streaming (NOT SSE) — `{"message":{"content":...}, "done": false}` + `{"done": true, ...stats}`
- Both providers: `buildRequest` + `parseChunk` + `ping`, all returning Phase 3-B0 `StreamEvent` shape unchanged
- 66 unit tests (>= 50 spec requirement)
- **NO** MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM **real API** connections (mock fetch in tests)

## 2. Files (Phase 6-A3)

```
desktop/src/main/services/model-provider/
  - registry.ts                                (NEW)  providerId -> factory
  - providers/
    - openai-compatible-provider.ts            (NEW)  OpenAI-shaped HTTP / SSE
    - ollama-provider.ts                       (NEW)  Ollama HTTP / NDJSON

desktop/tests/unit/
  - provider-factory.test.ts                   (NEW)  66 cases

desktop/docs/desktop-conversion/
  - provider-factory.md                        (NEW)  this file
```

## 3. Registry API

`desktop/src/main/services/model-provider/registry.ts`:

| Function | Signature | Behavior |
|----------|-----------|----------|
| `registerProvider` | `(providerId, factory, meta) => void` | Throws on invalid id / factory / meta. Re-registering overwrites. |
| `getProvider` | `(providerId, cfg?) => ModelProvider \| undefined` | Lazy-builds on first call; returns `undefined` if not registered. Caches by `(id, cfg)` reference. |
| `listProviders` | `() => ProviderRegistryMeta[]` | Metadata only — no factory callable from list. |
| `hasProvider` | `(providerId) => boolean` | Membership check. |
| `clearRegistry` | `() => void` | **TEST ONLY** — production must not call. |
| `registrySize` | `() => number` | Test helper. |

### Validation rules (Phase 6-A3)

`providerId`: any non-empty string (registry only — Phase 6-A2 SecretStore enforces lowercase a-z 2-32 chars for key storage).

`factory`: any function `(ModelConfig) => ModelProvider`.

`meta`: `{ type, capabilities, displayName, defaultModel }` where:
- `type` ∈ `'cloud' | 'local' | 'openai-compatible'`
- `capabilities` ≥ `{ streaming: boolean, tools, vision, functionCalling, jsonMode }`
- `displayName`, `defaultModel` non-empty strings

### Lazy-build + cache

```
registerProvider('openai', factory, meta)        // does NOT call factory
getProvider('openai', cfg)                        // calls factory on first call, caches
getProvider('openai', cfg)                        // returns cached
getProvider('openai', differentCfg)               // re-builds (different cfg reference)
```

This lets the caller swap `cfg.extra` or `cfg.endpoint` at runtime without restarting the app.

## 4. OpenAI-Compatible Provider

`providers/openai-compatible-provider.ts`:

### `buildOpenAiCompatibleRequest(req, cfg)` -> OpenAI /v1/chat/completions payload

```ts
{
  model: cfg.defaultModel,                    // 'gpt-4o' / 'minimax-cn' / 'qwen-plus'
  messages: [
    { role: 'system', content: '...' },
    { role: 'user', content: '...' },
    { role: 'assistant', content: '...' },
    { role: 'tool', content: '...', tool_call_id: '...', name: '...' }
  ],
  temperature?: 0.7,
  max_tokens?: 256,
  stop?: ['</end>'],
  stream: true                                 // required for SSE
}
```

### `parseOpenAiCompatibleChunk(raw)` -> `StreamEvent | null`

Delegates to Phase 6-A1 `normalizeStreamChunk`. Supports:

| Input | Output |
|-------|--------|
| `data: {"choices":[{"delta":{"content":"hi"}}]}` | `{ type: 'text_delta', delta: 'hi' }` |
| `data: {"choices":[{"delta":{"tool_calls":[{...}]}}]}` | `{ type: 'tool_use', tool_name, tool_use_id, tool_input }` |
| `data: {"choices":[{"delta":{},"finish_reason":"stop"}], "usage":{...}}` | `{ type: 'done', finish_reason, usage }` |
| `data: [DONE]` | `{ type: 'done' }` |
| `[DONE]` | `{ type: 'done' }` |
| `data: {"error":{"message":"...","code":"..."}}` | `{ type: 'error', message, error_code }` |
| `: comment` | `null` |
| empty | `null` |
| pure JSONL (no `data:` prefix) | parsed same way |

### `pingOpenAiCompatible(cfg, apiKey, fetcher)` -> `{ ok, latencyMs?, error? }`

```
GET {cfg.endpoint}/v1/models
Headers: Authorization: Bearer {apiKey}     // only if apiKey present
Body: -
```

- 200 → `ok=true, latencyMs`
- non-200 → `ok=false, error="HTTP {status} {statusText}"`
- network error → `ok=false, error=message`
- `cfg.endpoint` missing → `ok=false, error="endpoint missing"`

The `apiKey` and `fetcher` parameters are **injected** at factory construction time (not via global). This keeps tests hermetic and matches Phase 6-A2 SecretStore pattern.

## 5. Ollama Provider

`providers/ollama-provider.ts`:

### `buildOllamaRequest(req, cfg)` -> Ollama /api/chat payload

```ts
{
  model: cfg.defaultModel,                    // 'qwen3:8b' / 'llama3:8b' / 'mistral:7b'
  messages: [{ role, content }, ...],
  stream: true,
  options?: {                                 // only if temp/max_tokens set
    temperature?: 0.7,
    num_predict?: 256                          // Ollama's name for max_tokens
  }
}
```

Key differences from OpenAI:
- `max_tokens` → `options.num_predict` (Ollama's vocabulary)
- No `Authorization` header (Ollama assumes local-trust)
- No `stop` array in Phase 6-A3 (Ollama `stop` is via `options.stop` — future)

### `parseOllamaChunk(raw)` -> `StreamEvent | null`

Ollama uses **NDJSON** (one JSON per line, NOT SSE):

| Input | Output |
|-------|--------|
| `{"model":"qwen3:8b","message":{"role":"assistant","content":"hi"},"done":false}` | `{ type: 'text_delta', delta: 'hi' }` |
| `{"done":true}` | `{ type: 'done', finish_reason: 'stop' }` |
| `{"done":true,"done_reason":"length"}` | `{ type: 'done', finish_reason: 'length' }` |
| `{"done":true,"eval_count":50,"prompt_eval_count":20}` | `{ type: 'done', finish_reason: 'stop', usage: { completion_tokens: 50, prompt_tokens: 20 } }` |
| `{"error":"model not found"}` | `{ type: 'error', message: 'model not found' }` |
| `data: {...}` (SSE prefix — wrong format) | `null` (graceful skip) |
| empty / non-JSON | `null` |

### `pingOllama(cfg, fetcher)` -> `{ ok, latencyMs?, error? }`

```
GET {cfg.endpoint}/api/tags
Headers: -                                    // no Authorization
Body: -
```

- 200 + body has `models: []` array → `ok=true`
- 200 + body missing `models` array → `ok=false, error="response missing models array"`
- non-200 → `ok=false, error="HTTP {status}"`
- `cfg.endpoint` missing → `ok=false`
- network error → `ok=false`

## 6. Lifecycle (Phase 6-A5 Wiring sketch)

```
[Renderer chat store]
   ↓ window.api.chat.startStream({ message, session_id })
[preload] IPC API gateway
   ↓
[main] chat-stream.service.ts (Phase 6-A5: route switch)
   ↓ feature flag → decide fastapi vs provider
[main] registry.getProvider(providerId, cfg)
   ↓ first call -> factory(cfg).cached
   ↓ cache hit -> return cached
[main] provider.buildRequest(req, cfg)
   ↓
[main] provider.parseChunk(raw) for each SSE/NDJSON line
   ↓
[main] chat-stream.service.ts broadcasts Phase 3-B0 StreamEvent to renderer
   ↓
[Renderer ChatView] displays chunk
```

Phase 6-A5 wires this. Phase 6-A3 ships the factory + registry only.

## 7. Stream normalization (Phase 3-B0 frozen)

Both providers emit **Phase 3-B0 `StreamEvent` unchanged** — the `type` field is always one of:

```
'text_delta' | 'thinking' | 'tool_use' | 'tool_result' | 'citation'
| 'rich_block' | 'done' | 'error' | 'retry' | 'sync_required'
| 'suggestions' | 'brief' | 'detail' | <vendor-specific string>
```

Phase 6-A3 forbids adding new variants. Vendor-specific types must reuse existing slots (e.g. `thinking` for both Qwen reasoning and Ollama thinking; `error` for both rate-limit and model-not-found).

## 8. Test coverage (66 / 66 PASSED, exceeds spec >= 50)

`tests/unit/provider-factory.test.ts`:

| describe | cases |
|----------|-------|
| Registry register / has / list / clear (12) | invalid id length, non-function factory, missing meta, empty displayName/defaultModel, invalid type, hasProvider true/false, listProviders empty/meta-only, re-register overwrite, clearRegistry |
| OpenAI buildRequest (7) | 4 message roles, tool_call_id+name, cfg.defaultModel, omit temp/max/stop when undefined, pass when provided, stream:true default, stream:false when requested |
| OpenAI parseChunk (11) | empty, comment, [DONE], data:[DONE], data: content delta, JSONL content delta, tool_calls delta, finish_reason-only chunk, error envelope, JSON-parse-fail-but-no-recognized-shape skip, data: empty payload |
| OpenAI ping (6) | 200 ok, non-200 fail, endpoint missing, Authorization header present, Authorization absent, network error |
| OpenAI factory wiring (3) | factory builds ModelProvider, buildRequest delegates, ping uses resolver |
| Ollama buildRequest (6) | 4 roles, temperature via options.temperature, max_tokens via options.num_predict, no options when empty, stream default+false, cfg.defaultModel |
| Ollama parseChunk (10) | empty, whitespace, invalid JSON, content chunk, done default, done with reason=length, usage stats, error envelope, skip SSE data: prefix, unknown shape |
| Ollama ping (6) | 200 + models array, missing models array, endpoint missing, non-200, network error, no Authorization |
| Ollama factory wiring (1) | factory builds ModelProvider |
| Integration (4) | getProvider undefined for unregistered, build on first call, cache on second same-cfg, rebuild on cfg change |
| **Total** | **66** |

## 9. Forbidden patterns (permanent)

- ❌ Add new `StreamEventType` variants. (Reason: Phase 3-B0 frozen; vendor-specific events reuse existing slots.)
- ❌ Call `fetch` directly inside `parseChunk` or `buildRequest`. (Reason: pure functions; HTTP lifecycle belongs to chat-stream.service.)
- ❌ Hardcode `Authorization` header. (Reason: OpenAI needs it; Ollama doesn't — each provider owns its own headers.)
- ❌ Import vendor SDK packages (e.g. `openai`, `ollama`). (Reason: pure adapter over `fetch` + JSON parsing; keeps bundle small.)
- ❌ Add a `deleteProvider` method. (Reason: process-lifetime registry; if a vendor must be removed, restart the app. Prevents "registered provider disappeared" runtime bugs.)
- ❌ Auto-register providers at module import. (Reason: side-effectful imports hide test pollution; caller explicitly invokes `registerProvider`.)

## 10. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| 6-A2 SecretStore + IPC | safeStorage vault + 4 IPC channels + window.api.model + 44 tests | done (5a17cab97) |
| **6-A3 Provider Factory + Registry** | registry + openai-compatible + ollama + 66 tests | **this commit** |
| 6-A4 Settings UI | renderer/views/settings + ProviderPanel.vue (uses window.api.model + registry.listProviders) | next |
| 6-A5 Wiring | chat-stream.service.ts route switch (feature-flagged; uses registry.getProvider) | follow |
| 6-A6 E2E | Ollama local e2e + docs (real /api/tags + /api/chat ping) | follow |

## 11. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1, f7f197447)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2, 5a17cab97)
- `docs/desktop-conversion/security.md` (token storage principles)

## Status (2026-08-22 Phase 6-A3)

- 1 registry (providerId -> factory + cache)
- 2 vendor providers (openai-compatible + ollama)
- 66 unit tests PASSED (exceeds spec >= 50)
- 0 changes to chat:* IPC, Phase 3-B0 schema, backend
- Doc complete (11 sections)
