import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { StreamCitationEntry } from '../../src/shared/chat-types'
import type { KnowledgeResponse } from '../../src/shared/knowledge-types'

/**
 * Phase 4-B: KnowledgeService unit tests.
 *
 * 策略:
 * - globalThis.window.api.api.request mock (Service 委托给 api/knowledge,
 *   底层走 window.api.api.request).
 * - 验证 cache hit / miss / eviction / batch dedup / invalid id / failure
 *   等 Service 行为.
 *
 * 注: knowledgeService 是 module-level singleton, cache 是 module-level LRUCache.
 * beforeEach 不清 cache (避免污染) -> 在单个 describe 块内手动 clear.
 */

const mockRequest = vi.fn()

beforeEach(() => {
  mockRequest.mockReset()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).window = {
    api: {
      api: {
        request: mockRequest
      },
      auth: {},
      session: {},
      chat: {}
    }
  }
})

async function importService(): Promise<typeof import('../../src/renderer/src/services/knowledge.service')> {
  return await import('../../src/renderer/src/services/knowledge.service')
}

function knowledgeResponseOf(id: number, overrides: Partial<KnowledgeResponse> = {}): KnowledgeResponse {
  return {
    id,
    title: `Doc ${id}`,
    content: 'c',
    category: 'test',
    tags: [],
    key_concepts: [],
    related_topics: [],
    knowledge_type: null,
    topic: null,
    analysis_status: 'completed',
    quality_score: 0.9,
    needs_review: false,
    thumbnail_url: null,
    image_count: 0,
    meta: {},
    created_by: 1,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-21T00:00:00Z',
    source: null,
    source_type: null,
    file_path: null,
    file_name: null,
    file_type: null,
    summary: null,
    ...overrides
  }
}

async function clearServiceCache(): Promise<void> {
  const { knowledgeService } = await importService()
  knowledgeService._internal.clearCache()
}

describe('KnowledgeService.getCategories', () => {
  it('成功: 转发到 GET /knowledge/categories', async () => {
    const fake = [{ name: '微纳米气泡', count: 18 }]
    mockRequest.mockResolvedValueOnce({ ok: true, data: fake })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getCategories()
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', path: '/knowledge/categories' })
    )
    expect(r.ok).toBe(true)
  })

  it('错误: 透传', async () => {
    mockRequest.mockResolvedValueOnce({ ok: false, error: { code: 'X', message: 'm' } })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getCategories()
    expect(r.ok).toBe(false)
  })
})

describe('KnowledgeService.listKnowledge', () => {
  it('成功: 查询参数合并', async () => {
    mockRequest.mockResolvedValueOnce({ ok: true, data: { items: [], total: 0 } })
    const { knowledgeService } = await importService()
    await knowledgeService.listKnowledge({ category: 'x', page: 2, pageSize: 10 })
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ category: 'x', page: 2, page_size: 10 })
      })
    )
  })

  it('默认参数 (page=1, pageSize=20)', async () => {
    mockRequest.mockResolvedValueOnce({ ok: true, data: { items: [], total: 0 } })
    const { knowledgeService } = await importService()
    await knowledgeService.listKnowledge()
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ page: 1, page_size: 20 })
      })
    )
  })
})

