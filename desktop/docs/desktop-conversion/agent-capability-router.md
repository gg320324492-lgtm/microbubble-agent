# Agent Capability Router (Phase 6-C2)

> **purpose**: Capability-driven model selection. Given a research task descriptor, the router picks the best provider+model that satisfies required capabilities (with an API key stored), falling back to the user's active provider when no candidate matches.
> **follows**: Phase 6-A1~A6, Phase 6-B (Active Model Integration, d417f8968), Phase 6-C1 (Model Capability Foundation, 33ce1eeb5).

## 1. Scope (Phase 6-C2 frozen)

- `ResearchTaskType` enum (9 task types): literature-review / paper-writing / coding / matlab / python-analysis / cfd-analysis / image-analysis / experiment-design / data-analysis
- `ResearchTaskProfile` type: `{ taskType, requiredCapabilities, optionalCapabilities?, priority? }`
- `BUILT_IN_TASK_PROFILES` — canonical mapping taskType → required caps (single source of truth)
- `resolveTaskProfile(taskType)` — lookup helper
- `routeResearchTask(profile)` — main router (capability-match → active-fallback → null)
- `routeResearchTaskExtended(profile)` — extended outcome with route label
- 49 unit tests (>= 30 spec requirement)
- **NO** changes to backend, Phase 3-B0 StreamEvent, chat:* IPC; **NO** apiKey leakage; **NO** legacy chat fallback broken

## 2. Files (Phase 6-C2)

```
desktop/src/shared/model/
  - research-task.ts                       (NEW)  ResearchTaskType + ResearchTaskProfile + BUILT_IN_TASK_PROFILES

desktop/src/main/services/model-provider/
  - capability-router.ts                   (NEW)  routeResearchTask + routeResearchTaskExtended

desktop/tests/unit/
  - capability-router.test.ts              (NEW)  49 cases

desktop/docs/desktop-conversion/
  - agent-capability-router.md             (NEW)  this file
```

## 3. Research Task Model

### ResearchTaskType taxonomy (9 task types)

| Type | Required Capabilities | Optional | Use case |
|------|----------------------|----------|----------|
| `literature-review` | literature | paper-writing | Paper digest + outline |
| `paper-writing` | paper-writing | literature | SCI paper draft |
| `coding` | coding | python | General code generation |
| `matlab` | matlab | math | MATLAB-specific code |
| `python-analysis` | python, data-analysis | math | Data exploration |
| `cfd-analysis` | cfd | math, python | CFD simulation |
| `image-analysis` | image-analysis | — | Figure analysis |
| `experiment-design` | coding | data-analysis, math | Lab protocol |
| `data-analysis` | data-analysis | python, math | Stats / plotting |

### ResearchTaskProfile

```ts
interface ResearchTaskProfile {
  taskType: ResearchTaskType
  requiredCapabilities: ResearchCapability[]  // ALL must be present
  optionalCapabilities?: ResearchCapability[] // boost score
  priority?: number  // 0-10; default 5
}
```

`isValidResearchTaskProfile` rejects payloads with unknown taskType, unknown capabilities, out-of-range priority, or apiKey/cipher substrings.

## 4. Router decision tree

```
routeResearchTask(profile):
  1. Validate profile (defensive; null -> fallback to coding)
  2. List ALL registered providers (Phase 6-A3 registry)
  3. Resolve CapabilityMatch per provider (Phase 6-C1)
  4. Filter: provider MUST have keyExists(providerId)
  5. Filter: provider MUST have ALL requiredCapabilities
  6. Rank by: requiredScore * 10 + optionalScore + priority/10
     Tie-breaker: alphabetical providerId for determinism
  7. If best match -> RouterDecision(source='capability-match')
  8. Else if active provider has key -> RouterDecision(source='active-provider')
  9. Else -> null (caller decides legacy / error)
```

The router never throws on empty registry — returns null.

## 5. RouterDecision shape

```ts
interface RouterDecision {
  providerId: string
  model: string
  profile: ModelResearchProfile
  source: 'capability-match' | 'active-provider' | 'no-match'
  reason: string  // human-readable; NEVER contains apiKey
}
```

`assertProfileSafe(profile)` is called on every decision — throws if profile leaks sk-/apiKey/cipher (defense in depth).

## 6. Route decision precedence

```
┌──────────────────────────────────────┐
│ routeResearchTask(profile)          │
└──────────────┬───────────────────────┘
               │
               ▼
   ┌─────────────────────────────────┐
   │ capability-match                 │ <-- best with all required caps + key
   │ (Phase 6-C1 + Phase 6-A2 check) │
   └──────────────┬──────────────────┘
                  │ no match
                  ▼
   ┌─────────────────────────────────┐
   │ active-provider                  │ <-- user's setActive fallback
   │ (Phase 6-A5)                     │
   └──────────────┬──────────────────┘
                  │ no active
                  ▼
   ┌─────────────────────────────────┐
   │ null (caller: legacy / error)    │
   └─────────────────────────────────┘
```

## 7. Security boundary (Phase 6-C2 strict)

