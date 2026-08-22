# Live E2E Validation (Phase 6-D)

> **purpose**: Validate the complete Phase 6 runtime chain end-to-end using in-memory mock providers. NO real network calls. NO backend changes. NO legacy chat fallback broken.
> **follows**: Phase 6-A1~A6, Phase 6-B (d417f8968), Phase 6-C1 (33ce1eeb5), Phase 6-C2 (b5c19a7e2), Phase 6-C3 (d0e4b53c1), Phase 6-C4 (f37d2d146).
> **Phase 6-D contract**: validate and harden the existing system. **NO** architecture redesign. **NO** new major features.

## 1. Scope (Phase 6-D frozen)

- `runtime-diagnostics.ts` — per-provider debug snapshot (status / latency / successRate / capabilities / budget)
- `tests/unit/runtime-diagnostics.test.ts` — 33 unit tests
- `tests/e2e/model-runtime-live.test.ts` — 26 e2e scenario tests (A through H + integration)
- 696 total tests (>= 680 spec target)
- **NO** backend changes, **NO** Phase 3-B0 StreamEvent changes, **NO** legacy chat fallback broken, **NO** apiKey leakage

## 2. Files (Phase 6-D)

```
desktop/src/main/services/model-provider/
  - runtime-diagnostics.ts                (NEW)  per-provider snapshot

desktop/tests/unit/
  - runtime-diagnostics.test.ts           (NEW)  33 cases

desktop/tests/e2e/
  - model-runtime-live.test.ts             (NEW)  26 cases (A-H + integration)

desktop/docs/desktop-conversion/
  - live-e2e-validation.md                 (NEW)  this file
```

## 3. Phase 6 runtime architecture (frozen)

```
[Renderer ChatView]
  ↓ window.api.chat.startStream + window.api.model.routeTask
[Preload contextBridge]
  ↓
[Main chat-stream.service.ts]
  ├─ legacy path: FastAPI /chat/stream  (Phase 2-Impl-3B unchanged)
  └─ provider path: runtime-router.routeChatRequest
                                          ↓
                              Phase 6-C4 capability-router
                                          ↓
                  ┌──────────────────────────────────────────┐
                  │ routeResearchTask(profile)               │
                  │   1. validate profile (Phase 6-C2)       │
                  │   2. resolve all candidates               │
                  │   3. filter: caps + key + health + budget│
                  │   4. rank: capability*10 + health*5 +    │
                  │              budget*3 + priority/10      │
                  │   5. pick best or fallback to active     │
                  └──────────────────────────────────────────┘
                                          ↓
                              Phase 6-A3 provider factory
                                          ↓
                              Phase 6-A6 real HTTP fetch + SSE/NDJSON
                                          ↓
                              Phase 3-B0 StreamEvent broadcast
```

Three layers, all frozen by Phase 6-A/B/C1/C2/C3/C4:
- **Layer 1 (router)**: capability + health + budget scoring (Phase 6-C2 + C4)
- **Layer 2 (provider)**: buildRequest + parseChunk per vendor (Phase 6-A3 + A6)
- **Layer 3 (transport)**: HTTP fetch + streaming (Phase 6-A6)

Phase 6-D only validates this stack end-to-end.

## 4. Provider lifecycle

```
register()                     -- Phase 6-A3: provider factory + metadata
  ↓
saveConfig()                   -- Phase 6-A4: non-secret config (endpoint, capabilities)
  ↓
saveKey()                      -- Phase 6-A2: apiKey in safeStorage
  ↓
setActive() OR selectTask()   -- Phase 6-A5 / 6-C3: pin as active
  ↓
getProviderDiagnostics()       -- Phase 6-D: snapshot for debug UI
  ↓
ping() / testProvider()        -- Phase 6-A4: connectivity check
  ↓
recordSuccess() / recordFailure()
                               -- Phase 6-C4: health tracking
  ↓
recordRequest()               -- Phase 6-C4: metrics
  ↓
recordUsage()                  -- Phase 6-C4: budget enforcement
```

Each stage is independent and the store layers never leak across boundaries.

## 5. Routing flow (Phase 6-D e2e scenarios)

