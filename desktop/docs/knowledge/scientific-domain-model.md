# Scientific Knowledge Domain Model (Phase 7-A0)

> **purpose**: Define the foundational scientific knowledge entities that MicroBubble Research OS operates on. This phase is **architecture-only** — no PDF parser, no RAG pipeline, no vector DB, no UI.
> **follows**: Phase 6 (Model Runtime frozen).
> **Phase 7-A0 frozen contract**: 6 entity types + 3 metadata standards. Distinct from Model Layer / Chat Layer / Legacy Backend.

## 1. Scope (Phase 7-A0 frozen)

Six first-class scientific entities:

1. `Paper` — scientific literature object
2. `Experiment` — experimental record
3. `Equipment` — laboratory equipment model
4. `Dataset` — raw and processed research data
5. `Figure` — scientific visualization asset
6. `ResearchProject` — top-level research container

Plus three metadata standards:

- `Parameter` — typed experimental input
- `Measurement` — typed experimental output
- `Citation` — paper reference with confidence

All schemas live in `desktop/src/shared/knowledge/schemas.ts`. All entities are **non-secret**: NEVER contain `apiKey` / `token` / `cipher` / `Authorization`.

## 2. Independence boundary (Phase 7-A0 strict)

The Knowledge Layer is **independent** from:

| Layer | Phase | Why independent |
|-------|-------|------------------|
| Model Provider | 6-A2/3 | Knowledge entities describe science, not LLM config |
| Capability Router | 6-C1/2 | Routing is a runtime concern; entities are domain concepts |
| Chat Runtime | 6-A5/6 | Streams are ephemeral; entities are persistent concepts |
| Legacy FastAPI | 2-Impl-3A | Backend has its own domain (members, sessions); entities are new |

Cross-cutting rules:

- Knowledge entities reference **stable IDs** (e.g. `paper:abc123`); they do NOT reference `providerId` / `model` / `endpoint`.
- Knowledge entities do NOT carry authentication state.
- Knowledge entities may be referenced by chat messages (Phase 7+) via `paperId` / `experimentId` only.

## 3. Entity 1: `Paper`

```ts
interface Paper {
  id: string                    // stable, e.g. 'paper:abc123'
  title: string                 // full paper title
  authors: string[]             // ['Wang, T.', 'Li, M.']
  journal: string               // 'Water Research'
  year: number                  // 2024
  doi?: string                  // '10.1016/j.watres.2024.123456'
  keywords: string[]             // ['ozone', 'microbubble', 'degradation']
  researchField: string          // 'water treatment'
  abstract: string
  methods?: string
  parameters?: Parameter[]       // experimental conditions from the paper
  results?: string
  conclusions?: string
  relatedExperiments?: string[]  // cross-references to Experiment entities
}
```

