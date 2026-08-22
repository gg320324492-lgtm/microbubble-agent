# Retrieval Architecture (Phase 8-C0)

> **purpose**: Define the knowledge retrieval foundation — how scientific documents become searchable chunks that feed the research agent with citable context.
> **Phase 8-C0 scope**: in-memory keyword retrieval, deterministic ranking, metadata filters, citations. NO vector database, NO embeddings, NO RAG generation.

## 1. Retrieval pipeline

```
 Scientific Knowledge Assets
   (Paper / Experiment / Dataset / Equipment / Report / Manual)
        │  Document { id, type, title, source, metadata, createdAt }
        ▼
 Chunker (LocalChunker, deterministic slices)
        │  DocumentChunk[] { id, documentId, content, position, metadata }
        ▼
 LocalRetriever (in-memory index)
   - keyword matching (camel/whitespace + CJK-aware tokenization)
   - metadata filtering (document.metadata / chunk.metadata / document.type)
   - deterministic ranking
        │  SearchResult[] { chunk, score, citation }
        ▼
 Context  ────────►  Research Agent (Phase 8 planner consumes Context)
```

## 2. Module map

| Module | File | Responsibility |
|--------|------|----------------|
| Document schema | `src/shared/knowledge/document-schema.ts` | `Document` / `DocumentType` / `DocumentChunk` / `CitationReference` + validators |
| Chunker schema | `src/shared/knowledge/chunker-schema.ts` | `Chunker` interface (`splitDocument` / `mergeChunks`) + `ChunkMetadata` |
| Retriever schema | `src/shared/knowledge/retriever-schema.ts` | `KnowledgeRetriever` interface (`search` / `retrieve` / `list`) + `SearchQuery` / `SearchResult` |
| Local chunker | `src/main/services/knowledge/local-chunker.ts` | deterministic slice-based `Chunker` implementation |
| Local retriever | `src/main/services/knowledge/local-retriever.ts` | in-memory index + keyword search + filters + ranking |

## 3. Chunk flow

1. A `Document` carries its source text under `metadata.content` (plus hints `section` / `page`).
2. `LocalChunker.splitDocument` slices `content` into `maxChars`-sized chunks (default 400), cutting exactly at character boundaries by default:
   - `overlapChars = 0` ⇒ **round-trip exact**: `mergeChunks(split(content)) === content`
   - `preserveWords = true` backs cuts up to whitespace (separators stay as the next chunk's head, so round-trip still holds; overlap is disabled in this mode)
   - `overlapChars > 0` adds overlap between consecutive chunks (not round-trip safe by design)
3. Each chunk gets `id = "<docId>#<index>"`, an increasing `position`, and inherited `metadata.section` / `metadata.page`.
4. `LocalRetriever.indexDocuments` is **atomic**: all documents are validated and chunked first; only then is any state mutated. Re-indexing a document id replaces its previous chunks.
5. `mergeChunks` reconstructs a single string ordered by `position`.

## 4. Search + ranking (deterministic)

- `tokenizeQuery`: lowercase, split on runs of non-letter/non-digit characters (Unicode-aware, so Chinese terms survive whole).
- `scoreChunk(queryTerms, content, position)`:
  ```
  0                        if NO query term appears in the chunk
  coverage*100             coverage = matchedTerms / queryTerms
  + min(20, occurrences)*0.5
  + 2/(position + 1)       earlier chunks win ties
  ```
  Pure function — same inputs ⇒ same score.
- Results sort by `score` desc, then `documentId`, then `position` (all tie-breaks deterministic).
- `limit` truncates when > 0; `filters` are ANDed with the text match.

## 5. Metadata filtering

`filters: { type: 'paper', tags: 'tc', year: 2024 }` — every entry must match:

| Key | Matched against |
|-----|-----------------|
| `type` | `document.type` |
| any other key | `document.metadata[key]` OR `chunk.metadata[key]` (strict equality; arrays match if they contain the value) |

## 6. Boundary (Phase 8-C0 strict)

- Retriever **consumes** Documents; it never modifies storage (Phase 7-B0 providers are a separate seam).
- Retriever **does not** modify the planner or the runtime. It produces `SearchResult[]` — a future phase converts these into `PlannerContext`-style context.
- No `model-provider` / `auth` / `backend` imports; no `Math.random` / `Date.now`.

## 7. Future vector extension (Phase 8+)

- `Chunker` interface already isolates chunk generation — a semantic chunker (header-aware, sentence-based, embedding-bounded) can replace `LocalChunker` without touching the retriever.
- `scoreChunk` is the only scoring point — a vector scorer can be added as a second ranking signal while keyword remains the deterministic fallback.
- `CitationReference` is stable, so vector hits get the same citation pipeline.

## 8. References

- `docs/knowledge/citation-pipeline.md` (source tracking + citation lifecycle)
- `src/shared/knowledge/{document-schema,chunker-schema,retriever-schema}.ts`
- `src/main/services/knowledge/{local-chunker,local-retriever}.ts`
- `src/shared/knowledge/schemas.ts` + `storage.ts` (Phase 7-A0 / 7-B0, consumed)