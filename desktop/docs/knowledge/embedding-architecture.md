# Embedding Architecture (Phase 8-C2)

> **purpose**: Define the embedding seam — DocumentChunk content becomes dense vectors.
> **follows**: `pdf-pipeline.md` + `scientific-paper-ingestion.md` (Phase 8-C1).
> **feeds**: `vector-retrieval.md` (Phase 8-C2 vector search + hybrid ranking).
> **Phase 8-C2 scope**: deterministic local feature-hash embedding. No network, no model download, no external API.

## 1. Boundary

```
 DocumentChunk (Phase 8-C0)
   │  content (string)
   ▼
 EmbeddingProvider  ←  INJECTED (interface only — no model download here)
   │  EmbeddingVector (id, dimension, values)
   ▼
 VectorStore        ←  INJECTED (interface only — no FAISS here)
   │  records indexed by chunkId
   ▼
 HybridRetriever    ←  PHASE 8-C2 glue (keyword + vector + ranking)
```

The embedding layer consumes **DocumentChunk content only**. It never touches:
- the PDF parser (Phase 8-C1)
- Document schema (Phase 8-C0)
- the tool layer (Phase 7)
- the agent runtime (Phase 8-A1)

## 2. Modules

| Module | File | Responsibility |
|--------|------|----------------|
| Embedding schema | `src/shared/knowledge/embedding-schema.ts` | `EmbeddingVector` / `EmbeddingProvider` contracts |
| Vector store schema | `src/shared/knowledge/vector-store-schema.ts` | `VectorRecord` / `VectorSearchQuery` / `VectorSearchHit` / `VectorStore` |
| Local embedding | `src/main/services/knowledge/local-embedding.ts` | deterministic feature-hash provider |
| Local vector store | `src/main/services/knowledge/local-vector-store.ts` | in-memory cosine search + filters + delete |
| Hybrid retriever | `src/main/services/knowledge/hybrid-retriever.ts` | keyword + vector fusion, ranking, citations |

## 3. Local embedding (deterministic)

- Tokenizer: Unicode runs of letters/digits/marks, with each CJK character as its own token. Bigrams of adjacent tokens are appended as `##`-joined features.
- Hashing: `FNV-1a` maps a token → `dimension` bucket; `djb2Sign` decides a `+1`/`-1` sign. Magnitude is `1/sqrt(tokens)` (comparable across lengths).
- Output is **L2-normalized** (rounded to 6 decimals) so cosine reduces to a dot product on a unit sphere.
- `embed(text)` and `embedBatch(texts, ids?)` are pure functions — same text ⇒ same vector.
- No RNG, no `Math.random`, no `Date.now`, no network.

## 4. Provider replacement

The interface is the only seam. Future phases can swap in:

| Provider | Notes |
|----------|-------|
| Local (default) | deterministic, offline, low quality |
| BGE / OpenAI / Cohere | real semantics; requires network/SDK (out of scope here) |
| Learned sparse (BM25 vectors) | in-domain |

The HybridRetriever takes the provider as an injected `EmbeddingProvider`. No other module knows which provider is in use.

## 5. Security boundary

- No credentials, model files, or network keys reach the embedding layer.
- `EmbeddingVector.values` is numeric only; `assertNoSecret` validates the vector object even though secrets can't live there — defense in depth.
- The hybrid retriever never logs query text or chunk content; only ids.

## 6. References

- `docs/knowledge/vector-retrieval.md` (Phase 8-C2 vector search + hybrid ranking)
- `src/shared/knowledge/{embedding-schema,vector-store-schema}.ts`
- `src/main/services/knowledge/{local-embedding,local-vector-store,hybrid-retriever}.ts`
- `src/shared/knowledge/document-schema.ts` (consumed: `DocumentChunk.content`)