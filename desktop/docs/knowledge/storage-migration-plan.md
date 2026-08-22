# Storage Migration Plan (Phase 7-B0)

> **purpose**: Define the staged migration path from local desktop storage to a multi-user research platform. Phase 7-B0 ships ONLY the plan — NO implementation.
> **follows**: `storage-architecture.md` + `local-storage-strategy.md` + `lab-server-architecture.md` (Phase 7-B0 Steps 2/4/5).
> **Phase 7-B0 strict**: plan only. NO actual storage migration code.

## 1. Scope (Phase 7-B0 frozen)

Four staged rollout:

| Stage | Scope | Mode | Phase |
|-------|-------|------|-------|
| 1 | Local desktop storage | `local` | 7-B |
| 2 | Shared lab server | `remote` | 7-B+ |
| 3 | Hybrid local cache + cloud | `hybrid` | 7-B+ |
| 4 | Multi-user platform | `hybrid` + multi-tenant | 8+ |

Phase 7-B0 ships ONLY the plan. Phase 7-B+ ships Stage 2. Phase 8+ ships Stages 3-4.

## 2. Stage 1 — Local desktop storage

### Goal

Single-user desktop research with no network dependency.

### Storage

- **Backend**: SQLite (single file `<userData>/knowledge/knowledge.db`)
- **Library**: `better-sqlite3` (Electron-compatible native binding)
- **Schema**: maps Phase 7-A0 entities to SQL tables
- **Versioning**: append-only `versions` table (Phase 7-B0 contract)
- **Encryption**: SQLCipher (optional, off by default)

### Capabilities

- ✅ Create / Read / Update / Delete entities
- ✅ Full-text search (SQLite FTS5)
- ✅ Version history (Phase 7-B0 `getVersionHistory`)
- ✅ Soft delete via tombstone (Phase 7-B0 contract)
- ✅ Local backup (manual copy of `<userData>/knowledge/` folder)
- ❌ Multi-user (single writer)
- ❌ Cloud sync (Phase 7-B+)
- ❌ Vector search (Phase 7-C)
- ❌ RAG (Phase 7+)

### Migration trigger (to Stage 2)

- Lab has 5+ users wanting to share knowledge
- Multi-user collaboration requested
- Network available in lab

### Phase 7-B (Stage 1) deliverables

- `SqliteLocalProvider implements KnowledgeStorageProvider`
- Phase 7-A0 schema → SQL schema mapping
- Migrations via `PRAGMA user_version`
- Phase 7-B0 versioning contract applied
- 1 .db file per desktop install

## 3. Stage 2 — Shared lab server

### Goal

Multi-user lab with shared knowledge base.

### Storage

- **Backend**: PostgreSQL 15+ (managed or self-hosted)
- **Lab server**: Node.js API server
- **Schema**: Phase 7-A0 entities → Postgres tables
- **Replication**: standard Postgres streaming replication
- **Backups**: `pg_dump` daily + WAL archiving

### Capabilities

- ✅ Everything from Stage 1
- ✅ Multi-user concurrent reads + writes (Postgres MVCC)
- ✅ Concurrent edit detection (Phase 7-B0 versioning + version number)
- ✅ Lab-server sync (Phase 7-B0 sync layer)
- ❌ Cloud sync (Stage 3)
- ❌ Vector search (Phase 7-C — adds pgvector extension)
- ❌ RAG (Phase 7+)

### Migration trigger (to Stage 3)

- Lab wants cross-device access (home / office / lab bench)
- Need for offline editing with sync
- Vector search demands (Phase 7-C)

### Phase 7-B+ (Stage 2) deliverables

- `PostgresLabServerProvider implements KnowledgeStorageProvider`
- REST + WebSocket API server
- Sync layer (push / pull / two-way / conflict resolution)
- Permission service (Phase 7-B0 `FutureAccountMetadata` fields become columns)

## 4. Stage 3 — Hybrid local cache + cloud

### Goal

Single-user desktop with offline editing AND cloud sync.

### Storage

- **Local**: SQLite (Stage 1)
- **Cloud**: Postgres (Stage 2) + S3-compatible blob
- **Sync layer**: bidirectional with conflict resolution (Phase 7-B0)

### Capabilities

- ✅ Everything from Stage 1 + 2
- ✅ Offline editing (desktop cache)
- ✅ Cloud sync on reconnect
- ✅ Multi-device (desktop / laptop / lab bench)
- ✅ Vector search via `pgvector` (Phase 7-C)
- ❌ Multi-user real-time collaboration (Stage 4)

### Migration trigger (to Stage 4)

- Lab has 50+ users
- Real-time collaboration needed (multiple users editing same paper)
- Need for institutional / cross-institution sharing

### Phase 7-B+ (Stage 3) deliverables

- `HybridCacheProvider` (wraps Stage 1 + Stage 2)
- Conflict resolution: `newest-wins` default (Phase 7-B0)
- Vector index sync between desktop cache and cloud

## 5. Stage 4 — Multi-user research platform

### Goal

Institutional / cross-institution multi-tenant platform.

### Storage

