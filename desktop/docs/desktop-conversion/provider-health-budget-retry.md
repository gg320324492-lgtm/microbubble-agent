# Provider Health + Budget + Retry Layer (Phase 6-C4)

> **purpose**: Upgrade Phase 6-C2 capability router from capability-only selection to production multi-model routing. Adds provider health tracking, runtime metrics, token-budget enforcement, and a retry/fallback policy. Preserves all Phase 6-A/B/C1/C2/C3 contracts.
> **follows**: Phase 6-A1~A6, Phase 6-B (Active Model Integration, d417f8968), Phase 6-C1 (Capability Foundation, 33ce1eeb5), Phase 6-C2 (Capability Router, b5c19a7e2), Phase 6-C3 (Task-aware UI, d0e4b53c1).

## 1. Scope (Phase 6-C4 frozen)

- **health-tracker.ts** — per-provider rolling window (latency, failures, state)
- **metrics-store.ts** — per-provider counters (requests, successes, failures, p50/p95)
- **budget-manager.ts** — per-provider token budget (default unlimited)
- **capability-router.ts** — extended scoring: `capability + health*5 + budget*3 + priority/10`
- **retryWithFallback** — runtime failure -> record metrics -> re-route
- **recordRequestOutcome** — helper for callers to record outcome
- 55 unit tests (>= 50 spec requirement)
- **NO** backend changes, **NO** Phase 3-B0 StreamEvent changes, **NO** legacy chat fallback broken, **NO** apiKey leakage

## 2. Files (Phase 6-C4)

```
desktop/src/main/services/model-provider/
  - health-tracker.ts                     (NEW)  per-provider health record + cooldown
  - metrics-store.ts                      (NEW)  per-provider request counters
  - budget-manager.ts                     (NEW)  per-provider token budget
  - capability-router.ts                  (MODIFY) +health + budget scoring + retryWithFallback

desktop/tests/unit/
  - provider-health.test.ts               (NEW)  55 cases

desktop/docs/desktop-conversion/
  - provider-health-budget-retry.md       (NEW)  this file
```

## 3. Health tracker

`health-tracker.ts` — per-provider health record:

```ts
interface HealthRecord {
  providerId: string
  state: 'healthy' | 'degraded' | 'cooldown' | 'unknown'
  recentLatencyMs: number[]      // last 10 samples (rolling window)
  failures: number              // consecutive failure count
  successes: number
  lastSuccessAt: number | null
  lastFailureAt: number | null
  cooldownUntil: number | null  // epoch ms; null = not in cooldown
  lastError: string | null
}
```

State transitions:
```
unknown ──recordSuccess──▶ healthy
unknown ──recordFailure──▶ degraded (1-2 failures)
                              └─recordFailure(3rd)──▶ cooldown (60s)
                                                              └─time elapsed──▶ healthy (failures reset)
healthy ──p95>5s──▶ degraded
degraded ──recordSuccess──▶ healthy
```

Score in `[0..1]`:
- `healthy`   → 1.0
- `degraded`  → 0.5
- `cooldown`  → 0.0 (router should skip)
- `unknown`   → 0.7 (neutral — no signal yet)

## 4. Metrics store

`metrics-store.ts` — per-provider counters:

```ts
interface MetricsRecord {
  providerId: string
  requests: number
  successes: number
  failures: number
  totalLatencyMs: number
  p50: number
  p95: number
  updatedAt: number
}
```

Lightweight p50/p95 approximation: `p50 = mean` and `p95 = 2 * mean` over recorded successes.
Used for router scoring and future debug / telemetry surfaces.

## 5. Budget manager

`budget-manager.ts` — per-provider token budget:

```ts
interface BudgetUsage {
  providerId: string
  used: number
  limit: number  // 0 = unlimited
  remaining: number  // Infinity when limit = 0
}
```

Default limit is `0` (unlimited). Phase 6-C4 strict: no `isOverBudget` returns true unless `limit > 0` AND `used >= limit`.

## 6. Router scoring (Phase 6-C4 extension)

```
score = capabilityScore * 10 + healthScore * 5 + budgetScore * 3 + priority / 10
```

Filters (in order, all must pass):
1. `hasAllCapabilities(c, required)` — Phase 6-C1 contract
2. `keyExists(c.providerId)` — Phase 6-A2 security boundary
3. `healthIsAvailable(c.providerId)` — **Phase 6-C4: skip cooldown**
4. `!isOverBudget(c.providerId)` — **Phase 6-C4: skip over-budget**

Result carries `rankedCandidates` (top 5) with score breakdown:
```ts
{
  providerId: string
  model: string
  score: number               // rounded 2 decimals
  capabilityScore: number
  healthScore: number         // 0..1
  budgetScore: number         // 0 or 1
}
```

Renderer-visible (no apiKey).

## 7. Retry / fallback policy

```
runtime error → retryWithFallback(profile, failedProviderId, latencyMs, error):
  1. recordMetrics(failedProviderId, latencyMs, false)
  2. re-route via routeResearchTask(profile)
     - cooldown provider filtered out by step 3 above
     - active provider still a fallback
  3. returns next RouterDecision (or null if no fallback possible)
```

