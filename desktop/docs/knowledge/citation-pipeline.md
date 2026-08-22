# Citation Pipeline (Phase 8-C0)

> **purpose**: Define how retrieval results stay traceable to their source documents and chunks.
> **follows**: `retrieval-architecture.md` (Phase 8-C0 retrieval flow).

## 1. Source tracking

Every retrieval hit carries an immutable point-back to its source:

```
SearchResult
 ├── chunk     DocumentChunk { id, documentId, content, position }
 └── citation  CitationReference { documentId, chunkId, confidence }
```

- `citation.documentId` → the owning `Document` (title / type / source in `Document`).
- `citation.chunkId` → the exact `DocumentChunk` whose `content` was retrieved.
- `citation.confidence` → normalized deterministic score (`min(1, score/100)`, 0..1).

None of these fields can contain secrets (`assertNoSecret` guard on the citation schema).

## 2. Citation lifecycle

```
Document ingested
  └─ indexDocuments → chunks stored with documentId back-refs
        └─ search → matches produce SearchResult
              └─ citation := { documentId, chunkId, confidence }
                    └─ consumer displays/saves the citation
                          └─ resolve later via retrieve(documentId) / listChunks(documentId)
```

The citation is **self-validating by construction**:

- `chunk.documentId === citation.documentId` always (chunk is stored under its owning document).
- Re-trieving `listChunks(citation.documentId)` always contains the chunk with `citation.chunkId` (removal of a document removes its chunks atomically).
- If a chunk should ever be un-resolvable, retrieval can respond `null` — the citation still points to the right source class.

## 3. Determinism

The citation confidence is derived from a pure score function, so two identical queries over identical indexes yield byte-identical citations.

## 4. Security

- `CitationReference`, `Document`, `DocumentChunk` all run `assertNoSecret` (8 forbidden substrings).
- Citations carry only ids + a confidence number — never content metadata that could smuggle credentials.

## 5. Future (Phase 8+)

- Merged/synthesized answers will attach multiple citations (a cited-context tracker) — the `CitationReference` shape is stable for that.
- Vector hits re-use the same citation pipeline unchanged.

## 6. References

- `docs/knowledge/retrieval-architecture.md` (retrieval + chunk flow)
- `src/shared/knowledge/document-schema.ts` (`CitationReference`)
- `src/main/services/knowledge/local-retriever.ts` (citation construction)
- `src/main/services/knowledge/local-chunker.ts` (chunk ids + positions)