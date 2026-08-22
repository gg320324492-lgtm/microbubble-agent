# Task-aware Chat Header UI (Phase 6-C3)

> **purpose**: Expose the Phase 6-C2 Agent Capability Router to users via a chat-header widget. Adds Manual / Auto research mode toggle, displays the resolved task, selected model, and routing reason. Preserves Phase 6-B manual model selection.
> **follows**: Phase 6-A1~A6, Phase 6-B (Active Model Integration, d417f8968), Phase 6-C1 (Model Capability Foundation, 33ce1eeb5), Phase 6-C2 (Agent Capability Router, b5c19a7e2).

## 1. Scope (Phase 6-C3 frozen)

- `model:route-task` IPC channel — main process runs capability-router, returns non-secret decision
- `task-selector` Pinia store — chat-side state for mode + taskType + lastDecision
- `TaskSelector.vue` chat-header widget — Manual/Auto toggle + task picker + decision display
- `chat.ts` store — auto-mode prefers router decision over Phase 6-B manual selection
- `ChatView` header — TaskSelector + ModelSelector side-by-side
- 35 unit tests (>= 30 spec requirement)
- **NO** backend changes, **NO** Phase 3-B0 StreamEvent changes, **NO** legacy chat fallback broken, **NO** apiKey leakage

## 2. Files (Phase 6-C3)

```
desktop/src/shared/
  - model/model-ipc.ts                    (MODIFY) +MODEL_ROUTE_TASK channel
  - ipc-types.ts                          (MODIFY) +MODEL_ROUTE_TASK channel
  - preload-api.ts                        (MODIFY) +ModelRouteTaskResult + DesktopModelApi.routeTask

desktop/src/main/services/model-provider/
  - model-ipc.ts                          (MODIFY) +model:route-task handler

desktop/src/renderer/src/
  - stores/task-selector.ts               (NEW)  Pinia store (no apiKey field)
  - components/chat/TaskSelector.vue      (NEW)  chat-header widget
  - components/chat/index.ts              (MODIFY) +TaskSelector + ModelSelector exports
  - stores/chat.ts                        (MODIFY) auto-mode uses router decision
  - views/ChatView.vue                    (MODIFY) +TaskSelector in chat header
  - preload/index.ts                      (MODIFY) +routeTask bridge

desktop/tests/unit/
  - task-selector.test.ts                 (NEW)  35 cases

desktop/docs/desktop-conversion/
  - task-aware-model-selection-ui.md      (NEW)  this file
```

## 3. Manual / Auto mode

```
[Chat Header]
  💬 Session Title              [TaskSelector]  [ModelSelector]
                                [Manual|Auto]    🧠 OpenAI · gpt-4o
                                task picker
```

```
Manual mode (Phase 6-B default):
  - ModelSelector picks provider+model
  - chat:start-stream modelContext = resolveForSession(sessionId)
  - existing behavior unchanged

Auto mode (Phase 6-C3 NEW):
  - TaskSelector picks taskType (literature-review / paper-writing / ...)
  - chat:start-stream modelContext = router decision (providerId + model)
  - Phase 6-C2 capability-router picks the best provider with required caps + key
  - If router can't find a match, falls back to active provider
  - If still no match, falls back to legacy FastAPI /chat/stream
```

## 4. TaskSelector.vue contract

Trigger: `🎯 <taskLabel> ▾` (e.g. "🎯 Paper Writing ▾")

Menu items: 9 task types
- literature-review
- paper-writing
- coding
- matlab
- python-analysis
- cfd-analysis
- image-analysis
- experiment-design
- data-analysis

Decision chip after pick:
```
[Auto-routed] [openai · gpt-4o]    <- capability match
[Active fallback] [chatty · v1]   <- no match → active
[No provider matches]              <- task has no candidate
```

The decision chip's title attribute shows the full `decision.reason` string for debugging.

## 5. IPC: model:route-task

Request (renderer → main):
```json
{
  "taskType": "paper-writing",
  "requiredCapabilities": ["paper-writing"]
}
```

Response (main → renderer):
```json
{
  "decision": {
    "providerId": "paperbot",
    "model": "paperbot-pro",
    "source": "capability-match",
    "reason": "matched task='paper-writing' required=[paper-writing]",
    "capabilities": ["paper-writing", "literature"]
  },
  "route": "task-routed",
  "reason": "..."
}
```

Phase 6-C3 strict: response NEVER contains apiKey / Authorization / ciphertext. The main process runs `routeResearchTask` which calls `assertProfileSafe` on the resulting profile before returning.

## 6. Chat store integration

