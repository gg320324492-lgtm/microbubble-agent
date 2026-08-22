# Model Provider Architecture (Phase 6-A Audit & Design)

> **purpose**: Establish architecture for future Model Provider integration (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM).
> **scope**: Audit + design only. **No code changes**. No backend / web modifications. No real provider wiring.
> **follows**: Phase 5-E3 (chat interaction frozen). Sits before Phase 6-A implementation.

## 1. Audit: current state

### 1.1 model invocation chain

```
[Renderer chat store]
   +- window.api.chat.startStream({ message, session_id })
        +- [preload] IPC API gateway
             +- [main] main/services/chat/chat-stream.service.ts :: startChatStream()
                  +- authService.getCurrentAccessToken() (Bearer in main only)
                  +- fetch(APP_CONFIG.backendUrl + '/chat/stream', { method: POST, body, headers })
                  +- ReadableStream reader + TextDecoder
                  +- SSE frame parse (data: ...\\n\\n, [DONE])
                  +- webContents.send('chat:stream-chunk', ctx, event)
```

Key fact: the desktop client **never talks to a model API directly**. It talks to `FastAPI /chat/stream` which is the backend's chat endpoint. The backend proxies / orchestrates the model call.

### 1.2 boundary (Desktop -> FastAPI -> Model)

```
Desktop (Electron renderer + main)
    |  HTTPS + Bearer JWT (Phase 1-2)
    v
FastAPI backend (app/api/v1/chat.py :: chat_stream_route)
    |  delegates to v2_agent.chat_stream() (Phase 3-B0)
    v
LLM provider client (current: MiniMax or Anthropic via internal abstraction)
    |  HTTPS + API key
    v
Model API endpoint (cloud or local OpenAI-compatible)
```

Current coupling: backend owns provider selection, key management, request orchestration, response streaming.

### 1.3 token + key boundaries (current)

| concern | storage | scope |
|---------|---------|-------|
| agent JWT (access_token) | main process module variable `currentAccessToken` (Phase 1-2) | per-session in-memory, cleared on refresh fail |
| agent refresh_token | `safeStorage.encryptString` + electron-store `refresh_token_cipher` (Phase 1-2) | per-machine OS keychain (Win DPAPI / macOS Keychain / Linux libsecret) |
| model API key (current backend-internal) | **env var** in `app/config.py` (Phase 3-B0) | server-side, NEVER reaches desktop |

**Phase 6-A introduces**: a *third* kind of credential on the desktop side -- a Model Provider API key (e.g. OpenAI key for BYO mode, Ollama URL, vLLM endpoint). This key MUST be:
- user-supplied (not bundled)
- stored with the same rigor as refresh_token (safeStorage -> OS keychain)
- scoped per provider (one key per provider at most)
- NEVER logged or echoed back to renderer in plaintext

## 2. Design: ModelProvider interface

### 2.1 type contract (Phase 6-A proposed, not yet implemented)

```ts
// shared/model-provider-types.ts (Phase 6-A NEW, frozen after commit)

export type ModelProviderType =
  | 'cloud'         // MiniMax / Qwen / Mimo / OpenAI cloud
  | 'local'         // Ollama / vLLM (self-hosted)
  | 'openai-compatible'  // any OpenAI-compatible HTTP endpoint

export interface ModelConfig {
  providerId: string          // stable id; 'minimax' | 'qwen' | 'mimo' | 'openai' | 'ollama' | 'vllm' | custom-openai
  displayName: string        // human label; 'MiniMax' / 'Local Ollama'
  type: ModelProviderType
  endpoint?: string          // local / openai-compatible only; e.g. 'http://localhost:11434'
  defaultModel: string        // 'minimax-cn' / 'qwen-plus' / 'gpt-4o' etc.
  apiKeyId?: string          // pointer into local SecretStore; never the raw key
  streamingEnabled: boolean  // all 6 providers support SSE / chunked
  maxContextTokens?: number  // hint for chat store chunking (future)
  extra?: Record<string, unknown>  // provider-specific knobs (e.g. vLLM `gpu_layers`)
}

export interface ModelProvider {
  readonly id: string
  readonly type: ModelProviderType
  /** Resolve API key from local SecretStore. NEVER cached; called per-request. */
  resolveApiKey(): Promise<string | null>
  /** Build the upstream request payload (provider-specific). */
  buildRequest(model: string, messages: ChatMsg[], opts: ModelOptions): unknown
  /** Parse a single upstream chunk into a normalized StreamChunk (Phase 5-B frozen). */
  parseChunk(raw: string): StreamChunk | null
  /** Health check (Phase 6-A: provider-specific ping). */
  ping(): Promise<{ ok: boolean; latencyMs?: number; error?: string }>
}
```

