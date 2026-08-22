# Lab Server Architecture (Phase 7-B0)

> **purpose**: Design the future lab-server tier of the Knowledge Layer. Phase 7-B0 ships ONLY the architecture — NO implementation.
> **follows**: `local-storage-strategy.md` (Phase 7-B0 Step 4) — SQLite is the desktop tier; this doc is the **lab server tier**.
> **Phase 7-B0 strict**: design only. NO database / NO backend / NO IPC.

## 1. Scope (Phase 7-B0 frozen)

Phase 7-B0 ships the architecture for a future lab server that:

- Hosts the shared lab knowledge base (postgraduate / staff / collaborators)
- Provides multi-user concurrency (5-50 active researchers)
- Replicates with desktop clients (Phase 7-B+ sync layer)
- Eventually runs an embedding service (Phase 7-C) + RAG pipeline (Phase 7+)

Phase 7-B0 ships ONLY the architecture. Phase 7-B+ ships the deployment.

## 2. Layer diagram (Phase 7-B0)

```
              ┌────────────────────────────┐
              │     Student Desktop (N)     │
              │  ┌──────────────────────┐  │
              │  │  SqliteLocalProvider  │  │
              │  │  (Phase 7-B)          │  │
              │  └──────────┬───────────┘  │
              └─────────────┼──────────────┘
                            │ HTTPS / WSS
                            ▼
              ┌────────────────────────────┐
              │   Knowledge Sync Layer     │
              │   ┌────────────────────┐   │
              │   │ ConflictResolver   │   │
              │   │ CRDT / vector clock│   │
              │   └────────────────────┘   │
              └─────────────┬──────────────┘
                            │
                            ▼
              ┌────────────────────────────┐
              │     Lab Knowledge Server    │
              │  ┌──────────────────────┐  │
              │  │  REST / GraphQL API   │  │
              │  └──────────┬───────────┘  │
              └─────────────┼──────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
     │  SQL DB     │ │ Vector DB   │ │ File Store  │
     │ (Postgres)  │ │ (pgvector / │ │ (S3 / NFS)  │
     │             │ │  FAISS)     │ │             │
     └─────────────┘ └─────────────┘ └─────────────┘
```

## 3. Server future components (Phase 7-B+)

### 3.1 SQL database (Phase 7-B+)

- **Choice**: PostgreSQL 15+
- **Why**: row-level locking, mature replication, JSONB columns for `ExtensionFields`
- **Schema sketch**: maps Phase 7-A0 entities to tables (paper / experiment / equipment / dataset / figure / project + version table)
- **Migrations**: standard `pg-migrate` or `node-pg-migrate`

### 3.2 Vector database (Phase 7-C)

- **Choice A**: `pgvector` extension inside Postgres (single DB, simpler ops)
- **Choice B**: standalone Qdrant / Milvus (better scale, separate ops)
- **Recommendation**: `pgvector` for Phase 7-C; migrate to Qdrant in Phase 8+ if scale demands
- **Embedding model**: Phase 7-B0 doesn't pick — left to Phase 7-E

### 3.3 File storage (Phase 7-B+)

- **PDF originals** + **figure assets** need blob storage
- **Option A**: S3-compatible (MinIO local, AWS S3 cloud)
- **Option B**: NFS share (lab-only, no cloud)
- **Recommendation**: S3-compatible (MinIO for lab, AWS S3 for cloud) — Phase 7-B+ ships the client

### 3.4 Permission service (Phase 7-B+)

- **Phase 7-B0 strict**: NO auth module dependency
- **Future contract** (NOT IMPLEMENTED):
  - `ownerId` / `projectId` / `visibility` fields per entity (already in `FutureAccountMetadata`)
  - Read: `private` / `lab-shared` / `public`
  - Write: only owner OR project-lead
- **Implementation**: Phase 7-B+ picks (Postgres RLS / external service / etc.)

### 3.5 Audit + observability (Phase 7-B+)

- Per-entity version history (Phase 7-B0 `StorageMetadata`)
- Sync event log (push / pull / conflict)
- Usage metrics (read counts per entity)
- All events timestamped + signed

## 4. Sync layer (Phase 7-B+)

```
Desktop (SqliteLocalProvider)
    │
    │  HTTPS
    ▼
Sync Layer (runs on lab server, OR on desktop)
    │
    │  WebSocket / Server-Sent Events
    ▼
PostgresLabServerProvider
```

