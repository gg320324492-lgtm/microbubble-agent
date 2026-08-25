// Database Service — Phase 8-M1-B
// 主进程启动时调用 bootstrap() 创建 SQLiteDatabase + 迁移 + repositories.
// 严禁渲染进程直接访问; 所有操作必须经 IPC bridge (db:*).

import { resolveDatabaseConfig, createSQLiteDatabase, createMigrationManager, type SQLiteDatabase, type MigrationManager } from '../database'
// R4: inline-import the 010-migration-workspace schema so callers (mbrp-importer) can
// re-apply it after a manual restore from a database backup.
import SCHEMA_010_MIGRATION_WORKSPACE from '../database/schema/010-migration-workspace.sql?raw'
import {
  createProjectRepository, createExperimentRepository, createMeasurementRepository,
  createDeviceRepository, createManuscriptRepository, createAgentHistoryRepository,
  createSampleRepository, createAnalysisResultRepository, createFigureRepository,
  type ProjectRepository, type ExperimentRepository, type MeasurementRepository,
  type DeviceRepository, type ManuscriptRepository, type AgentHistoryRepository,
  type SampleRepository, type AnalysisResultRepository, type FigureRepository
} from '../repositories'
import { createDatabaseAuditLogger, type DatabaseAuditLogger } from '../database/database-audit-logger'
import { logger } from './storage.service'
import { createAnalysisEngine, type AnalysisEngine } from './analysis/analysis-engine'
import { createLocalAnalysisEngineAdapter, type AnalysisEngineAdapter } from './analysis/adapter'
import { bootstrapAgentService, type AgentService } from './agent/agent.service'
import { bootstrapProductService, type ProductService } from './product.service'
import { bootstrapImportService, type ImportService } from './import.service'
import { bootstrapDeviceService, type DeviceService } from './device/device.service'
import { bootstrapELNProductService, type ELNProductService } from './eln.service'
import { bootstrapCaseReplayService, type CaseReplayService } from './case/case-replay'

export interface DatabaseService {
  db: SQLiteDatabase
  migrations: MigrationManager
  audit: DatabaseAuditLogger
  projects: ProjectRepository
  experiments: ExperimentRepository
  measurements: MeasurementRepository
  devices: DeviceRepository
  manuscripts: ManuscriptRepository
  agents: AgentHistoryRepository
  samples: SampleRepository
  analysisResults: AnalysisResultRepository
  figures: FigureRepository
  analysisEngine: AnalysisEngine
  analysisAdapter: AnalysisEngineAdapter
  agent: AgentService
  product: ProductService
  importSvc: ImportService
  deviceSvc: DeviceService
  elnProduct: ELNProductService
  caseReplay: CaseReplayService
  status(): { open: boolean; path: string; version: number; environment: string }
  close(): void
}

let service: DatabaseService | null = null

/**
 * 主进程启动钩子: 创建 SQLite + 迁移 + 注册 repositories.
 * 任何失败抛错让 Electron 启动失败 (走 BootstrapRecoveryCard 兜底).
 */
export function bootstrapDatabase(): DatabaseService {
  if (service) return service
  const cfg = resolveDatabaseConfig(1)
  const db = createSQLiteDatabase(cfg)
  db.open()
  const migrations = createMigrationManager(db)
  migrations.initialize()
  migrations.migrate()
  const audit = createDatabaseAuditLogger(db, (entry) => {
    logger.warn('database.audit', 'audit log write failed', { action: entry.action, module: entry.module })
  })
  const projects = createProjectRepository(db)
  const experiments = createExperimentRepository(db)
  const measurements = createMeasurementRepository(db)
  const devices = createDeviceRepository(db)
  const manuscripts = createManuscriptRepository(db)
  const agents = createAgentHistoryRepository(db)
  const samples = createSampleRepository(db)
  const analysisResults = createAnalysisResultRepository(db)
  const figures = createFigureRepository(db)
  service = {
    db, migrations, audit, projects, experiments, measurements, devices, manuscripts, agents,
    samples, analysisResults, figures,
    analysisEngine: createAnalysisEngine(db, analysisResults),
    analysisAdapter: createLocalAnalysisEngineAdapter(createAnalysisEngine(db, analysisResults)),
    agent: bootstrapAgentService(() => service),
    product: bootstrapProductService(() => service),
    importSvc: bootstrapImportService(() => service),
    deviceSvc: bootstrapDeviceService(() => service),
    elnProduct: bootstrapELNProductService(() => service),
    caseReplay: bootstrapCaseReplayService(() => service),
    status() {
      return {
        open: db.isOpen(),
        path: cfg.path,
        version: migrations.currentVersion(),
        environment: cfg.environment
      }
    },
    close() {
      try { db.close() } catch { /* ignore */ }
      service = null
    }
  }
  return service
}

export function getDatabaseService(): DatabaseService | null {
  return service
}

export function resetDatabaseService(): void {
  if (service) {
    try { service.db.close() } catch { /* ignore */ }
  }
  service = null
}

/**
 * R4 — apply an inline-loaded SQL schema against an open SQLiteDatabase.
 * Used by the mbrp-importer to ensure the migration_runs / source_id_map /
 * workspace_documents tables exist after a fresh install or a manual
 * restore from database-*.db backup.
 *
 * Idempotent (CREATE IF NOT EXISTS), no transaction wrapper needed.
 */
export function applyMigrationSchema(db: SQLiteDatabase, schemaSql: string): void {
  if (!db.isOpen()) throw new Error('applyMigrationSchema: database not open')
  db.execute(schemaSql)
}

/** R4 — the 010-migration-workspace SQL, inlined at build time (vite ?raw). */
export const MIGRATION_SCHEMA_010 = SCHEMA_010_MIGRATION_WORKSPACE
