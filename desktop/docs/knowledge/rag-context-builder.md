# RAG Context Builder (Phase 8-C3)

> **purpose**: Define the retrieval-to-context boundary — how `SearchResult[]` becomes a citation-aware `RAGContext` the agent consumes.
> **follows**: `vector-retrieval.md` (Phase 8-C2 hybrid retriever).
> **feeds**: `context-security.md` (Phase 8-C3 source trust + prompt injection boundary).

## 1. Retrieval to generation

```
 Question
   │
   ▼
 HybridRetriever.search (Phase 8-C2)
   │  SearchResult[] { chunk, score, citation }
   ▼
 RAGContextBuilder.buildContext
   │  rank → cap → merge similar → dedupe citations → truncate by token budget
   ▼
 RAGContext { query, chunks[], citations[], tokenBudget, metadata }
   │
   ▼
 ResearchContextProvider  (Phase 8-C3 adapter — the only seam the agent uses)
   │
   ▼
 Research Agent  (future phase)
```

The ContextBuilder consumes **SearchResult + CitationReference only**. It never touches the embedding layer, the vector store, the PDF parser, the tool layer, or the agent runtime.

## 2. Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Context schema | `src/shared/knowledge/context-schema.ts` | `RAGContext` / `ContextChunk` contracts + secret guard |
| Citation formatter | `src/main/services/knowledge/citation-formatter.ts` | inline marker + reference list + dedupe |
| RAG context builder | `src/main/services/knowledge/rag-context-builder.ts` | rank / cap / merge / dedupe / truncate |
| Research context provider | `src/main/services/knowledge/research-context-provider.ts` | agent-facing adapter |

## 3. Pipeline (buildContext)

```
 1. rankChunks(results, query)
      -> deterministic score desc, docId asc, position asc;
         optional query-boost (per-chunk term-hit ratio added to score).
 2. cap to maxChunks
 3. mergeSimilarChunks(threshold)
      -> drop the lower-scored of consecutive same-doc chunks
         whose token-set Jaccard >= threshold (default 0.5).
 4. dedupeSearchResults  (per (documentId, chunkId, page))
 5. truncateByTokenBudget(chunks, budget, estimator)
      -> greedy take until tokens fit; estimator defaults to estimateTokens().
 6. citations = deduplicateCitation(truncated.chunk.citation)
      -> truncated is already aligned 1:1 with citations.
 7. context.metadata.totalTokens = sum(estimator(chunk.content))
```

## 4. Citation rendering

`formatInlineCitation(citation, { number, title?, section? })`:
- Default: `[1]`
- With title: `[1] Microbubble Dynamics, page 5`
- With page only: `[1, page 5]`

`formatReferenceList(citations, titleResolver)`:
```
[1] Microbubble Dynamics, page 5
[2] Other Paper, page 3
```
`titleResolver(citation, number)` decouples the formatter from the retriever — the resolver owns how a title is fetched.

`deduplicateCitation(citations)` keys on `documentId::chunkId::page`, preserving first-seen order. Stable + deterministic.

## 5. Token budgeting

`estimateTokens(text)` — words × 1.3 + chars / 4, rounded. No LLM, deterministic. Plug a custom estimator via `BuildContextOptions.tokenEstimator`.

`truncateByTokenBudget` never overflows: each chunk reserves one trailing token; on overflow it breaks.

## 6. Determinism

- Pure ranking, dedupe, merge, truncation.
- Same `SearchResult[]` + same options ⇒ byte-identical `RAGContext`.
- `merged` drops `prev.score >= r.score` first (stable order: rank then iterate).
- Citations are deduped in insertion order (numbering 1..N corresponds to chunks[i]).

## 7. Security boundary

- The context schema's secret guard runs over the full `RAGContext` (incl. metadata) — defense in depth.
- The formatter is pure strings out of `CitationReference`; the builder never holds credentials.
- See `context-security.md` for the prompt-injection + source trust model.

## 8. References

- `docs/knowledge/context-security.md` (Phase 8-C3 threat model)
- `src/shared/knowledge/context-schema.ts`
- `src/main/services/knowledge/{citation-formatter,rag-context-builder,research-context-provider}.ts`
- `src/shared/knowledge/{retriever-schema,document-schema}.ts` (consumed contracts)