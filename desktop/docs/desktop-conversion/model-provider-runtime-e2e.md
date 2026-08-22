# Model Provider Runtime E2E Verification (Phase 6-A6)

> **purpose**: Verify the full `ModelProvider → RuntimeRouter → fetch → SSE/NDJSON → parseChunk → StreamEvent` pipeline using a local mock HTTP server. No real vendor API calls; legacy FastAPI fallback remains byte-identical.
> **follows**: Phase 6-A1 (foundation, f7f197447), Phase 6-A2 (SecretStore + IPC, 5a17cab97), Phase 6-A3 (Provider Factory + Registry, adda703e1), Phase 6-A4 (Settings + ConfigStore, 8ecb303f2), Phase 6-A5 (Runtime Routing, ac1e4a3b4).

## 1. Scope (Phase 6-A6 frozen)

- Real HTTP fetch + SSE/NDJSON streaming in `runProviderRuntime()` (replaces Phase 6-A5 stub)
- Mock Provider Server (`tests/fixtures/mock-model-server.ts`) — Node `http` server simulating OpenAI SSE and Ollama NDJSON
- 33 e2e test cases (>= 30 spec requirement) covering OpenAI / Ollama / errors / timeout / abort / security / status
- `model-runtime-status.ts` — non-secret status snapshot type for Phase 6-B chat header
- **NO** real production API calls; **NO** changes to chat:* IPC contract; **NO** changes to Phase 3-B0 StreamEvent schema; **NO** changes to backend

## 2. Files (Phase 6-A6)

```
desktop/src/main/services/model-provider/
  - runtime-router.ts                (MODIFY)  runProviderRuntime: stub -> real HTTP fetch + SSE/NDJSON
  - model-runtime-status.ts          (NEW)     non-secret status snapshot type + assertStatusSafe

desktop/tests/fixtures/
  - mock-model-server.ts             (NEW)     Node http server (SSE + NDJSON)

desktop/tests/unit/
  - model-provider-runtime-e2e.test.ts (NEW)   33 cases

desktop/docs/desktop-conversion/
  - model-provider-runtime-e2e.md     (NEW)    this file
```

## 3. Runtime flow

```
runProviderRuntime(req, resolved, callbacks, signal, options):
  1. build canonical request (Phase 6-A3 buildRequest)
  2. compute URL: {endpoint}/v1/chat/completions (openai)
                  {endpoint}/api/chat (ollama)
  3. compute headers: Bearer for openai, none for ollama
  4. fetch(url, POST, body, signal)
       on non-2xx: callbacks.onError(mapHttpToErrorCode(status))
       on no body: callbacks.onError('INVALID_RESPONSE')
  5. read response.body.getReader() in a loop
       decode chunk with TextDecoder (utf-8, stream: true)
       splitBuffer(buffer, type):
         - type=='local'  -> split '\n'        (Ollama NDJSON)
         - else            -> split '\n\n'      (OpenAI SSE)
       for each chunk:
         strip 'data:' prefix
         provider.parseChunk(cleaned) -> StreamEvent | null
         callbacks.onChunk(event)
  6. drain final buffer (one trailing line / SSE terminator)
  7. callbacks.onEnd()
```

Timeout is composed via `AbortSignal.any([userSignal, timeoutSignal])`. The runtime distinguishes timeout vs user-abort:

| signal.aborted | timeoutController.signal.aborted | code |
|----------------|-----------------------------------|------|
| true           | any                               | `ABORTED` |
| false          | true                              | `TIMEOUT` |

## 4. HTTP streaming

### OpenAI SSE

```
POST {endpoint}/v1/chat/completions
Authorization: Bearer sk-...
Content-Type: application/json
Accept: text/event-stream

{ "model": "gpt-4o-mini", "messages": [...], "stream": true }

→ HTTP/1.1 200
  Content-Type: text/event-stream

data: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"world"},"finish_reason":null}]}

data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"total_tokens":42}}

data: [DONE]
```

### Ollama NDJSON

```
POST {endpoint}/api/chat
Content-Type: application/json
Accept: application/x-ndjson

{ "model": "qwen3:8b", "messages": [...], "stream": true, "options": {...} }

→ HTTP/1.1 200
  Content-Type: application/x-ndjson

{"model":"qwen3:8b","message":{"role":"assistant","content":"hello"},"done":false}
{"model":"qwen3:8b","message":{"role":"assistant","content":" world"},"done":false}
{"model":"qwen3:8b","message":{"role":"assistant","content":""},"done":true,"done_reason":"stop","eval_count":5,"prompt_eval_count":3}
```

The mock server (`tests/fixtures/mock-model-server.ts`) implements both shapes verbatim. Tests assert:

- OpenAI: SSE `data: ` prefix is stripped; `[DONE]` is consumed by `parseChunk` and emits no event.
- Ollama: NDJSON final line with `done: true` becomes `{ type: 'done', usage: {...} }`.

