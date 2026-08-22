# Model Capability Intelligence Foundation (Phase 6-C1)

> **purpose**: Add a research-domain capability layer to the model provider stack — for chat-header chips now, and for the future Agent Router (Phase 6-C2). Distinct from Phase 6-A1 ModelCapability (which describes chat API surface: streaming / tools / vision). ResearchCapability describes WHAT the model is good at in our research domain.
> **follows**: Phase 6-A1 (foundation, f7f197447), Phase 6-A2 (SecretStore + IPC, 5a17cab97), Phase 6-A3 (Provider Factory + Registry, adda703e1), Phase 6-A4 (Settings + ConfigStore, 8ecb303f2), Phase 6-A5 (Runtime Routing, ac1e4a3b4), Phase 6-A6 (E2E Runtime, 4b2181b99), Phase 6-B (Active Model Integration, d417f8968).

## 1. Scope (Phase 6-C1 frozen)

- `ResearchCapability` enum (10 tags): chat / coding / math / matlab / python / cfd / literature / paper-writing / image-analysis / data-analysis
- `ModelResearchProfile` type: `{ providerId, model, capabilities, maxContext?, strengths?, limitations? }`
- `isValidModelResearchProfile` shape validator
- `assertProfileSafe` defensive runtime guard
- `ProviderRegistryMeta.researchProfile?` — backward-compatible optional field
- `ProviderConfig.researchProfile?` (Phase 6-A4 ConfigStore) — backward-compatible optional field
- `capability-resolver.ts` (main process) — `resolveModelCapability`, `matchTaskCapability`, `hasAllCapabilities`, `hasAnyCapability`
- ModelSelector.vue extended — research chips per provider + selected row
- 43 unit tests (>= 30 spec requirement)
- **NO** changes to backend, Phase 3-B0 StreamEvent, chat:* IPC; **NO** apiKey leakage; **NO** breaking changes to legacy providers (researchProfile is optional)

## 2. Files (Phase 6-C1)

```
desktop/src/shared/model/
  - research-capability.ts                  (NEW)  ResearchCapability enum + ModelResearchProfile + validators

desktop/src/main/services/model-provider/
  - capability-resolver.ts                  (NEW)  resolveModelCapability / matchTaskCapability / hasAllCapabilities / hasAnyCapability
  - registry.ts                             (MODIFY) +researchProfile? on ProviderRegistryMeta
  - provider-config-store.ts               (MODIFY) +researchProfile? on ProviderConfig + saveConfig/getConfig passthrough

desktop/src/shared/
  - preload-api.ts                          (MODIFY) +ResearchCapability + ModelResearchProfile + ModelProviderConfig.researchProfile

desktop/src/renderer/src/
  - components/chat/ModelSelector.vue      (MODIFY) +research capability chips per provider row + selected row

desktop/tests/unit/
  - model-capability.test.ts                (NEW)  43 cases

desktop/docs/desktop-conversion/
  - model-capability-system.md              (NEW)  this file
```

## 3. Capability model

### Two distinct capability types

| Type | Phase | Purpose | Lives in |
|------|-------|---------|----------|
| `ModelCapability` (Phase 6-A1) | chat API surface | 'streaming' \| 'tools' \| 'vision' \| 'function-calling' \| 'json-mode' | shared/model/model-types |
| `ResearchCapability` (Phase 6-C1) | research domain | 10 tags (see below) | shared/model/research-capability |

Phase 6-C1 strict: the two types do NOT overlap. `ModelCapability.vision` (API surface) is distinct from `ResearchCapability.image-analysis` (research task).

### ResearchCapability taxonomy

```
'chat'             // generic conversation
'coding'           // code generation / debugging
'math'             // mathematical reasoning
'matlab'           // MATLAB-specific code
'python'           // Python-specific code
'cfd'              // computational fluid dynamics
'literature'       // literature review / paper digest
'paper-writing'    // academic prose / SCI paper draft
'image-analysis'   // vision for scientific figures
'data-analysis'    // statistics / plotting / pandas
```

`researchCapabilityLabel(cap)` / `researchCapabilityGlyph(cap)` are stable UI helpers. Renaming any tag is a Phase bump.

