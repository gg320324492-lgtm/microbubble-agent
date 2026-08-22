# Knowledge Relationship Model (Phase 7-A0)

> **purpose**: Define the relationships between scientific entities. This phase is **architecture-only** — no SQL, no graph DB, no RAG pipeline.
> **follows**: `scientific-domain-model.md` (Phase 7-A0 Step 2).
> **Phase 7-A0 strict**: relationship validity is a structural check, NOT a database lookup.

## 1. Scope (Phase 7-A0 frozen)

Six relationship kinds:

| Source | Direction | Target | Kind string |
|--------|-----------|--------|-------------|
| `ResearchProject` | contains | `Paper` | `paper` |
| `ResearchProject` | contains | `Experiment` | `experiment` |
| `ResearchProject` | contains | `Equipment` | `equipment` |
| `ResearchProject` | contains | `Dataset` | `dataset` |
| `Paper` | references | `Experiment` | `experiment` |
| `Experiment` | uses | `Equipment` | `equipment` |
| `Experiment` | generates | `Dataset` | `dataset` |
| `Dataset` | produces | `Figure` | `figure` |

All relationships are validated via `isValidRelationship(parent, childId, kind)`.

## 2. ER diagram

```
                            ┌────────────────────┐
                            │  ResearchProject   │
                            │   - members[]       │
                            │   - topic           │
                            └────────┬───────────┘
                                     │ contains (1:N each)
            ┌────────────────────────┼─────────────────────────┐
            │                        │                         │
            ▼                        ▼                         ▼
    ┌──────────────┐         ┌──────────────┐          ┌──────────────────┐
    │    Paper     │         │  Equipment   │          │     Dataset      │
    │ - authors[]  │         │ - specs{}    │          │ - variables[]    │
    │ - journal    │         │ - type       │          │ - units{}        │
    │ - year       │         └──────┬───────┘          │ - samples        │
    └──────┬───────┘                │ used by                └────────┬─────────┘
           │ references              │                              │ produces
           ▼                        │                              ▼
    ┌──────────────┐                │                       ┌──────────────────┐
    │ Experiment   │ ◀──────────────┘                       │     Figure       │
    │ - params[]   │                                        │ - type (SEM/CFD) │
    │ - measurements[]                                       │ - source         │
    └──────┬───────┘                                        └──────────────────┘
           │ generates
           ▼
    (back to Dataset)
```

## 3. Relationship details

### 3.1 `ResearchProject` contains `Paper` / `Experiment` / `Equipment` / `Dataset`

```
ResearchProject.papers[]       -> Paper.id
ResearchProject.experiments[]  -> Experiment.id
ResearchProject.datasets[]     -> Dataset.id
(Equipment is project-scoped too, via Experiment.equipment[])
```

A `ResearchProject` is a top-level container. All sub-entities reference it indirectly through their `equipment` / `paper` / `experiment` / `dataset` ID chains.

### 3.2 `Paper` references `Experiment`

```
Paper.relatedExperiments[] -> Experiment.id
```

Used when a paper documents an experiment. The `paperId` field on `Citation` references `Paper.id`, so the chain is: chat message → Citation → Paper → Experiment (the protocol the user might want to re-run).

### 3.3 `Experiment` uses `Equipment`

```
Experiment.equipment[] -> Equipment.id
```

Many-to-one: an experiment may use multiple equipment; an equipment may serve multiple experiments. The reverse direction (`Equipment.relatedExperiments[]`) is a denormalized cache for search.

### 3.4 `Experiment` generates `Dataset`

```
Dataset.source -> Experiment.id (when source === 'experiment:exp:xxx')
```

One experiment may generate multiple datasets (e.g. raw + processed).

### 3.5 `Dataset` produces `Figure`

```
Figure.relatedDataset -> Dataset.id
Figure.relatedPaper   -> Paper.id   (optional)
```

