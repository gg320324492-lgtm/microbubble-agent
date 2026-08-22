// Knowledge Storage Contracts (Phase 7-B0: Knowledge Storage Architecture).
//
// Phase 7-B0: typed contracts for the storage layer. Distinct from
//   - Phase 7-A0 schemas (entities / metadata)
//   - Phase 6 Model Runtime (Provider / Router / Chat)
//   - Phase 6-A5 legacy FastAPI /chat/stream
//
// Phase 7-B0 frozen contract:
//   - KnowledgeStorageProvider interface (Phase 7+ implementations plug here)
//   - StorageMetadata (version, author, timestamp, changeReason)
//   - FutureAccountMetadata (owner / project / visibility) — fields ONLY,
//     NO auth module dependency
//   - StorageMode (local / remote / hybrid)
//   - SyncDirection + ConflictResolution (for Phase 7+ sync layer)
//
// Phase 7-B0 strict:
//   - NEVER contains apiKey / token / cipher / authorization
//   - Knowledge Storage is INDEPENDENT from Model Provider / Capability Router /
//     Chat Runtime / Auth / Legacy backend

import type {
  Paper, Experiment, Equipment, Dataset, Figure, ResearchProject,
  Parameter, Measurement, Citation
} from './schemas'

// ============ Entity union (Phase 7-A0 frozen) ============

export type KnowledgeEntity =
  | Paper
  | Experiment
  | Equipment
  | Dataset
  | Figure
  | ResearchProject

export type KnowledgeEntityType =
  | 'paper'
  | 'experiment'
  | 'equipment'
  | 'dataset'
  | 'figure'
  | 'project'

export type KnowledgeMetadata =
  | Parameter
  | Measurement
  | Citation

// ============ Version metadata ============

/**
 * Phase 7-B0: per-entity version metadata.
 *
 * Scientific data MUST NOT be silently overwritten. Each save increments
 * `version`. The previous version pointer (`previousVersion`) is preserved.
 */
export interface StorageMetadata {
  /** monotonic version number (1-based). */
  version: number
  /** ID of the previous version, or null for the first version. */
  previousVersion: string | null
  /** Epoch ms when this version was saved. */
  savedAt: number
  /** Free-text author placeholder. Phase 7-A0: empty string or username. Phase 7+: real user. */
  author: string
  /** Free-text change reason (e.g. 'repeat experiment', 'fix typo'). */
  changeReason: string
  /** Field names changed in this version (Phase 7+). Phase 7-A0: empty array. */
  changedFields: string[]
}

// ============ Future account fields (Phase 7-B0 strict) ============

/**
 * Phase 7-B0: forward-compatible ownership / project / visibility fields.
 * Phase 7-A0 entities have NO such fields. Phase 7-B0 introduces these as
 * OPTIONAL container so Phase 7+ storage layer can attach them without
 * modifying the schema contracts.
 */
export interface FutureAccountMetadata {
  /** Phase 7+ ownerId (string only). Phase 7-B0: empty string. */
  ownerId: string
  /** Phase 7+ projectId (string only). Phase 7-B0: empty string. */
  projectId: string
  /** Phase 7+ visibility. Phase 7-B0: 'private'. */
  visibility: 'private' | 'lab-shared' | 'public'
  /** Phase 7+ createdBy (string only). Phase 7-B0: empty string. */
  createdBy: string
}

// ============ Storage mode + sync ============

export type StorageMode = 'local' | 'remote' | 'hybrid'

export type SyncDirection = 'push' | 'pull' | 'two-way'

export type ConflictResolution = 'local-wins' | 'remote-wins' | 'newest-wins' | 'manual'

/**
 * Phase 7-B0: storage configuration attached to the provider.
 * Phase 7-A0: not persisted. Phase 7+ may persist in electron-store.
 */
export interface StorageConfig {
  mode: StorageMode
  endpoint?: string
  syncIntervalMs?: number
  conflictResolution: ConflictResolution
}

// ============ Provider interface (Phase 7+ sketch) ============

export interface KnowledgeQuery {
  text?: string
  filters?: {
    entityType?: KnowledgeEntityType
    researchField?: string
    keywords?: string[]
    dateRange?: { from: number; to: number }
  }
  limit?: number
}

export interface KnowledgeSearchHit {
  entity: KnowledgeEntity
  score: number
  snippet?: string
}

export interface KnowledgeSearchResult {
  hits: KnowledgeSearchHit[]
  total: number
}

/**
 * Phase 7-B0: provider interface — Phase 7+ ships implementations.
 * Phase 7-A0 schema contracts are the input/output of these methods.
 */
export interface KnowledgeStorageProvider {
  /** Phase 7-B0: lifecycle */
  initialize(): Promise<void>
  close(): Promise<void>

