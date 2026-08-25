// Database Service — Phase 8-M1-B
// 主进程启动时调用 bootstrap() 创建 SQLiteDatabase + 迁移 + repositories.
// 严禁渲染进程直接访问; 所有操作必须经 IPC bridge (db:*).

import { resolveDatabaseConfig, createSQLiteDatabase, createMigrationManager, type SQLiteDatabase, type MigrationManager } from '../database'
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