### ModelResearchProfile

```ts
interface ModelResearchProfile {
  providerId: string                              // matches registry
  model: string                                  // vendor model name
  capabilities: ResearchCapability[]            // tags
  maxContext?: number                            // tokens
  strengths?: string[]                           // human-readable
  limitations?: string[]
}
```

Phase 6-C1 strict: profile NEVER contains apiKey / token / cipher. The shape validator (`isValidModelResearchProfile`) rejects payloads with `sk-` / `apiKey` / `cipher` substrings.

## 4. Research profile

Two storage paths for a profile:

```
1. ProviderConfigStore (Phase 6-A4) — user-configurable per-provider
   SaveConfig({ ..., researchProfile: { ... } })

2. ProviderRegistryMeta (Phase 6-A3) — hardcoded by factory at registration
   registerProvider(id, factory, { ..., researchProfile: { ... } })

3. unknown — no metadata available
   { providerId, model, capabilities: ['chat'] }
```

Resolution order (Phase 6-C1 resolver):

```
resolveModelCapability(providerId, model?):
  1. ProviderConfigStore researchProfile  -> source: 'config'
  2. ProviderRegistryMeta researchProfile -> source: 'registry'
  3. unknown fallback                       -> source: 'unknown', capabilities: ['chat']
```

Backwards compat: legacy providers (Phase 6-A3 without `researchProfile`) fall through to step 3 and still resolve — capability display shows `['chat']`.

## 5. Capability resolver

`desktop/src/main/services/model-provider/capability-resolver.ts`:

```ts
interface CapabilityMatch {
  providerId: string
  model: string
  source: 'config' | 'registry' | 'unknown'
  profile: ModelResearchProfile
}

resolveModelCapability(providerId, model?) -> CapabilityMatch | null
matchTaskCapability(taskCaps)                -> CapabilityMatch[]   (ranked)
hasAllCapabilities(match, required)          -> boolean
hasAnyCapability(match, required)            -> boolean
```

`matchTaskCapability(['paper-writing'])`:
1. Filter valid caps (drop unknown tags)
2. For each registered provider, compute overlap count
3. Sort by overlap desc (best match first)
4. Return ALL providers (zero-overlap included so caller can fall back)

Phase 6-C2 (Agent Router) will consume `matchTaskCapability` to pick the best provider+model for a given task.

## 6. UI contract

### ModelSelector.vue (chat-header widget)

Provider row (Phase 6-C1):
```
OpenAI           gpt-4o-mini    🔑  📚 literature  📝 paper
Ollama           qwen3:8b       🔑  🌊 cfd
```

Selected row capabilities section:
```
Capabilities
  [streaming] [tools] [vision]   <- ModelCapability chips (Phase 6-A1)
  📚 Literature  📝 Paper         <- ResearchCapability chips (Phase 6-C1)
```

If a provider has no `researchProfile`, no research chips appear (clean fallback).

## 7. Future Agent Router

Phase 6-C2 sketch (NOT shipped in Phase 6-C1):

```ts
// future Agent Router picks provider+model per task
function pickModelForTask(task: { required: ResearchCapability[] }) {
  const ranked = matchTaskCapability(task.required)
  // Phase 6-C2 logic: filter by online status, hasKey, maxContext budget
  // For now: return top-1
  return ranked[0] ?? null
}
```

Phase 6-C1 lays the foundation (taxonomy, profile, resolver). Phase 6-C2 wires routing + budget + online status + retry.

## 8. Test coverage (43 / 43 PASSED, exceeds spec >= 30)

| describe | cases |
|----------|-------|
| isValidResearchCapability (12) | 10 known + 1 unknown + 3 non-string |
| label / glyph stability (5) | chat / cfd / paper-writing / literature glyph / matlab glyph |
| isValidModelResearchProfile (8) | minimal / full / empty id / empty model / non-array caps / unknown tag / negative maxContext / secret-like field |
| resolveModelCapability (5) | invalid id / config path / registry path / unknown fallback / config wins over registry |
| matchTaskCapability (3) | ranked by overlap / all returned / invalid tag filtered |
| hasAllCapabilities / hasAnyCapability (4) | all / missing / any one / none |
| Security (3) | assertProfileSafe sk- / apiKey / clean |
| Backward compat (3) | legacy provider / ConfigStore without profile / profile field absence |
| **Total** | **43** |