Caller (Phase 6-A6 runtime) wires:
```
try {
  await runProviderRuntime(...)
  recordRequestOutcome(providerId, latencyMs, true)
} catch (e) {
  const next = retryWithFallback(profile, providerId, latencyMs, e.message)
  if (next) {
    // recurse: try the next provider
  }
}
```

## 8. Security boundary (Phase 6-C4 strict)

| Item | Lives in | NEVER crosses to |
|------|----------|------------------|
| apiKey | SecretStore (Phase 6-A2) | renderer, IPC, log |
| Health record | in-memory Map | renderer (no IPC) |
| Metrics record | in-memory Map | renderer (no IPC) |
| Budget record | in-memory Map | renderer (no IPC) |
| `RouterDecision.reason` | main process | grep-tested — no key |
| `rankedCandidates` | main process | grep-tested — no key |
| `lastError` in HealthRecord | main process | main-only |

Test enforcement:
- "RouterDecision.reason NEVER contains apiKey"
- "rankedCandidates NEVER contain apiKey"
- "health-tracker recordFailure error message stays clean"
- "metrics-store snapshot NEVER carries key"
- "budget-manager getUsage NEVER carries key"

## 9. Test coverage (55 / 55 PASSED, exceeds spec >= 50)

| describe | cases |
|----------|-------|
| health-tracker — initial state (3) | fresh record / score 0.7 / isAvailable true |
| health-tracker — success path (5) | unknown->healthy / score 1.0 / rolling window / window cap / reset failures |
| health-tracker — failure path + cooldown (5) | failure counter / 3-fail cooldown / isAvailable false / score 0.0 / auto-recover |
| health-tracker — degraded state (3) | p95>5s / clear one / clear all |
| metrics-store (8) | snapshot / counters / latency only on success / p50+p95 estimate / negative ignored / reset / zero successes / empty id |
| budget-manager — limits (5) | default 0 / round-trip / negative / fractional / Infinity |
| budget-manager — usage (7) | accumulate / fractional / negative / under-limit / over-limit / unlimited / reset |
| router — health filter (2) | skips cooldown / null when all cooldown |
| router — budget filter (1) | skips over-budget |
| router — rankedCandidates (4) | field present / breakdown / optional caps rank / reason contains health= |
| router — health-degraded scoring (1) | degraded ranks lower than healthy |
| retryWithFallback (5) | records failure / returns decision / alt exists / null no candidate / success helper |
| Security (5) | reason clean / rankedCandidates clean / error msg clean / metrics clean / budget clean |
| **Total** | **55** |

## 10. Forbidden patterns (permanent)

- ❌ Persist health / metrics / budget to disk. (Reason: Phase 6-C4 strict — process-lifetime only.)
- ❌ Log apiKey in HealthRecord.lastError. (Reason: defense in depth.)
- ❌ Pick a cooldown provider. (Reason: healthIsAvailable filter blocks.)
- ❌ Pick an over-budget provider. (Reason: isOverBudget filter blocks.)
- ❌ Throw on empty registry. (Reason: caller decides legacy fallback path.)
- ❌ Auto-reset failures on cooldown entry. (Reason: caller-driven via success.)
- ❌ Use this layer to manage Auth tokens. (Reason: SecretStore owns that.)
- ❌ Couple router to a specific chat-store. (Reason: pure module; chat-stream.service.ts wires.)

## 11. Phase 6-D plan

- Live e2e: from desktop chat, pick task → router picks best healthy+in-budget provider → runtime failure → retry picks next-best
- ConversationModelContext gains `taskProfile?` field for per-task binding
- Settings UI exposes budget editor (per-provider daily token limit)
- Persistent storage for health / metrics / budget (Phase 6-E or later)

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
| 6-C2 Agent Capability Router | ResearchTaskProfile + routeResearchTask + 49 tests | done (b5c19a7e2) |
| 6-C3 Task-aware Chat Header UI | task-selector Pinia + TaskSelector.vue + IPC + 35 tests | done (d0e4b53c1) |
| **6-C4 Provider Health + Budget + Retry** | health-tracker + metrics-store + budget-manager + 55 tests | **this commit** |
| 6-D Live e2e | follow | next |

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
- `docs/desktop-conversion/agent-capability-router.md` (Phase 6-C2)
- `docs/desktop-conversion/task-aware-model-selection-ui.md` (Phase 6-C3)

## Status (2026-08-22 Phase 6-C4)

- `health-tracker.ts` — rolling latency window + 3-fail cooldown (60s) + auto-recover
- `metrics-store.ts` — per-provider counters + p50/p95 estimate
- `budget-manager.ts` — per-provider token budget + over-budget detection
- `capability-router.ts` extended — health + budget filters + scored ranking + retryWithFallback
- 55 unit tests PASSED (exceeds spec >= 50)
- 0 changes to backend, Phase 3-B0 StreamEvent, chat:* IPC, legacy chat fallback
- Phase 6-A/B/C1/C2/C3 tests ALL PASS UNCHANGED
- Doc complete (13 sections)