### 2.2 registry (Phase 6-A proposed)

```ts
// main/services/model-provider/registry.ts
const REGISTRY: Record<string, () => ModelProvider> = {
  minimax: createMinimaxProvider,
  qwen: createQwenProvider,
  mimo: createMimoProvider,
  openai: createOpenAIProvider,
  ollama: createOllamaProvider,
  vllm: createVlllmProvider,
  'openai-compatible': createOpenAICompatibleProvider
}

export function resolveProvider(type: ModelProviderType, config: ModelConfig): ModelProvider {
  const factory = REGISTRY[config.providerId]
  if (!factory) throw new Error(`Unknown provider: ${config.providerId}`)
  return factory()
}
```

### 2.3 unified interface (3 provider types)

| concern | cloud | local | openai-compatible |
|---------|-------|-------|------------------|
| API style | proprietary | Ollama REST | OpenAI Chat Completions |
| Auth | `Authorization: Bearer <key>` | none (or bearer) | bearer |
| Stream format | vendor-specific (need normalizer) | Ollama NDJSON | OpenAI SSE |
| Endpoint | fixed URL (provider's cloud) | user-provided `endpoint` | user-provided `endpoint` |
| Key source | safeStorage entry `model_<providerId>` | none | safeStorage entry |
| Ping | vendor health endpoint (or first chat) | Ollama `/api/tags` | OpenAI `/v1/models` |
| Local cache | LRU per model (Phase 4-B pattern, no key cache) | n/a | LRU per model |

Phase 6-A unified normalization: every provider parses into the same `StreamChunk` (Phase 3-B0 frozen union + Phase 5-B extension), so chat-stream.service.ts can stay unchanged.

## 3. Secret storage design

### 3.1 reuse Phase 1-2 vault (preferred)

```ts
// main/services/model-provider/secret-store.ts (Phase 6-A NEW)
export function vaultStoreModelApiKey(providerId: string, apiKey: string): void
export function vaultLoadModelApiKey(providerId: string): string | null
export function vaultDeleteModelApiKey(providerId: string): void
```

Backed by existing safeStorage + electron-store (Phase 1-2):
- Win: DPAPI (current user / machine scope)
- macOS: Keychain
- Linux: libsecret / kwallet

**Storage shape**: `electron-store` JSON `{ 'model_<providerId>': base64-cipher }`. One entry per provider.

### 3.2 IPC contract (Phase 6-A NEW)

```ts
// shared/model-provider-ipc.ts (Phase 6-A NEW)
export interface DesktopChatStreamApi {
  configureProvider(config: ModelConfig): Promise<{ ok: true } | { ok: false; error: ... }>
  startProviderStream(req: ChatStreamRequest, config: ModelConfig): Promise<string> // returns streamId
  cancelProviderStream(streamId: string): Promise<{ ok: true } | { ok: false }>
  pingProvider(config: ModelConfig): Promise<{ ok: boolean; latencyMs?: number }>
  listProviders(): Promise<ModelConfig[]>
  deleteProvider(providerId: string): Promise<{ ok: true }>
}
```

This is **parallel to** `chat:start-stream` (Phase 3-A). Both go through the same SSE/IPC pipeline; only the URL + auth headers differ.

## 4. migration plan (current -> Phase 6-A)

| step | change | risk | rollback |
|------|-------|------|----------|
| 1 | introduce `ModelProviderType` enum + frozen contract in `shared/model-provider-types.ts` | none | revert commit |
| 2 | introduce SecretStore wrapper `main/services/model-provider/secret-store.ts` (vault wrap) | low | revert commit |
| 3 | introduce Provider registry skeleton + 1 factory (openai-compatible) - others placeholder | low | revert commit |
| 4 | add IPC channel group `chat:provider-*` + preload types | low | revert commit |
| 5 | add ChatView settings panel (provider + model select + api-key input) - manual config only | med (UX) | keep button disabled |
| 6 | wire `chat-stream.service.ts` to switch URL based on active provider (model vs fastapi) | high | feature flag off |

Steps 1-4 are pure foundation (zero behaviour change). Steps 5-6 are user-facing; feature-flag gated.

## 5. Phase 6-A implementation plan

| task | scope | estimate | deps |
|------|-------|----------|------|
| 6-A.1 shared types (frozen) | shared/model-provider-types.ts, shared/model-provider-ipc.ts | 0.5d | - |
| 6-A.2 SecretStore | main/services/model-provider/secret-store.ts + tests | 0.5d | 6-A.1 |
| 6-A.3 Provider registry skeleton + openai-compatible factory | main/services/model-provider/* + tests | 1d | 6-A.1, 6-A.2 |
| 6-A.4 IPC + preload types | chat:provider-* channels + preload | 0.5d | 6-A.1 |
| 6-A.5 Settings UI (manual) | renderer views/settings + ProviderPanel.vue + tests | 1.5d | 6-A.1 |
| 6-A.6 chat-stream wiring (feature-flagged) | chat-stream.service.ts route switch | 1d | all above |
| 6-A.7 docs update + tests (end-to-end with Ollama local) | chat-knowledge-hotpath.md etc. | 0.5d | all above |

Total: 5.5d. Phase 6-A final commit includes documentation + Ollama e2e test.

## 6. risk analysis

| risk | severity | mitigation |
|------|-----------|------------|
| API key leakage (electron-store plaintext) | high | safeStorage wrap (Phase 1-2 vault pattern reused); never log key |
| API key leakage (renderer log) | high | preload return shape excludes key field; only `ok` + display name |
| provider URL misconfig (local Ollama wrong host) | med | `pingProvider` on save; reject on connect fail |
| cloud API rate limit / quota | low | Phase 6-B: telemetry + circuit breaker |
| model hallucination risk | none (backend handles with system prompt) | - |
| SSE parsing mismatch across providers | med | each provider factory has its own `parseChunk`; Phase 5-B StreamChunk union frozen |
| local Ollama server unavailable | low | fallback to fastapi default; UI shows "model offline" badge |
| token expiry mid-stream (Phase 6-A provider key) | low | per-request `resolveApiKey` -> re-decrypt each call |
| key rotation by user | low | secret-store `delete + store` pattern |
| multi-window / multi-store | low (Phase 6+) | SharedWorker sync (reserve) |

## 7. Phase 6-A + 6-B+ roadmap

| phase | scope |
|-------|-------|
| 6-A (this) | Audit + design doc + frozen contract only |
| 6-A impl | Types + SecretStore + 1 provider factory (openai-compatible) + IPC + Settings UI (manual config) - feature-flagged |
| 6-B | All 6 provider factories (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM) wired |
| 6-C | Telemetry + circuit breaker + multi-window |
| 6-D | Offline mode + IndexedDB persistent cache for model responses |

## 8. references

- `desktop/src/main/services/chat/chat-stream.service.ts` - current SSE pipeline (Phase 6-A target)
- `desktop/src/main/services/api/api.service.ts` - API gateway + single-flight refresh
- `desktop/src/main/services/auth.service.ts` - login + token lifecycle
- `desktop/src/main/services/token-vault.ts` - safeStorage pattern (Phase 6-A reuse)
- `desktop/src/renderer/src/services/knowledge.service.ts` - Phase 4-B cache + service pattern
- `docs/desktop-conversion/security.md` - token storage principles (apply to model keys)
- `docs/desktop-conversion/auth-api-contract.md` - Phase 1-2 auth contract
- `docs/desktop-conversion/chat-stream-contract.md` - Phase 3-B0 SSE schema (consumed by Phase 6-A providers)

## Status (2026-08-22 Phase 6-A audit)

- Audit done (current state mapped)
- 3-tier boundary (Desktop -> FastAPI -> Model) confirmed
- Token + key boundaries documented (3 credential types)
- 7 provider types frozen (MiniMax / Qwen / Mimo / OpenAI / Ollama / vLLM / openai-compatible)
- SecretStore design reused (safeStorage)
- IPC + migration plan locked (6 steps)
- 5.5d implementation plan
- Risk matrix (high-severity items mitigated)
- Zero code changes (audit + design only)

---

Maintenance rules (Phase 6-A+):
- 6 provider types frozen; new provider requires Phase 6-A+ bump
- SecretStore API frozen (vaultStoreModelApiKey / vaultLoadModelApiKey); never expose raw key
- ModelConfig.providerId is stable id; displayName is human label
- chat-stream.service.ts stays unchanged; Phase 6-A wraps with provider switch
- IPC channel group `chat:provider-*` parallel to `chat:*`; never pollute Phase 3-A chat flow
