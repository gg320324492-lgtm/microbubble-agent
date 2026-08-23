# Model Gateway (Phase 8-D0)

> **purpose**: Define the agent → online-model boundary. RAGContext in, ModelResponse out.
> **follows**: `rag-context-builder.md` (Phase 8-C3) + `citation-pipeline.md` (Phase 8-C1).
> **Phase 8-D0 scope**: thin, deterministic, online-only. No local model. Reuses Phase 6 registry / health / budget seams at construction (out of scope here) and adds the agent-facing request/response shape.

## 1. Architecture

```
 RAGContext  (Phase 8-C3)
     │
     ▼
 ResearchModelProvider   ← the only seam the agent runtime imports
     │
     ▼
 ModelGateway
     │  buildRequest(RAGContext, options)            -> ModelRequest
     │  pickAdapter(taskType)                           (task-aware, preferred-order)
     │  call adapter.chat() OR iterate adapter.stream()
     │  surface ModelResponse / StreamChunk
     ▼
 OnlineModelAdapter
     │  Xiaomi MIMO adapter (mimo-adapter.ts)
     │  MiniMax adapter   (minimax-adapter.ts)
     │  any future adapter implementing the same seam
     ▼
 HTTP (fetch) — Phase 6 model-secret-store.ts supplies API keys at construction
```

## 2. Modules (all NEW in Phase 8-D0)

| Module | File |
|--------|------|
| Contracts | `src/shared/agent/model-gateway-schema.ts` (`ModelRequest` / `ModelResponse` / `StreamChunk` / `TaskType` + secret guard) |
| Adapter seam | `src/main/services/agent/model-adapter.ts` (`OnlineModelAdapter` interface + helpers) |
| Xiaomi MIMO | `src/main/services/agent/providers/mimo-adapter.ts` |
| MiniMax | `src/main/services/agent/providers/minimax-adapter.ts` |
| SSE helper | `src/main/services/agent/providers/sse-stream.ts` |
| Gateway | `src/main/services/agent/model-gateway.ts` |
| Agent seam | `src/main/services/agent/research-model-provider.ts` |

## 3. Pipeline (ModelGateway.generateAnswer)

```
 ragContext + options
     │
     ▼ buildRequest
     │
     │  - inject system prompt template with {context} + {question}
     │  - build user message from ragContext.query
     │  - set tokenBudget, temperature, taskType
     │
     ▼ pickAdapter (task-aware)
     │
     │  preferredOrder ids → first adapter whose capabilities().tasks contains taskType
     │  fallback: any adapter with matching task
     │
     ▼ adapter.chat(modelRequest)
     │
     │  secretResolver(providerId) -> apiKey  (Phase 6 secret store injected)
     │  POST {baseUrl}/chat/completions   Authorization: Bearer {apiKey}
     │  AbortController for timeout (default 30s)
     │  response -> ModelResponse { content, usage, provider, latencyMs }
     │
     ▼ fallbackOnError -> retry with next adapter
     │
     ▼ return ModelResponse
```

`streamAnswer` and `collectStream` follow the same pipeline with SSE chunked output.

## 4. Provider abstraction

`OnlineModelAdapter` is the single seam:
```ts
interface OnlineModelAdapter {
  readonly id: string
  chat(req): Promise<ModelResponse>
  stream(req): AsyncIterable<StreamChunk>
  healthCheck(): Promise<HealthCheck>
  capabilities(): AdapterCapabilities
}
```

Adding a new online provider is **one file**: implement the interface, register with the gateway. No SDK imports, no local model code. The Phase 6 `registry.ts` / `health-tracker.ts` / `budget-manager.ts` stay untouched; the gateway calls them at construction (wiring) only.

## 5. Fallback strategy

- **No SDK** (no `@anthropic-ai/sdk`, `openai`, etc.). Adapters use `fetch` with credentials from the Phase 6 `model-secret-store.ts`.
- `fallbackOnError` (default `true`): if the preferred adapter throws, try the next adapter that supports the task. Surface the original error when all adapters fail.
- `timeoutMs` (default 30s): `AbortController` cancels the request.

## 6. Determinism

- `buildRequest` produces the same `ModelRequest` for the same `RAGContext` + `options`.
- Provider selection is deterministic: `preferredOrder` first, then any task-capable adapter, in registration order.
- Latency and `usage` come from the provider response; only `latencyMs = Date.now() - start` is non-deterministic — recorded but not used for ranking.

## 7. References

- `docs/agent/online-provider-security.md` (Phase 8-D0 secret / key boundary)
- `src/shared/agent/model-gateway-schema.ts`
- `src/main/services/agent/{model-adapter,model-gateway,research-model-provider}.ts`
- `src/main/services/agent/providers/{mimo-adapter,minimax-adapter,sse-stream}.ts`
- `src/shared/knowledge/context-schema.ts` (consumed)
- `src/shared/model/provider-types.ts` + `src/main/services/model-provider/registry.ts` (reused at construction)