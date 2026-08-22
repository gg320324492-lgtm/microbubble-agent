# Knowledge Storage Provider Interface (Phase 7-B0)

> **purpose**: Define the future storage provider interface. Phase 7-B0 ships ONLY the contract — NO implementation.
> **follows**: `storage-architecture.md` (Phase 7-B0 Step 2).
> **Phase 7-B0 strict**: interface must support local + remote + vector + sync. NO implementation.

## 1. Scope (Phase 7-B0 frozen)

Phase 7-B0 ships the `KnowledgeStorageProvider` interface in `desktop/src/shared/knowledge/storage.ts`. Phase 7+ ships 3 implementations:

- `SqliteLocalProvider` — Phase 7-B (desktop, offline)
- `PostgresLabServerProvider` — Phase 7-B+ (lab network)
- `HybridCacheProvider` — Phase 7-B+ (local cache + remote primary)

Phase 7-B0 explicitly does **NOT** ship:
- ❌ Any concrete class implementing `KnowledgeStorageProvider`
- ❌ A factory / DI container
- ❌ A connection pool
- ❌ IPC handlers

## 2. The interface

```ts
interface KnowledgeStorageProvider {
  // ===== Lifecycle =====
  initialize(): Promise<void>
  close(): Promise<void>

  // ===== CRUD =====
  create(entity: KnowledgeEntity, meta: StorageMetadata): Promise<string>
  update(id: string, entity: KnowledgeEntity, meta: StorageMetadata): Promise<void>
  delete(id: string, reason: string): Promise<void>
  get(id: string): Promise<KnowledgeEntity | null>
  list(
    type: KnowledgeEntityType,
    options?: { limit?: number; offset?: number }
  ): Promise<KnowledgeEntity[]>

  // ===== Search =====
  search(query: KnowledgeQuery): Promise<KnowledgeSearchResult>

  // ===== Versioning =====
  getStorageMetadata(id: string): Promise<StorageMetadata | null>
  getVersionHistory(id: string): Promise<StorageMetadata[]>

  // ===== Future account (Phase 7+) =====
  attachAccount(id: string, account: FutureAccountMetadata): Promise<void>
}
```

All inputs use `KnowledgeEntity` (entity union from Phase 7-A0) and `StorageMetadata` (Phase 7-B0). All outputs are non-secret.

## 3. Method-by-method contract

### `initialize()`

Opens the underlying storage (SQLite file / Postgres connection / vector store connection). Idempotent.

- Returns when storage is ready
- Throws on connection failure
- Phase 7-B0: signature only

### `close()`

Closes the underlying storage. Releases handles / connections.

- Idempotent
- Phase 7-B0: signature only

### `create(entity, meta) → string`

Persists a new entity. Returns the entity ID.

- `entity` MUST pass `isValidPaper` / `isValidExperiment` / etc.
- `meta` MUST pass `isValidStorageMetadata`
- `meta.version` MUST be 1 (first save)
- `meta.previousVersion` MUST be null
- Throws on validation failure
- Throws on duplicate ID
- Phase 7-B0: signature only

### `update(id, entity, meta) → void`

Updates an existing entity. Does NOT mutate the previous version — see `getVersionHistory`.

- `meta.version` MUST be `prev.version + 1`
- `meta.previousVersion` MUST be `prev`'s full versioned ID
- Throws if entity ID does not exist
- Throws on version mismatch (concurrent edit detection)
- Phase 7-B0: signature only

### `delete(id, reason) → void`

Soft-deletes an entity.

- `reason` is logged in the audit trail
- The entity remains recoverable via `getVersionHistory`
- Phase 7-B0: signature only

### `get(id) → KnowledgeEntity | null`

Returns the current version of an entity.

- Returns null if not found
- Phase 7-B0: signature only

### `list(type, options?) → KnowledgeEntity[]`

Returns all current-version entities of a type.

- `options.limit` defaults to 100 (Phase 7+ may paginate)
- `options.offset` defaults to 0
- Phase 7-B0: signature only

### `search(query) → KnowledgeSearchResult`

Free-text + structured search.

```ts
interface KnowledgeQuery {
  text?: string
  filters?: {
    entityType?: KnowledgeEntityType
    researchField?: string
    keywords?: string[]
    dateRange?: { from: number; to: number }
  }
  limit?: number
}
```

Phase 7-B0: signature only. Phase 7-C ships the actual retrieval (vector + structured).

### `getStorageMetadata(id) → StorageMetadata | null`

Returns the current version's metadata (version / savedAt / author / changeReason / changedFields).

- Phase 7-B0: signature only

### `getVersionHistory(id) → StorageMetadata[]`

Returns ALL versions of an entity, oldest first.

- Empty array if entity never existed
- Phase 7-B0: signature only

### `attachAccount(id, account) → void`

Phase 7+ only — Phase 7-B0 ships the signature. The `FutureAccountMetadata` carries ownership / project / visibility fields (no auth module dependency).

- Phase 7-B0: signature only

