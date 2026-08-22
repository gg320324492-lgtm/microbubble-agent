# Knowledge Versioning (Phase 7-B0)

> **purpose**: Define the versioning model for Knowledge entities. Scientific data MUST NOT be silently overwritten — each save is a new version, and the full history is preserved.
> **follows**: `storage-architecture.md` (Phase 7-B0 Step 2) + `storage-provider-interface.md` (Phase 7-B0 Step 3).
> **Phase 7-B0 strict**: versioning contract only. NO implementation.

## 1. Scope (Phase 7-B0 frozen)

Phase 7-B0 ships:
- `StorageMetadata` type (version / previousVersion / savedAt / author / changeReason / changedFields)
- Versioning rules (immutable history, monotonic version, append-only audit)
- 1 validator (`isValidStorageMetadata`)
- Conflict-resolution policies (`newest-wins` recommended)

Phase 7-B0 explicitly does **NOT** ship:
- ❌ Storage backend with version history
- ❌ Diff / merge logic
- ❌ Audit log UI
- ❌ Branching / forking

## 2. Why versioning matters (Phase 7-B0)

Scientific entities represent:

- A paper that the user has read
- An experiment that was run on a specific date
- A dataset produced by an instrument at a specific time

When the user re-runs an experiment with a different `ozone_concentration`:

- v1: `{ ozone_concentration: 5.0 }` (Sept 15)
- v2: `{ ozone_concentration: 7.5 }` (Sept 20)

Both are real experiments. The user may want to cite v1 in a paper they're writing. **Silent overwrite would destroy the citation.**

## 3. Versioning rules (Phase 7-B0 strict)

```
Rule 1: monotonic version
  - first save: version = 1
  - second save: version = 2
  - Nth save: version = N
  - version MUST be a positive integer

Rule 2: previousVersion pointer
  - first save: previousVersion = null
  - Nth save (N > 1): previousVersion = "{id}:v{N-1}"
  - this is the BACK pointer to the prior version's full ID

Rule 3: append-only
  - Phase 7-B0 forbids UPDATE that overwrites version N
  - UPDATE creates a new version N+1
  - the prior version remains queryable via getVersionHistory

Rule 4: timestamp monotonic
  - savedAt is the epoch ms at save time
  - newer versions MUST have savedAt >= older versions' savedAt
  - the storage layer MUST reject out-of-order saves (e.g. N+1 with savedAt < N)

Rule 5: changedFields recorded
  - the array of field names that changed in this version
  - Phase 7+ may use this for "what's new" notifications
  - Phase 7-A0: empty array allowed (legacy / migration)

Rule 6: changeReason required (free text)
  - empty string allowed (Phase 7-A0) but Phase 7+ may require non-empty
  - typical values: "repeat experiment", "fix typo", "re-run after calibration"
```

## 4. `StorageMetadata` type

```ts
interface StorageMetadata {
  /** monotonic version number (1-based). */
  version: number

  /** ID of the previous version, or null for the first version. */
  previousVersion: string | null

  /** Epoch ms when this version was saved. */
  savedAt: number

  /** Free-text author placeholder. Phase 7-B0: empty string. Phase 7+: real user. */
  author: string

  /** Free-text change reason (e.g. 'repeat experiment', 'fix typo'). */
  changeReason: string

  /** Field names changed in this version. Phase 7-A0: empty array. */
  changedFields: string[]
}
```

### Validator

`isValidStorageMetadata(m: unknown): m is StorageMetadata`

- `version` is a positive integer (>= 1)
- `previousVersion` is either null or a non-empty string
- `savedAt` is a non-negative number
- `author` is a string (Phase 7-B0: empty allowed)
- `changeReason` is a string
- `changedFields` is an array of strings
- `assertNoSecret` runs on the whole payload (throws on forbidden substrings)

## 5. Versioned ID format (Phase 7-B0)

```
Phase 7-A0 entity ID:  "paper:abc123"
Phase 7-B0 versioned ID: "paper:abc123:v1"
                         "paper:abc123:v2"
```

When the renderer / chat references an entity, the ID is the **current** version (latest). Older versions are accessible via `getVersionHistory`.

## 6. Example history

