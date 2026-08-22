# Knowledge Storage Architecture (Phase 7-B0)

> **purpose**: Define the storage architecture for the Knowledge Layer. This phase is **architecture-only** — NO database, NO server, NO sync implementation.
> **follows**: `scientific-domain-model.md` + `knowledge-relationship-model.md` + `scientific-metadata-standard.md` (Phase 7-A0).
> **Phase 7-B0 frozen contract**: storage module ships ONLY contracts. Phase 7+ ships implementations.

## 1. Scope (Phase 7-B0 frozen)

Phase 7-B0 ships:
- `StorageMetadata` type (version / author / timestamp / changeReason)
- `FutureAccountMetadata` type (owner / project / visibility — fields ONLY, no auth)
- `StorageMode` enum (local / remote / hybrid)
- `KnowledgeStorageProvider` interface (CRUD + search + history)
- `StorageConfig` type (mode / endpoint / sync / conflict resolution)
- Validator contracts for each

Phase 7-B0 explicitly does **NOT** ship:
- ❌ SQLite / PostgreSQL / any database
- ❌ Local / remote storage implementation
- ❌ Sync layer implementation
- ❌ Vector store integration
- ❌ User authentication
- ❌ Permission service

## 2. Layer diagram (Phase 7-B0)

```
                       Research Agent
                             │
                             ▼
                  Knowledge Provider API
                             │
                             ▼
                ┌────────────┼────────────┐
                │            │            │
           Local Store  Lab Server   Vector Store
                │            │            │
                └────────────┼────────────┘
                             │
                  (Phase 7+ implementations)
```

Three independent storage backends (Phase 7+):
- **Local Store**: SQLite / electron-store (desktop, offline)
- **Lab Server**: PostgreSQL / network attached
- **Vector Store**: pgvector / FAISS (Phase 7-C, future)

Phase 7-B0 defines the **Provider API** that all three implement. The renderer / chat-stream / Model layers see only the Provider API; they never touch raw databases.

## 3. Independence boundary (Phase 7-B0 strict)

The Storage Layer does NOT depend on:

| Layer | Why independent |
|-------|------------------|
| Model Provider (`desktop/src/main/services/model-provider/`) | Storage holds science, not LLM config |
| Capability Router (`desktop/src/main/services/model-provider/capability-router.ts`) | Routing is a runtime concern; storage is persistence |
| Chat Runtime (`desktop/src/main/services/chat/chat-stream.service.ts`) | Storage persists; streams are ephemeral |
| Auth (`desktop/src/main/services/auth/`, `desktop/src/auth/`, `desktop/src/renderer/auth/`) | Storage layer is independent of authentication |
| Legacy FastAPI (`backend/`) | New schema; old backend has its own domain |
| LLM SDKs (anthropic / openai / etc.) | Storage holds structured data, not LLM calls |

Cross-cutting rules:

- Storage Layer **only depends on**:
  - `desktop/src/shared/knowledge/schemas.ts` (Phase 7-A0 entity / metadata types)
  - `desktop/src/shared/knowledge/storage.ts` (Phase 7-B0 contracts)
- Storage Layer **never imports** from `model-provider/`, `auth/`, `chat/`, `backend/`, or any LLM SDK package.
- Storage Layer **never holds** `apiKey` / `token` / `cipher` / `Authorization` (Phase 7-B0 strict: `assertNoSecret` runs on every validator).

## 4. Persistence boundary

```
+-------------------------------------------------------+
|                  Renderer (Phase 6 frozen)            |
|  - chat-stream Pinia stores (volatile)                 |
|  - ModelSelector / TaskSelector (volatile)             |
+-------------------------------------------------------+
                            │ IPC
                            ▼
+-------------------------------------------------------+
|              Main Process (Phase 6 frozen)             |
|  - chat-stream.service.ts (FastAPI / provider)        |
|  - model-provider/* (Phase 6-A..D)                    |
+-------------------------------------------------------+
                            │ imports
                            ▼
+-------------------------------------------------------+
|           Knowledge Layer (Phase 7-A0 frozen)          |
|  - schemas.ts (entity + metadata types)               |
|  - storage.ts (Phase 7-B0 storage contracts)           |
+-------------------------------------------------------+
                            │ imports
                            ▼
+-------------------------------------------------------+
|         Storage Providers (Phase 7+ — not 7-B0)       |
|  - SqliteLocalProvider (Phase 7-B)                    |
|  - PostgresLabServerProvider (Phase 7-B+)             |
|  - VectorStore (Phase 7-C)                            |
+-------------------------------------------------------+
```

The Storage Layer sits BELOW Knowledge but ABOVE the actual database engines. Knowledge never imports from Storage; Storage imports Knowledge.

