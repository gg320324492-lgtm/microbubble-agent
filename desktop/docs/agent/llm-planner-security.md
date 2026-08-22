# LLM Planner Security (Phase 8-B1)

> **purpose**: Document how the hybrid LLM planner keeps secrets isolated, defends against prompt injection, and validates every plan.
> **follows**: `hybrid-planner.md` (Phase 8-B1 architecture).

## 1. Secret isolation

The planner model path is secret-free **by construction**:

| Layer | Guarantee |
|-------|-----------|
| Prompt | `buildModelPrompt` only emits intent fields + tool ids + capability tags + knowledge entity type names. It never serializes `availableTools` profiles wholesale (no credentials could be in scope), never includes `apiKey`/`token`/anything credential-shaped. |
| Adapter | receives only an injected `ModelCaller`; never imports `model-provider`, never calls an SDK, never reads config/env. |
| Schema | every LLM contract runs the shared `assertNoSecret` guard (8 forbidden substrings: `sk-`, `apiKey`, `cipher`, `Bearer `, `token`, `authorization`, `providerId`, `modelId`). |
| Parse | `normalizeParsedPlan` reuses the Phase 8-A0 secret guard — a model that echoes a secret into any plan field fails validation and the whole LLM result is rejected. |
| Plans | plan `metadata` carries only `planner`, `domain`, `taskType`, `topic`, `constraints`, `plannerStrategy` — no credentials, no provider config. |

Source-level tests mirror this: `planner-model-adapter.ts` and `hybrid-planner.ts` are scanned for forbidden imports (`model-provider`, `auth`, `backend`), forbidden literals (`apiKey = `), and RNG (`Math.random` / `Date.now`).

## 2. Prompt injection defense

The model output is treated as **untrusted data**, never as instructions:

1. **JSON envelope extraction** — only the first `{` … last `}` substring is parsed; surrounding prose is ignored, so an injection answer cannot smuggle in raw control text.
2. **Strict schema re-validation** — the parsed object must become a valid Phase 8-A0 `ResearchPlan` (`isValidResearchPlan`), no exceptions.
3. **Type allowlist** — steps are kept only if `type ∈ {knowledge, tool, model, analysis, synthesis}`; anything else is dropped silently.
4. **Dependency sanitization** — refs to unknown/external ids are dropped; the plan is re-checked for cycles.
5. **Never trust extra fields** — only `id`/`goal`/`tasks`/`status`/`metadata` (rebuilt) survive normalization; injected `role`, `system`, `commands`, etc. are discarded.
6. **The LLM never executes** — even a fully valid injected plan can only name tools/capabilities in step `input`; the runtime executes, and it uses injected callers with their own guards.

## 3. Plan validation

Every LLM-produced plan must pass the Phase 8-B1 gates before acceptance:

```
validatePlan(plan).ok            # structure + no cycles + resolvable deps
(hybrid) confidence > rule conf  # LLM must actually improve on baseline
capabilitySatisfied(context)     # tool ids / capabilities / entity types resolvable
```

Failure path: **fallback to the rule plan**. The deterministic B0 baseline is always recomputed first, so a malicious/toxic LLM output can never torpedo planning — it is simply ignored.

Additional defenses:
- adapter `generatePlan` throws on unparseable output → caught by the hybrid planner → rule fallback
- `detectCycle` in normalization rejects dependency cycles before they ever reach the runtime
- confidence is clamped to [0,1]; repairs to the model's plan cap confidence at 0.6, biasing hybrid mode back toward the rule plan

## 4. Threat model recap

| Attack | Defense | Outcome |
|--------|---------|---------|
| Model leaks a secret into the plan | `assertNoSecret` at parse + schema validation | LLM result rejected → rule plan |
| Injection in model text tries to add steps | type allowlist + JSON envelope + field trust-list | extra/invalid steps dropped |
| Dependency cycle from model | `detectCycle` in `normalizeParsedPlan` + `validatePlan` | LLM result rejected → rule plan |
| Model hallucinates a tool id | `capabilitySatisfied` gate against `context.availableTools` | LLM result rejected → rule plan |
| Adapter / model unavailable | try/catch → soft `llm-error` fallback | rule plan returned |
| Model demands direct tool execution | architecture forbids it (adapter produces plans only) | impossible |

## 5. References

- `docs/agent/hybrid-planner.md` (Phase 8-B1 architecture + fallback)
- `src/shared/agent/llm-planner-schema.ts` (contracts + secret guard)
- `src/main/services/agent/planner-model-adapter.ts` (prompt + parse + validate)
- `src/main/services/agent/hybrid-planner.ts` (acceptance gates + fallback)