describe('KnowledgeService.getKnowledge - cache + IPC (Phase 4-B 核心)', () => {
  beforeEach(async () => {
    await clearServiceCache()
  })

  it('invalid id 直接返 INVALID_INPUT, 不调 IPC', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledge(0)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.error.code).toBe('INVALID_INPUT')
      expect(r.error.message).toContain('无效 knowledgeId')
    }
    expect(mockRequest).not.toHaveBeenCalled()
  })

  it('cache miss -> fetch + cache set', async () => {
    const doc = knowledgeResponseOf(42)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledge(42)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.id).toBe(42)
    expect(mockRequest).toHaveBeenCalledOnce()
    expect(knowledgeService._internal.cacheSize()).toBe(1)
  })

  it('cache hit -> 不调 IPC', async () => {
    const doc = knowledgeResponseOf(42)
    const { knowledgeService } = await importService()
    // 1. 第一次写 cache
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    await knowledgeService.getKnowledge(42)
    expect(knowledgeService._internal.cacheSize()).toBe(1)
    mockRequest.mockClear()
    // 2. 第二次: 命中 cache
    const r2 = await knowledgeService.getKnowledge(42)
    expect(r2.ok).toBe(true)
    if (r2.ok) expect(r2.data.id).toBe(42)
    expect(mockRequest).not.toHaveBeenCalled()
  })

  it('IPC 失败不污染 cache', async () => {
    mockRequest.mockResolvedValueOnce({ ok: false, error: { code: 'NOT_FOUND', message: 'x' } })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getKnowledge(999)
    expect(r.ok).toBe(false)
    expect(knowledgeService._internal.cacheSize()).toBe(0)
    // 第二次同 id 还是会 miss (不污染 -> 不被错误缓存冻结)
    mockRequest.mockResolvedValueOnce({ ok: true, data: knowledgeResponseOf(999) })
    const r2 = await knowledgeService.getKnowledge(999)
    expect(r2.ok).toBe(true)
  })

  it('cacheLookup 命中返真实值 (Phase 4-A 留口激活)', async () => {
    const doc = knowledgeResponseOf(42)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    const { knowledgeService } = await importService()
    await knowledgeService.getKnowledge(42)
    const cached = knowledgeService.cacheLookup(42)
    expect(cached).not.toBeNull()
    expect(cached?.id).toBe(42)
  })

  it('cacheLookup 未命中返 null', async () => {
    const { knowledgeService } = await importService()
    expect(knowledgeService.cacheLookup(99999)).toBeNull()
  })
})

describe('KnowledgeService.getManyKnowledge - batch (Phase 4-B)', () => {
  beforeEach(async () => {
    await clearServiceCache()
  })

  it('empty input -> ok + data []', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getManyKnowledge([])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual([])
    expect(mockRequest).not.toHaveBeenCalled()
  })

  it('dedup 重复 id 只 fetch 一次', async () => {
    const doc = knowledgeResponseOf(5)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getManyKnowledge([5, 5, 5, 5])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toHaveLength(1)
    expect(mockRequest).toHaveBeenCalledOnce()
  })

  it('invalid id 过滤 (0 / 负 / NaN)', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getManyKnowledge([0, -1, NaN, 1.5])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual([])
    expect(mockRequest).not.toHaveBeenCalled()
  })

  it('partial-cache: 命中跳过 fetch, 缺失 fetch + 写回', async () => {
    const doc1 = knowledgeResponseOf(1)
    const doc3 = knowledgeResponseOf(3)
    const doc5 = knowledgeResponseOf(5)
    const { knowledgeService } = await importService()
    // 预填 cache 1
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc1 })
    await knowledgeService.getKnowledge(1)
    mockRequest.mockClear()
    // batch [1, 3, 5]: 1 命中, 3 + 5 走 fetch
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc3 })
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc5 })
    const r = await knowledgeService.getManyKnowledge([1, 3, 5])
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data).toHaveLength(3)
      expect(r.data.map((x) => x.id)).toEqual([1, 3, 5])  // 保序
    }
    expect(mockRequest).toHaveBeenCalledTimes(2)  // 仅 3 + 5
    expect(knowledgeService._internal.cacheSize()).toBe(3)
  })

  it('成功 fetch 顺序 = 入参顺序', async () => {
    const doc20 = knowledgeResponseOf(20)
    const doc10 = knowledgeResponseOf(10)
    const doc30 = knowledgeResponseOf(30)
    // mock 顺序对应 input order [20, 10, 30] -> fetch 1st returns doc(20), etc.
    mockRequest
      .mockResolvedValueOnce({ ok: true, data: doc20 })
      .mockResolvedValueOnce({ ok: true, data: doc10 })
      .mockResolvedValueOnce({ ok: true, data: doc30 })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getManyKnowledge([20, 10, 30])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.map((x) => x.id)).toEqual([20, 10, 30])
  })

  it('失败 partial: 成功的项 cache + 返回, 失败的丢弃', async () => {
    const doc1 = knowledgeResponseOf(1)
    const { knowledgeService } = await importService()
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc1 })
    mockRequest.mockResolvedValueOnce({ ok: false, error: { code: 'NOT_FOUND', message: 'x' } })
    const r = await knowledgeService.getManyKnowledge([1, 999])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.map((x) => x.id)).toEqual([1])  // 999 失败丢弃
    expect(knowledgeService._internal.cacheSize()).toBe(1)  // 仅 1 缓存
  })

  it('全失败 -> ok + data []', async () => {
    mockRequest.mockResolvedValue({ ok: false, error: { code: 'X', message: 'm' } })
    const { knowledgeService } = await importService()
    const r = await knowledgeService.getManyKnowledge([1, 2, 3])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual([])
  })
})

