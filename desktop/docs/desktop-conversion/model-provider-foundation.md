# Model Provider Foundation (Phase 6-A1)

> **purpose**: Establish the model-provider abstraction layer. No real provider connections (no MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM).
> **follows**: Phase 6-A audit (9fbd8d589). Pre-implementation foundation; vendor SDK wiring lives in Phase 6-A2+.

## 1. Scope (Phase 6-A1 frozen)

- shared types: `ModelConfig`, `ProviderType`, `ModelCapability`, `ProviderCapabilities`, `CanonicalMessage`, `CanonicalRequest`, `StreamEvent`, `ModelProvider`
- vendor-agnostic factory interface (Phase 6-A1: 1 openai-compatible skeleton + MockProvider for tests)
- stream normalizer: vendor chunks -> Phase 3-B0 frozen `StreamEvent`
- 28 unit tests (>= 20 spec requirement)
- documentation
- **NO** real provider connections
- **NO** secret-store wiring (Phase 6-A2)

## 2. Type Design (frozen contract)

### 2.1 `ModelProviderType` (3 categories)

```ts
type ModelProviderType =
  | 'cloud'               // MiniMax / Qwen / Mimo / OpenAI cloud
  | 'local'               // Ollama / vLLM (self-hosted)
  | 'openai-compatible'   // any OpenAI-compatible HTTP endpoint
```

### 2.2 `ModelCapability`

```ts
type ModelCapability =
  | 'streaming'
  | 'tools'
  | 'vision'
  | 'function-calling'
  | 'json-mode'
```

### 2.3 `ModelConfig`

```ts
interface ModelConfig {
  providerId: string       // stable id (Phase 6-A: 'minimax' | 'openai-compatible' etc.)
  displayName: string     // human label
  type: ModelProviderType
  defaultModel: string     // vendor model name
  endpoint?: string        // required for 'local' / 'openai-compatible'
  capabilities: ModelCapability[]
  extra?: Record<string, unknown>
}
```

### 2.4 `CanonicalMessage` / `CanonicalRequest`

```ts
interface CanonicalMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  name?: string
  tool_call_id?: string
}

interface CanonicalRequest {
  model: string
  messages: CanonicalMessage[]
  temperature?: number
  max_tokens?: number
  stop?: string[]
  stream: boolean
}
```

## 3. `ModelProvider` interface (frozen)

```ts
interface ModelProvider {
  readonly id: string
  readonly type: ModelProviderType
  readonly capabilities: ProviderCapabilities

  buildRequest(req: CanonicalRequest, cfg: ModelConfig): unknown
  parseChunk(raw: string): StreamEvent | null
  ping(cfg: ModelConfig): Promise<{ ok: boolean; latencyMs?: number; error?: string }>
}
```

Phase 6-A1 ships 1 factory (openai-compatible skeleton) + MockProvider for tests.

## 4. Provider boundary (Phase 6-A1)

```
[Renderer chat store]
   ↓ window.api.chat.startStream({ message, session_id, ... })
[preload] IPC API gateway
   ↓
[main] main/services/chat/chat-stream.service.ts
   ↓ Phase 6-A2: route switch (fastapi vs provider)
[main] main/services/model-provider/{factory, stream-normalizer, secret-store}
   ↓ Phase 6-A2: vault provider key
[Model API endpoint]
```

Phase 6-A1: only `stream-normalizer` + `mock-provider` skeleton shipped. No `factory` wired, no `secret-store`.

## 5. Stream normalization (Phase 3-B0 frozen output)

`stream-normalizer.ts` accepts vendor chunks and emits Phase 3-B0 `StreamEvent` (no modification).

Supported input shapes:
1. OpenAI-compatible SSE: `data: {json}\n\n`
2. JSONL: each line is a JSON object
3. Plain text chunk (treated as `text_delta`)
4. SSE terminator: `[DONE]`
5. Error envelope: `{ error: { message, code? } }`
6. Explicit `type` field: `thinking` / `citation` / `rich_block` / `tool_use` / `tool_result` / `done` / `error`