```
Paper "O3-MNB-TC degradation" (id: paper:o3-mnb-tc-2024)

v1 (Sept 15, 2024):
  metadata:
    version: 1
    previousVersion: null
    savedAt: 1726358400000
    author: ""
    changeReason: "initial import"
    changedFields: []
  content:
    title: "O3-MNB-TC degradation"
    year: 2024

v2 (Oct 1, 2024):
  metadata:
    version: 2
    previousVersion: "paper:o3-mnb-tc-2024:v1"
    savedAt: 1727750400000
    author: ""
    changeReason: "fix typo in title"
    changedFields: ["title"]
  content:
    title: "Ozone micro-nano bubble TC degradation"   <- changed
    year: 2024
```

## 7. Storage layer protocol (Phase 7-B0 contract)

When the provider receives `create(entity, meta)`:

```
1. Validate meta (isValidStorageMetadata)
2. Validate meta.version === 1
3. Validate meta.previousVersion === null
4. Persist entity (Phase 7+ storage backend)
5. Persist metadata
6. Return entity ID
```

When the provider receives `update(id, entity, meta)`:

```
1. Validate meta
2. Fetch the latest version (entity + meta) by ID
3. Validate meta.version === latest.version + 1
4. Validate meta.previousVersion === latest.fullVersionedID
5. Validate meta.savedAt >= latest.savedAt
6. Persist new entity version (NOT overwrite)
7. Persist new metadata
8. Return (no value)
```

When the provider receives `delete(id, reason)`:

```
1. Soft-delete: append a tombstone version (version N+1, content = null)
2. Reason logged in metadata
3. Recovery via getVersionHistory + manually "undelete"
```

Phase 7-B0 strict: NO hard delete. Soft delete only (append tombstone).

## 8. Conflict resolution (Phase 7-B0)

When the desktop client (SqliteLocalProvider) and the lab server (PostgresLabServerProvider) both have unsynced edits to the same entity:

```
Strategy: 'local-wins' | 'remote-wins' | 'newest-wins' | 'manual'
```

Phase 7-B0 recommendation: `newest-wins` by default.

```
local.version = 5, local.savedAt = T1
remote.version = 5, remote.savedAt = T2

if T2 > T1: keep remote (newer)
else:       keep local
```

If both `savedAt` are equal (rare): fall back to `manual` (Phase 7-B+ UI).

## 9. Recovery (Phase 7-B0 sketch)

```
getVersionHistory('paper:o3-mnb-tc-2024')
  -> [
    { version: 1, savedAt: 1726358400000, content: ... },
    { version: 2, savedAt: 1727750400000, content: ... },
    { version: 3, savedAt: 1728800000000, content: ..., deleted: true, reason: 'wrong sample' }
  ]

restore('paper:o3-mnb-tc-2024', fromVersion: 2)
  -> creates new version 4 with content of version 2
```

Phase 7-B0: contract only. Phase 7-B+ ships restore.

## 10. Phase 7-B0 strict forbids

- ❌ Implement version history storage
- ❌ Implement diff / merge logic
- ❌ Implement restore
- ❌ Add audit log UI
- ❌ Allow hard delete (soft delete only via tombstone)
- ❌ Allow version decrement
- ❌ Allow version reuse across save calls

## 11. References

- `docs/knowledge/storage-architecture.md` (Phase 7-B0 Step 2)
- `docs/knowledge/storage-provider-interface.md` (Phase 7-B0 Step 3 — `getVersionHistory`)
- `docs/knowledge/local-storage-strategy.md` (Phase 7-B0 Step 4 — SqliteLocalProvider)
- `docs/knowledge/lab-server-architecture.md` (Phase 7-B0 Step 5 — PostgresLabServerProvider)
- `docs/knowledge/future-account-compatibility.md` (Phase 7-B0 Step 7 — author field)
- `desktop/src/shared/knowledge/storage.ts` (StorageMetadata contract)

## Status (2026-08-22 Phase 7-B0)

- 6 versioning rules documented
- `StorageMetadata` type + `isValidStorageMetadata` validator
- Versioned ID format `paper:abc123:v1`
- 4 conflict-resolution strategies (`local-wins` / `remote-wins` / `newest-wins` / `manual`)
- Append-only history contract (soft delete via tombstone, no hard delete)
- 0 implementations (Phase 7-B0 ships ONLY the contract)
- Doc complete (11 sections)
