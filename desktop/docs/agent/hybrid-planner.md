# Hybrid LLM Planner (Phase 8-B1)

> **purpose**: Document the upgrade of the deterministic B0 planner into a hybrid rule + LLM planner.
> **follows**: `research-intent-planner.md` (Phase 8-B0) + `planner-vs-runtime.md` (WHAT vs HOW).
> **Phase 8-B1 strict**: the LLM path only extends PLAN creation. It never executes tools and never queries knowledge directly.

## 1. Architecture

```
 User Request
      │
      ▼
 Intent Classifier (Phase 8-B0) ---------> ResearchIntent
      │
      ▼
 Hybrid Planner
   ┌──────────────────────────────────────────────┐
   │  rule baseline  (ResearchPlanner / B0)       │  always computed
   │  LLM planner    (PlannerModelAdapter / B1)   │  optional
   │        │              │                      │
   │        └──────┬───────┘                      │
   │               ▼                              │
   │     accept LLM plan ONLY IF:                 │
   │       - validatePlan ok (no cycle / deps ok) │
   │       - (hybrid) llm.confidence > rule conf  │
   │       - capability satisfied (context)       │
   │               │                              │
   │               ▼  else fallback to rule plan  │
   └───────────────┴──────────────────────────────┘
      │
      ▼
 ResearchPlan  ───────────► Agent Runtime (Phase 8-A1)
```

## 2. Modules (Phase 8-B1)

| Module | File | Responsibility |
|--------|------|----------------|
| LLM planner schema | `src/shared/agent/llm-planner-schema.ts` | `PlannerMode` (rule-only/hybrid/llm-only), `LLMPlannerRequest`, `LLMPlannerResponse` + validators |
| Planner model adapter | `src/main/services/agent/planner-model-adapter.ts` | builds prompt, calls injected `ModelCaller`, parses model text back into a validated plan |
| Hybrid planner | `src/main/services/agent/hybrid-planner.ts` | pipeline + acceptance gates + fallback, mode switching |
| Rule service (B0) | `src/main/services/agent/research-planner.ts` | unchanged — the deterministic baseline |

## 3. Fallback strategy

1. The **rule baseline is ALWAYS computed first** (deterministic, never skipped).
2. The LLM planner is asked only when the mode needs it.
3. The LLM result is accepted **only when all gates pass**; any failure — adapter throw, unparseable output, structural invalidity, cycle, lower confidence (hybrid), or capability mismatch — **falls back to the rule plan**.
4. This means the hybrid planner can never emit less than the deterministic B0 baseline.

Acceptance gates (all must hold):

| Gate | Hybrid | LLM-only |
|------|--------|----------|
| `validatePlan(plan).ok` (structure + no cycle + resolvable deps) | ✔ | ✔ |
| `llm.confidence > rule.confidence` | ✔ | — |
| `capabilitySatisfied(plan, context)` | ✔ | ✔ |

Modes:

| Mode | Behavior |
|------|----------|
| `rule-only` | LLM never consulted; deterministic rule plan returned |
| `hybrid` | default — LLM consulted, accepted only if gates pass, else rule |
| `llm-only` | LLM required (throws if no adapter); invalid LLM output falls back to rule |

## 4. LLM boundary (what the LLM planner may / may not do)

**MAY** (through the adapter only):
- produce a `ResearchPlan` (decides WHAT)
- consult `availableTools` / `availableKnowledge` metadata in the prompt

**MUST NOT**:
- execute a tool (no `ToolExecutor`)
- query knowledge (no `KnowledgeStorage`)
- access `apiKey` / token / credentials (adapter prompt is secret-free by construction)
- import `model-provider` / auth / backend (adapter wraps an injected `ModelCaller`)

## 5. Plan validation of LLM output

Model text is parsed defensively by `normalizeParsedPlan` (in the adapter):

- JSON is extracted from fenced/prose text (first `{` … last `}`)
- every step is normalized: `id` (generated when missing), valid `type` (invalid steps dropped), default `description`, object `input`, string `dependencies`
- dependency refs to unknown/external ids are dropped
- cycles are rejected via Phase 8-A0 `detectCycle`
- the repaired plan must pass Phase 8-A0 `isValidResearchPlan`
- an explanation + model-assisted confidence are attached

## 6. Traceability

Every hybrid decision records, secret-free:
- `mode`, `winner` (`rule` / `llm`), `reason` (`rule-only` / `no-adapter` / `llm-error` / `llm-invalid` / `llm-lower-confidence` / `llm-capability-mismatch` / `llm-accepted`)
- `confidence`, `steps`, step-type `template`
- `plan.metadata.plannerStrategy` (`'rule'` / `'llm'`)

## 7. References

- `docs/agent/llm-planner-security.md` (Phase 8-B1 security)
- `docs/agent/research-intent-planner.md` (Phase 8-B0 pipeline)
- `docs/agent/planner-vs-runtime.md` (WHAT vs HOW)
- `src/shared/agent/llm-planner-schema.ts` / `src/main/services/agent/{planner-model-adapter,hybrid-planner}.ts`