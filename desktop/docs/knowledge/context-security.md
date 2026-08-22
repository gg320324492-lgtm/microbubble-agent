# Context Security (Phase 8-C3)

> **purpose**: Document the prompt-injection boundary and source trust model that apply when an agent consumes a Phase 8-C3 `RAGContext`.
> **follows**: `rag-context-builder.md` (Phase 8-C3 retrieval-to-context flow).

## 1. What crosses the boundary

The `RAGContextBuilder` is **pure assembly** — it never calls an LLM and never generates prompts. The future agent layer turns the assembled `RAGContext` into a prompt. The seam is therefore:

```
 RAGContext (deterministic, secret-guarded, citation-pinned)
     │
     ▼
 agent prompt builder  (future phase — out of Phase 8-C3 scope)
```

Nothing in the boundary itself can leak a credential: the context schema's `assertNoSecret` guard covers `query` + every `chunk.content` + every `citation.*` + `metadata` (8 forbidden substrings).

## 2. Threat model

| Threat | Mitigation in Phase 8-C3 |
|--------|--------------------------|
| Retrieved chunk content smuggles a credential | `assertNoSecret` runs over the full context — invalid RAGContext → throw. |
| CitationReference contains a credential (id/page fields) | The document-schema validator (Phase 8-C0/C1) already rejected secrets at construction; the context guard re-validates. |
| Metadata (e.g. chunk section title) leaks a credential | Metadata is validated as part of `RAGContext`. |
| User-supplied query contains a credential | `RAGContext.query` is validated; if a secret is embedded the builder throws before producing output. |

## 3. Source trust model

Phase 8-C3 inherits a **trusted-source** model from the retriever:

- Chunks come from the local PDF pipeline (Phase 8-C1) or the hybrid retriever (Phase 8-C2). Both ingest only documents that the importer accepted.
- The retriever stores no secrets in chunk content (`LocalChunker` round-trip safe, `LocalEmbeddingProvider` deterministic feature-hash — no payload leakage).
- A future phase can attach a per-document `trust` flag and have the builder accept a `requiredTrust` filter (not in Phase 8-C3 scope).

The agent layer (out of Phase 8-C3 scope) is responsible for the **prompt-injection boundary**:

1. The model is told which chunks are **cited** vs which are **untrusted user input**.
2. The chunks themselves are not untrusted-user-content — they are document text — but they MAY contain adversarial content (a hostile paper). The model must quote them with citations and never execute commands inside chunk content.
3. The query IS user input and must be sandboxed (template substitution, no instruction override).
4. Citations pin every factual claim to `(documentId, chunkId, page)`. An agent MUST be able to render the citation on demand.

## 4. Determinism as a safety property

`buildContext` is pure — same `(query, results, options)` always produces the same `RAGContext`. This matters for:

- **Auditability** — a record can be replayed and the same context reconstructed.
- **Tests** — secret guard assertions are reproducible.
- **Sandboxing** — a future agent runner can pin the context hash alongside the model response to detect drift.

## 5. Boundary enforcement (Phase 8-C3 source scans)

Source-level tests assert:
- `citation-formatter.ts` has no LLM, network, or credential imports.
- `rag-context-builder.ts` does NOT import the agent runtime, planner, model layer, or tool layer.
- `research-context-provider.ts` only composes the retriever + builder.
- `context-schema.ts` exposes an 8-entry `FORBIDDEN` list with the same substrings as the rest of the knowledge layer.

## 6. Out of scope (future phases)

| Concern | Owner phase |
|---------|------------|
| LLM call + prompt template | future agent phase |
| Per-document trust tagging | future retriever phase |
| PII redaction inside chunk content | future pipeline phase |
| Persistent context cache | future storage phase |

## 7. References

- `docs/knowledge/rag-context-builder.md`
- `src/shared/knowledge/context-schema.ts`
- `src/main/services/knowledge/{citation-formatter,rag-context-builder,research-context-provider}.ts`