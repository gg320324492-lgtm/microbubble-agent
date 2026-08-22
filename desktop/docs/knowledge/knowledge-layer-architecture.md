# Knowledge Layer Architecture (Phase 7-A0)

> **purpose**: Define the architecture of the Knowledge Layer that wraps the schema contracts from `scientific-domain-model.md`. This phase is **architecture-only** — NO implementation of storage, NO RAG, NO UI.
> **follows**: `scientific-domain-model.md` + `knowledge-relationship-model.md` + `scientific-metadata-standard.md` (Phase 7-A0 Steps 2/3/4).

## 1. Scope (Phase 7-A0 frozen)

Phase 7-A0 ships:
- 6 entity types + 3 metadata types in `desktop/src/shared/knowledge/schemas.ts`
- Structural validators (`isValidPaper`, `isValidExperiment`, etc.)
- `isValidRelationship(parent, childId, kind)`
- `KnowledgeProvider` interface (Phase 7+ implementation sketch)

Phase 7-A0 explicitly does **NOT** ship:
- ❌ PDF parser
- ❌ RAG pipeline
- ❌ Vector database
- ❌ External database
- ❌ User authentication
- ❌ Knowledge UI

## 2. Layer diagram (Phase 7-A0)

```
                       Research Agent
                            │
                            ▼
                    Knowledge Retrieval
                            │
                            ▼
              ┌─────────────┼─────────────┐
              │             │             │
        Paper KB    Experiment KB    Equipment KB
              │             │             │
              └─────────────┼─────────────┘
                            │
                  (future storage backends)
                            │
            ┌───────────────┼───────────────┐
            │               │               │
        Vector DB       Graph DB       SQL Storage
        (Phase 7+)     (Phase 7+)     (Phase 7+)
```

Three independent knowledge bases (Paper / Experiment / Equipment) plus derived views (Dataset / Figure / ResearchProject) follow the Phase 7-A0 schemas. Phase 7+ may split these into separate stores.

## 3. KnowledgeProvider interface (Phase 7+ sketch)

```ts
interface KnowledgeProvider {
  search(query: KnowledgeQuery): Promise<KnowledgeSearchResult>
  retrieve(entityId: string): Promise<KnowledgeEntity | null>
  link(sourceId: string, targetId: string, kind: RelationshipKind): Promise<void>
  query(cypherOrSql: string): Promise<KnowledgeEntity[]>
}

interface KnowledgeQuery {
  text?: string
  filters?: {
    entityType?: 'paper' | 'experiment' | 'equipment' | 'dataset' | 'figure' | 'project'
    researchField?: string
    keywords?: string[]
    dateRange?: { from: number; to: number }
  }
  limit?: number
}

interface KnowledgeSearchResult {
  hits: Array<{
    entity: KnowledgeEntity
    score: number
    snippet?: string
  }>
  total: number
}

type KnowledgeEntity = Paper | Experiment | Equipment | Dataset | Figure | ResearchProject
type RelationshipKind = 'paper' | 'experiment' | 'equipment' | 'dataset' | 'figure' | 'project'
```

Phase 7-A0 ships ONLY the interface shape. Implementation is Phase 7+.

## 4. Storage independence (Phase 7-A0 strict)

The Knowledge Layer does NOT depend on:

| Layer | Why independent |
|-------|------------------|
| Model Layer (`desktop/src/main/services/model-provider/`) | Knowledge is data, Model is LLM runtime |
| Auth (`auth.ts`, `auth.service.ts`) | Knowledge entities are public science; no auth state |
| Chat Runtime (`chat-stream.service.ts`) | Knowledge is persistent; streams are ephemeral |
| Legacy FastAPI (`backend/`) | New schema; old backend has its own domain |

The Knowledge Layer **only depends on**:
- `desktop/src/shared/knowledge/schemas.ts` (Phase 7-A0)
- `desktop/src/shared/knowledge/queries.ts` (Phase 7+ future)

This is verified at runtime by import-graph tests (Phase 7+).

## 5. Future extension points (Phase 7+)

### 5.1 RAG pipeline (Phase 7+)

```
PDF → Parser → Chunker → Embedder → VectorStore → Retriever → ResearchAgent
```

The Knowledge Layer's `KnowledgeProvider.search` is the consumer of the Retriever's output. The Retriever itself is a Phase 7+ component.

### 5.2 SQL storage (Phase 7+)

Tables (sketch — NOT IMPLEMENTED):

```
papers(id, title, journal, year, doi, ...)
authors(id, name)
paper_authors(paper_id, author_id, ord)
paper_keywords(paper_id, keyword)
experiments(id, name, research_topic, paper_id)
experiment_equipment(experiment_id, equipment_id)
experiment_parameters(experiment_id, name, value, unit)
experiment_measurements(experiment_id, metric, value, method, instrument)
datasets(id, name, experiment_id, source, ...)
figures(id, type, source, dataset_id, paper_id)
research_projects(id, title, topic)
project_papers(project_id, paper_id)
project_experiments(project_id, experiment_id)
project_datasets(project_id, dataset_id)
```

Phase 7-A0 ships the schema types. Phase 7+ ships the migration.

### 5.3 Graph storage (Phase 7+)