  /** Phase 7-B0: CRUD (entity union) */
  create(entity: KnowledgeEntity, meta: StorageMetadata): Promise<string>
  update(id: string, entity: KnowledgeEntity, meta: StorageMetadata): Promise<void>
  delete(id: string, reason: string): Promise<void>
  get(id: string): Promise<KnowledgeEntity | null>
  list(type: KnowledgeEntityType, options?: { limit?: number; offset?: number }): Promise<KnowledgeEntity[]>

  /** Phase 7-B0: search (Phase 7+ implements actual retrieval) */
  search(query: KnowledgeQuery): Promise<KnowledgeSearchResult>

  /** Phase 7-B0: metadata accessors */
  getStorageMetadata(id: string): Promise<StorageMetadata | null>
  getVersionHistory(id: string): Promise<StorageMetadata[]>

  /** Phase 7-B0: account / project (Phase 7+ fields) */
  attachAccount(id: string, account: FutureAccountMetadata): Promise<void>
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`storage leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-B0 strict)`)
    }
  }
}

const VALID_ENTITY_TYPES: ReadonlySet<KnowledgeEntityType> = new Set([
  'paper', 'experiment', 'equipment', 'dataset', 'figure', 'project'
])

const VALID_STORAGE_MODES: ReadonlySet<StorageMode> = new Set(['local', 'remote', 'hybrid'])
const VALID_SYNC_DIRECTIONS: ReadonlySet<SyncDirection> = new Set(['push', 'pull', 'two-way'])
const VALID_CONFLICT_RESOLUTIONS: ReadonlySet<ConflictResolution> = new Set([
  'local-wins', 'remote-wins', 'newest-wins', 'manual'
])
const VALID_VISIBILITIES: ReadonlySet<FutureAccountMetadata['visibility']> = new Set([
  'private', 'lab-shared', 'public'
])

export function isValidStorageMetadata(m: unknown): m is StorageMetadata {
  if (!m || typeof m !== 'object') return false
  const o = m as Record<string, unknown>
  if (typeof o.version !== 'number' || o.version < 1 || !Number.isInteger(o.version)) return false
  if (o.previousVersion !== null && typeof o.previousVersion !== 'string') return false
  if (typeof o.savedAt !== 'number' || o.savedAt < 0) return false
  if (typeof o.author !== 'string') return false
  if (typeof o.changeReason !== 'string') return false
  if (!Array.isArray(o.changedFields) || !o.changedFields.every((x) => typeof x === 'string')) return false
  assertNoSecret(m, 'StorageMetadata')
  return true
}

export function isValidFutureAccountMetadata(a: unknown): a is FutureAccountMetadata {
  if (!a || typeof a !== 'object') return false
  const o = a as Record<string, unknown>
  if (typeof o.ownerId !== 'string') return false
  if (typeof o.projectId !== 'string') return false
  if (typeof o.visibility !== 'string' || !VALID_VISIBILITIES.has(o.visibility as FutureAccountMetadata['visibility'])) return false
  if (typeof o.createdBy !== 'string') return false
  assertNoSecret(a, 'FutureAccountMetadata')
  return true
}

export function isValidStorageConfig(c: unknown): c is StorageConfig {
  if (!c || typeof c !== 'object') return false
  const o = c as Record<string, unknown>
  if (typeof o.mode !== 'string' || !VALID_STORAGE_MODES.has(o.mode as StorageMode)) return false
  if (o.endpoint !== undefined && typeof o.endpoint !== 'string') return false
  if (o.syncIntervalMs !== undefined && (typeof o.syncIntervalMs !== 'number' || o.syncIntervalMs < 0)) return false
  if (typeof o.conflictResolution !== 'string'
      || !VALID_CONFLICT_RESOLUTIONS.has(o.conflictResolution as ConflictResolution)) return false
  assertNoSecret(c, 'StorageConfig')
  return true
}

export function isValidEntityType(t: unknown): t is KnowledgeEntityType {
  return typeof t === 'string' && VALID_ENTITY_TYPES.has(t as KnowledgeEntityType)
}

export function isValidSyncDirection(d: unknown): d is SyncDirection {
  return typeof d === 'string' && VALID_SYNC_DIRECTIONS.has(d as SyncDirection)
}

/**
 * Phase 7-B0: storage module independence guard.
 * Throws if the storage module imports from forbidden paths.
 * (Static check — Phase 7+ adds import-graph tests.)
 */
export function assertStorageIndependence(): void {
  // Phase 7-B0: no runtime check; the import-graph test (Phase 7+) verifies this.
}

export const __testHelpers = {
  FORBIDDEN,
  VALID_ENTITY_TYPES,
  VALID_STORAGE_MODES,
  VALID_SYNC_DIRECTIONS,
  VALID_CONFLICT_RESOLUTIONS,
  VALID_VISIBILITIES
}
