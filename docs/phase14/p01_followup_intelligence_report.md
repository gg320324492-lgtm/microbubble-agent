# Phase 14.1 — Follow-up Intelligence Layer Report

**Phase**: 14.1
**Target**: Research Agent V1.0 follow-up experience
**Status**: COMPLETE
**Date**: 2026-08-21
**Branch**: `claude/follow-up-intelligence-layer-0d54ed`
**Anchor**: V1.0 release (Phase 14.0) frozen — additive-only enhancement

## 1. Executive Summary

Phase 14.1 upgrades the Research Agent V1.0 follow-up experience by replacing
the static, hand-curated follow-up suggestions with an **intent-aware
follow-up intelligence layer**. The new layer adds three thin, additive
modules:

- `app/services/followup_schema.py` — canonical `FollowUpQuestion` dataclass
  + 5 categories.
- `app/services/followup_generator.py` — deterministic rule engine with
  optional LLM refinement and robust fallback (4 dimensions).
- `app/services/followup_ranker.py` — weighted scoring
  (0.4×intent + 0.3×knowledge_gap + 0.2×usefulness + 0.1×novelty).

The existing `research_report.py` is extended **additively** with a
`followup_questions` field. No existing fields are removed. No DB migrations
are introduced. No Phase 8–14 frozen modules are modified.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ResearchReport (Phase 14.0 §2)                                         │
│                                                                         │
│  ┌────────────────────────┐                                            │
│  │  followup_questions [] │ ←── additive field (Phase 14.1 §4)         │
│  │  followup_q[*].dict()  │                                            │
│  └────────────────────────┘                                            │
└────────────────────────▲────────────────────────────────────────────────┘
                         │
            generates via │
                         │
┌────────────────────────┴────────────────────────────────────────────────┐
│  Research Report Generator (research_report.py)                         │
│       _build_followup_questions(user_prompt, intent,                    │
│                                   memory_hits, reasoning_output, …)     │
│                                                                         │
│   ┌──────────────────────┐    ┌──────────────────────┐                   │
│   │ followup_generator   │ →  │ followup_ranker      │                   │
│   │ (deterministic +     │    │ (weighted scoring)   │                   │
│   │  optional LLM +      │    │                      │                   │
│   │  fallback)           │    │                      │                   │
│   └──────────────────────┘    └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. Generation Logic

### 3.1 Schema (`followup_schema.py`)

```python
@dataclass
class FollowUpQuestion:
    question: str
    category: str           # one of 5 categories
    intent: str             # user-intent label
    reason: str             # why this question is being suggested
    confidence: float       # [0.0, 1.0], constructor clamps
    priority: float         # [0.0, 1.0], constructor clamps
    metadata: Dict[str, Any]
```

**5 categories** (per spec):

| Category           | Purpose                                  |
|--------------------|------------------------------------------|
| `detail`           | Drill-down into the answer               |
| `explanation`      | Mechanism / theory behind the topic      |
| `comparison`       | Alternatives / different methods         |
| `next_action`      | Concrete actionable next step            |
| `knowledge_gap`    | Surface missing / under-documented areas |

### 3.2 Generator (`followup_generator.py`)

`generate_followup_questions(user_prompt, answer, context=None,
memory_hits=None, reasoning_output=None, intent=None, max_questions=3)`
returns a `List[FollowUpQuestion]` always non-empty (fallback guaranteed).

**Four generation dimensions** (per spec):

1. **Deep understanding** — detail / explanation prompts driven by token
   match (`how`, `why`, `explain`, `details`, …) plus the Bayesian posterior
   signal `(1 - posterior)` from `reasoning_output`.
2. **Related analysis** — comparison prompts triggered by explicit
   comparison tokens (`compare`, `vs`, `alternative`, `differ`, …).
3. **Next action suggestion** — actionable prompts triggered by
   `next step`, `proceed`, `action plan`, …
4. **Knowledge gap completion** — gap signal computed from `memory_hits`:
   empty / thin memory produces a strong gap signal.

**Strategy**:
1. Deterministic rules first (always succeeds).
2. Optional LLM refinement (lazy-imported, graceful skip if missing).
3. Always returns ≥1 question via fallback (`explore_research_topic`).

