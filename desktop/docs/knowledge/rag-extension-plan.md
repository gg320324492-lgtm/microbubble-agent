# RAG Extension Plan (Phase 7-A0)

> **purpose**: Define the future RAG (Retrieval-Augmented Generation) pipeline that will plug into the Knowledge Layer. Phase 7-A0 ships ONLY the plan — no implementation.
> **follows**: `knowledge-layer-architecture.md` (Phase 7-A0 Step 5).
> **Phase 7-A0 strict**: Knowledge Layer does NOT depend on a specific LLM or vector store.

## 1. Scope (Phase 7-A0 frozen)

This document defines:
- Future RAG pipeline stages
- LLM-agnostic boundary
- Storage pluggability
- Knowledge ↔ RAG ↔ Agent data flow

Phase 7-A0 ships ONLY the plan. Phase 7+ ships the implementation.

## 2. Pipeline overview (Phase 7+)

```
                        ┌─────────────────┐
                        │       PDF       │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │     Parser      │   Phase 7+
                        │ (PDF / DOCX)    │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │     Chunker     │   Phase 7+
                        │ (semantic split)│
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Embedder     │   Phase 7+
                        │ (LLM-agnostic)  │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Vector Store   │   Phase 7+
                        │ (pgvector/FAISS)│
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │    Retriever    │   Phase 7+
                        │  (top-K search) │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Research Agent  │   Phase 7+
                        │ (uses Model LLM)│
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   StreamEvent   │   Phase 3-B0 (frozen)
                        │   (chat output) │
                        └─────────────────┘
```

Each stage is a Phase 7+ module. Phase 7-A0 ships ONLY the contracts.

## 3. LLM-agnostic boundary (Phase 7-A0 strict)

The Knowledge Layer and RAG pipeline MUST NOT depend on any specific LLM.

```ts
// Phase 7-A0: Embedder contract (LLM-agnostic)
interface Embedder {
  embed(text: string): Promise<number[]>
  readonly dimension: number
  readonly modelId: string       // e.g. 'bge-m3' | 'qwen3-embed' | 'text-embedding-3-small'
}

// Phase 7+ may have multiple embedder implementations:
//   BgeM3Embedder       (local)
//   OpenAIEmbedder       (cloud)
//   OllamaEmbedder       (local)
//
// All conform to the Embedder interface.
```

The Knowledge Layer accepts ANY `Embedder` instance. The Model Provider Layer (Phase 6-A3) is the ONLY place where specific LLM SDKs are imported.

## 4. Storage pluggability (Phase 7+)

```ts
interface VectorStore {
  upsert(id: string, vector: number[], metadata: Record<string, unknown>): Promise<void>
  query(vector: number[], topK: number, filter?: Record<string, unknown>): Promise<Array<{ id: string; score: number; metadata: Record<string, unknown> }>>
  delete(id: string): Promise<void>
}

// Phase 7+ implementations:
//   PgVectorStore     (production)
//   FaissVectorStore   (in-process, dev/test)
//   QdrantVectorStore  (cloud)
```

Phase 7-A0 ships ONLY the interface. Phase 7+ picks implementations.

## 5. Parser pluggability (Phase 7+)

```ts
interface DocumentParser {
  parse(input: Buffer | string): Promise<ParsedDocument>
}

interface ParsedDocument {
  text: string
  metadata: {
    pages?: number
    title?: string
    authors?: string[]
    doi?: string
    [key: string]: unknown
  }
}

// Phase 7+ implementations:
//   PdfParser     (PDF)
//   DocxParser    (Word)
//   HtmlParser    (web)
```

The ParsedDocument's `metadata` follows Phase 7-A0's `Paper` schema (best-effort extraction).

## 6. Chunker pluggability (Phase 7+)

```ts
interface Chunker {
  chunk(doc: ParsedDocument): Promise<Chunk[]>
}

interface Chunk {
  text: string
  metadata: {
    paperId?: string
    sectionTitle?: string
    pageNumber?: number
    startOffset: number
    endOffset: number
  }
}

// Phase 7+ strategies:
//   FixedSizeChunker       (e.g. 512 tokens)
//   SemanticChunker        (paragraph + heading aware)
//   SlidingWindowChunker    (overlap for context)
```

## 7. Retriever pluggability (Phase 7+)

```ts
interface Retriever {
  retrieve(query: string, options?: { topK?: number; filter?: Record<string, unknown> }): Promise<RetrievedChunk[]>
}

interface RetrievedChunk {
  chunk: Chunk
  score: number
  metadata: Record<string, unknown>
}

// Phase 7+ strategies:
//   VectorOnlyRetriever      (pure cosine similarity)
//   HybridRetriever           (vector + BM25)
//   GraphAugmentedRetriever   (vector + graph traversal)
```

