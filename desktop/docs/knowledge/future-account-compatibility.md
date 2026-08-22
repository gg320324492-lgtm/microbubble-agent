# Future Account Compatibility (Phase 7-B0)

> **purpose**: Define forward-compatible ownership / project / visibility fields. Phase 7-B0 ships ONLY the field shape — NO auth implementation, NO auth dependency.
> **follows**: `storage-architecture.md` (Phase 7-B0 Step 2).
> **Phase 7-B0 strict**: forward-compatible fields ONLY. NO import from auth modules.

## 1. Scope (Phase 7-B0 frozen)

Phase 7-B0 ships:
- `FutureAccountMetadata` type (ownerId / projectId / visibility / createdBy)
- 1 validator (`isValidFutureAccountMetadata`)
- The `attachAccount(id, account)` method on `KnowledgeStorageProvider`
- Forward-compatible design rules

Phase 7-B0 explicitly does **NOT** ship:
- ❌ Auth modules (`desktop/src/main/services/auth/`, `desktop/src/auth/`, `desktop/src/renderer/auth/`)
- ❌ Login / logout / session management
- ❌ OAuth / OIDC / SAML
- ❌ Token verification
- ❌ Permission service
- ❌ User profile

## 2. Future ownership hierarchy (Phase 7-B0 design only)

```
        ┌──────────┐
        │   User   │   Phase 7+: real authenticated user
        └─────┬────┘
              │ ownerId
              ▼
        ┌──────────┐
        │ Project  │   Phase 7+: container of related entities
        └─────┬────┘
              │ projectId
              ▼
   ┌──────────────────────┐
   │   Knowledge Asset    │   Paper / Experiment / Equipment / Dataset / Figure
   └──────────────────────┘   + visibility: 'private' | 'lab-shared' | 'public'
```

Phase 7-B0 strict: this diagram is the design intent. NO entities reference any of these concepts yet. The fields are FORWARD-COMPATIBLE — they may be attached in Phase 7+ without modifying Phase 7-A0 schemas.

## 3. `FutureAccountMetadata` type

```ts
interface FutureAccountMetadata {
  /** Phase 7+ ownerId (string only). Phase 7-B0: empty string. */
  ownerId: string

  /** Phase 7+ projectId (string only). Phase 7-B0: empty string. */
  projectId: string

  /** Phase 7+ visibility. Phase 7-B0: 'private'. */
  visibility: 'private' | 'lab-shared' | 'public'

  /** Phase 7+ createdBy (string only). Phase 7-B0: empty string. */
  createdBy: string
}
```

### Field rules (Phase 7-B0 strict)

| Field | Type | Phase 7-B0 default | Phase 7+ future use |
|-------|------|--------------------|--------------------|
| `ownerId` | string | `""` | user ID (from auth) |
| `projectId` | string | `""` | project ID |
| `visibility` | enum | `'private'` | `'private'` / `'lab-shared'` / `'public'` |
| `createdBy` | string | `""` | user ID (from auth) |

### Validator

`isValidFutureAccountMetadata(a: unknown): a is FutureAccountMetadata`

- `ownerId` is a string
- `projectId` is a string
- `visibility` is one of the 3 valid values
- `createdBy` is a string
- `assertNoSecret` runs on the whole payload

## 4. Visibility semantics (Phase 7-B0 design)

| Value | Phase 7-B0 meaning | Phase 7+ future meaning |
|-------|-------------------|------------------------|
| `private` | only the local desktop can see | only `ownerId` can see |
| `lab-shared` | N/A in Phase 7-B0 (no lab server yet) | `projectId`'s lab can see |
| `public` | N/A in Phase 7-B0 | anyone with the entity ID can see |

Phase 7-B0 ships the enum. Phase 7+ enforces the visibility rules.

## 5. Why these fields are on `FutureAccountMetadata` (not on `KnowledgeEntity`)

Phase 7-A0 entities (Paper / Experiment / etc.) are **purely scientific**. They do NOT carry ownership / project / visibility because:

- A published paper is a public scientific fact — ownership is irrelevant to the science
- An experiment's parameters / measurements are reproducible — ownership doesn't change the data
- Visibility is a STORAGE-LAYER concern (who can READ this row in the database), not a SCIENCE concern

