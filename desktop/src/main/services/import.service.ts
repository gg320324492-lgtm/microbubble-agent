// Import Service — Phase 9-A
// 入口单例, 持有 ImportEngine.

import { createImportEngine, type ImportEngine } from './import/import-engine'
import type { DatabaseService } from './database.service'
export type { ImportEngine, ImportFormat, RawImportTable, ColumnMapping, ColumnMappingSuggestion, ColumnTarget, ValidationResult, ValidationError, ImportResult, ImportDataset } from './import/types'
export { SUPPORTED_FORMATS } from './import/types'
export { suggestMapping, validateMapping } from './import/column-mapper'
export { parseCsv } from './import/csv-importer'
export { parseJson } from './import/json-importer'
export { parseXlsx } from './import/xlsx-importer'
export { validate } from './import/validator'

export interface ImportService {
  engine: ImportEngine
}

class ImportServiceImpl implements ImportService {
  readonly engine: ImportEngine
  constructor(getService: () => DatabaseService | null) {
    this.engine = createImportEngine(getService)
  }
}

let serviceInstance: ImportService | null = null

export function bootstrapImportService(getService: () => DatabaseService | null): ImportService {
  if (serviceInstance) return serviceInstance
  serviceInstance = new ImportServiceImpl(getService)
  return serviceInstance
}

export function getImportService(): ImportService | null {
  return serviceInstance
}

export function resetImportService(): void {
  serviceInstance = null
}
