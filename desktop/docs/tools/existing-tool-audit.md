# Existing Tool Infrastructure Audit (Phase 7-T0)

> **purpose**: Audit the existing tool-related code in MicroBubble Research OS desktop client. Identify what concepts exist, where execution happens, and what gaps Phase 7-T0 must fill.
> **follows**: Phase 7-A0 (Knowledge Schema) + Phase 7-B0 (Storage Architecture).
> **Phase 7-T0 frozen contract**: audit only. NO code changes.

## 1. Scope (Phase 7-T0 frozen)

Phase 7-T0 ships:
- Inventory of existing tool-related code
- Documented gaps
- Foundation for the Tool Layer (Phase 7+ implements on top of this audit)

Phase 7-T0 does **NOT** ship:
- ❌ Any tool execution runtime
- ❌ Any LLM tool-calling integration
- ❌ Any IPC changes

## 2. Existing tool code (Phase 7-T0 audit)

| File | Phase | What it does | Status |
|------|-------|--------------|--------|
| `src/main/services/model-provider/stream-normalizer.ts` | 6-A1 | parses vendor `tool_use` chunks | partial (vendor-specific, not generic) |
| `src/main/services/model-provider/providers/openai-compatible-provider.ts` | 6-A3 | emits `tool_use` StreamEvent | partial |
| `src/main/services/model-provider/providers/ollama-provider.ts` | 6-A3 | emits `tool_use` StreamEvent | partial |
| `src/main/services/agent/core.py` (backend) | n/a | `_execute_tool` | NOT migrated to desktop |
| `src/main/services/agent/tools/*.py` (backend) | n/a | 17+ tools (search_knowledge, create_task, ...) | NOT migrated to desktop |

**Audit verdict:** The desktop client has **no formal Tool Layer**. Tools exist only as ad-hoc `tool_use` chunk parsing in the LLM stream normalizer. The desktop-side Agent Runtime (Phase 6) lacks the tool-execution counterpart that the Python backend (`agent/core.py`) provides.

## 3. Existing service-level concepts (NOT yet exposed as Tools)

The desktop main process already exposes many services (Phase 6-B main process), but none are wrapped as `ToolDefinition`. Phase 7-T0 identifies these as **candidates** for future tool wrappers:

| Service | Current location | Future Tool ID (Phase 7+) |
|---------|-------------------|-----------------------------|
| TaskService | `app/services/task_service.py` (backend) | `tool:task-list` |
| MeetingService | `app/services/meeting_service.py` (backend) | `tool:meeting-list` |
| KnowledgeService | `app/services/knowledge_service.py` (backend) | `tool:knowledge-search` |
| ProjectService | `app/services/project_service.py` (backend) | `tool:project-list` |
| MemberService | `app/services/member_service.py` (backend) | `tool:member-list` |
| ReminderService | `app/services/reminder_service.py` (backend) | `tool:reminder-list` |
| Kinetics analysis (MicroBubble) | n/a (backend agents) | `tool:kinetic-analysis` |

## 4. Audit checklist (Phase 7-T0 Step 1 deliverable format)

For each existing or future tool, the audit captures:

| Field | Example |
|-------|---------|
| Tool | `kinetic-analysis` |
| Current location | `app/agents/scientific_tools/kinetics.py` (backend) |
| Input | `Dataset` (CSV / numpy array) |
| Output | `KineticResult` (k_obs, R², half-life) |
| Current caller | Phase 4 agent (Python) |
| Future Agent callable | YES (Phase 7-G Research Agent) |
| Reason | Ozone degradation kinetics is core MicroBubble research |

Phase 7-T0 ships ONLY the audit format. The actual fill-out of each tool is Phase 7+.

## 5. Gaps identified (Phase 7-T0)

| Gap | What Phase 7-T0 defines | When implemented |
|-----|------------------------|------------------|
| Tool definition schema | `ToolDefinition` type + validators | Phase 7-T0 (now) |
| Tool input schema | `ToolInputSchema` + field validators | Phase 7-T0 (now) |
| Tool output schema | `ToolOutputSchema` + result envelope | Phase 7-T0 (now) |
| Tool registry | Interface only | Phase 7-T+ |
| Tool security boundary | Doc only | Phase 7-T+ |
| Tool execution runtime | NOT IMPLEMENTED | Phase 7-T+ |
| Agent tool calling | Doc only (no planner) | Phase 7-G |
| Existing-app adapter | Doc only | Phase 7-T+ |

## 6. Independence boundary (Phase 7-T0 strict)

The Tool Layer does NOT depend on:

| Layer | Why independent |
|-------|------------------|
| Model Provider (`src/main/services/model-provider/`) | Tool describes capability, not LLM config |
| Auth (`src/main/services/auth.service.ts`, `src/auth/`) | Tool execution is independent of auth |
| Chat Runtime (`src/main/services/chat/`) | Tool is a separate IPC surface |
| Legacy FastAPI (`backend/`) | Tool wraps desktop-side functions, not HTTP calls |

The Tool Layer **only depends on**:
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)

## 7. Phase 7-T0 strict forbids

- ❌ Import anything from `desktop/src/main/services/model-provider/`
- ❌ Import anything from `desktop/src/main/services/auth.service.ts`
- ❌ Import anything from `desktop/src/auth/` or `desktop/src/renderer/auth/`
- ❌ Import anything from `backend/`
- ❌ Add IPC handlers
- ❌ Add a tool executor runtime
- ❌ Wrap existing functions as Tools (Phase 7-T+ does this)
- ❌ Touch the existing `_execute_tool` flow

## 8. References

- `src/main/services/model-provider/stream-normalizer.ts` (Phase 6-A1 — tool_use parsing)
- `src/main/services/model-provider/providers/openai-compatible-provider.ts` (Phase 6-A3)
- `src/main/services/model-provider/providers/ollama-provider.ts` (Phase 6-A3)
- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 — Tool references Knowledge entities)
- `docs/tools/tool-registry-architecture.md` (Phase 7-T0 — Tool Registry)
- `docs/tools/tool-security-boundary.md` (Phase 7-T0 — Security)
- `docs/tools/agent-tool-interface.md` (Phase 7-T0 — Agent integration)
- `docs/tools/application-adapter-design.md` (Phase 7-T0 — Adapter)
- `desktop/src/shared/tools/tool-schema.ts` (Phase 7-T0 contracts)

## Status (2026-08-22 Phase 7-T0)

- Existing tool code inventoried (Phase 6-A1 + 6-A3 partial coverage)
- Gaps identified (8 items)
- Service-level tool candidates listed (7 backend services)
- Audit format defined (Tool / Location / Input / Output / Caller / Callable / Reason)
- Doc complete (8 sections)
