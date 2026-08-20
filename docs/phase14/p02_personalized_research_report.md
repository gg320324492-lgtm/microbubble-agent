# Phase 14.2 — Personalized Research Intelligence Layer Report

**Phase**: 14.2
**Target**: Personalized Research Intelligence Layer (升级 Follow-up)
**Status**: COMPLETE
**Date**: 2026-08-21
**Branch**: `claude/follow-up-intelligence-layer-0d54ed`
**Anchor**: Phase 14.0 V1.0 (frozen) + Phase 14.1 follow-up intelligence

## 1. Executive Summary

Phase 14.2 takes the Phase 14.1 follow-up intelligence layer and turns it
into a **Personalized Research Intelligence Layer**. The core V1.0 research
agent is untouched. Six new additive modules and one additive dataclass
extension on ``ResearchReport`` make the agent aware of the user's research
profile, recommend concrete next-step research actions, and prevent
hallucinated citations.

**Key upgrades over Phase 14.1:**

| Phase 14.1 | Phase 14.2 |
|------------|------------|
| Generic follow-up questions | Profile-aware, dimension-aware questions |
| Single-axis ranking | Five-axis weighted ranking incl. user_relevance + research_value |
| No user-profile extraction | Rule-based profile from memory + history |
| No action recommendation | 6 typed research actions (deepen / compare / validate / review / expand / engineering) |
| No citation guard | Detect + safe-rewrite hallucinated author/year/bracket citations |

## 2. Architecture

```
                   Phase 14.2 Personalized Research Pipeline
                   ────────────────────────────────────────────

  user_prompt
      │
      ├──► memory_hits (caller-supplied or empty)
      │
      ├────► research_profile.py  (rule-based, NO LLM)
      │     ├─ extract_profile_from_memory()
      │     └─ extract_profile_from_history()
      │
      ├────► research_agent.py  (delegated, Phase 14.0 — UNCHANGED)
      │     └─► report (existing 14.0/14.1 fields)
      │
      ├────► citation_guard.py   (Phase 14.2 §5)
      │     ├─ validate_citations(text)
      │     └─ summarize_citation_status()
      │
      ├────► personalized_followup_generator.py  (§3, 5-axis scoring)
      │     └─ generate_personalized_followups(ctx)
      │
      └────► research_action_recommender.py   (§4, 6 action types)
            └─ recommend_research_actions(ctx)  ──► ResearchAction[]

  ResearchReport (additive: 3 new fields + 1 summary)
    personalized_followups: List[Dict]
    recommended_actions:     List[Dict]
    citation_status:         List[Dict]
    citation_status_summary: Optional[Dict]
```

## 3. Modules

### 3.1 `followup_context.py` — Phase 14.2 §1

```python
@dataclass
class FollowUpContext:
    current_question: str
    generated_answer: str
    user_profile: Optional[Any]                # ResearchProfile
    research_domain: str                        # inferred or explicit
    user_expertise_level: str                   # general | practitioner | researcher
    historical_projects: List[Dict]
    research_goal: str
    memory_hits: List[Any]
    reasoning_summary: str
    reasoning_output: Optional[Any]

build_followup_context(...)  # back-compat factory
```

### 3.2 `research_profile.py` — Phase 14.2 §2

Rule-based profile inference (no LLM). The domain detection example from
the spec:

```
if "微纳米气泡" / "臭氧" / "污染控制" / "CFD" / "水处理" appear:
    domain     = pollution_control_water_treatment
    expertise  = researcher
```

Public API:
- `ResearchProfile` dataclass.
- `extract_profile_from_memory(memory_hits)`.
- `extract_profile_from_history(history_items)`.
- `merge_profiles(...)`.

### 3.3 `personalized_followup_generator.py` — Phase 14.2 §3

