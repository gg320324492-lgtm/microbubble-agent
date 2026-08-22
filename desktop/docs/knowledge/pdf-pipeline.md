# PDF Pipeline (Phase 8-C1)

> **purpose**: Define the scientific PDF import pipeline — PDF text → scientific document → chunks → storage.
> **follows**: `retrieval-architecture.md` (Phase 8-C0). **feeds**: `scientific-paper-ingestion.md` (Phase 8-C1 mapping).
> **Phase 8-C1 scope**: deterministic text-based parsing. NO OCR, NO embeddings, NO LLM.

## 1. Import flow

```
 PDF paper (text layer)
        │  raw text with page boundaries
        ▼
 TextExtractor (LinePageExtractor: \f  or  @@PAGE:N@@)
        │  page strings[]
        ▼
 LocalPdfParser (ScientificDocumentParser)
   ├─ extractMetadata()  → title / authors / year / journal (deterministic heuristics)
   └─ extractSections()  → ParsedSection[] (title / level / content / pageStart / pageEnd)
        │  ParsedPDF { document, sections }
        ▼
 DocumentImporter
   ├─ toDocument()       → Phase 8-C0 Document (type: paper, metadata carries content+bbox)
   ├─ toScientificChunks() → section/page-tagged DocumentChunk[]
   └─ citations[]        → CitationReference { documentId, chunkId, page, confidence }
        ▼
 Storage (LocalRetriever.indexDocuments — search chunks)
```

## 2. Module map

| Module | File | Responsibility |
|--------|------|----------------|
| PDF schema | `src/shared/knowledge/pdf-schema.ts` | `PDFDocument` / `PDFMetadata` / `ParsedSection` + validators |
| Parser schema | `src/shared/knowledge/parser-schema.ts` | `ScientificDocumentParser` interface + `ParsedPDF` |
| Text extractor | `src/main/services/knowledge/text-extractor.ts` | page-boundary splitting (`\f` / `@@PAGE:N@@`) |
| Local PDF parser | `src/main/services/knowledge/pdf-parser.ts` | deterministic metadata + section detection |
| Document importer | `src/main/services/knowledge/document-importer.ts` | Paper → Document → chunks → citations → storage |

## 3. Metadata extraction (deterministic)

| Field | Rule |
|-------|------|
| title | first non-noise line (not a page number / DOI/URL), ≤ 240 chars, trailing periods stripped |
| authors | name-like lines after the title until `abstract`/`keywords`/numeric heading; lines split on `,` / ` and `; parentheticals stripped; deduped, ≤ 12 |
| year | first `19xx`/`20xx` not on a standalone page-number line (1900–2099) |
| journal | first header-region line matching a known journal word (`journal`, `letters`, `nature`, `science`, `applied`, …); trailing `(YYYY)` stripped |

All absent when the heuristics find nothing — parsing is never fatal.

## 4. Section extraction (deterministic)

Headings are detected in priority order (each must be ≤ 90 chars and not end with `.`):

| Form | Example | Level |
|------|---------|-------|
| numeric | `1. Introduction`, `2.1 Methods` | segments count (cap 3) |
| roman | `I. Introduction`, `II Methods` | 1 |
| keyword | `Abstract`, `References`, `Materials and Methods`, … (18 keywords) | 1 |
| full-uppercase | `RESULTS AND DISCUSSION` | 1 |

- Lines that are standalone page numbers, `DOI:`/URLs, or blank are noise and skipped.
- A heading starts a new section; its content runs until the next heading.
- `pageStart` / `pageEnd` come from the page boundary of the heading / last content line.
- No headings found ⇒ one fallback section `{ title: 'body', level: 0, … }`.

## 5. Chunk + citation flow

- `DocumentImporter.toScientificChunks` emits one chunk per section (long sections re-split at 800 chars, deterministic), each tagged `metadata.section` + `metadata.page` (the section's `pageStart`).
- Every chunk gets a `CitationReference { documentId, chunkId, page, confidence: 1 }` — page pinned from the source section.
- `LocalRetriever` independently indexes the `Document` content for keyword search; its own chunks and searches return citations via the C0 pipeline.

## 6. Determinism

- Plan/ids: `pdf:<contentHash(text)>` (djb2). Same text ⇒ same document id.
- `createdAt` defaults to `0` so imports are byte-reproducible; pass a timestamp to override.
- No `Math.random` / `Date.now` in the pipeline.

## 7. Future OCR extension (Phase 8+)

- `TextExtractor` is the only seam that touches raw PDF bytes. A real renderer (pdf.js) or an OCR engine (tesseract) can be injected without changing the parser/importer.
- Metadata heuristics may be replaced by a small schema-aware classifier; section detection can be upgraded to heading-font-distance clustering.

## 8. References

- `docs/knowledge/scientific-paper-ingestion.md` (Paper → Document mapping + citation lifecycle)
- `docs/knowledge/retrieval-architecture.md` (Phase 8-C0 retrieval + chunk flow)
- `src/shared/knowledge/{pdf-schema,parser-schema,document-schema}.ts`
- `src/main/services/knowledge/{text-extractor,pdf-parser,document-importer}.ts`