Functions:
- `normalizeStreamChunk(raw: string): StreamEvent | null`
- `parseJsonEvent(payload: string): StreamEvent | null`
- `normalizeStream(rawStream: string): StreamEvent[]`
- `isKnownStreamEvent(ev): ev is StreamEvent`
- `extractToolCallArgs(raw): Record<string, unknown>` (helper, handles string-JSON + object)

Phase 6-A1 strict: does NOT modify Phase 3-B0 `StreamEvent` shape. Vendor-specific fields stay inside vendor factory's `parseChunk`.

## 6. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| **6-A1 foundation** | types + interface + normalizer + tests + doc | **this commit** |
| 6-A2 SecretStore | main/services/model-provider/secret-store.ts + IPC | next |
| 6-A3 Registry | vendor factories (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM) | follow |
| 6-A4 Settings UI | renderer/views/settings + ProviderPanel.vue | follow |
| 6-A5 Wiring | chat-stream.service.ts route switch (feature-flagged) | follow |
| 6-A6 E2E | Ollama local e2e + docs | follow |

## 7. Test coverage (28 / 28 PASSED, exceeds spec >= 20)

`tests/unit/model-provider-foundation.test.ts`:

| describe | cases |
|----------|-------|
| ModelConfig validation | 5 |
| Provider id + capabilities | 3 |
| CanonicalMessage conversion | 5 |
| MockProvider + replayChunks | 2 |
| Stream normalization (SSE / JSONL / plain / error / [DONE] / finish_reason / etc.) | 8 |
| parseJsonEvent edge cases + multi-line + isKnownStreamEvent | 5 |
| **Total** | **28** |

## 8. Files (Phase 6-A1)

```
desktop/src/shared/model/
  - model-types.ts         (ModelProviderType, ModelCapability, ModelConfig + isValidModelConfig)
  - provider-types.ts      (CanonicalMessage, CanonicalRequest, StreamEvent + ProviderCapabilities + isValidProviderId)
  - canonical-message.ts   (toCanonicalMessage / toCanonicalMessages / fromCanonicalMessage)

desktop/src/main/services/model-provider/
  - stream-normalizer.ts   (normalizeStreamChunk, parseJsonEvent, normalizeStream, isKnownStreamEvent)
  - mock-provider.ts       (Phase 6-A1 test mock implementing ModelProvider)

desktop/tests/unit/
  - model-provider-foundation.test.ts (28 cases)

desktop/docs/desktop-conversion/
  - model-provider-architecture.md (Phase 6-A audit doc)
  - model-provider-foundation.md (this file)
```

## 9. Maintenance rules (Phase 6-A1 frozen)

- ModelProviderType / ModelCapability / ModelConfig / CanonicalMessage / CanonicalRequest / StreamEvent / ModelProvider **are frozen**. Any change requires a new Phase bump (6-A2, 6-B, ...).
- `stream-normalizer.ts` MUST NOT modify Phase 3-B0 `StreamEventType` union; only normalize into existing types.
- Vendor-specific fields (e.g. proprietary retry codes, custom reasoning schemas) stay inside the vendor factory's `parseChunk`, not in the normalizer.
- MockProvider is test-only; never imported by production code.
- No real vendor SDK imports in this Phase; Phase 6-A3 wires them.

## 10. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589) - design rationale, risk matrix, roadmap
- `docs/desktop-conversion/security.md` - token storage principles (apply to model keys in Phase 6-A2)
- `docs/desktop-conversion/chat-stream-contract.md` - Phase 3-B0 SSE schema (consumed unchanged)

## Status (2026-08-22 Phase 6-A1)

- 3 shared types files (frozen contract)
- 1 normalizer file (vendor -> StreamEvent)
- 1 mock-provider (test-only)
- 28 unit tests PASSED
- Doc complete (10 sections)
- No real provider connections
- No secret-store wiring (Phase 6-A2)
