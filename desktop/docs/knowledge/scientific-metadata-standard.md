# Scientific Metadata Standard (Phase 7-A0)

> **purpose**: Define the typed metadata formats that all scientific entities use to carry experimental values. This phase is **architecture-only** — no actual measurements, no processing.
> **follows**: `scientific-domain-model.md` (Phase 7-A0 Step 2).

## 1. Scope (Phase 7-A0 frozen)

Three metadata standards:

1. `Parameter` — controlled experimental input (set by user / extracted from paper)
2. `Measurement` — observed experimental output (collected during run)
3. `Citation` — paper reference with confidence (used by chat messages)

All three are NON-SECRET. NO `apiKey` / `token` / `cipher` / `Authorization` in any field.

## 2. Parameter format

A `Parameter` describes a controlled experimental input.

```ts
interface Parameter {
  name: string
  value: number | string | boolean
  unit?: string
  uncertainty?: number
  source?: 'experiment' | 'literature' | 'simulation' | 'derived' | 'unknown'
}
```

### Field rules

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | yes | unique within Experiment. Use snake_case (`ozone_concentration`, `ph`) |
| `value` | number/string/boolean | yes | typed value; no objects/arrays |
| `unit` | string | no | SI unit preferred (`MPa`, `mg/L`, `°C`) |
| `uncertainty` | number | no | absolute (not relative); same unit as `value` |
| `source` | enum | no | where this parameter came from |

### Examples

```ts
// ozone concentration in O3-MNB-TC degradation experiment
{
  name: 'ozone_concentration',
  value: 5.0,
  unit: 'mg/L',
  source: 'experiment'
}

// pressure with uncertainty
{
  name: 'pressure',
  value: 0.3,
  unit: 'MPa',
  uncertainty: 0.02,
  source: 'experiment'
}

// pH
{ name: 'ph', value: 7.2, uncertainty: 0.1, source: 'experiment' }

// bubble size (from paper)
{ name: 'bubble_size', value: '50um', source: 'literature' }

// categorical boolean flag
{ name: 'stirrer_on', value: true }
```

### Validator

`isValidParameter(p: unknown): boolean` checks:
- `name` non-empty
- `value` is one of number/string/boolean
- `unit` / `uncertainty` types if present
- `source` enum if present
- `assertNoSecret` on the whole payload

## 3. Measurement format

A `Measurement` describes an observed experimental output.

```ts
interface Measurement {
  metric: string
  value: number | string
  method?: string
  instrument?: string
}
```

### Field rules

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metric` | string | yes | unique within Experiment. E.g. `tc_removal_rate`, `bubble_size_mean` |
| `value` | number/string | yes | NO boolean (a measurement is observed, not set) |
| `method` | string | no | how it was measured (HPLC, ICP-MS, image analysis) |
| `instrument` | string | no | equipment used (free-text) |

### Examples

```ts
// TC removal rate via HPLC
{
  metric: 'tc_removal_rate',
  value: 87.3,
  unit: '%',                  // Phase 7+ future: add unit field
  method: 'HPLC',
  instrument: 'Agilent 1260'
}

// bubble size from image analysis
{
  metric: 'bubble_size_mean',
  value: 45.2,
  method: 'image-analysis',
  instrument: 'Olympus BX53'
}

// qualitative observation
{ metric: 'observation', value: 'slight foam' }
```

### Validator

`isValidMeasurement(m: unknown): boolean` checks:
- `metric` non-empty
- `value` is number/string (NOT boolean)
- `method` / `instrument` types if present
- `assertNoSecret`

## 4. Citation format

A `Citation` ties a paper to a chat message or another knowledge entity.

```ts
interface Citation {
  paperId: string
  source: 'paper' | 'book' | 'web' | 'preprint' | 'other'
  confidence?: 'verified' | 'inferred' | 'unverified'
}
```

### Field rules

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `paperId` | string | yes | refs `Paper.id` |
| `source` | enum | yes | where the citation came from |
| `confidence` | enum | no | trust level |

### Confidence semantics

- `verified` — manually checked by user or extracted from a peer-reviewed paper
- `inferred` — derived by the assistant (e.g. from conversation context)
- `unverified` — the citation exists but hasn't been validated

### Examples

```ts
// Verified citation from a paper
{ paperId: 'paper:abc123', source: 'paper', confidence: 'verified' }

// Inferred citation (assistant found a related paper)
{ paperId: 'paper:def456', source: 'web', confidence: 'inferred' }

// Book reference
{ paperId: 'book:handbook-ozone', source: 'book' }
```

### Validator

`isValidCitation(c: unknown): boolean` checks:
- `paperId` non-empty
- `source` is one of the 5 valid values
- `confidence` is one of the 3 valid values (or absent)
- `assertNoSecret`

## 5. Cross-reference summary

| Use case | Field | References |
|----------|-------|------------|
| Experimental input | `Parameter` | Experiment.parameters[] |
| Experimental output | `Measurement` | Experiment.measurements[] |
| Paper reference | `Citation` | Chat message / Experiment / Paper |

The three are independent types. A `Parameter` is NOT a `Measurement` (different semantics: input vs output). A `Citation` is NOT a `Parameter` (different semantics: reference vs value).

## 6. SI unit guidance

The Knowledge Layer does NOT enforce unit canonicalization at Phase 7-A0. However:

- SI base units preferred: `m`, `kg`, `s`, `K`, `mol`, `A`, `cd`
- Common derived: `Pa`, `J`, `W`, `V`, `Hz`, `mg/L`, `°C`
- Microbubble research vocabulary: `um`, `nm`, `MPa`, `mg-O3/L`, `mL/min`

Phase 7+ may add a `UnitRegistry` to canonicalize / convert. Phase 7-A0 just carries the string.

## 7. Uncertainty semantics

`Parameter.uncertainty` is **absolute** (same unit as `value`):

```ts
{ name: 'ph', value: 7.2, uncertainty: 0.1 }   // pH 7.2 ± 0.1 (absolute)
{ name: 'pressure', value: 0.3, uncertainty: 0.02, unit: 'MPa' }  // ± 0.02 MPa
```

Future (Phase 7+) may add `relativeUncertainty` (e.g. 5%). Phase 7-A0 ships only absolute.

## 8. Source semantics

`Parameter.source` describes where the value came from:

- `experiment` — set by the user running the experiment
- `literature` — extracted from a Paper
- `simulation` — derived from a CFD / numerical model
- `derived` — calculated from other values
- `unknown` — origin not yet tracked

This is metadata for the renderer / future RAG layer. It does NOT affect validation.

## 9. Phase 7-A0 strict

- All three types reject any secret-like substring via `assertNoSecret`
- ID regex applies to `paperId` (same as other IDs)
- `value` is never an object/array
- `metric` / `name` are non-empty strings
- No database lookups in validators
- No dependency on Model Layer / Chat Layer / legacy backend

## 10. References

- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 Step 2 — entities that USE these types)
- `docs/knowledge/knowledge-relationship-model.md` (Phase 7-A0 Step 3 — relationship kinds)
- `desktop/src/shared/knowledge/schemas.ts` (validators implementation)

## Status (2026-08-22 Phase 7-A0)

- `Parameter` standard with 5 fields (name / value / unit / uncertainty / source)
- `Measurement` standard with 4 fields (metric / value / method / instrument)
- `Citation` standard with 3 fields (paperId / source / confidence)
- 3 validators (`isValidParameter` / `isValidMeasurement` / `isValidCitation`)
- `assertNoSecret` defensive guard on every validator
- Doc complete (10 sections)