```ts
// chat.ts:sendUserMessageStream
const taskSelector = useTaskSelectorStore()
const modelSelector = useModelSelectorStore()

let modelContext = taskSelector.isAuto && taskSelector.lastDecision?.decision
  ? {
      providerId: taskSelector.lastDecision.decision.providerId,
      model: taskSelector.lastDecision.decision.model
    }
  : modelSelector.resolveForSession(currentSessionId.value) ?? undefined

if (!modelContext && taskSelector.isAuto && taskSelector.lastDecision?.decision === null) {
  // auto mode but router returned no-route -> fall through to manual pick
  modelContext = modelSelector.resolveForSession(currentSessionId.value) ?? undefined
}
```

Auto mode wins when router has a decision. Manual mode always wins when mode='manual'.

## 7. Security boundary (Phase 6-C3 strict)

- `lastDecision.decision` shape has NO apiKey field
- IPC response shape has NO apiKey field
- routeTask IPC payload (profile) has NO apiKey field
- Decision reason string is set by main process from `routeResearchTask` (uses safe strings)
- `assertProfileSafe` runs on every decision in main process (defense in depth)

Test enforcement:
- "store state dump NEVER contains apiKey substring" (uses distinctive sentinels)
- "lastDecision shape has no apiKey field" (Object.keys check)
- "routeTask IPC payload does NOT carry apiKey field" (captures payload + grep)
- "store NEVER has a key-bearing field after routeTask IPC"

## 8. Backward compatibility

| Change | Compatibility |
|--------|---------------|
| Mode default 'manual' | Phase 6-B flow unchanged (ModelSelector wins) |
| `task-selector` Pinia store | New; chat store falls back to legacy if not loaded |
| `TaskSelector.vue` | New; chat header renders without it (manual mode hides it) |
| `model:route-task` IPC | New; not called in manual mode |
| `chat.ts` integration | Reads task-selector only when `isAuto`; manual flow identical |
| Phase 6-A/B/C1/C2 tests | All pass unchanged (582 -> 582 + 35 in this Phase) |

## 9. Test coverage (35 / 35 PASSED, exceeds spec >= 30)

| describe | cases |
|----------|-------|
| initial state (3) | manual mode / no task / no error |
| setMode (4) | auto sets isAuto / manual clears decision / preserves taskType / clears lastError |
| selectTask (5) | manual doesn't call routeTask / auto calls routeTask / null clears / IPC error sets lastError / routing flag |
| getters (4) | hasDecision / decisionLabel / decisionSourceLabel x2 |
| reset (2) | clears all state / clears error |
| Security (5) | state dump clean / shape has no key field / reason handling / IPC payload clean / Authorization absent |
| TASK_TYPE_CAPABILITIES (9) | one per task type |
| TASK_TYPE_CAPABILITIES mapping (4) | literature-review / paper-writing / python-analysis |
| **Total** | **35** |

## 10. Forbidden patterns (permanent)

- ❌ Send apiKey over `model:route-task` IPC. (Reason: shape has no key field.)
- ❌ Store apiKey in `task-selector` state. (Reason: Pinia store has no key field.)
- ❌ Log router decision in plaintext. (Reason: dev tools console is world-readable.)
- ❌ Auto-pick a task on mount. (Reason: explicit user choice only.)
- ❌ Bypass `setMode` reset logic. (Reason: stale state from previous mode must not bleed.)
- ❌ Couple task-selector to chat store internals. (Reason: separation of concerns.)
- ❌ Override manual mode silently. (Reason: user must explicitly opt into auto.)

## 11. Phase 6-C4 / 6-D plan

Phase 6-C4 (next):

- Cost / latency budget integration (skip models above user's monthly budget)
- Online status check before routing (skip offline providers)
- Retry policy: if capability-matched provider fails at runtime, retry with next-best

Phase 6-D (later):

- Live e2e from desktop chat: "summarize this paper" → Agent Router picks the literature-capable model automatically
- ConversationModelContext gains `taskProfile?` field for per-task binding
- Settings UI shows router suggestions + cost breakdown

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
| **6-C3 Task-aware Chat Header UI** | task-selector Pinia + TaskSelector.vue + IPC + 35 tests | **this commit** |
| 6-C4 Budget + online + retry | follow | next |
| 6-D Live e2e | follow | later |

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

## Status (2026-08-22 Phase 6-C3)

- `model:route-task` IPC channel (main process runs Phase 6-C2 router)
- `task-selector` Pinia store (no apiKey field)
- `TaskSelector.vue` chat-header widget (Manual/Auto toggle + task picker + decision chip)
- `chat.ts` auto-mode uses router decision over manual selection
- `ChatView` header shows TaskSelector + ModelSelector
- 35 unit tests PASSED (exceeds spec >= 30)
- 0 changes to backend, Phase 3-B0 StreamEvent, chat:* IPC contract, legacy chat fallback
- Doc complete (13 sections)
