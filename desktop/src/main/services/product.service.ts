// Product Service — Phase 8-M1-G
// 集中入口: 持有 AuthService + ConfigService + BackupService + AuditChainService + Exporter 单例.

import { createAuthService, type AuthService } from './security/auth.service'
import { createConfigService, type ConfigService } from './config/config.service'
import { createBackupService, type BackupService } from './config/backup.service'
import { createAuditChainService, type AuditChainService } from './audit/audit-chain.service'
import { createExporter, type Exporter } from './export/exporter'
import type { DatabaseService } from './database.service'

export interface ProductService {
  auth: AuthService
  config: ConfigService
  backup: BackupService
  audit: AuditChainService
  exporter: Exporter
}

class ProductServiceImpl implements ProductService {
  readonly auth: AuthService
  readonly config: ConfigService
  readonly backup: BackupService
  readonly audit: AuditChainService
  readonly exporter: Exporter

  constructor(getService: () => DatabaseService | null) {
    this.auth = createAuthService(getService)
    this.config = createConfigService(getService)
    this.backup = createBackupService(getService)
    this.audit = createAuditChainService(getService)
    this.exporter = createExporter(getService)
  }
}

let serviceInstance: ProductService | null = null

export function bootstrapProductService(getService: () => DatabaseService | null): ProductService {
  if (serviceInstance) return serviceInstance
  serviceInstance = new ProductServiceImpl(getService)
  return serviceInstance
}

export function getProductService(): ProductService | null {
  return serviceInstance
}

export function resetProductService(): void {
  serviceInstance = null
}