- **apiKey NEVER** enters RouterDecision (shape has no key field)
- **reason string** NEVER contains apiKey (test enforces via grep)
- **assertProfileSafe** runs on every decision (defense in depth)
- **keyExists(providerId) check** ensures the picked provider has stored key (not just has capability)
- Provider without stored key is **filtered out** of candidates (security boundary from Phase 6-A2)

## 8. Backward compatibility

| Change | Compatibility |
|--------|---------------|
| New shared type `ResearchTaskProfile` | Old `ConversationModelContext` continues to work; router is opt-in. |
| `BUILT_IN_TASK_PROFILES` | New constant; doesn't affect existing `matchTaskCapability`. |
| `routeResearchTask` | New; not called by legacy chat flow. Old `routeChatRequest` unchanged. |
| `routeResearchTaskExtended` | New; convenience for callers that want route label. |
| Phase 6-A/B/C1 tests | All pass unchanged. |

## 9. Test coverage (49 / 49 PASSED, exceeds spec >= 30)

| describe | cases |
|----------|-------|
| isValidResearchTaskType (12) | 9 known + unknown + 2 non-string |
| researchTaskLabel stability (3) | literature-review / python-analysis / paper-writing |
| isValidResearchTaskProfile (8) | minimal / full / unknown taskType / empty required / non-array / unknown cap / priority out of range / secret field |
| BUILT_IN_TASK_PROFILES completeness (9) | one per task type |
| resolveTaskProfile (3) | python / matlab / cfd |
| routeResearchTask — capability-match (4) | paper / coding / cfd / no-key filter |
| routeResearchTask — active-fallback (1) | no match -> active |
| routeResearchTask — no-route (2) | empty registry / active without key |
| routeResearchTask — invalid profile (1) | null -> coding fallback |
| routeResearchTaskExtended (4) | task-routed / active-fallback / no-route / invalid |
| Security (3) | reason clean / shape clean / no-throw on invalid |
| **Total** | **49** |

## 10. Forbidden patterns (permanent)

- ❌ Throw on empty registry. (Reason: caller decides legacy fallback path.)
- ❌ Return a provider without verifying `keyExists`. (Reason: security boundary.)
- ❌ Include apiKey in RouterDecision shape. (Reason: shape definition has no key field.)
- ❌ Mutate `BUILT_IN_TASK_PROFILES` at runtime. (Reason: `Object.freeze()` enforces immutability.)
- ❌ Bypass `assertProfileSafe`. (Reason: defense in depth.)
- ❌ Add a route that picks a provider without all required capabilities. (Reason: `hasAllCapabilities` is the contract.)
- ❌ Couple router to a specific chat-store or session. (Reason: router is pure; caller wires session).
- ❌ Replace `routeChatRequest` (Phase 6-A5). (Reason: legacy flow stays intact.)

## 11. Phase 6-C3 / 6-D plan

Phase 6-C3 (next):

- Chat header UI button: "Pick by task" → user picks taskType → router decision → selected
- ConversationModelContext gain `taskProfile?` field for per-task binding
- Settings UI shows router suggestions

Phase 6-D (later):

- Cost / latency budget integration (skip models above user's monthly budget)
- Online status check before routing (skip offline providers)
- Retry policy: if capability-matched provider fails at runtime, retry with next-best

## 12. Phase 6 Roadmap

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
| 6-C1 Model Capability Foundation | ResearchCapability + ModelResearchProfile + resolver + 43 tests | done (33ce1eeb5) |
| **6-C2 Agent Capability Router** | ResearchTaskProfile + BUILT_IN_TASK_PROFILES + routeResearchTask + 49 tests | **this commit** |
| 6-C3 Chat header "pick by task" UI | follow | next |
| 6-D Live e2e + budget + retry | follow | later |

## 13. References

- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit)
- `docs/desktop-conversion/model-provider-foundation.md` (Phase 6-A1)
- `docs/desktop-conversion/model-secret-store.md` (Phase 6-A2)
- `docs/desktop-conversion/provider-factory.md` (Phase 6-A3)
- `docs/desktop-conversion/model-settings.md` (Phase 6-A4)
- `docs/desktop-conversion/model-runtime-routing.md` (Phase 6-A5)
- `docs/desktop-conversion/model-provider-runtime-e2e.md` (Phase 6-A6)
- `docs/desktop-conversion/active-model-integration.md` (Phase 6-B)
- `docs/desktop-conversion/model-capability-system.md` (Phase 6-C1)

## Status (2026-08-22 Phase 6-C2)

- `ResearchTaskType` enum (9 task types) + label helper
- `ResearchTaskProfile` + `isValidResearchTaskProfile` validator
- `BUILT_IN_TASK_PROFILES` frozen constant (canonical task -> caps mapping)
- `resolveTaskProfile(taskType)` lookup
- `routeResearchTask` — 5-step decision tree with security boundary
- `routeResearchTaskExtended` — labeled outcome for callers
- 49 unit tests PASSED (exceeds spec >= 30)
- 0 changes to chat:* IPC, Phase 3-B0 StreamEvent, backend, legacy chat fallback, Phase 6-A/B/C1 tests
- Doc complete (13 sections)