Therefore:
- **Phase 7-A0 entities** (Paper / Experiment / ...): no ownership fields
- **Phase 7-B0 storage layer** (`FutureAccountMetadata`): ownership fields as a sidecar

The storage layer attaches `FutureAccountMetadata` to entities via `attachAccount(id, account)`. The entities themselves remain untouched.

## 6. How Phase 7+ uses these fields

```
Phase 7+ SQL schema:

CREATE TABLE knowledge (
  entity_id    TEXT PRIMARY KEY,
  entity_type  TEXT NOT NULL,
  entity_body  JSONB NOT NULL,        -- Phase 7-A0 schema content
  version      INT NOT NULL,          -- Phase 7-B0 StorageMetadata.version
  previous_version TEXT,
  saved_at     BIGINT NOT NULL,
  author       TEXT,                  -- Phase 7-B0 FutureAccountMetadata.createdBy
  owner_id     TEXT,                  -- Phase 7-B0 FutureAccountMetadata.ownerId
  project_id   TEXT,                  -- Phase 7-B0 FutureAccountMetadata.projectId
  visibility   TEXT DEFAULT 'private'
);
```

The Phase 7-B0 fields become columns in the future SQL schema. Phase 7+ does NOT modify Phase 7-A0 `KnowledgeEntity` types — it adds sidecar metadata at the storage layer.

## 7. Phase 7-B0 strict forbids

- ❌ Import from `desktop/src/main/services/auth/`
- ❌ Import from `desktop/src/auth/`
- ❌ Import from `desktop/src/renderer/auth/`
- ❌ Add a User type
- ❌ Add a Project type
- ❌ Add session / token / cookie types
- ❌ Reference `userId` directly (use the `ownerId` field)
- ❌ Hard-code any auth provider name (OAuth / OIDC / etc.)

## 8. Why `FutureAccountMetadata` is separate from `StorageMetadata`

| Concern | Type | Carries |
|---------|------|---------|
| Versioning | `StorageMetadata` | version / savedAt / author (free-text) / changeReason / changedFields |
| Account | `FutureAccountMetadata` | ownerId / projectId / visibility / createdBy |

These are deliberately separate because:

- `StorageMetadata` is per-version (each version has its own)
- `FutureAccountMetadata` is per-entity (shared across all versions of the same entity)
- Phase 7+ may persist `StorageMetadata` in a `versions` table and `FutureAccountMetadata` in the main `knowledge` row

## 9. Phase 7+ migration path (NOT IMPLEMENTED in 7-B0)

```
Phase 7-B0:
  KnowledgeEntity { id, title, ... }                       <- no ownership
  StorageMetadata { version, author: '', ... }              <- empty author
  FutureAccountMetadata { ownerId: '', visibility: 'private', ... }  <- empty strings

Phase 7+ (auth added):
  KnowledgeEntity { id, title, ... }                       <- STILL no ownership
  StorageMetadata { version, author: 'alice', ... }         <- author populated
  FutureAccountMetadata { ownerId: 'user:alice', visibility: 'lab-shared', ... }  <- populated

The schema contracts from Phase 7-A0 + 7-B0 are UNCHANGED. Only the runtime values change.
```

## 10. References

- `docs/knowledge/storage-architecture.md` (Phase 7-B0 Step 2)
- `docs/knowledge/storage-provider-interface.md` (Phase 7-B0 Step 3 — `attachAccount` method)
- `docs/knowledge/lab-server-architecture.md` (Phase 7-B0 Step 5 — future permission service)
- `docs/knowledge/knowledge-versioning.md` (Phase 7-B0 Step 6 — author field in StorageMetadata)
- `desktop/src/shared/knowledge/storage.ts` (FutureAccountMetadata contract)

## Status (2026-08-22 Phase 7-B0)

- `FutureAccountMetadata` type with 4 fields (ownerId / projectId / visibility / createdBy)
- `isValidFutureAccountMetadata` validator
- `attachAccount(id, account)` method on `KnowledgeStorageProvider`
- Visibility semantics documented (3 levels)
- Forward-compatibility rules (Phase 7-A0 entities stay scientific, ownership is sidecar)
- 0 auth module dependencies (verified by import-graph test Phase 7+)
- Doc complete (10 sections)