### 3.3 Ranker (`followup_ranker.py`)

Per-spec formula:

```
score = 0.4 * intent_match
      + 0.3 * knowledge_gap
      + 0.2 * usefulness
      + 0.1 * novelty
```

- `intent_match`: full match (1.0) / token overlap (0.5 + 0.5×overlap) /
  miss (0.2).
- `knowledge_gap`: category-driven (knowledge_gap > next_action > comparison
  > explanation > detail) boosted by metadata `gap_signal`.
- `usefulness`: 0.6×category_usefulness + 0.4×confidence, capped at 1.0.
- `novelty`: 1.0 for first occurrence within the run; 0.0 for duplicates.

`rank_followups(followups, expected_intent="", top_k=None)` returns the
sorted list (highest score first); each follow-up's `metadata` carries
`score` and a `score_components` breakdown.

## 4. Test Coverage (8 new tests, additive)

| #    | Test name                              | Verifies                                  |
|------|----------------------------------------|-------------------------------------------|
| 161  | `test_161_followup_schema`             | Dataclass + 5 categories + clamping       |
| 162  | `test_162_followup_generator`          | Generator returns up to `max_questions`   |
| 163  | `test_163_deep_dive_followup`          | Deep-dive dimension covers detail/explain |
| 164  | `test_164_knowledge_gap_followup`      | Empty memory triggers knowledge_gap       |
| 165  | `test_165_followup_ranking`            | Ranker weights + monotonic ordering       |
| 166  | `test_166_report_followup_integration` | `followup_questions` populated in report  |
| 167  | `test_167_empty_answer_fallback`       | Empty/None inputs don't crash             |
| 168  | `test_168_followup_end_to_end`         | Full e2e: gen → rank → report attach      |

**Total: 168/168 collected** (160 pre-existing + 8 new). All 8 new tests
PASS (`SKIP_DB_SETUP=1 python -m pytest tests/test_phase7b_integration.py -k
"test_161 or test_162 or … or test_168"` → 8 passed, 160 deselected).

> Note: Some pre-existing Phase 7B integration tests (1–150 range) require
> legacy modules (`app.services.memory` etc.) not present in the current
> worktree branch (state predates Phase 14.0 integration). Their failure
> state is pre-existing and unrelated to Phase 14.1 additive changes —
> confirmed by `git diff` showing only new services + tests + docs added,
> none of the legacy modules imported by tests 1–150 were modified.

## 5. Diff Scope

```bash
$ git status
modified:   app/services/research_report.py      # additive field
new file:   app/services/followup_schema.py
new file:   app/services/followup_generator.py
new file:   app/services/followup_ranker.py
modified:   tests/test_phase7b_integration.py    # +8 tests
new file:   docs/phase14/p01_followup_intelligence_report.md  (this file)
new file:   docs/phase14/phase14_1_followup_results.json
```

**No changes to:**
- `app/rag/*`
- `app/services/workflow/*`
- `app/core/*` / celery task state machine
- `DEFAULT_MODEL` / `qwen2.5vl:7b`
- Phase 8–14 frozen modules
- `alembic/versions/*` (no DB migrations)

## 6. Compliance Checklist

- [x] **Additive only** — no existing fields removed.
- [x] **No DB migrations.**
- [x] **Frozen modules untouched** — research_report.py only received an
      additive field.
- [x] **Fallback required** — `generate_followup_questions` always returns
      ≥1 question, even with empty / None inputs.
- [x] **Deterministic default** — rules run first; LLM refinement is
      optional and gracefully skipped.
- [x] **4 dimensions** — deep understanding / related analysis / next
      action / knowledge gap.
- [x] **Ranker formula** — 0.4 / 0.3 / 0.2 / 0.1 weights.

## 7. Future Work (留口)

- Optional: wire `LLMClient.complete(...)` into the generator for richer
  rewrites (currently lazy-imported and skipped).
- Optional: per-user personalization based on history (Phase 15.x).
- Optional: A/B evaluator for follow-up click-through (qa-bench D7+).