Nodes: Paper / Experiment / Equipment / Dataset / Figure / ResearchProject
Edges:
- `(Paper)-[:REFERENCES]->(Experiment)`
- `(Experiment)-[:USES]->(Equipment)`
- `(Experiment)-[:GENERATES]->(Dataset)`
- `(Dataset)-[:PRODUCES]->(Figure)`
- `(Project)-[:CONTAINS]->(Paper|Experiment|Equipment|Dataset)`

Phase 7-A0 ships the validator. Phase 7+ ships the runtime.

### 5.4 Vector storage (Phase 7+)

| Entity | Embedded field |
|--------|---------------|
| Paper | `abstract` |
| Experiment | `objective` + concatenated `parameters.name` |
| Equipment | `specifications` map joined to text |
| Dataset | `source` + `variables` joined to text |
| Figure | `caption` |
| ResearchProject | `topic` + concatenated titles |

Phase 7-A0 ships NO embeddings. Phase 7+ ships the embedding model + vector store.

## 6. Phase 7+ interface contracts (Phase 7-A0 frozen)

The interfaces below are Phase 7-A0 **contracts** that Phase 7+ must respect:

```ts
// Read API (Phase 7+)
interface ReadAPI {
  getPaper(id: string): Promise<Paper | null>
  getExperiment(id: string): Promise<Experiment | null>
  getEquipment(id: string): Promise<Equipment | null>
  getDataset(id: string): Promise<Dataset | null>
  getFigure(id: string): Promise<Figure | null>
  getResearchProject(id: string): Promise<ResearchProject | null>
}

// Search API (Phase 7+)
interface SearchAPI {
  searchByKeyword(keyword: string, limit?: number): Promise<KnowledgeEntity[]>
  searchByEntityType(type: EntityType, limit?: number): Promise<KnowledgeEntity[]>
  // Phase 7+ will add: searchByEmbedding / hybridSearch / facetSearch
}

// Write API (Phase 7+)
interface WriteAPI {
  savePaper(paper: Paper): Promise<void>
  saveExperiment(exp: Experiment): Promise<void>
  // ... one per entity type
  linkExperimentToPaper(expId: string, paperId: string): Promise<void>
  // ... one per relationship kind
}
```

Phase 7-A0 ships ONLY type definitions. Phase 7+ ships implementations.

## 7. Knowledge ↔ Chat integration (Phase 7+)

When a chat message references a `Paper.id`, the renderer (Phase 7+) will:

1. Read the message metadata `citations: Citation[]` (Phase 7-A0 frozen)
2. For each `Citation.paperId`, retrieve `Paper` via `KnowledgeProvider.retrieve(paperId)`
3. Display a "References" panel with the paper title + abstract + figure thumbnails
4. The chat answer itself is unaffected (the chat-stream.service.ts is unchanged)

Phase 7-A0 ships the `Citation` type. Phase 7+ ships the renderer integration.

## 8. Knowledge ↔ Model integration (Phase 7+)

When the Research Agent needs context for a chat answer:

1. The agent receives a chat request from the user
2. The agent calls `KnowledgeProvider.search({ text: userMessage })`
3. The top-K entities are added to the LLM prompt as context
4. The LLM generates a response citing the entities (via `Citation`)

The Knowledge Layer does NOT call the LLM. The Model Layer does NOT call the Knowledge Layer directly. They communicate via `ResearchAgent` orchestration (Phase 7+).

## 9. Phase 7-A0 strict forbids

- ❌ Import anything from `desktop/src/main/services/model-provider/`
- ❌ Import anything from `desktop/src/main/services/auth/`
- ❌ Import anything from `desktop/src/renderer/src/stores/{auth,user}.ts`
- ❌ Add Electron IPC handlers in Phase 7-A0
- ❌ Add renderer stores / components
- ❌ Add a database connection
- ❌ Add a vector store connection
- ❌ Add a PDF parser
- ❌ Add user authentication
- ❌ Persist any data to disk in Phase 7-A0

## 10. Phase 7-A0 file manifest

```
desktop/src/shared/knowledge/
  - schemas.ts            (NEW)  entity + metadata types + validators

desktop/docs/knowledge/
  - scientific-domain-model.md
  - knowledge-relationship-model.md
  - scientific-metadata-standard.md
  - knowledge-layer-architecture.md   (this file)
  - rag-extension-plan.md             (Phase 7-A0 Step 6)

desktop/tests/unit/
  - knowledge-schema.test.ts          (Phase 7-A0 Step 7)
```

## 11. References

- `docs/knowledge/scientific-domain-model.md` (Step 2)
- `docs/knowledge/knowledge-relationship-model.md` (Step 3)
- `docs/knowledge/scientific-metadata-standard.md` (Step 4)
- `docs/knowledge/rag-extension-plan.md` (Step 6 — next doc)
- `docs/desktop-conversion/live-e2e-validation.md` (Phase 6-D end-state — boundary reference)

## Status (2026-08-22 Phase 7-A0)

- `schemas.ts` — 6 entity types + 3 metadata types + 10 validators + 1 relationship validator
- `KnowledgeProvider` interface (Phase 7+ sketch — read / search / write API sketched)
- Read / Search / Write API contracts defined for Phase 7+ implementation
- 0 dependencies on Model / Auth / Chat / Legacy layers
- Doc complete (11 sections)
