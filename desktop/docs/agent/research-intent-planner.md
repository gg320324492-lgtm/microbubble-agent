# Research Intent Understanding + Planner Core (Phase 8-B0)

> **purpose**: Define the deterministic planner foundation that turns a natural-language research request into a `ResearchPlan` the Phase 8-A1 runtime can execute.
> **follows**: `research-plan-schema.md` (Phase 8-A0) — the planner emits Phase 8-A0 plans.
> **feeds**: `runtime-execution-flow.md` (Phase 8-A1) — the runtime executes those plans.
> **Phase 8-B0 strict**: deterministic only. NO LLM call, NO RNG, NO model-provider / auth / backend imports, NO plan executed here.

## 1. Intent pipeline (Phase 8-B0)

```
 user request (free text)
        │
        ▼
 IntentClassifier  (intent-classifier.ts)
   - domain detection   (environment / chemistry / communication / control / experiment)
   - task detection     (literature-review / experiment-analysis / data-analysis /
                          simulation / paper-writing)
   - topic extraction   (first sentence, ≤60 chars)
   - constraint tags    (quantitative / recent / chinese / fast / precise / compare)
        │  ResearchIntent
        ▼
 RulePlanner  (rule-planner.ts)
   - fixed step-type template per task type
   - deterministic plan id (content hash — no Math.random)
        │  ResearchPlan
        ▼
 ResearchPlanner  (research-planner.ts)
   - validatePlan (structure + cycles + resolvable deps)
   - estimateConfidence (deterministic 0..1)
   - reasoningSummary (secret-free trace)
        │  PlannerDecision
        ▼
 Phase 8-A1 ResearchAgentRuntime  (executes the plan)
```

## 2. Planner architecture

| Module | File | Responsibility |
|--------|------|----------------|
| Planner schema | `src/shared/agent/planner-schema.ts` | `ResearchIntent`, `PlannerContext`, `PlannerDecision`, `IntentEvidence` + validators + secret guard |
| Intent classifier | `src/main/services/agent/intent-classifier.ts` | deterministic keyword scoring → `ResearchIntent` |
| Rule planner | `src/main/services/agent/rule-planner.ts` | `ResearchIntent` → `ResearchPlan` (5 templates) |
| Planner service | `src/main/services/agent/research-planner.ts` | `analyzeIntent` / `createPlan` / `validatePlan` / `estimateConfidence` (+ `plan` full pipeline) |
| Runtime | `src/main/services/agent/agent-runtime.ts` (Phase 8-A1) | executes the plan — NOT imported by the planner |

## 3. Domains + tasks (deterministic, keyword-scored)

**Domains** — winner = max matching keyword count; ties broken by enum order; zero matches → fallback `experiment`.

| Domain | English signals | Chinese signals |
|--------|-----------------|-----------------|
| environment | water, air quality, bubble, pollutant | 水 / 空气 / 环境 / 污染 / 气泡 |
| chemistry | reaction, molecule, catalyst | 化学 / 反应 / 分子 / 催化剂 |
| communication | signal, transmission, wireless | 通信 / 信号 / 传输 / 无线 |
| control | controller, pid, stability, feedback | 控制 / PID / 反馈 / 稳定 |
| experiment | experiment, measurement, protocol | 实验 / 测量 / 装置 / 仪器 |

**Tasks** — winner = max matching keyword count; ties broken by enum order; zero matches → fallback `data-analysis`.

| Task | Template (StepType chain) | Required capabilities |
|------|---------------------------|----------------------|
| experiment-analysis | knowledge → tool → tool → synthesis | experiment-analysis, statistics, visualization |
| literature-review | knowledge → synthesis | literature-processing, summarization |
| data-analysis | knowledge → analysis → tool → synthesis | data-analysis, statistics, regression, visualization |
| simulation | knowledge → tool → analysis → tool → synthesis | simulation, modeling |
| paper-writing | knowledge → model → synthesis | writing, summarization |

## 4. Rule examples (Phase 8-B0)

### "Analyze water quality data" (environment · data-analysis)

```
step:1:knowledge   { entityType: 'dataset', query: goal }
step:2:analysis    { sourceStepId: 'step:1:knowledge' }
step:3:tool        { toolId: 'tool:data-visualization' }
step:4:synthesis   { format: 'summary', sourceStepIds: [step:1..3] }
```

### "Write a literature review of micro-nano bubble papers" (environment · literature-review)

```
step:1:knowledge   { entityType: 'paper', query: goal }
step:2:synthesis   { sourceStepIds: ['step:1:knowledge'] }
```

### Confidence (deterministic)

```
base 0.45
+ template depth (>=3 steps: +0.15  else +0.05)
+ domain confidence (non-fallback +0.08   fallback 'experiment' +0.02)
+ topic quality (>=8 chars +0.05  else +0.01)
+ constraints (+0.02 each, cap +0.06)
+ capability coverage vs PlannerContext.availableTools (cov * 0.20)
clamped to [0,1], rounded to 2 decimals
```

## 5. Security boundary (Phase 8-B0 strict)

- `assertNoSecret` guard on every schema object (8 forbidden substrings)
- `planner-schema.ts`, `intent-classifier.ts`, `rule-planner.ts`, `research-planner.ts` MUST NOT import `model-provider` / `auth` / `backend`
- `research-planner.ts` MUST NOT import `agent-runtime` — the planner decides WHAT; the runtime executes HOW
- Plan ids are content hashes (djb2); NO `Math.random` / `Date.now` in the planner path

## 6. Future LLM planner extension (Phase 8+)

The `ResearchPlanner` interface is the seam. A future LLM-driven planner can:

- keep `analyzeIntent` / `createPlan` / `validatePlan` / `estimateConfidence` as the entry points
- replace the internal rule templates with `model.complete()` output parsed into a `ResearchPlan`
- reuse `PlannerContext` (previousResults / availableTools / availableKnowledge) for prompt grounding
- keep the **same** `PlannerDecision` contract — the Phase 8-A1 runtime is unaffected

The deterministic classifier / rule planner remain as the **fallback** planner when the LLM planner is unavailable or the request is below the LLM threshold.

## 7. References

- `src/shared/agent/planner-schema.ts` (Phase 8-B0 contracts)
- `src/main/services/agent/intent-classifier.ts` (classifier)
- `src/main/services/agent/rule-planner.ts` (rule templates)
- `src/main/services/agent/research-planner.ts` (planner service)
- `src/shared/agent/research-plan-schema.ts` (Phase 8-A0 plan contract)
- `src/shared/tools/tool-capability-schema.ts` (Phase 7-T3 metadata used by capability coverage)
- `docs/agent/planner-vs-runtime.md` (WHAT vs HOW separation)
- `docs/agent/runtime-execution-flow.md` (Phase 8-A1 execution)