A figure may link to either a dataset (raw data) or a paper (published version). The renderer (Phase 7+) chooses which to display based on availability.

## 4. Relationship validator

```ts
isValidRelationship(
  parent: { id: string } | null | undefined,
  childId: string,
  kind: 'paper' | 'experiment' | 'equipment' | 'dataset' | 'figure' | 'project'
): boolean
```

Returns `true` only if:
- `parent` exists and has a non-empty `id`
- `childId` is a non-empty string
- `kind` is one of the 6 valid kinds
- `parent.id !== childId` (no self-reference)

`isValidRelationship` is the **only structural check** Phase 7-A0 ships. Database-level referential integrity is deferred to the storage layer (Phase 7+).

## 5. Future database mapping (Phase 7+ sketch — NOT IMPLEMENTED)

```
+------------------+      +-------------------+
|      Paper      |      |   Experiment      |
+------------------+      +-------------------+
| id (PK)          |<-+   | id (PK)           |
| title            |  |   | name              |
| authors (JSON)   |  |   | researchTopic     |
| journal          |  +---| paper_id (FK)     |
| year             |      | system            |
| doi (unique)     |      | equipment_ids[]   |
| keywords (JSON)  |      | parameters (JSON) |
| research_field   |      | measurements(JSON)|
| abstract         |      +-------------------+
| ...              |              |
+------------------+              |
                                   | 1:N
                                   v
                          +-------------------+
                          |      Dataset      |
                          +-------------------+
                          | id (PK)           |
                          | experiment_id(FK) |
                          | variables (JSON)  |
                          | units (JSON)      |
                          | ...               |
                          +-------------------+
```

Key migration constraints (Phase 7+):
- `Paper.doi` UNIQUE (when present)
- `Experiment.equipment_ids[]` resolves to `Equipment.id` via join table
- `Dataset.source` parses `experiment:exp:xxx` → FK to `Experiment.id`
- `Figure.related_*` nullable; both can be set

## 6. Graph DB mapping (Phase 7+ sketch)

```
(Paper)-[:REFERENCES]->(Experiment)
(Paper)-[:PRODUCED_BY]->(Project)
(Experiment)-[:USES]->(Equipment)
(Experiment)-[:GENERATES]->(Dataset)
(Dataset)-[:PRODUCES]->(Figure)
(Project)-[:CONTAINS]->(Paper|Experiment|Equipment|Dataset)
```

Use cases Phase 7+ will support:
- "What experiments reference this paper?" → graph traversal
- "Which equipment is shared across projects?" → multi-hop query
- "Show all figures for project X" → Project → Experiment → Dataset → Figure

## 7. Vector DB mapping (Phase 7+ sketch — NOT IMPLEMENTED)

```
Paper abstract      -> embedding (768-d)
Experiment params   -> embedding (768-d)
Dataset description -> embedding (768-d)
Equipment specs     -> embedding (768-d)
```

Phase 7-A0 strict: NO embedding computation happens in this phase. The mapping is documented only.

## 8. Phase 7-A0 strict

- `isValidRelationship` does NOT do database lookups
- Knowledge Layer MUST NOT depend on Model Layer / Chat Layer
- All entity IDs follow `^[a-zA-Z][a-zA-Z0-9_-]{1,63}$`
- No `apiKey` / `token` / `cipher` in any relationship field
- Phase 7-A0 ships ONLY the structural validators; storage is Phase 7+

## 9. References

- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 Step 2)
- `docs/knowledge/scientific-metadata-standard.md` (Phase 7-A0 Step 4)
- `docs/knowledge/knowledge-layer-architecture.md` (Phase 7-A0 Step 5)

## Status (2026-08-22 Phase 7-A0)

- 8 relationship kinds documented
- ER diagram + Graph DB mapping + Vector DB mapping sketched (NOT IMPLEMENTED)
- `isValidRelationship` structural validator
- Doc complete (9 sections)