## 5. SSE normalization

`parseChunk(raw)` per vendor:

| Vendor | Input | StreamEvent |
|--------|-------|-------------|
| OpenAI | `data: {"choices":[{"delta":{"content":"hi"}}]}` | `{ type: 'text_delta', delta: 'hi' }` |
| OpenAI | `data: {"choices":[{"delta":{"tool_calls":[{...}]}}]}` | `{ type: 'tool_use', tool_name, tool_use_id, tool_input }` |
| OpenAI | `data: {"choices":[{"delta":{},"finish_reason":"stop"}], "usage":{...}}` | `{ type: 'done', finish_reason, usage }` |
| OpenAI | `data: {"error":{"message":"...","code":"..."}}` | `{ type: 'error', message, error_code }` |
| OpenAI | `data: [DONE]` | `{ type: 'done' }` (consumed; no event) |
| Ollama | `{"message":{"role":"assistant","content":"hi"},"done":false}` | `{ type: 'text_delta', delta: 'hi' }` |
| Ollama | `{"done":true}` | `{ type: 'done', finish_reason: 'stop' }` |
| Ollama | `{"done":true,"done_reason":"length"}` | `{ type: 'done', finish_reason: 'length' }` |
| Ollama | `{"done":true,"eval_count":50,"prompt_eval_count":20}` | `{ type: 'done', usage: { completion_tokens: 50, prompt_tokens: 20 } }` |
| Ollama | `{"error":"..."}` | `{ type: 'error', message: '...' }` |

Phase 6-A6 strict: never introduce new `StreamEventType` variants. Reuse existing slots.

## 6. Error handling

| Cause | StreamErrorPayload.code | Example |
|-------|--------------------------|---------|
| HTTP 401 | `UNAUTHORIZED` | bad api key |
| HTTP 403 | `FORBIDDEN` | permission denied |
| HTTP 404 | `NOT_FOUND` | model not found |
| HTTP 429 | `RATE_LIMITED` | quota exceeded |
| HTTP 5xx | `SERVER_ERROR` | upstream outage |
| HTTP other | `INVALID_RESPONSE` | 4xx not above |
| Empty body | `INVALID_RESPONSE` | upstream closed |
| Network fail | `NETWORK_ERROR` | ECONNREFUSED |
| Timeout | `TIMEOUT` | > 30000ms |
| User abort | `ABORTED` | renderer cancel |

The renderer subscribes via the existing `chat:stream-error` IPC channel (Phase 2-Impl-3B, untouched). The error code reaches `StreamErrorPayload.code` unchanged.

## 7. Abort lifecycle

```
renderer.startStream(req) → main.startChatStream(req)
  → chat:stream-chunk listener (renderer) attaches
  → user clicks "Stop" → window.api.chat.cancelStream(streamId)
  → main.cancelChatStream(streamId) → AbortController.abort()
  → runProviderRuntime sees signal.aborted = true
  → callbacks.onError('ABORTED', ...)
  → main: chat:stream-error broadcast
```

Phase 6-A6 strict: abort is a real AbortError that propagates through `fetch` and `reader.read`. Mock server also accepts the abort signal (server.close mid-response) for clean shutdown.

## 8. Security boundary (Phase 6-A6 strict — same as Phase 6-A5)

| Item | Where it lives | Where it MUST NOT go |
|------|----------------|----------------------|
| apiKey (plaintext) | SecretStore (Phase 6-A2), ResolvedProvider.apiKey | Renderer state, IPC payload, log line |
| apiKey (cipher) | electron-store `model-provider-keys.json` | Renderer, log |
| Authorization header | HTTP request to provider (Bearer <apiKey>) | Anywhere else (NOT query string, NOT body) |
| Status snapshot | `model-runtime-status.ts` shape | apiKey / cipher / Authorization |

Test enforcement (`tests/unit/model-provider-runtime-e2e.test.ts`):

- `apiKey NEVER appears in any StreamEvent chunk payload` (run + JSON.stringify + grep `sk-supersecret-1234` / `apiKey` / `cipher`)
- `apiKey NEVER appears in any error message` (similar)
- `apiKey goes into Authorization header (NOT query string, NOT body)` (server captures both `headers.authorization` and `body`)
- `runtime payload sent over the wire does NOT contain model-context metadata that leaks apiKey` (server captures `body` + grep)
- `assertStatusSafe(status)` throws on `sk-` / `apiKey` / `cipher` / `Bearer ` substrings

## 9. Mock server

`tests/fixtures/mock-model-server.ts`:

