# Research Memory Architecture (Phase 8-F0)

> **purpose**: Define the persistence boundary ABOVE the agent — sessions, conversation, memory, checkpoints.
> **follows**: `research-agent-orchestration.md` (Phase 8-E0). **feeds**: `agent-memory-vs-knowledge.md` (Phase 8-F0).

## 1. Architecture

```
                 Research Workspace
                         |
                         v
              Research Session Manager
                         |
        +----------------+----------------+
        |                                 |
        v                                 v
 Conversation Memory              Research Memory
        |                                 |
        v                                 v
  Agent Runs (question/answer)     Papers / Data / Experiments
        |                                 |
        +----------------+----------------+
                         |
                         v
                 MemoryProvider (LocalMemoryProvider)
```

`ResearchMemoryAdapter` connects `ResearchAgent` (Phase 8-E0) to the `ResearchSessionManager` **without touching the agent core**:

```
 before run:  load previous context  (conversation + memory + checkpoints)
 agent.run(request)
 after run:   store question + answer + citations + confidence
```

## 2. Modules (all NEW in Phase 8-F0)

| Module | File | Responsibility |
|--------|------|----------------|
| Session contracts | `src/shared/agent/research-session-schema.ts` | `ResearchSession` / `ConversationEntry` / `MemoryItem` / `AgentCheckpoint` + `SessionEvent` + secret guard |
| Memory seam | `src/shared/agent/memory-provider.ts` | `MemoryProvider` interface + deterministic `LocalMemoryProvider` |
| Session manager | `src/main/services/agent/research-session-manager.ts` | session lifecycle + conversation + memory + checkpoints, injectable storage |
| Agent binding | `src/main/services/agent/research-memory-adapter.ts` | load-before / store-after wrapper |

## 3. Session lifecycle

```
 createSession()  -> status = active
      |
      v
 appendConversation(user) / appendConversation(assistant)
 addMemory(...) / saveCheckpoint(...)
      |
      v
 pauseSession()   -> paused
 closeSession()   -> completed
 archiveSession() -> archived
```

`updateSession` bumps `updatedAt` to the injected `now` (or `Date.now()`); `createdAt` is immutable once set.

## 4. Memory types

| MemoryType | Meaning | Example |
|------------|---------|---------|
| conversation | Q&A history | "asked about bubble kinetics" |
| experiment | lab result | "degradation rate k = 0.05/min" |
| paper | literature fact | "Zhang 2024 found stable bubbles" |
| parameter | measured constant | "pH = 7.2, T = 25°C" |
| conclusion | agent-generated result | "bubbles improve mixing" |

`MemoryItem.confidence ∈ [0,1]`, `source` records origin (e.g. the requestId that produced it).

## 5. Checkpoint recovery

`saveCheckpoint(sessionId, { planId, stepState })` snapshots a run's progress.
`restoreCheckpoint(sessionId, checkpointId)` returns the snapshot for resume.
`listCheckpoints(sessionId)` orders by `createdAt` asc.
Restore emits `context_restored`.

## 6. Events

Reusing the Phase 8-E0 event shape (same `{ type, timestamp, payload }` envelope — the orchestrator's `AgentEvent` uses `requestId`; the session layer's `SessionEvent` uses `sessionId`):

| Event | Emitted by |
|-------|------------|
| `session_created` | `createSession` |
| `memory_added` | `addMemory` |
| `checkpoint_saved` | `saveCheckpoint` |
| `context_restored` | `restoreCheckpoint` / `loadContext` |

A future workspace layer can multiplex both event streams.

## 7. Security boundary

- The request/response/session schemas run a string-only secret guard walking leaf values (keys are identifiers — they can't carry secrets).
- Forbidden substrings: `'sk-'`, `'apiKey'`, `'secret'`, `'token value'`, `'cipher'`, `'authorization'`, `'Bearer '`, `'providerId/'`.
- Sessions/memory are in-memory by default (`LocalMemoryProvider`); a durable store can replace `SessionStorageLike` / `MemoryProvider` without changing the manager or the adapter.

## 8. References

- `docs/agent/agent-memory-vs-knowledge.md`
- `src/shared/agent/{research-session-schema,memory-provider,research-agent-schema}.ts`
- `src/main/services/agent/{research-session-manager,research-memory-adapter}.ts`
- `src/main/services/agent/research-agent.ts` (Phase 8-E0 — adapted, not modified)