## 4. Cross-cutting requirements (Phase 7-B0 strict)

| Requirement | How enforced |
|-------------|--------------|
| No apiKey | `assertNoSecret` on every input validator |
| No LLM dependency | Storage interface accepts only `KnowledgeEntity` types |
| No auth dependency | `FutureAccountMetadata` is fields-only |
| No legacy backend | Storage interface is independent of FastAPI |
| Phase 3-B0 schema contracts unchanged | Storage consumes Phase 7-A0 types |

## 5. Implementation variants (Phase 7+ sketches — NOT in Phase 7-B0)

### Local SQLite (Phase 7-B)

```ts
class SqliteLocalProvider implements KnowledgeStorageProvider {
  private db: Database
  
  async initialize(): Promise<void> {
    this.db = new Database(this.path)
    this.db.exec(`CREATE TABLE IF NOT EXISTS papers (...)`)
  }
  
  async create(entity: KnowledgeEntity, meta: StorageMetadata): Promise<string> {
    // INSERT INTO papers (...) VALUES (...)
  }
  // ... etc
}
```

### Lab server Postgres (Phase 7-B+)

```ts
class PostgresLabServerProvider implements KnowledgeStorageProvider {
  private client: Pool
  
  async initialize(): Promise<void> {
    this.client = new Pool({ connectionString: this.dsn })
  }
  
  async create(entity, meta): Promise<string> {
    await this.client.query('INSERT INTO knowledge ...')
  }
  // ... etc
}
```

### Hybrid cache + remote (Phase 7-B+)

```ts
class HybridCacheProvider implements KnowledgeStorageProvider {
  private cache: SqliteLocalProvider
  private remote: PostgresLabServerProvider
  
  async get(id): Promise<KnowledgeEntity | null> {
    const local = await this.cache.get(id)
    if (local && !this.isStale(local, this.cache.getStorageMetadata(id))) {
      return local
    }
    const fresh = await this.remote.get(id)
    await this.cache.update(id, fresh, ...)
    return fresh
  }
}
```

Phase 7-B0: all 3 are sketches in this doc. Implementation deferred.

## 6. Sync layer (Phase 7-B+ sketch)

```ts
interface KnowledgeSyncLayer {
  push(entityIds: string[], direction: SyncDirection): Promise<void>
  pull(entityIds: string[], direction: SyncDirection): Promise<void>
  resolve(local: KnowledgeEntity, remote: KnowledgeEntity, strategy: ConflictResolution): KnowledgeEntity
}
```

Phase 7-B0: signature only. Phase 7-B+ ships:
- `push` for offline-first → server sync
- `pull` for fresh-fetch
- `resolve` for conflict mediation (Phase 7-B+ may integrate CRDT)

## 7. Vector store integration (Phase 7-C sketch)

```ts
interface VectorKnowledgeStorageProvider extends KnowledgeStorageProvider {
  upsertEmbedding(id: string, vector: number[], metadata: Record<string, unknown>): Promise<void>
  searchByEmbedding(vector: number[], topK: number): Promise<KnowledgeSearchHit[]>
  hybridSearch(query: KnowledgeQuery, vector?: number[]): Promise<KnowledgeSearchResult>
}
```

Phase 7-B0: signature only. Phase 7-C ships the embedding integration.

## 8. Phase 7-B0 strict forbids

- ❌ Add IPC handlers
- ❌ Add a concrete `KnowledgeStorageProvider` implementation
- ❌ Persist any data (Phase 7-B0 is architecture-only)
- ❌ Import from `model-provider/`, `auth/`, `chat/`, `backend/`, or any LLM SDK
- ❌ Include `apiKey` / `token` / `cipher` / `Authorization` in any field
- ❌ Add a database connection

## 9. References

- `docs/knowledge/storage-architecture.md` (Phase 7-B0 Step 2 — layer diagram)
- `docs/knowledge/local-storage-strategy.md` (Phase 7-B0 Step 4 — Option A SQLite)
- `docs/knowledge/lab-server-architecture.md` (Phase 7-B0 Step 5 — Option B Postgres)
- `docs/knowledge/knowledge-versioning.md` (Phase 7-B0 Step 6 — StorageMetadata)
- `docs/knowledge/future-account-compatibility.md` (Phase 7-B0 Step 7 — FutureAccountMetadata)
- `desktop/src/shared/knowledge/storage.ts` (interface implementation)

## Status (2026-08-22 Phase 7-B0)

- `KnowledgeStorageProvider` interface (10 methods)
- `KnowledgeEntity` / `KnowledgeEntityType` / `KnowledgeMetadata` type unions
- `StorageConfig` / `StorageMode` / `SyncDirection` / `ConflictResolution` enums
- 4 validators (`isValidStorageMetadata` / `isValidFutureAccountMetadata` / `isValidStorageConfig` / `isValidEntityType` / `isValidSyncDirection`)
- `assertNoSecret` defensive guard on every validator
- 0 implementations (Phase 7-B0 ships ONLY the contracts)
- Doc complete (9 sections)