describe('KnowledgeService.prefetchKnowledgeForCitations (Phase 4-B)', () => {
  beforeEach(async () => {
    await clearServiceCache()
  })

  it('valid citation 列表 -> 走 getManyKnowledge (cache hit 优先)', async () => {
    const doc = knowledgeResponseOf(7)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    const { knowledgeService } = await importService()
    const citations: StreamCitationEntry[] = [
      { type: 'citation', knowledgeId: 7, title: 't' } as StreamCitationEntry
    ]
    const r = await knowledgeService.prefetchKnowledgeForCitations(citations)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toHaveLength(1)
    expect(mockRequest).toHaveBeenCalledOnce()
  })

  it('empty input -> ok + []', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.prefetchKnowledgeForCitations([])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual([])
    expect(mockRequest).not.toHaveBeenCalled()
  })

  it('mixed invalid + valid: invalid 过滤 + valid 预取', async () => {
    const doc = knowledgeResponseOf(7)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    const { knowledgeService } = await importService()
    const citations: StreamCitationEntry[] = [
      { type: 'citation', knowledgeId: 0, title: 'invalid' } as StreamCitationEntry,
      { type: 'citation', knowledgeId: 7, title: 'valid' } as StreamCitationEntry,
      { type: 'citation', knowledgeId: -1, title: 'invalid' } as StreamCitationEntry
    ]
    const r = await knowledgeService.prefetchKnowledgeForCitations(citations)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toHaveLength(1)
  })
})

describe('KnowledgeService.listItems - cache-only (Phase 4-B)', () => {
  beforeEach(async () => {
    await clearServiceCache()
  })

  it('cache 空 -> []', async () => {
    const { knowledgeService } = await importService()
    const r = await knowledgeService.listItems(10)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toEqual([])
    expect(mockRequest).not.toHaveBeenCalled()
  })

  it('cache 命中返 lightweight items (截断到 limit)', async () => {
    const doc1 = knowledgeResponseOf(1)
    const doc2 = knowledgeResponseOf(2)
    const doc3 = knowledgeResponseOf(3)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc1 })
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc2 })
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc3 })
    const { knowledgeService } = await importService()
    await knowledgeService.getManyKnowledge([1, 2, 3])
    const r = await knowledgeService.listItems(2)
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data).toHaveLength(2)
      expect(r.data.map((x) => x.id)).toEqual([1, 2])  // LRU 序
    }
  })
})

describe('KnowledgeService 内部 _internal (Phase 4-B 调试)', () => {
  beforeEach(async () => {
    await clearServiceCache()
  })

  it('cacheSize / maxCacheSize / clearCache', async () => {
    const { knowledgeService } = await importService()
    expect(knowledgeService._internal.cacheSize()).toBe(0)
    expect(knowledgeService._internal.maxCacheSize).toBe(200)
    const doc = knowledgeResponseOf(1)
    mockRequest.mockResolvedValueOnce({ ok: true, data: doc })
    await knowledgeService.getKnowledge(1)
    expect(knowledgeService._internal.cacheSize()).toBe(1)
    knowledgeService._internal.clearCache()
    expect(knowledgeService._internal.cacheSize()).toBe(0)
  })
})
