# Online Provider Security (Phase 8-D0)

> **purpose**: Define the API key boundary between the agent runtime / model gateway and online model providers.
> **follows**: `model-gateway.md` (Phase 8-D0 architecture).

## 1. Trust boundary

```
 RAGContext (in-process data)
     │
     ▼
 ResearchModelProvider    ←  agent-runtime never imports model code
 ModelGateway
 OnlineModelAdapter       ←  one file per provider, no SDK
 HTTP fetch + AbortController
     │
 Bearer {apiKey}            ←  resolved at fetch time from the Phase 6 secret store
     │
     ▼
 online provider (Xiaomi MIMO, MiniMax)
```

**The agent runtime, the gateway, and every provider adapter NEVER hold an API key in source, log, or memory beyond a single fetch() call.** Keys live in the Phase 6 `model-secret-store.ts` (DPAPI on Windows / Keychain on macOS / libsecret on Linux).

## 2. Secret resolution at fetch time

```
OnlineModelAdapter.chat(req):
   apiKey = secretResolver(providerId)        // 1 lookup, no caching
   response = fetch(url, { Authorization: `Bearer ${apiKey}`, ... })
   apiKey   dropped from local scope after fetch()
```

The resolver is injected at gateway construction. The gateway never re-exposes the key; adapters throw immediately if the resolver returns `null`.

## 3. Source-level guarantees (enforced by `npm run test`)

- `model-gateway-schema.ts` `assertNoSecret` walks only string values (keys are identifiers and can't carry secrets). Forbidden substrings: `'sk-'`, `'apiKey'`, `'secret'`, `'token value'`, `'cipher'`, `'authorization'`, `'Bearer '`, `'providerId/'`.
- Provider adapters' `buildRequest` payloads contain no `Authorization` headers — those are added at `fetch` time only.
- Adapters don't `console.log` or persist any header or body field that could carry a key.

## 4. Threat model

| Threat | Mitigation in Phase 8-D0 |
|--------|--------------------------|
| Key leaks via prompt/log | Secret guard rejects strings containing key material; adapters never embed keys in `ModelRequest` (the schema only carries `messages`/`context`/`taskType`/`tokenBudget`/`temperature`). |
| Key leaks via headers/payload | Headers are constructed in `post()` and only passed to `fetch()` — never to `console.log`/`JSON.stringify`. |
| Compromised provider exposes a chunk citation back | Citations live in `CitationReference` (no `apiKey` field). The provider can echo only what was sent — and we never send secrets. |
| Prompt injection in retrieved content | The gateway's system prompt template explicitly tells the model to answer using ONLY the numbered context. The agent layer (out of Phase 8-D0) adds the prompt-injection boundary; the gateway enforces a deterministic, secret-free payload. |
| Token-budget exhaustion / runaway streaming | `AbortController` on `timeoutMs`; deterministic truncation by `tokenBudget` (the gateway caps `max_tokens` against `MIMO_DEFAULT_MAX_TOKENS_CAP` / `MINIMAX_DEFAULT_MAX_TOKENS_CAP`). |

## 5. Out of scope (future phases)

| Concern | Owner phase |
|---------|------------|
| Per-document trust tagging | future retriever phase |
| LLM-side PII redaction in chunk content | future pipeline phase |
| Persistent request log | future observability phase |
| Circuit breaker / global kill switch | future ops phase |

## 6. References

- `docs/agent/model-gateway.md`
- `src/shared/agent/model-gateway-schema.ts` (secret guard)
- `src/main/services/agent/model-adapter.ts` (OnlineModelAdapter seam)
- `src/main/services/agent/providers/{mimo,minimax}-adapter.ts` (key resolution + fetch)
- `src/main/services/model-provider/model-secret-store.ts` (Phase 6 — reused at construction)