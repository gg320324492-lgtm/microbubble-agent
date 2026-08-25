// Config Service — Phase 8-M1-G
// 类型安全的 key-value 存储. 敏感字段经 safeStorage 加密 (Electron safeStorage API).

import type { DatabaseService } from '../database.service'

export type ConfigScope = 'system' | 'user' | 'project'
export type ConfigValueType = 'string' | 'number' | 'boolean' | 'json'

export interface ConfigEntry {
  scope: ConfigScope
  key: string
  value: unknown
  valueType: ConfigValueType
  isSensitive: boolean
  updatedAt: number
  updatedBy: string | null
}

export interface ConfigService {
  get<T = unknown>(scope: ConfigScope, key: string): T | null
  set(scope: ConfigScope, key: string, value: unknown, opts?: { valueType?: ConfigValueType; isSensitive?: boolean; updatedBy?: string }): void
  list(scope?: ConfigScope): ConfigEntry[]
  delete(scope: ConfigScope, key: string): boolean
}

function safeStorageAvailable(): boolean {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { safeStorage } = require('electron') as { safeStorage?: { isEncryptionAvailable?: () => boolean } }
    return safeStorage?.isEncryptionAvailable?.() ?? false
  } catch {
    return false
  }
}

function encryptIfSensitive(value: string, isSensitive: boolean): string {
  if (!isSensitive) return value
  if (!safeStorageAvailable()) return value
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { safeStorage } = require('electron') as { safeStorage: { encryptString: (s: string) => Buffer } }
    return safeStorage.encryptString(value).toString('base64')
  } catch {
    return value
  }
}

function decryptIfSensitive(value: string, isSensitive: boolean): string {
  if (!isSensitive) return value
  if (!safeStorageAvailable()) return value
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { safeStorage } = require('electron') as { safeStorage: { decryptString: (b: Buffer) => string } }
    return safeStorage.decryptString(Buffer.from(value, 'base64'))
  } catch {
    return value
  }
}

class ConfigServiceImpl implements ConfigService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  get<T = unknown>(scope: ConfigScope, key: string): T | null {
    const svc = this.getService()
    if (!svc) return null
    const row = svc.db.queryOne<{ value: string; value_type: string; is_sensitive: number }>(
      'SELECT value, value_type, is_sensitive FROM config WHERE scope = ? AND key = ?',
      [scope, key]
    )
    if (!row) return null
    const raw = decryptIfSensitive(row.value, Number(row.is_sensitive) === 1)
    return deserialize(raw, row.value_type) as T
  }

  set(scope: ConfigScope, key: string, value: unknown, opts: { valueType?: ConfigValueType; isSensitive?: boolean; updatedBy?: string } = {}): void {
    const svc = this.getService()
    if (!svc) return
    const valueType: ConfigValueType = opts.valueType ?? inferType(value)
    const isSensitive = opts.isSensitive ?? false
    const serialized = serialize(value, valueType)
    const encrypted = encryptIfSensitive(serialized, isSensitive)
    svc.db.execute(
      `INSERT INTO config (scope, key, value, value_type, is_sensitive, updated_at, updated_by)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(scope, key) DO UPDATE SET
         value = excluded.value,
         value_type = excluded.value_type,
         is_sensitive = excluded.is_sensitive,
         updated_at = excluded.updated_at,
         updated_by = excluded.updated_by`,
      [scope, key, encrypted, valueType, isSensitive ? 1 : 0, Date.now(), opts.updatedBy ?? null]
    )
  }

  list(scope?: ConfigScope): ConfigEntry[] {
    const svc = this.getService()
    if (!svc) return []
    const where = scope ? 'WHERE scope = ?' : ''
    const params = scope ? [scope] : []
    const rows = svc.db.query<Record<string, unknown>>(
      `SELECT scope, key, value, value_type, is_sensitive, updated_at, updated_by FROM config ${where} ORDER BY scope ASC, key ASC`,
      params
    )
    return rows.map((r) => {
      const raw = decryptIfSensitive(String(r['value']), Number(r['is_sensitive']) === 1)
      return {
        scope: String(r['scope']) as ConfigScope,
        key: String(r['key']),
        value: deserialize(raw, String(r['value_type'])),
        valueType: String(r['value_type']) as ConfigValueType,
        isSensitive: Number(r['is_sensitive']) === 1,
        updatedAt: Number(r['updated_at']),
        updatedBy: r['updated_by'] == null ? null : String(r['updated_by'])
      }
    })
  }

  delete(scope: ConfigScope, key: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const result = svc.db.execute('DELETE FROM config WHERE scope = ? AND key = ?', [scope, key])
    return result.changes > 0
  }
}

function inferType(value: unknown): ConfigValueType {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'object') return 'json'
  return 'string'
}

function serialize(value: unknown, type: ConfigValueType): string {
  if (type === 'json') return JSON.stringify(value)
  if (type === 'number' || type === 'boolean') return String(value)
  return String(value)
}

function deserialize(raw: string, type: string): unknown {
  if (type === 'json') {
    try { return JSON.parse(raw) } catch { return null }
  }
  if (type === 'number') {
    const n = Number(raw); return Number.isFinite(n) ? n : null
  }
  if (type === 'boolean') return raw === 'true'
  return raw
}

export function createConfigService(getService: () => DatabaseService | null): ConfigService {
  return new ConfigServiceImpl(getService)
}