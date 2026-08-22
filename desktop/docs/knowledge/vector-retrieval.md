# Vector Retrieval (Phase 8-C2)

> **purpose**: Define the vector search path + hybrid ranking that fuses keyword and semantic signals.
> **follows**: `embedding-architecture.md` (Phase 8-C2).

## 1. Pipeline

```
 SearchQuery { text, filters, limit }
   │
   ├──► LocalRetriever.search(query)        ← Phase 8-C0 keyword
   │      SearchResult[] { chunk, score, citation }
   │
   └──► EmbeddingProvider.embed(query.text)
           │
           ▼
         VectorStore.search({ queryEmbedding, filters, limit: 0 })
           VectorSearchHit[] { chunkId, score (cosine) }
   │
   ▼
 HybridRetriever.merge(ranked chunks)
   total = keywordWeight * clamp01(keywordScore / 110)
         + semanticWeight * clamp01(cosineScore)
   sorted by total desc, docId asc, position asc
   → SearchResult[] (citations reused from chunk)
```

## 2. Cosine search

`LocalVectorStore.search` iterates every record, applies `matchesVectorFilters` (strict equality / array containment), scores with `cosineSimilarity`, and keeps only positive / non-zero hits. Sort key is `(score desc, chunkId asc)` — fully deterministic.

`cosineSimilarity` throws on dim mismatch or non-finite components; returns `0` for zero-norm vectors (so junk tokens never push unrelated hits up).

## 3. Hybrid ranking

```
 total = keywordWeight * clamp01(kwScore / 110)
       + semanticWeight * clamp01(cos)
```

| signal | source | range | normalization |
|--------|--------|-------|---------------|
| `kwScore` | `LocalRetriever.search` | 0..~110 (coverage × 100 + boosts) | `clamp01(score / 110)` |
| `cos`     | `VectorStore.search` | -1..1 (real) | `clamp01(cos)` |

`HybridRetriever.search` returns the union of keyword + vector hits — a chunk that matches both wins on both scores, a chunk that matches only one side still appears with the other side contributing `0`.

Citation confidence mirrors `total / (keywordWeight + semanticWeight)` clamped to `[0, 1]` and rounded to 2 decimals — the citation stays on the same `CitationReference` contract.

## 4. Determinism

- Pure functions (`embed`, `computeEmbedding`, `cosineSimilarity`) are deterministic; `LocalEmbeddingProvider` returns identical vectors for identical text.
- The merge sorts by `(total desc, docId asc, position asc)` — equal totals break ties predictably.
- Re-indexing the same document yields identical record sets (insert path is replace-then-insert).

## 5. Boundary

- The hybrid retriever **does NOT modify** the keyword retriever, Document schema, vector store, or the embedding provider — only orchestrates them.
- `HybridRetriever` depends on `LocalRetriever` (Phase 8-C0) and the Phase 8-C2 `VectorStore`/`EmbeddingProvider`. Future phases can swap either side without touching this module.

## 6. References

- `docs/knowledge/embedding-architecture.md`
- `src/shared/knowledge/{embedding-schema,vector-store-schema,document-schema,retriever-schema}.ts`
- `src/main/services/knowledge/{local-embedding,local-vector-store,hybrid-retriever}.ts`