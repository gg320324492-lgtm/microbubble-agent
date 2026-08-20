# Phase 15.0 — Memory & Workspace Report

**Phase**: 15.0
**Target**: Long-term researcher memory + persistent workspaces
**Status**: COMPLETE
**Date**: 2026-08-21

## 1. Long-term Memory (`research_memory_service.py`)

### Save Profile

```python
payload = ResearchMemoryService().save_profile(
    user_id=42,
    name="杜同贺",
    research_domain="pollution_control_water_treatment",
    expertise_level="researcher",
    research_topics=["microbubble", "ozone oxidation", "TC degradation"],
    preferred_answer_style="paper_level",
)
# => {
#     "user_id": 42, "name": "杜同贺",
#     "research_domain": "pollution_control_water_treatment",
#     "expertise_level": "researcher", ...
# }
```

### Load / Update

```python
svc = ResearchMemoryService()
loaded = svc.load_profile(42)
# => full payload (DB or in-memory snapshot)

svc.update_profile(42, research_topics=["engineering scale-up"])
# => merged profile
```

### 7 memory categories

| Constant                    | Use                                  |
|-----------------------------|--------------------------------------|
| `user_fact`                 | Researcher identity facts            |
| `research_topic`            | Topic of interest / questions        |
| `method_preference`         | Method preference (DOE / kinetic)    |
| `current_problem`           | Open problem / blocker               |
| `important_decision`        | Decision moments                     |
| `failed_attempt`            | Failed approaches (avoid redoing)    |
| `research_direction`        | Long-term research direction         |

```python
svc.save_project_memory(
    user_id=42,
    workspace_id="ws_abc",
    category="research_topic",
    content="微纳米气泡强化臭氧",
    metadata={"intent": "mechanism_analysis"},
)
```

## 2. Workspace Lifecycle

```python
mgr = ResearchWorkspaceManager()
snap = mgr.create_workspace(
    user_id=42,
    title="臭氧微纳米气泡强化TC降解机制研究",
    domain="pollution_control_water_treatment",
    goal="明确机制链",
)
# snap.current_stage = "exploration"

mgr.update_stage(snap.workspace_id, "hypothesis")
mgr.add_hypothesis(
    snap.workspace_id,
    hypothesis_id="H1",
    text="MNB increases ozone mass transfer coefficient kLa",
)
mgr.add_evidence(snap.workspace_id, kind="EPR", summary="detected ·OH radicals")
mgr.add_evidence(snap.workspace_id, kind="LC-MS", summary="intermediates")
mgr.update_progress(
    snap.workspace_id,
    {
        "literature_progress": 0.85,
        "evidence_progress": 0.6,
    },
)
status = mgr.get_research_status(snap.workspace_id)
# => {
#     "workspace_id": "ws_xxxx", "title": "...", "status": "active",
#     "current_stage": "experiment", "hypothesis_count": 1,
#     "evidence_count": 2, "evidence_kinds": ["EPR", "LC-MS"],
#     "progress": {...}
# }
```

### Status enum

```
active → paused → completed → archived
```

### Stage progression

```
exploration → literature → hypothesis → experiment → analysis → writing
```

## 3. Progress Tracker

```python
prog = ResearchProgressTracker().evaluate_workspace(snap)
# => ResearchProgress(
#     literature_progress = 0.85,
#     hypothesis_progress = 0.7,
#     evidence_progress   = 0.4,
#     experiment_progress = 0.45,
#     paper_progress      = 0.25,
#     overall_score       = 0.5,
#     next_action         = "梳理近 5 年顶刊文献路线并整理研究空白"
#     (whichever dimension is lowest)
# )
```

### 5-dimension weights

```python
W_LITERATURE  = 0.15
W_HYPOTHESIS  = 0.25
W_EVIDENCE    = 0.25
W_EXPERIMENT  = 0.25
W_PAPER       = 0.10
```

## 4. Quality Evaluator

```python
score = ResearchQualityEvaluator().evaluate_answer(
    answer="...mechanism chain 通过 ·OH free radicals..."
    , intent="mechanism_analysis"
)
# => ResearchQualityScore(
#     intent_score        = 0.667,
#     depth_score         = 0.65,
#     evidence_score      = 0.4,
#     completeness_score  = 0.667,
#     overall_score       = 0.5,
#     missing_elements    = ["quantitative variables"],
#     suggestions         = ["补充关键元素: quantitative variables"],
# )
```

### 5-metric weights

```python
W_INTENT        = 0.30
W_DEPTH         = 0.25
W_EVIDENCE      = 0.20
W_COMPLETENESS  = 0.25
```

## 5. End-to-End Product Pipeline

```python
result = run_product_research_agent(
    user_prompt="微纳米气泡强化臭氧氧化TC的机理研究",
    user_id=42,
    use_llm=False,
    force_intent="mechanism_analysis",
)
```

Returns `ProductizedAgentResult` with:

- `profile` (loaded profile dict)
- `workspace_id` (active workspace)
- `classification` (Phase 14.3 IntentClassification)
- `strategy` (Phase 14.3 AnswerStrategy)
- `agent_result` (delegated V1.0)
- `final_report` (decorated with Phase 15.0 fields)
- `quality_score` (Phase 15.0 §6)
- `progress` (Phase 15.0 §5)
- `recommended_next_actions` (merged from quality + progress)
- `steps` (audit trail)
- `success` / `error` (delegated V1.0 failure → graceful)

### Steps audit trail

```
load_profile    → load_workspace   → intent_detection
              ↓
research_agent_v1 (delegated, Phase 14.0 — UNCHANGED)
              ↓
quality_evaluation → progress_update → save_memory
```

## 6. Example Real Run

```python
# Input:
#   user_prompt = "微纳米气泡强化臭氧氧化TC的机理研究"
#   user_id    = 42 (researcher, pollution_control_water_treatment)
#   workspace_id = ws_demo_001

# Output:
result.classification.intent == "mechanism_analysis"
result.quality_score.overall_score in [0.4, 0.8]
result.progress.next_action != ""
result.recommended_next_actions = [
    *result.quality_score.suggestions,
    result.progress.next_action,
]
result.final_report.research_status == result.progress
result.final_report.quality_score   == result.quality_score
```

## 7. Persistence Notes

When an `AsyncSession` is supplied to `ResearchMemoryService` or
`ResearchWorkspaceManager`, both services commit through the SQLAlchemy
session. Without a session they run in-memory and keep state on the
service instance. The in-memory path is deterministic for tests and
ad-hoc callers.

The new tables (`research_user_profiles` + `research_workspaces`) follow
the standard TimestampMixin + single-chain discipline:

- `107_add_summary_columns → 127_research_user_profile → 128_research_workspace`

`down_revision` is exact and explicit; the chain resolves to a single
head. Existing API behavior is unchanged because every new field on
`ResearchReport` is additive with safe defaults.
