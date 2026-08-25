// Import Types — Phase 9-A
// 共享契约: 文件格式 / 列映射 / 校验 / 导入结果

export type ImportFormat = 'csv' | 'xlsx' | 'json'

export const SUPPORTED_FORMATS: ReadonlyArray<ImportFormat> = ['csv', 'xlsx', 'json']

/** 原始导入表: parser 输出 */
export interface RawImportTable {
  /** 解析来源文件绝对路径 (主进程读取) */
  sourcePath: string
  /** 文件 SHA-256 hex, 用于去重 (同一文件不重复导入) */
  sourceHash: string
  /** 文件名 (basename) */
  sourceName: string
  /** 文件 size in bytes */
  sourceSize: number
  /** 解析格式 */
  format: ImportFormat
  /** 列名 (按文件顺序) */
  columns: string[]
  /** 行数据: 每行 map<列名, 字符串原始值> */
  rows: Array<Record<string, string>>
  /** 解析耗时 ms */
  parseMs: number
}

/** 列映射: 标识每个列名 → 目标字段 */
export type ColumnTarget =
  | 'timestamp'
  | 'metric'
  | 'value'
  | 'unit'
  | 'sample_batch'
  | 'replicate'
  | 'operator'
  | 'notes'
  | 'ignore'

export interface ColumnMapping {
  [sourceColumn: string]: ColumnTarget
}

export interface ColumnMappingSuggestion {
  mapping: ColumnMapping
  /** 置信度 0-1 (heuristic 命中比例) */
  confidence: number
  /** 推断说明 (中文, 给操作者看) */
  rationale: string
}

/** 校验结果 */
export interface ValidationError {
  rowIndex: number
  column: string | null
  reason: 'missing' | 'duplicate' | 'invalid' | 'unit_mismatch' | 'outlier'
  message: string
  value: string
}

export interface ValidationResult {
  validRowCount: number
  invalidRowCount: number
  errors: ValidationError[]
  /** 推断的 metric 列表 (按出现频次) */
  detectedMetrics: string[]
  /** 推断的 unit 列表 (去重) */
  detectedUnits: string[]
  /** 校验耗时 ms */
  validateMs: number
}

export interface ImportDataset {
  experimentId: string
  experimentName: string
  fileName: string
  fileHash: string
  format: ImportFormat
  rowCount: number
  importedAt: number
  sampleCount: number
}

export interface ImportResult {
  experimentId: string
  sampleCount: number
  measurementCount: number
  durationMs: number
}

/** ImportEngine 接口 */
export interface ImportEngine {
  parseFile(filePath: string, format?: ImportFormat): Promise<RawImportTable>
  suggestMapping(raw: RawImportTable): Promise<ColumnMappingSuggestion>
  validate(raw: RawImportTable, mapping: ColumnMapping): Promise<ValidationResult>
  commit(input: {
    projectId: string
    experimentName: string
    mapping: ColumnMapping
    raw: RawImportTable
    fileHash: string
    importedBy?: string
  }): Promise<ImportResult>
  listDatasets(projectId?: string): Promise<ImportDataset[]>
}