### Scenario A — Provider connection test
1. Configure cloud provider with `safeStorage.encryptString(apiKey)`
2. `keyExists(providerId)` returns true (Phase 6-A2 boundary check)
3. `resolveActiveProvider()` builds ResolvedProvider (apiKey NEVER crosses IPC)
4. IPC response contains NO secret (defense in depth: assertProfileSafe + JSON.stringify grep)

### Scenario B — Auto routing for literature-review
1. User types "分析这篇论文的创新点和实验方法"
2. ChatView (Phase 6-C3) auto-mode picks `taskType='literature-review'`
3. capability-router requires `['literature']` (BUILT_IN_TASK_PROFILES)
4. Picks provider with literature cap (e.g. `paperbot`)
5. `RouterDecision.rankedCandidates` shows score breakdown (capability / health / budget)

### Scenario C — Paper writing routing
1. User types "根据实验结果撰写SCI论文Results部分"
2. Task = `paper-writing`, requires `['paper-writing']`
3. Router picks provider with paper-writing cap; skips chat-only providers
4. `decision.reason` mentions `paper-writing` for debug

### Scenario D — CFD analysis routing
1. User types "分析微纳米气泡发生器Fluent流场"
2. Task = `cfd-analysis`, requires `['cfd']`
3. Router picks cfd-capable provider
4. `rankedCandidates[0]` is the cfd provider (top of ranking)

### Scenario E — Data analysis routing
1. User types "分析TC降解动力学数据"
2. Task = `data-analysis`, requires `['data-analysis']`
3. Router picks data-analysis provider

### Scenario F — Manual override
1. User in **manual mode** (Phase 6-B ModelSelector)
2. `chat.ts` reads `useModelSelectorStore.resolveForSession()`
3. Phase 6-C2 router decision IGNORED in manual mode
4. Active provider wins (Phase 6-B contract preserved)

### Scenario G — Health fallback (A cooldown -> B)
1. `recordFailure('provider-a')` x3 -> `provider-a` enters cooldown
2. `provider-b` healthy
3. Router picks `provider-b` (Phase 6-C4 health filter)
4. If BOTH cooldown -> router returns null

### Scenario H — Budget filter
1. `setLimit('over-budget', 1000)` + `recordUsage('over-budget', 1000)`
2. `isOverBudget('over-budget')` = true
3. Router EXCLUDES over-budget provider
4. `rankedCandidates` shows in-budget provider with `budgetScore: 1`
5. Over-budget provider is filtered out (not in rankedCandidates)

## 6. Failure recovery (Phase 6-D e2e validated)

```
runtime error during provider chat:
  ↓
runProviderRuntime catch:
  ↓
retryWithFallback(profile, failedProviderId, latencyMs, error):
  1. recordMetrics(failed, latencyMs, success=false)
  2. recordFailure(failed)  // bumps health failure count
  3. if 3rd failure: provider enters cooldown
  4. re-route via routeResearchTask(profile)
     - cooldown provider filtered out (Phase 6-C4)
     - over-budget provider filtered out (Phase 6-C4)
     - returns next RouterDecision or null
  5. caller decides: retry with new provider OR give up (null)
```

## 7. Security boundary (Phase 6-D strict)

| Boundary | Phase | Status |
|----------|-------|--------|
| apiKey in renderer state | Phase 6-A2 | NEVER |
| apiKey in chat:* IPC | Phase 6-A5 | NEVER |
| apiKey in model:* IPC | Phase 6-A2 | NEVER |
| apiKey in Pinia task-selector | Phase 6-C3 | NEVER |
| apiKey in RouterDecision | Phase 6-C2 | NEVER (assertProfileSafe) |
| apiKey in health-tracker | Phase 6-C4 | NEVER |
| apiKey in metrics-store | Phase 6-C4 | NEVER |
| apiKey in budget-manager | Phase 6-C4 | NEVER |
| apiKey in ProviderDiagnostics | Phase 6-D | NEVER (assertSnapshotSafe) |
| apiKey in mock HTTP body | Phase 6-A6 | ONLY in Authorization header |