```ts
interface MockScript {
  chunks: { content: string }[]
  errorStatus?: number     // HTTP error code
  errorBody?: string       // JSON body for errors
  delayMs?: number         // wait before responding (for timeout tests)
  signal?: AbortSignal     // abort mid-response
}

await startMockProviderServer(kind: 'openai' | 'ollama', script): Promise<{
  url: string
  port: number
  requests: Array<{ method, path, headers, body }>
  close(): Promise<void>
}>
```

The server binds to `127.0.0.1:0` (ephemeral port) and is fully torn down in `finally { await server.close() }`. Tests can run in parallel without port conflicts.

## 10. Test coverage (33 / 33 PASSED, exceeds spec >= 30)

| describe | cases |
|----------|-------|
| OpenAI SSE e2e (6) | text_delta emission / multi-chunk no drop / [DONE] handling / 401 / 429 / 500 |
| Ollama NDJSON e2e (5) | text_delta emission / done with usage stats / 404 / empty stream / no Authorization header |
| Timeout (2) | TIMEOUT when delay > timeoutMs / no timeout when within |
| Abort (2) | ABORTED when pre-aborted / ABORTED mid-stream |
| Runtime Router integration (5) | legacy default / provider mode active / bad id fallback / missing config fallback / end-to-end provider path |
| Security (5) | apiKey not in chunks / apiKey not in errors / apiKey in Authorization only / assertStatusSafe rejects leaks / wire body has no apiKey |
| Model Runtime Status (5) | connected / failed / unknown default / numeric updatedAt / cipher substring rejected |
| Edge cases (3) | OpenAI body shape / Ollama body shape / reason string clean |
| **Total** | **33** |

## 11. Forbidden patterns (permanent)

- ❌ Mock a real vendor API in tests. (Reason: must remain hermetic; no network coupling to OpenAI/Ollama/Anthropic/etc.)
- ❌ Pass apiKey through `RouteDecision.reason`. (Reason: `reason` is renderer-visible for debugging.)
- ❌ Persist `ResolvedProvider.apiKey` outside the runtime function. (Reason: function-scoped lifetime only.)
- ❌ Use `AbortController` without checking `signal.aborted` before each fetch call. (Reason: prevents silent network calls after cancel.)
- ❌ Skip the SSE `data:` prefix strip. (Reason: parseChunk receives payload, not the `data: ` envelope.)
- ❌ Skip the NDJSON `\n` split for Ollama. (Reason: provider type drives the split.)
- ❌ Add `StreamEventType` variants. (Reason: Phase 3-B0 frozen.)
- ❌ Replace the legacy FastAPI path. (Reason: legacy users continue to work unchanged.)

## 12. Phase 6-B migration plan

Phase 6-B (next):

- Chat header shows `ModelRuntimeStatus` (read from chat-stream.service.ts push).
- Settings UI exposes `setActiveProvider` (already wired in Phase 6-A4 Pinia store; needs IPC bridge).
- ChatView emits `modelContext: { providerId, model }` when active is set.
- Live e2e: Ollama + OpenAI all reachable from desktop chat (with stored key).

Phase 6-C (later):

- Capability gating: vision-only providers filter to vision requests.
- Per-provider retry/timeout policies.
- Streaming backpressure (handle slow renderer).

## 13. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| 6-A2 SecretStore + IPC | safeStorage vault + 4 IPC channels + window.api.model + 44 tests | done (5a17cab97) |
| 6-A3 Provider Factory + Registry | registry + openai-compatible + ollama + 66 tests | done (adda703e1) |
| 6-A4 Model Settings + Provider Management | ConfigStore + 4 IPC + Pinia store + UI + 58 tests | done (8ecb303f2) |
| 6-A5 Model Runtime Integration | ActiveProviderStore + RuntimeRouter + feature flag + 25 tests | done (ac1e4a3b4) |
| **6-A6 Model Provider Runtime E2E** | real HTTP fetch + SSE/NDJSON + mock server + 33 tests | **this commit** |
| 6-B Settings UI active provider + chat integration | follow | next |
| 6-C capability gating | follow | later |

## 14. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1, f7f197447)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2, 5a17cab97)
- `docs/desktop-conversion/provider-factory.md` (Phase 6-A3, adda703e1)
- `docs/desktop-conversion/model-settings.md` (Phase 6-A4, 8ecb303f2)
- `docs/desktop-conversion/model-runtime-routing.md` (Phase 6-A5, ac1e4a3b4)
- `docs/desktop-conversion/security.md` (token storage principles)

## Status (2026-08-22 Phase 6-A6)

- `runProviderRuntime`: stub → real HTTP fetch + SSE/NDJSON streaming
- Mock server: SSE + NDJSON + error + delay + abort
- Status snapshot type: `ModelRuntimeStatus` + `assertStatusSafe`
- 33 e2e tests PASSED (exceeds spec >= 30)
- 0 changes to chat:* IPC, Phase 3-B0 StreamEvent, backend
- Doc complete (14 sections)