Use cases:
- Search by keyword / author / journal
- Link from `Citation` (every chat message referencing a paper)
- Cross-link to `Experiment` (when the user re-runs the paper's protocol)

Validation rules (`isValidPaper`):
- `id` matches `^[a-zA-Z][a-zA-Z0-9_-]{1,63}$`
- `title`, `journal`, `researchField`, `abstract` are non-empty strings
- `authors` is a non-empty string array
- `year` is 1800..2200
- `keywords` is a string array (may be empty)

## 4. Entity 2: `Experiment`

```ts
interface Experiment {
  id: string                   // 'exp:o3-mnb-tc-degradation'
  name: string                 // 'O3-MNB-TC degradation'
  researchTopic: string        // 'ozone micro-nano bubble degradation of tetracycline'
  objective: string            // 'quantify TC removal rate under varying ozone dose'
  system: string               // 'semi-batch bubble column'
  materials?: string[]         // ['O3', 'TC standard', 'DI water']
  equipment: string[]          // refs to Equipment.id
  parameters: Parameter[]      // controlled experimental inputs
  conditions?: string          // ambient / lab notes
  measurements?: Measurement[] // observed outputs
  results?: string             // raw text summary
  conclusion?: string          // interpretation
}
```

Example (the task's reference):
- `O3-MNB-TC degradation`
- Parameters: `ozone concentration`, `gas flow`, `pressure`, `bubble size`, `pH`, `TC concentration`

Validation rules:
- All required fields populated
- `parameters` is a non-empty array (each parameter must pass `isValidParameter`)
- `equipment` IDs are validated at usage time (Phase 7+), not at entity creation

## 5. Entity 3: `Equipment`

```ts
interface Equipment {
  id: string               // 'eq:mnb-generator-001'
  name: string             // 'Microbubble generator'
  type: string             // 'bubble-generator' | 'pump' | 'ozone-generator' | 'cfd-model' | 'spectrometer' | ...
  manufacturer?: string    // 'XYZ Corp'
  specifications?: Record<string, string>  // { 'flow-rate': '1 L/min', 'pressure': '0.3 MPa' }
  operatingRange?: string // free text
  relatedExperiments?: string[] // refs to Experiment.id
}
```

Validation: required `id` / `name` / `type`; `specifications` is a string→string map (no numeric values; use `Parameter` for typed values).

## 6. Entity 4: `Dataset`

```ts
interface Dataset {
  id: string               // 'ds:tcd-2024-09-15'
  name: string
  source: string           // 'experiment:exp:o3-mnb-tc-degradation' | 'simulation' | 'literature' | 'imported'
  variables: string[]      // ['time', 'tc-concentration', 'o3-dose']
  units?: Record<string, string>  // { 'time': 'min', 'tc-concentration': 'mg/L' }
  samples?: number         // 240
  processingMethod?: string
  results?: string
}
```

Validation: `variables` is non-empty; `samples >= 0`; `units` keys must be subset of `variables` (cross-validated at use time).

## 7. Entity 5: `Figure`

```ts
type FigureType =
  | 'SEM'
  | 'CFD-contour'
  | 'particle-distribution'
  | 'kinetic-curve'
  | 'spectrum'
  | 'microscopy'
  | 'other'

interface Figure {
  id: string
  type: FigureType
  source: string             // file path / dataset reference
  caption: string
  relatedDataset?: string   // refs to Dataset.id
  relatedPaper?: string     // refs to Paper.id
}
```

Validation: `type` is one of the enum values; `id` matches ID regex.

## 8. Entity 6: `ResearchProject`

```ts
interface ResearchProject {
  id: string
  title: string
  members: string[]         // ['Wang Tianzhi', 'Li Min']
  topic: string             // 'Ozone micro-nano bubble water treatment'
  papers: string[]          // refs to Paper.id
  experiments: string[]     // refs to Experiment.id
  datasets: string[]        // refs to Dataset.id
}
```

Validation: arrays are non-empty (members may be empty); all IDs follow the ID regex.

## 9. Metadata standards

### Parameter

```ts
interface Parameter {
  name: string
  value: number | string | boolean
  unit?: string
  uncertainty?: number
  source?: 'experiment' | 'literature' | 'simulation' | 'derived' | 'unknown'
}
```

Example:
```ts
{ name: 'pressure', value: 0.3, unit: 'MPa', source: 'experiment' }
{ name: 'pH', value: 7.2, uncertainty: 0.1, source: 'experiment' }
```

### Measurement

```ts
interface Measurement {
  metric: string
  value: number | string
  method?: string
  instrument?: string
}
```

Example:
```ts
{ metric: 'TC-removal-rate', value: 87.3, method: 'HPLC', instrument: 'Agilent 1260' }
```

### Citation

```ts
interface Citation {
  paperId: string
  source: 'paper' | 'book' | 'web' | 'preprint' | 'other'
  confidence?: 'verified' | 'inferred' | 'unverified'
}
```

Example:
```ts
{ paperId: 'paper:abc123', source: 'paper', confidence: 'verified' }
```

## 10. Extension compatibility (Phase 7+ safe)

All entities expose an `ExtensionFields` container that future schema versions can use without breaking older consumers:

```ts
interface ExtensionFields { [key: string]: unknown }
```

Usage rules:
- Phase 7-A0 entities MUST NOT define extension fields inline
- Future versions (Phase 7+) add new optional fields explicitly
- Old consumers ignore unknown fields (TypeScript structural typing)

## 11. Security boundary (Phase 7-A0 strict)

`schemas.ts` enforces:
- `assertNoSecret(value, ctx)` runs on every validator, throws on `sk-` / `apiKey` / `cipher` / `Bearer ` / `token` / `authorization` substrings
- ID regex rejects empty / overly long / special-char IDs

Knowledge Layer MUST NOT import:
- Anything from `desktop/src/main/services/model-provider/`
- Anything from `desktop/src/main/services/auth/`
- Anything from `desktop/src/renderer/src/stores/{auth,user}.ts`

## 12. Phase 7-A0 file manifest

```
desktop/src/shared/knowledge/
  - schemas.ts                         (Phase 7-A0: entity + metadata types + validators)

desktop/docs/knowledge/
  - scientific-domain-model.md         (this file)
  - knowledge-relationship-model.md    (Phase 7-A0 Step 3)
  - scientific-metadata-standard.md     (Phase 7-A0 Step 4)
  - knowledge-layer-architecture.md    (Phase 7-A0 Step 5)
  - rag-extension-plan.md              (Phase 7-A0 Step 6)

desktop/tests/unit/
  - knowledge-schema.test.ts           (Phase 7-A0 Step 7)
```

## 13. References

- `docs/desktop-conversion/live-e2e-validation.md` (Phase 6-D end-state)
- `docs/desktop-conversion/model-provider-architecture.md` (Phase 6-A audit, for boundary contrast)

## Status (2026-08-22 Phase 7-A0)

- `schemas.ts` — 6 entities + 3 metadata standards + 10 validators
- `assertNoSecret` defensive guard on every validator
- 0 dependencies on Model Layer / Chat Layer / legacy backend
- Doc complete (13 sections)
