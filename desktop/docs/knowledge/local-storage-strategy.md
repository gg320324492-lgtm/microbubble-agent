# Local Storage Strategy (Phase 7-B0)

> **purpose**: Analyze 3 options for local desktop knowledge storage and recommend the best path for MicroBubble Research OS. Phase 7-B0 ships ONLY the analysis + recommendation — NO implementation.
> **follows**: `storage-architecture.md` (Phase 7-B0 Step 2).
> **Phase 7-B0 strict**: analysis only. No actual storage implementation.

## 1. Scope (Phase 7-B0 frozen)

Three options analyzed:

- **Option A**: SQLite (embedded SQL)
- **Option B**: Embedded document storage (JSON / MessagePack / LMDB)
- **Option C**: Local cache + server (hybrid)

Phase 7-B0 ships the recommendation. Phase 7-B ships the implementation.

## 2. Constraints / requirements

The MicroBubble Research OS desktop client must support:

| Requirement | Why |
|------------|-----|
| Desktop installation for students | Phase 7+ students run the .exe directly |
| Offline capability | Lab may have intermittent network |
| Research data safety | Multi-year PhD experiments must survive |
| Future lab collaboration | Phase 7-B+ multi-user server |
| Small dataset sizes | Single lab: hundreds of papers / experiments |
| Vector search (Phase 7-C) | Retrieval-augmented agent |
| Cross-platform | Win / macOS / Linux |

## 3. Option A: SQLite

### Pros

- ✅ Electron friendly (better-sqlite3 native binding)
- ✅ Offline by default (single file, no network)
- ✅ Simple deployment (one .exe + one .db file)
- ✅ ACID transactions (no data loss on crash)
- ✅ Strong tooling (sqlite3 CLI / DB Browser)
- ✅ Schema migrations via PRAGMA user_version
- ✅ Phase 7-C integration: `sqlite-vss` extension provides vector search inside SQLite

### Cons

- ❌ Multi-user weak (no native row-level locking across processes; lab server is separate concern)
- ❌ Concurrent writers serialize (single-writer)
- ❌ No built-in replication (Phase 7-B+ sync layer handles this)
- ❌ Binary format (harder to inspect with text tools)

## 4. Option B: Embedded document storage

### Pros

- ✅ Flexible schema (no migrations needed)
- ✅ Human-readable (JSON)
- ✅ Easy to backup (copy a folder)

### Cons

- ❌ Querying difficulty (no SQL — must load all + filter in JS)
- ❌ Performance degrades at scale (10K+ documents)
- ❌ No transaction support (Phase 7-A0 versioning needs atomicity)
- ❌ Vector search requires external lib + manual sync
- ❌ Larger on disk (JSON overhead)

## 5. Option C: Local cache + server

### Pros

- ✅ Scalable to many users
- ✅ Lab collaboration features

### Cons

- ❌ Requires backend (out of Phase 7-B0 scope)
- ❌ Cannot fully work offline (cache may be stale)
- ❌ Higher operational complexity (sync conflicts)
- ❌ Phase 7-B0 forbids backend implementation

## 6. Recommendation: **Option A (SQLite)**

For MicroBubble Research OS Phase 7-B0 + 7-B:

1. **Offline-first** — students can run research at lab bench without network
2. **Single-file portability** — students can copy `knowledge.db` to USB / backup / share
3. **Proven technology** — SQLite is the most-deployed database in the world; zero new dependencies beyond `better-sqlite3` (which Electron supports natively)
4. **Vector search ready** — `sqlite-vss` extension or `pgvector`-equivalent gives us embeddings without an external service (Phase 7-C)
5. **Phase 7-A0 schema fits** — entities / relationships / metadata map cleanly to SQL tables
6. **Future migration path** — Phase 7-B+ adds Postgres lab server; SQLite stays as local cache (Option C hybrid)
7. **Low operational burden** — students don't run a server; they run a desktop app

### SQLite specifics (Phase 7-B+ sketches — NOT IMPLEMENTED in 7-B0)

| Aspect | Choice | Why |
|--------|--------|-----|
| File location | `<userData>/knowledge/knowledge.db` | Electron convention |
| Schema migration | PRAGMA `user_version` + version table | Native SQLite |
| Encryption | SQLCipher | Optional — research data may be sensitive |
| Vector search | `sqlite-vss` (Phase 7-C) | Single-file vector store |
| Full-text search | FTS5 | Built-in, no extra dep |
| Backup | `<userData>/backups/knowledge-YYYYMMDD.db` | One-line copy |

## 7. When NOT to use SQLite (Phase 7-B+ handoff)

- Multi-user lab server with 50+ concurrent writers → **Postgres** (Phase 7-B+)
- Cloud-only deployment (no desktop install) → **Postgres + S3** (Phase 7-B+)
- Heavy analytic queries (>100M rows) → **ClickHouse / Druid** (Phase 8+)

Phase 7-B0 strict: SQLite is the recommendation for **Phase 7-B (desktop local)**. Phase 7-B+ may add Postgres for the lab server tier; that is a separate phase.

## 8. Phase 7-B0 strict forbids

- ❌ Implement Option A / B / C in this phase
- ❌ Add `better-sqlite3` dependency
- ❌ Add a SQLite database connection
- ❌ Persist any data
- ❌ Define SQL schema in this phase (Phase 7-B ships that)

## 9. References

- `docs/knowledge/storage-architecture.md` (Phase 7-B0 Step 2)
- `docs/knowledge/lab-server-architecture.md` (Phase 7-B0 Step 5 — Postgres tier)
- `docs/knowledge/storage-migration-plan.md` (Phase 7-B0 Step 8 — migration path)

## Status (2026-08-22 Phase 7-B0)

- 3 options analyzed (SQLite / embedded document / hybrid)
- Recommendation: **Option A (SQLite)** for desktop local
- Phase 7-B+ may add Postgres for lab server (separate tier)
- Phase 7-C may add `sqlite-vss` for vector search
- 0 implementations (Phase 7-B0 ships ONLY the analysis + recommendation)
- Doc complete (9 sections)
