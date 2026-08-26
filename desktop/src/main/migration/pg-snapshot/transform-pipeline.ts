// Transform Pipeline — Phase 11 Stage 0
// PG row → SQLite row 通用转换. 单个 transformer 调用此管线完成:
// 1. 日期 (timestamptz) → epoch ms
// 2. JSONB / JSON → TEXT (JSON.stringify)
// 3. ARRAY → TEXT (JSON.stringify) 或 TEXT[] (JOIN)
// 4. ENUM 验证 enum 白名单
// 5. Vector (pgvector) → BLOB 或丢弃
// 6. HalfVector (pgvector) → BLOB
// 7. BOOLEAN / NUMERIC passthrough
// 8. identifier 重写 (web_id / username 解析)

/**
 * 把 PG timestamptz / date / timestamp 字符串转 epoch ms.
 * PG 输出形如 '2026-08-26 10:00:00.123+08' 或 '2026-08-26' (date-only).
 */
export function pgTimestampToEpochMs(raw: unknown): number | null {
  if (raw == null) return null
  if (raw instanceof Date) return raw.getTime()
  const s = String(raw)
  if (s === '\\N' || s === '') return null
  // ISO 8601 with timezone
  const t = Date.parse(s)
  if (!Number.isFinite(t)) return null
  return t
}

/** JSONB / JSON 字符串 → 解析 + 重新 JSON.stringify (规范化) */
export function pgJsonToJsonString(raw: unknown): string | null {
  if (raw == null) return null
  if (typeof raw === 'object') return JSON.stringify(raw)
  const s = String(raw)
  if (s === '\\N' || s === '') return null
  try {
    return JSON.stringify(JSON.parse(s))
  } catch {
    return s // fallback to raw
  }
}

/** PG TEXT[] → JSON array string. psql array literal: '{a,b,c}'. */
export function pgTextArrayToJsonString(raw: unknown): string | null {
  if (raw == null) return null
  const s = String(raw)
  if (s === '\\N' || s === '') return null
  if (!s.startsWith('{')) return JSON.stringify([s])
  // 移除 '{' '}' 并 split by ',' — 简单 parser (不支持 quoted 元素内的逗号)
  const inner = s.slice(1, -1)
  if (inner === '') return '[]'
  const items = inner.split(',').map((it) => it.trim().replace(/^"(.*)"$/, '$1'))
  const result = JSON.stringify(items)
  return result
}

/** Validate enum 字符串 (白名单). 失败 throw. */
export function pgEnumValidate<T extends string>(
  raw: unknown,
  whitelist: ReadonlyArray<T>,
  fallback?: T
): T | null {
  if (raw == null) return null
  const s = String(raw)
  if (whitelist.includes(s as T)) return s as T
  if (fallback) return fallback
  throw new Error(`Invalid enum value: '${s}' not in [${whitelist.join(', ')}]`)
}

/**
 * PG enum 字符串 → desktop enum 重写映射.
 * 例如 web TaskStatus enum 'todo'/'in_progress'/'blocked'/'review'/'done'/'cancelled'
 * → desktop TaskStatus 'todo'/'in_progress'/'blocked'/'review'/'done'/'cancelled' (一致).
 */
export function pgEnumRewrite<T extends string>(
  raw: unknown,
  map: Record<string, T>,
  whitelist: ReadonlyArray<T>
): T | null {
  if (raw == null) return null
  const s = String(raw)
  const mapped = map[s]
  if (mapped) return mapped
  // 直接尝试匹配 desktop enum
  if (whitelist.includes(s as T)) return s as T
  throw new Error(`Cannot rewrite enum '${s}' (whitelist=[${whitelist.join(', ')}])`)
}

/** Vector (pgvector) — 不存 SQLite. 返回 null 占位. */
export function pgVectorDrop(_raw: unknown): null {
  return null
}

/** HalfVector (pgvector) — 同上. */
export function pgHalfVectorDrop(_raw: unknown): null {
  return null
}

/**
 * PG UUID → 保留为 string (UUID format 不变).
 */
export function pgUuidString(raw: unknown): string | null {
  if (raw == null) return null
  const s = String(raw)
  if (s === '\\N' || s === '') return null
  return s
}

/**
 * PG INTEGER (member FK) → desktop username string.
 * 需调用方提供 lookup table (id → username).
 * 返回 null 如果 id 不在 lookup.
 */
export function pgMemberIdToUsername(raw: unknown, lookup: Map<number, string> | null): string | null {
  if (raw == null) return null
  if (!lookup) return null
  const id = Number(raw)
  if (!Number.isFinite(id)) return null
  return lookup.get(id) ?? null
}

/** Truncate text 到 max chars (用于 chat_history 摘要). */
export function truncateText(raw: unknown, max = 1000): string | null {
  if (raw == null) return null
  const s = String(raw)
  if (s.length <= max) return s
  return s.slice(0, max - 3) + '...'
}

/**
 * 给 row 应用 transformer map.
 * @param row - PG raw row
 * @param map - { webColumnName: transformer function }
 * @returns partial SQLite row (含所有 transformed fields)
 */
export type TransformerMap = Record<string, (raw: unknown) => unknown>

export function applyTransformers(
  row: Record<string, unknown>,
  map: TransformerMap
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [col, fn] of Object.entries(map)) {
    out[col] = fn(row[col])
  }
  return out
}