## 8. Knowledge ↔ RAG ↔ Agent data flow

```
[User chat message]
    │
    ▼
[chat-stream.service.ts]   ← Phase 3-B0 frozen (no changes)
    │
    ▼
[Research Agent]            ← Phase 7+
    │
    │ 1. Search Knowledge
    ▼
[KnowledgeProvider.search]  ← Phase 7+
    │
    │ 2. Retrieve relevant chunks
    ▼
[Retriever.retrieve]        ← Phase 7+
    │
    │ 3. Build context
    ▼
[Prompt = user_msg + chunks + system]
    │
    ▼
[Model LLM call]            ← Phase 6-A6 (no changes)
    │
    ▼
[StreamEvent response]      ← Phase 3-B0 frozen
```

Key principle: **Knowledge and Model are siblings**, not parent-child.

```
                  ┌──────────────┐
                  │   Research   │
                  │    Agent     │
                  └──────┬───────┘
              ┌─────────┴─────────┐
              ▼                   ▼
       ┌─────────────┐     ┌─────────────┐
       │  Knowledge  │     │   Model     │
       │   Layer     │     │   Layer     │
       └─────────────┘     └─────────────┘
        (Phase 7+)            (Phase 6, frozen)
```

## 9. Knowledge embedding strategy (Phase 7+)

When the Retriever returns chunks, the Agent constructs context like:

```ts
{
  userMessage: "How does ozone degrade TC?",
  knowledgeContext: [
    { paperId: 'paper:abc123', title: 'O3 degradation of TC', snippet: '...' },
    { paperId: 'paper:def456', title: 'Microbubble ozonation', snippet: '...' }
  ],
  citations: [
    { paperId: 'paper:abc123', source: 'paper', confidence: 'verified' }
  ]
}
```

The `Citation[]` shape comes from Phase 7-A0. Phase 7+ wires it into the chat message metadata.

## 10. RAG and the Phase 6 Model Layer

The RAG pipeline uses the Model Layer ONLY for embedding (via `Embedder` interface) and answer generation (via the standard `runProviderRuntime` path). It does NOT bypass Phase 6 security:

- `Embedder.embed()` is main-process-only (no LLM key crossing IPC)
- Citation building happens main-side
- Renderer receives only `Citation[]` shapes (non-secret)

## 11. Phase 7-A0 strict

- Knowledge Layer MUST NOT depend on a specific LLM SDK
- Knowledge Layer MUST NOT depend on a specific vector store
- Knowledge Layer MUST NOT depend on a specific PDF parser
- Knowledge Layer MUST NOT add new IPC channels (Phase 7+ may add)
- Knowledge Layer MUST NOT touch the Model Layer directly (communication via Research Agent)
- Knowledge Layer MUST NOT bypass Phase 6-A2 secret storage (apiKey NEVER in knowledge entities)

## 12. Phase 7+ milestones

Phase 7+ timeline (NOT in this commit):

- **Phase 7-B**: SQL storage (Paper / Experiment / Equipment tables)
- **Phase 7-C**: Vector storage (pgvector / FAISS)
- **Phase 7-D**: PDF parser + Chunker
- **Phase 7-E**: Embedder pluggability + local BGE-M3
- **Phase 7-F**: Retriever pluggability + HybridRetriever
- **Phase 7-G**: Research Agent orchestration (uses Model Layer)
- **Phase 7-H**: Citation in chat message metadata + renderer panel
- **Phase 7-I**: Knowledge UI (search / browse / detail views)

Phase 7-A0 only ships the schema contracts + this plan. No Phase 7+ work in this commit.

## 13. References

- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 Step 2)
- `docs/knowledge/knowledge-relationship-model.md` (Phase 7-A0 Step 3)
- `docs/knowledge/scientific-metadata-standard.md` (Phase 7-A0 Step 4)
- `docs/knowledge/knowledge-layer-architecture.md` (Phase 7-A0 Step 5)
- `desktop/src/shared/knowledge/schemas.ts` (entity + metadata contracts)

## Status (2026-08-22 Phase 7-A0)

- 7-stage RAG pipeline documented (PDF → Parser → Chunker → Embedder → VectorStore → Retriever → ResearchAgent)
- 5 pluggable interfaces sketched (Embedder / VectorStore / DocumentParser / Chunker / Retriever)
- LLM-agnostic boundary contract defined
- Storage pluggability contract defined
- Knowledge ↔ RAG ↔ Agent data flow documented
- 0 implementations (Phase 7-A0 ships ONLY the plan + contracts)
- Doc complete (13 sections)