- **Cloud**: Managed Postgres (AWS RDS / GCP Cloud SQL)
- **Blob**: S3-compatible (AWS S3 / GCP Storage / MinIO)
- **Auth**: Phase 7+ picks (Auth0 / Cognito / Keycloak / etc.) — NOT in Phase 7-B0
- **Tenant isolation**: row-level security (Postgres RLS) or per-tenant schema

### Capabilities

- ✅ Everything from Stage 1-3
- ✅ Multi-tenant (each lab has its own knowledge base)
- ✅ Real-time collaboration (operational transform / CRDT)
- ✅ Institutional sharing (cross-lab knowledge transfer)
- ✅ Audit + compliance (HIPAA / GDPR ready)
- ✅ SLO monitoring (Prometheus + Grafana)

### Phase 8+ (Stage 4) deliverables

- Multi-tenant data model (tenant_id column on every row)
- Permission service (Phase 7+ picks implementation)
- Audit log
- SLO dashboards

## 6. Cross-stage migration rules

| From → To | What changes |
|----------|--------------|
| 1 → 2 | Add Postgres on lab server; desktops gain sync layer |
| 2 → 3 | Add SQLite local cache on each desktop; conflict resolution enabled |
| 3 → 4 | Add tenant_id column; permission service; audit log |

### Forward compatibility

Each stage must remain forward-compatible:

- Stage 1 (Phase 7-B) data MUST import cleanly to Stage 2 schema (no data loss)
- Stage 2 (Phase 7-B+) data MUST import cleanly to Stage 3 (no schema break)
- Stage 3 data MUST import cleanly to Stage 4 (just adds tenant_id)

### Backward compatibility

Each stage must remain backward-compatible:

- Stage 4 client can still open Stage 3 data (just shows "no tenant" by default)
- Stage 3 client can still open Stage 2 data (no offline cache)
- Stage 2 client can still open Stage 1 data (read-only mode)

## 7. Schema migration example (Phase 7-A0 → Stage 1)

```sql
-- Phase 7-A0: papers schema (subset)
CREATE TABLE papers (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors TEXT NOT NULL,             -- JSON array
  journal TEXT NOT NULL,
  year INTEGER NOT NULL,
  doi TEXT,
  keywords TEXT NOT NULL,             -- JSON array
  research_field TEXT NOT NULL,
  abstract TEXT NOT NULL,
  methods TEXT,
  parameters TEXT,                   -- JSON array
  results TEXT,
  conclusions TEXT,
  related_experiments TEXT,          -- JSON array of IDs
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_research_field ON papers(research_field);

-- Phase 7-B0: version history
CREATE TABLE paper_versions (
  paper_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  previous_version TEXT,
  saved_at INTEGER NOT NULL,
  author TEXT,
  change_reason TEXT,
  changed_fields TEXT,                -- JSON array
  PRIMARY KEY (paper_id, version)
);

-- Phase 7-FTS (Stage 1): full-text search
CREATE VIRTUAL TABLE papers_fts USING fts5(
  title, abstract, keywords,
  content='papers'
);
```

The full schema is similar for experiments / equipment / datasets / figures / projects.

## 8. Backward-compatibility matrix

| Schema version | Stage 1 | Stage 2 | Stage 3 | Stage 4 |
|----------------|---------|---------|---------|---------|
| 1.0 (Phase 7-B) | native | import | import | import |
| 2.0 (Phase 7-B+) | read-only | native | import | import |
| 3.0 (Phase 7-B+ hybrid) | n/a | read-only | native | import |
| 4.0 (Phase 8+ multi-tenant) | n/a | n/a | read-only | native |

Phase 7-B0 ships the contract that schema upgrades MUST preserve data.

## 9. Phase 7-B0 strict forbids

- ❌ Implement any stage migration code
- ❌ Add a database connection
- ❌ Define actual SQL (only sketch in this doc)
- ❌ Add IPC handlers for sync
- ❌ Add a sync implementation
- ❌ Persist any data

## 10. References

- `docs/knowledge/storage-architecture.md` (Phase 7-B0 Step 2)
- `docs/knowledge/local-storage-strategy.md` (Phase 7-B0 Step 4 — Stage 1)
- `docs/knowledge/lab-server-architecture.md` (Phase 7-B0 Step 5 — Stages 2/3/4)
- `docs/knowledge/knowledge-versioning.md` (Phase 7-B0 Step 6 — append-only history)
- `docs/knowledge/future-account-compatibility.md` (Phase 7-B0 Step 7 — ownerId)
- `docs/knowledge/rag-extension-plan.md` (Phase 7-A0 Step 6 — RAG plugs into Stage 3 vector)
- `desktop/src/shared/knowledge/storage.ts` (Provider interface — same across stages)

## Status (2026-08-22 Phase 7-B0)

- 4-stage migration plan documented (Stage 1 SQLite → Stage 2 Postgres → Stage 3 Hybrid → Stage 4 Multi-tenant)
- Cross-stage forward + backward compatibility rules
- Schema migration example for Stage 1 (SQLite)
- Backward-compatibility matrix
- 0 implementations (Phase 7-B0 ships ONLY the plan)
- Doc complete (10 sections)
