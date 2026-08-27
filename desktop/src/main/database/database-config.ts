// Database Config — Phase 8-M1-B
// 配置: 路径 + 版本 + 环境. 严禁硬编码用户路径 (走 resolveAppConfig 的 dataDir).

import { join } from 'node:path'
import { resolveAppConfig } from '@shared/config'

export interface DatabaseConfig {
  /** 数据库文件绝对路径 */
  path: string
  /** 当前 schema 版本号 */
  version: number
  /** 当前运行环境: development | production */
  environment: string
}

/**
 * 解析数据库配置.
 * - 路径: <dataDir>/ScientificResearchOS/data/scientific.db
 * - version: 当前最大 schema 序号, 由 MigrationManager 提供
 * - environment: 走 ApplicationInfo.environment
 */
export function resolveDatabaseConfig(version: number = 1): DatabaseConfig {
  const cfg = resolveAppConfig()
  const dbDir = join(cfg.dataDir, 'ScientificResearchOS', 'data')
  return {
    path: join(dbDir, 'scientific.db'),
    version,
    environment: cfg.environment
  }
}