**5-axis weighted scoring** (replaces 14.1's formula):

```
score = 0.25 * intent_match
      + 0.25 * knowledge_gap
      + 0.25 * user_relevance     ← NEW
      + 0.15 * research_value     ← NEW
      + 0.10 * novelty
```

Generates 4 candidate templates per scenario:
1. `deepen_mechanism` — researcher-only: ties ``subject`` to
   kLa / ·OH / kinetics / 膜污染 signals.
2. `design_experiment` — researcher-only: DOE + ANOVA + optimal window.
3. `literature_review` — researcher + practitioner: CEJ/JHM/WR路线 + 研究空白.
4. `engineering_design` — researcher: 实验室 → 工程级 放大.

A `_filter_generic` step **bans** "了解更多 / 想深入了解 / do you want to know
more" patterns.

### 3.4 `research_action_recommender.py` — Phase 14.2 §4

6 canonical action types:

| Type                       | 中文  | Description |
|----------------------------|-------|-------------|
| `deepen_mechanism`         | 深入机理 | Analyse transport / kinetics / radicals |
| `expand_application`       | 拓展应用 | Industrial / scale / new matrices |
| `compare_methods`          | 方法对比 | vs. alternatives on efficiency / energy |
| `validate_experiment`      | 实验验证 | DOE validation + uncertainty |
| `literature_review`        | 文献分析 | CEJ / JHM / WR review |
| `engineering_design`       | 工程设计 | Process scale-up + reactor design |

`recommend_research_actions(ctx)` returns ranked actions (priority desc).

### 3.5 `citation_guard.py` — Phase 14.2 §5

Detects hallucinated citations and replaces them with safe placeholders:

| Pattern                              | Detected status | Replacement |
|--------------------------------------|-----------------|-------------|
| ``[1]``, ``[12]``                   | generated       | "建议参考相关研究" |
| `Smith et al., 2023`                 | uncertain       | "（待验证来源）" |
| DOI `10.1234/...`                    | verified        | (kept) |
| Marker in `allowed_sources`          | verified        | (kept) |

`validate_citations(text)` returns ``(cleaned_text, records)``. Each record
carries ``marker``, ``status``, ``original_text``, ``replacement``,
``confidence``.

### 3.6 `research_agent_personalized.py` — Phase 14.2 §6

Pipeline (delegates Phase 14.0 untouched):

```
User Question
   ↓
Memory Retrieval (caller-supplied)
   ↓
Profile Extraction       (research_profile.py)
   ↓
Research Agent V1.0      (research_agent.run_research_agent, NOT modified)
   ↓
Citation Guard           (citation_guard.py)
   ↓
Personalized Follow-up   (personalized_followup_generator.py)
   ↓
Research Action Recommendation (research_action_recommender.py)
   ↓
Final Report (with 4 additive fields populated)
```

### 3.7 `research_report.py` — Phase 14.2 §7 (additive)

```python
@dataclass
class ResearchReport:
    # ... existing 14.0 fields ...
    # ... 14.1 followup_questions field ...
    # NEW 14.2 fields (all default to [] or None):
    personalized_followups:  List[Dict] = field(default_factory=list)
    recommended_actions:     List[Dict] = field(default_factory=list)
    citation_status:         List[Dict] = field(default_factory=list)
    citation_status_summary: Optional[Dict] = None
```

`to_dict()` carries the new fields through. **No existing fields removed.**

## 4. Test Coverage (12 new tests, additive)

| #    | Test                                     | Verifies                                     |
|------|------------------------------------------|----------------------------------------------|
| 169  | `test_169_followup_context_schema`       | FollowUpContext factory + empty defaults     |
| 170  | `test_170_research_profile_extraction`   | Profile from memory (no LLM)                 |
| 171  | `test_171_researcher_profile_detection`  | Researcher domain detection (微/臭/CFD)       |
| 172  | `test_172_personalized_generator`        | Diverse categories + 5-axis weights sum=1    |
| 173  | `test_173_user_relevance_scoring`        | Researcher-aligned > generic                 |
| 174  | `test_174_research_action_recommendation`| 6 action types + priority ordering            |
| 175  | `test_175_citation_guard`                | Bracket + author-year + DOI handling         |
| 176  | `test_176_citation_uncertain_handling`   | Uncertainty summary + hallucination flag     |
| 177  | `test_177_personalized_agent_pipeline`   | E2E pipeline runs through V1.0 + guards      |
| 178  | `test_178_microbubble_researcher_scenario`| Researcher-grade coverage of all dimensions |
| 179  | `test_179_generic_user_scenario`         | General user gets accessible suggestions    |
| 180  | `test_180_phase14_2_regression`          | ResearchReport keeps 14.0+14.1 + gains 14.2  |

**Result:** `SKIP_DB_SETUP=1 python -m pytest tests/test_phase7b_integration.py
-k "test_169 or test_170 or ... or test_180"` → **12 passed, 168 deselected**.

Total in file: **180 tests collected**; **all 12 new PASS**; pre-existing
Phase 14.0 / 14.1 tests (153–168) continue to PASS.

## 5. Diff Scope

```
modified:   app/services/research_report.py        (additive fields only)
modified:   tests/test_phase7b_integration.py      (+12 new tests)
new file:   app/services/followup_context.py
new file:   app/services/research_profile.py
new file:   app/services/personalized_followup_generator.py
new file:   app/services/research_action_recommender.py
new file:   app/services/citation_guard.py
new file:   app/services/research_agent_personalized.py
new file:   docs/phase14/p02_personalized_research_report.md
new file:   docs/phase14/phase14_2_personalized_results.json
```

**NOT modified:**

- `app/rag/*` — DO NOT MODIFY ✅
- `app/services/workflow/*` — DO NOT MODIFY ✅
- `app/core/*` celery state machine — DO NOT MODIFY ✅
- `DEFAULT_MODEL`, `qwen2.5vl:7b` — DO NOT MODIFY ✅
- `app/services/research_agent.py` (Phase 14.0 frozen) — preserved
- `app/services/followup_generator.py` (Phase 14.1 preserved) — preserved
- `app/services/followup_ranker.py` (Phase 14.1 preserved) — preserved
- `app/services/followup_schema.py` (Phase 14.1 preserved) — preserved
- `alembic/versions/*` — no migrations ✅

## 6. Real-Scenario Test

**Input:** ``"微纳米气泡技术在水处理中的应用"`` + profile
``domain=pollution_control_water_treatment, expertise_level=researcher`` + 
memory hint ``"关注臭氧微纳米气泡的传质系数 kLa 与 ·OH 自由基"``.

**Generated follow-ups (researcher scenario):**

```
[explanation]   在微纳米气泡技术在水处理中的应用过程中，如何结合传质系数、自由基产率与
                动力学常数系统解释其强化机制（结合微纳米气泡相关指标）？
[next_action]   如何设计一组DOE实验，定量评估微纳米气泡技术在水处理中的应用的关键影响
                因素，并通过方差分析给出最优工艺窗口？
[knowledge_gap] 近5年与微纳米气泡技术在水处理中的应用相关的CEJ/JHM/WR等顶刊研究路线
                如何演化，下一步值得切入的研究空白是什么？
```

**Generated actions:**

```
[deepen_mechanism]   分析微纳米气泡提高臭氧传质和·OH生成机制
[literature_review]  整理近5年CEJ/JHM相关研究路线
[validate_experiment] 设计DOE 实验验证关键假设并量化不确定度
[engineering_design] 工艺放大与反应器工程化设计草案
```

**Forbidden patterns NOT emitted:**
- "需要了解更多吗？" — banned
- "你想深入了解..." — banned
- "了解更多关于..." — banned

## 7. Compliance Checklist

- [x] **Additive only** — no fields removed from any existing dataclass.
- [x] **No DB migrations.**
- [x] **No Phase 8–14 frozen module modifications** — V1.0 research_agent
      and Phase 14.1 followup_* modules are preserved verbatim.
- [x] **Rule-based profile extraction** — no LLM calls in profile layer.
- [x] **5-axis weighted formula** — weights sum to 1.0.
- [x] **6 action types** — taxonomy enforced at runtime.
- [x] **Citation guard** — detect + safe-rewrite suspected hallucinated
      citations.
- [x] **ResearchReport backward compat** — all new fields have safe
      defaults; ``to_dict`` carries everything through.

## 8. Future留口

- Optional: load `ResearchProfile` from a persisted store
  (`Member.research_profile`) — needs migration.
- Optional: per-session personalization via session-level cache.
- Optional: cite-grounding model to verify DOIs against a knowledge base.