## 9. Forbidden patterns (permanent)

- ❌ Add capability tags to `ModelCapability` enum (Phase 6-A1). (Reason: distinct concern — chat API surface vs research domain.)
- ❌ Auto-rename a `ResearchCapability` tag without a Phase bump. (Reason: UI labels and resolver depend on stable tag names.)
- ❌ Include `apiKey` field in any profile shape. (Reason: validator refuses + assertProfileSafe throws.)
- ❌ Make `researchProfile` required. (Reason: legacy providers must keep working.)
- ❌ Hardcode provider capability lists in the resolver. (Reason: provider config + registry are the single source of truth.)
- ❌ Bypass `assertProfileSafe` when reading profiles from IPC. (Reason: defense-in-depth.)
- ❌ Read apiKey from `ConfigStore` or `Registry` in the resolver. (Reason: resolver is capability-only; apiKey access is the runtime router's job.)

## 10. Phase 6-C2 plan

- Agent Router: pick best provider+model per task (using `matchTaskCapability` + hasKey + connectionStatus)
- Capability gating: refuse requests with capabilities the active model lacks (Phase 6-B's `CapabilityGate`)
- Live e2e: from desktop chat, type "summarize this paper" → Agent Router picks the literature-capable model automatically
- Cost / latency budget: pick model that fits user's budget + latency requirement

## 11. Phase 6 Roadmap

| phase | scope | status |
|-------|-------|--------|
| 6-A audit | doc-only design | done (9fbd8d589) |
| 6-A1 foundation | types + interface + normalizer + tests + doc | done (f7f197447) |
| 6-A2 SecretStore + IPC | safeStorage vault + 4 IPC channels + 44 tests | done (5a17cab97) |
| 6-A3 Provider Factory + Registry | registry + openai-compatible + ollama + 66 tests | done (adda703e1) |
| 6-A4 Model Settings + Provider Management | ConfigStore + 4 IPC + Pinia store + UI + 58 tests | done (8ecb303f2) |
| 6-A5 Model Runtime Integration | ActiveProviderStore + RuntimeRouter + feature flag + 25 tests | done (ac1e4a3b4) |
| 6-A6 Model Provider Runtime E2E | real HTTP fetch + SSE/NDJSON + mock server + 33 tests | done (4b2181b99) |
| 6-B Active Model Integration | ConversationModelContext + selector + UI + 26 tests | done (d417f8968) |
| **6-C1 Model Capability Foundation** | ResearchCapability + ModelResearchProfile + resolver + 43 tests | **this commit** |
| 6-C2 Agent Router (capability-driven selection) | follow | next |
| 6-D Live e2e (desktop chat with provider runtime) | follow | later |

## 12. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, 9fbd8d589)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2)
- `docs/desktop-conversion/provider-factory.md` (Phase 6-A3)
- `docs/desktop-conversion/model-settings.md` (Phase 6-A4)
- `docs/desktop-conversion/model-runtime-routing.md` (Phase 6-A5)
- `docs/desktop-conversion/model-provider-runtime-e2e.md` (Phase 6-A6)
- `docs/desktop-conversion/active-model-integration.md` (Phase 6-B)

## Status (2026-08-22 Phase 6-C1)

- `ResearchCapability` enum (10 tags) + label/glyph helpers
- `ModelResearchProfile` + `isValidModelResearchProfile` + `assertProfileSafe`
- `ProviderRegistryMeta.researchProfile?` + `ProviderConfig.researchProfile?` (backward-compatible)
- `capability-resolver.ts` (main process): 4 functions
- ModelSelector.vue extended with research capability chips
- 43 unit tests PASSED (exceeds spec >= 30)
- 0 changes to chat:* IPC, Phase 3-B0 StreamEvent, backend, legacy chat fallback
- Doc complete (12 sections)