Sync operations:
- **push**: desktop → server (new entity / new version)
- **pull**: server → desktop (refresh stale cache)
- **two-way**: bidirectional (Phase 7-B+ conflict resolution)

Conflict resolution strategies (Phase 7-B0 enum):
- `local-wins`: desktop overwrites server
- `remote-wins`: server overwrites desktop
- `newest-wins`: compare `StorageMetadata.savedAt` and keep the newer
- `manual`: surface UI prompt (Phase 7-B+ UI)

## 5. API contract (Phase 7-B+ sketch — NOT IMPLEMENTED)

```
POST   /v1/papers              — create Paper
GET    /v1/papers/:id          — fetch Paper
PUT    /v1/papers/:id          — update Paper (auto-increments version)
DELETE /v1/papers/:id          — soft-delete Paper
GET    /v1/papers              — list (paginated, filtered)
POST   /v1/papers/search       — search (Phase 7-C: vector + structured)
GET    /v1/papers/:id/history  — version history

(same shape for /experiments / equipment / datasets / figures / projects)

POST   /v1/sync/push           — desktop → server
POST   /v1/sync/pull           — server → desktop
POST   /v1/sync/resolve        — manual conflict resolution
WS     /v1/sync/events         — server-pushed events (push / pull / conflict)
```

All API payloads follow Phase 7-A0 schema contracts. NO apiKey / token in payloads.

## 6. Deployment (Phase 7-B+ sketch — NOT IMPLEMENTED)

```
Single lab server (small lab, 5-15 users):
  - 1x Postgres 15 (with pgvector)
  - 1x MinIO (or local FS)
  - 1x Node.js API server (Phase 7-B+)
  - 1x nginx reverse proxy

Cloud (large lab, 50+ users, Phase 8+):
  - Managed Postgres (AWS RDS / GCP Cloud SQL)
  - S3-compatible blob (AWS S3 / GCP Storage)
  - Kubernetes for API server
  - CloudFront / nginx edge
```

Phase 7-B0 ships ONLY the architecture. No actual lab server exists yet.

## 7. Cost / scale (informational — Phase 7-B+ to validate)

| Component | Lab-scale (5-15 users) | Cloud-scale (50+ users) |
|-----------|----------------------|------------------------|
| Postgres | $50/mo (managed) | $500/mo (managed + replica) |
| MinIO/S3 | $0 (local FS) | $20/mo (S3 standard) |
| API server | $10/mo (1 vCPU) | $100/mo (k8s) |
| Total | ~$60/mo | ~$620/mo |

Phase 7-B0 ships ONLY the architecture. Cost is informational.

## 8. Phase 7-B0 strict forbids

- ❌ Implement the lab server in this phase
- ❌ Define REST endpoints in code (only sketched in this doc)
- ❌ Add an API server dependency
- ❌ Add IPC handlers that talk to the server
- ❌ Add a Postgres / S3 connection
- ❌ Add a sync implementation (interface only in Phase 7-B0)
- ❌ Import from `auth/` modules

## 9. References

- `docs/knowledge/storage-architecture.md` (Phase 7-B0 Step 2 — desktop + server + vector layers)
- `docs/knowledge/storage-provider-interface.md` (Phase 7-B0 Step 3 — `KnowledgeStorageProvider`)
- `docs/knowledge/local-storage-strategy.md` (Phase 7-B0 Step 4 — desktop tier = SQLite)
- `docs/knowledge/knowledge-versioning.md` (Phase 7-B0 Step 6 — version metadata)
- `docs/knowledge/future-account-compatibility.md` (Phase 7-B0 Step 7 — owner / project / visibility)
- `docs/knowledge/storage-migration-plan.md` (Phase 7-B0 Step 8 — staged rollout)
- `docs/knowledge/rag-extension-plan.md` (Phase 7-A0 — RAG pipeline plugs into the vector DB)

## Status (2026-08-22 Phase 7-B0)

- Lab-server architecture documented (SQL + Vector + File + Permission + Audit + Sync)
- API contract sketched (REST + WebSocket) — NOT IMPLEMENTED
- Sync layer architecture documented (push / pull / two-way / conflict resolution)
- Cost / scale guidance documented
- 0 implementations (Phase 7-B0 ships ONLY the architecture)
- Doc complete (9 sections)
