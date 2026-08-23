// Memory Provider (Phase 8-F0).
//
// Phase 8-F0: the persistence seam for MemoryItem records. Deterministic,
// in-memory by default — a later phase may swap a durable store.
//
// Phase 8-F0 strict:
//   - NEVER contains apiKey / secret / token value / cipher / authorization
//   - No database dependency

import type { MemoryItem, MemoryType } from './research-session-schema'
import { isValidMemoryItem } from './research-session-schema'

// ============ Interface ============

export interface MemoryProvider {
  save(item: MemoryItem): boolean
  search(query: string, limit?: number): MemoryItem[]
  list(type?: MemoryType, limit?: number): MemoryItem[]
  delete(memoryId: string): boolean
  clear(): void
  size(): number
}

// ============ LocalMemoryProvider (deterministic, in-memory) ============

function lowerTokens(text: string): string[] {
  return text.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((t) => t.length > 0)
}

function contentScore(queryTerms: string[], content: string): number {
  if (queryTerms.length === 0) return 0
  const hay = content.toLowerCase()
  let hits = 0
  for (const t of queryTerms) if (hay.includes(t)) hits++
  return hits / queryTerms.length
}

/**
 * Phase 8-F0: in-memory MemoryProvider with deterministic ranking.
 * - save: returns false when memoryId already exists (no overwrite).
 * - search: hits require >=1 query term present in content; ranked by
 *   term-hit ratio desc, then confidence desc, then memoryId asc.
 * - list: sorted by confidence desc, then memoryId asc.
 */
export class LocalMemoryProvider implements MemoryProvider {
  private readonly items = new Map<string, MemoryItem>()

  save(item: MemoryItem): boolean {
    if (!isValidMemoryItem(item)) {
      throw new Error('local memory provider: invalid MemoryItem (Phase 8-F0 strict)')
    }
    if (this.items.has(item.memoryId)) return false
    this.items.set(item.memoryId, item)
    return true
  }

  search(query: string, limit?: number): MemoryItem[] {
    if (typeof query !== 'string') {
      throw new Error('local memory provider: query must be a string (Phase 8-F0 strict)')
    }
    const terms = lowerTokens(query)
    const hits: Array<{ item: MemoryItem; ratio: number }> = []
    for (const item of this.items.values()) {
      const ratio = contentScore(terms, item.content)
      if (ratio <= 0) continue
      hits.push({ item, ratio })
    }
    hits.sort((a, b) =>
      b.ratio - a.ratio
      || b.item.confidence - a.item.confidence
      || a.item.memoryId < b.item.memoryId ? -1 : a.item.memoryId > b.item.memoryId ? 1 : 0
    )
    const n = typeof limit === 'number' && limit > 0 ? limit : hits.length
    return hits.slice(0, n).map((h) => h.item)
  }

  list(type?: MemoryType, limit?: number): MemoryItem[] {
    const values = Array.from(this.items.values())
      .filter((i) => type === undefined || i.type === type)
      .sort((a, b) =>
        b.confidence - a.confidence
        || (a.memoryId < b.memoryId ? -1 : a.memoryId > b.memoryId ? 1 : 0)
      )
    const n = typeof limit === 'number' && limit > 0 ? limit : values.length
    return values.slice(0, n)
  }

  delete(memoryId: string): boolean {
    if (typeof memoryId !== 'string') {
      throw new Error('local memory provider: memoryId must be a string (Phase 8-F0 strict)')
    }
    return this.items.delete(memoryId)
  }

  clear(): void {
    this.items.clear()
  }

  size(): number {
    return this.items.size
  }
}

export const __testHelpers = {
  contentScore,
  lowerTokens
}