## 5. Storage modes (Phase 7-B0)

```
type StorageMode = 'local' | 'remote' | 'hybrid'

local    — desktop only, no network (offline research / students)
remote   — lab server only, no local cache (multi-user lab)
hybrid   — local cache + remote primary (production research OS)
```

Phase 7-B0 ships the enum + config. Phase 7+ ships the implementations + sync layer.

## 6. Provider interface (Phase 7+ sketch — see storage-provider-interface.md)

```ts
interface KnowledgeStorageProvider {
  initialize(): Promise<void>
  close(): Promise<void>
  create(entity, meta): Promise<string>           // returns ID
  update(id, entity, meta): Promise<void>
  delete(id, reason): Promise<void>
  get(id): Promise<KnowledgeEntity | null>
  list(type, options?): Promise<KnowledgeEntity[]>
  search(query): Promise<KnowledgeSearchResult>
  getStorageMetadata(id): Promise<StorageMetadata | null>
  getVersionHistory(id): Promise<StorageMetadata[]>
  attachAccount(id, account): Promise<void>
}
```

Phase 7-B0 ships the interface. Phase 7+ ships 3 implementations (SqliteLocal / PostgresLab / HybridCache).

## 7. Phase 7-B0 strict forbids

- ❌ Import from `desktop/src/main/services/model-provider/`
- ❌ Import from `desktop/src/main/services/auth/`
- ❌ Import from `desktop/src/auth/`
- ❌ Import from `desktop/src/renderer/auth/`
- ❌ Import from `desktop/src/main/services/chat/`
- ❌ Import from `backend/`
- ❌ Add Electron IPC handlers in Phase 7-B0
- ❌ Add renderer stores / components in Phase 7-B0
- ❌ Add any database connection (SQLite / Postgres / vector / etc.)
- ❌ Persist any data to disk in Phase 7-B0
- ❌ Include `apiKey` / `token` / `cipher` / `Authorization` anywhere

## 8. Phase 7-B0 file manifest

```
desktop/src/shared/knowledge/
  - schemas.ts                       (Phase 7-A0)
  - storage.ts                       (Phase 7-B0 NEW: storage contracts)

desktop/docs/knowledge/
  - scientific-domain-model.md      (Phase 7-A0)
  - knowledge-relationship-model.md (Phase 7-A0)
  - scientific-metadata-standard.md  (Phase 7-A0)
  - knowledge-layer-architecture.md (Phase 7-A0)
  - rag-extension-plan.md            (Phase 7-A0)
  - storage-architecture.md          (Phase 7-B0 NEW: this file)
  - storage-provider-interface.md    (Phase 7-B0)
  - local-storage-strategy.md        (Phase 7-B0)
  - lab-server-architecture.md       (Phase 7-B0)
  - knowledge-versioning.md          (Phase 7-B0)
  - future-account-compatibility.md  (Phase 7-B0)
  - storage-migration-plan.md        (Phase 7-B0)

desktop/tests/unit/
  - knowledge-schema.test.ts          (Phase 7-A0)
  - knowledge-storage-architecture.test.ts (Phase 7-B0 NEW)
```

## 9. References

- `docs/knowledge/scientific-domain-model.md` (Phase 7-A0 Step 2)
- `docs/knowledge/knowledge-relationship-model.md` (Phase 7-A0 Step 3)
- `docs/knowledge/scientific-metadata-standard.md` (Phase 7-A0 Step 4)
- `docs/knowledge/knowledge-layer-architecture.md` (Phase 7-A0 Step 5)
- `docs/knowledge/rag-extension-plan.md` (Phase 7-A0 Step 6)
- `docs/knowledge/storage-provider-interface.md` (Phase 7-B0 Step 3)
- `docs/knowledge/local-storage-strategy.md` (Phase 7-B0 Step 4)
- `docs/knowledge/lab-server-architecture.md` (Phase 7-B0 Step 5)
- `docs/knowledge/knowledge-versioning.md` (Phase 7-B0 Step 6)
- `docs/knowledge/future-account-compatibility.md` (Phase 7-B0 Step 7)
- `docs/knowledge/storage-migration-plan.md` (Phase 7-B0 Step 8)
- `desktop/src/shared/knowledge/storage.ts` (Phase 7-B0 contracts)

## Status (2026-08-22 Phase 7-B0)

- `storage.ts` — KnowledgeStorageProvider interface + 6 supporting types + 4 validators + assertNoSecret
- Storage Layer boundaries documented (independence from Model / Auth / Chat / Legacy)
- 0 dependencies on Model / Auth / Chat / Legacy layers (verified by import-graph tests Phase 7+)
- Doc complete (9 sections)
