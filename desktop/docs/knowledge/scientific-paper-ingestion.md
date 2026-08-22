# Scientific Paper Ingestion (Phase 8-C1)

> **purpose**: Document the Paper → Document mapping and the citation lifecycle for imported PDFs.
> **follows**: `pdf-pipeline.md` (Phase 8-C1 import flow).

## 1. Paper → Document mapping

| PDF paper (PDFDocument / PDFMetadata) | Phase 8-C0 Document |
|---------------------------------------|---------------------|
| id (content hash) | `id` |
| type — always `paper` | `type` |
| metadata.title ?? filename | `title` |
| filename | `source` |
| metadata.title | `metadata.title` |
| metadata.authors | `metadata.authors` |
| metadata.year | `metadata.year` |
| metadata.journal | `metadata.journal` |
| pages count | `metadata.pages` |
| sections (title/level/pageStart/pageEnd) | `metadata.sections[]` |
| section content (joined by blank lines) | `metadata.content` (what the retriever chunks) |
| options.createdAt ?? 0 | `createdAt` |

The `document.type === 'paper'` plus `metadata.sections` gives the agent enough
structure to reason about *where* in the paper a fact sits.

## 2. Chunks produced

Two chunk views serve two consumers:

1. **Retriever search chunks** — `LocalRetriever.indexDocuments([document])` slices
   `metadata.content` with the injected `Chunker`. These power keyword search.
2. **Scientific citation chunks** — `DocumentImporter.toScientificChunks` emits one
   chunk per section (re-split at 800 chars), tagged `metadata.section` + `metadata.page`.

## 3. Citation lifecycle

```
importText(text)
  → parsed (sections tagged with pages)
  → document (Paper mapping above)
  → scientific chunks (section/page)
  → citations: { documentId, chunkId, page, confidence: 1 }
       |
       ▼
  report / RAG answer cites { documentId, chunkId, page }
       |
       ▼
  resolve source: importer/retriever → chunk.content + document.title/journal
```

- `documentId`  → the imported paper (title / journal / year).
- `chunkId`     → an exact section chunk (`<docId>#s<position>`).
- `page`        → the 1-based source page from the section's `pageStart`.
- `confidence`  → the importer sets `1` (this is a *source* reference, not a
  fuzzy match — retrieval scoring adds its own confidence later).

The citation is stable across re-imports of the same text (content-hash id) and
never contains secrets (`assertNoSecret` guards every schema).

## 4. Determinism guarantees

- Same PDF text ⇒ same `Document` id, same chunks, same citations.
- `createdAt: 0` by default keeps imports byte-reproducible; pass `createdAt` to stamp wall-clock time explicitly.

## 5. References

- `docs/knowledge/pdf-pipeline.md` (import flow + section extraction)
- `src/shared/knowledge/document-schema.ts` (`CitationReference.page`)
- `src/main/services/knowledge/document-importer.ts`
- `src/main/services/knowledge/pdf-parser.ts` + `text-extractor.ts`