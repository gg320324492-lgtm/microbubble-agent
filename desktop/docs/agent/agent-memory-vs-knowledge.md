# Agent Memory vs. Knowledge (Phase 8-F0)

> **purpose**: Explain the boundary between the knowledge layer (external science) and the memory layer (agent/user/project history).
> **follows**: `research-memory-architecture.md` (Phase 8-F0) + `rag-context-builder.md` (Phase 8-C3).

## 1. The one-line split

| Layer | Contents | Source |
|-------|----------|--------|
| **Knowledge** | external scientific information | PDFs, papers, datasets, experiments, lab equipment |
| **Memory** | agent / user / project history | prompts, answers, corrections, preferences, prior decisions |

## 2. Where each lives

```
 Knowledge (Phase 8-C*)
   Document -> Chunk -> VectorStore -> HybridRetriever -> RAGContext
        ^ (facts about the world, shared, immutable-ish)

 Memory (Phase 8-F0)
   ResearchSession -> ConversationEntry[] + MemoryItem[] + AgentCheckpoint[]
        ^ (what WE said, what the agent concluded, per-project history)
```

| Property | Knowledge | Memory |
|----------|-----------|--------|
| Unit | `Document` / `DocumentChunk` (Phase 8-C0) | `MemoryItem` / `ConversationEntry` / `AgentCheckpoint` (Phase 8-F0) |
| Mutated? | ingestion adds; content is authoritative | appended on every run; corrected eagerly |
| Scoped to | whole lab / team | a `projectId` / `sessionId` |
| Confidence | retrieval score (0..1) | `MemoryItem.confidence` (0..1) |
| Feeding | RAGContext → model prompt context | load-context → prior turns + standing conclusions |
| Expiry | retention policy | archive / checkpoint GC |

## 3. Why the split matters

1. **Trust.** Knowledge must be cited (`CitationReference`) and immutable once chunked. Memory is conversational — it can be overwritten by new conclusions without breaking provenance.
2. **Scope.** A scientist's "give me the last 3 experiments" is memory; "what does the literature say about bubble coalescence" is knowledge.
3. **Security.** Knowledge chunks are validated through the document schema; memory items through the session schema — each with its own secret guard, so a secret can't leak between the two paths.
4. **Independence.** The memory layer sits ABOVE the retrieval pipeline. It never queries PDFs — it only sums up what the agent has already produced (answers, conclusions, checkpoints).

## 4. Determinism

- `LocalMemoryProvider` returns the same ranked `MemoryItem[]` for the same inserts (confidence desc, id asc tie-break).
- `ResearchSessionManager.createSession(sessionId, title)` yields the same session every time for the same inputs.
- Same input + same memory => same adapter load → same agent context → same result.

## 5. References

- `docs/agent/research-memory-architecture.md` (Phase 8-F0)
- `docs/knowledge/retrieval-architecture.md` (Phase 8-C0 knowledge)
- `src/shared/agent/research-session-schema.ts` + `src/shared/agent/memory-provider.ts`
- `src/shared/knowledge/document-schema.ts` + `src/shared/knowledge/context-schema.ts`