Phase 6-D strict: every return value across module boundaries is grep-tested for `sk-` / `apiKey` / `cipher` / `Bearer ` / `token` / `Authorization`. `assertSnapshotSafe` throws if any violation is detected.

## 8. Debug workflow

When a provider misbehaves in production:

```
1. Phase 6-A4: Test connection
   window.api.model.testProvider('openai')
   → { ok: false, latencyMs: 250, error: 'HTTP 401' }

2. Phase 6-D: Snapshot diagnostics (main process only)
   getProviderDiagnostics('openai')
   → { status: 'failed', healthScore: 0, cooldownUntil: 1735000000 }

3. Phase 6-C4: Check health state
   getHealth('openai').state
   → 'cooldown'

4. Phase 6-C4: Check budget
   isOverBudget('openai')
   → false (separate concern)

5. Phase 6-C4: Check metrics
   metricsSnapshot('openai').failures
   → 3 (matches cooldown threshold)

6. Phase 6-D: Re-run after cooldown
   wait 60s -> auto-recover (clock-based)
   -> state = 'healthy', failures = 0
```

No `apiKey` ever appears in any of these snapshots — defense in depth.

## 9. Test coverage (59 / 59 PASSED — runtime-diagnostics + e2e)

| File | Cases |
|------|-------|
| `runtime-diagnostics.test.ts` | 33 (shape / status / success-rate / latency / budget / hasApiKey boolean / researchCapabilities / getAllProviderDiagnostics / assertSnapshotSafe) |
| `model-runtime-live.test.ts` (e2e) | 26 (Scenario A 3 / B 4 / C 3 / D 3 / E 2 / F 3 / G 5 / H 3 + integration 1) |
| **Phase 6-D total new** | **59** |

**Project total: 696 tests** (>= 680 spec target ✓).

## 10. Forbidden patterns (permanent)

- ❌ Add new IPC channel in Phase 6-D. (Reason: existing model:* namespace is sufficient.)
- ❌ Persist health / metrics / budget to disk in Phase 6-D. (Reason: process-lifetime is sufficient for runtime validation.)
- ❌ Move apiKey to renderer for "debugging". (Reason: defense in depth — keys stay in main.)
- ❌ Modify `RouteDecision` shape. (Reason: Phase 6-C2 frozen contract.)
- ❌ Modify `ChatStreamRequest`. (Reason: Phase 6-A5 frozen contract.)
- ❌ Replace `routeResearchTask` with a new picker. (Reason: Phase 6-C2 router is the canonical entry.)
- ❌ Add external database for diagnostics. (Reason: in-memory Map is sufficient.)

## 11. Phase 6-D summary

| phase | scope | tests |
|-------|-------|-------|
| 6-A audit | doc-only design | n/a |
| 6-A1 | types + interface + normalizer | 204 |
| 6-A2 | SecretStore + IPC | 44 |
| 6-A3 | Provider Factory + Registry | 66 |
| 6-A4 | Model Settings + ConfigStore | 58 |
| 6-A5 | Runtime Integration | 24 |
| 6-A6 | Runtime E2E (mock server) | 33 |
| 6-B | Active Model Integration | 26 |
| 6-C1 | Capability Foundation | 43 |
| 6-C2 | Capability Router | 49 |
| 6-C3 | Task-aware UI | 35 |
| 6-C4 | Health + Budget + Retry | 55 |
| **6-D** | **Live E2E Validation** | **59** |
| **Total** | | **696** |

## 12. References

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
- `docs/desktop-conversion/provider-health-budget-retry.md` (Phase 6-C4)

## Status (2026-08-22 Phase 6-D)

- `runtime-diagnostics.ts` — per-provider snapshot (status / latency / successRate / capabilities / budget / hasApiKey boolean)
- `assertSnapshotSafe` — defensive runtime guard (throws on sk-/apiKey/cipher/Bearer/token/Authorization)
- 33 unit tests + 26 e2e tests = 59 new tests PASSED
- Project total: **696 tests PASSED** (>= 680 target ✓)
- 0 changes to backend, Phase 3-B0 StreamEvent, chat:* IPC, legacy chat fallback
- Phase 6-A/B/C1/C2/C3/C4 tests ALL PASS UNCHANGED
- Doc complete (12 sections)
